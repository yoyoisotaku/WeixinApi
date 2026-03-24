#!/usr/bin/env python3
"""Lightweight cross-platform HR data connector.

Features:
- Watches configured folders for new/changed HR files.
- Ships file metadata (and optional content) to backend in batches.
- Pulls Feishu org API and Timesheet API on a schedule.
- Stores local sync state so incremental scans are fast.

This script is dependency-free (Python 3.10+ standard library).
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import logging
import os
import pathlib
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

SUPPORTED_EXTENSIONS = {".xls", ".xlsx", ".doc", ".docx", ".pdf", ".csv"}


@dataclass
class AgentConfig:
    backend_base_url: str
    backend_token: str
    watch_dirs: list[str]
    scan_interval_seconds: int
    max_file_size_mb: int
    include_file_content: bool
    max_inline_file_size_mb: int
    batch_size: int
    state_file: str
    feishu_enabled: bool
    feishu_endpoint: str
    feishu_token: str
    timesheet_enabled: bool
    timesheet_endpoint: str
    timesheet_token: str


class StateStore:
    def __init__(self, path: str):
        self.path = path
        self._state = {"files": {}, "last_feishu_sync": None, "last_timesheet_sync": None}
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self.path):
            return
        with open(self.path, "r", encoding="utf-8") as f:
            self._state = json.load(f)

    def save(self) -> None:
        directory = os.path.dirname(self.path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self._state, f, ensure_ascii=False, indent=2)

    def get_file_fingerprint(self, file_path: str) -> dict[str, Any] | None:
        return self._state["files"].get(file_path)

    def set_file_fingerprint(self, file_path: str, fingerprint: dict[str, Any]) -> None:
        self._state["files"][file_path] = fingerprint

    def get_last_sync(self, key: str) -> str | None:
        return self._state.get(key)

    def set_last_sync(self, key: str, value: str) -> None:
        self._state[key] = value


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(8192):
            digest.update(chunk)
    return digest.hexdigest()


def load_config(path: str) -> AgentConfig:
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return AgentConfig(
        backend_base_url=raw["backend"]["base_url"].rstrip("/"),
        backend_token=raw["backend"]["token"],
        watch_dirs=raw["watch"]["directories"],
        scan_interval_seconds=int(raw["watch"].get("scan_interval_seconds", 60)),
        max_file_size_mb=int(raw["watch"].get("max_file_size_mb", 20)),
        include_file_content=bool(raw["watch"].get("include_file_content", False)),
        max_inline_file_size_mb=int(raw["watch"].get("max_inline_file_size_mb", 5)),
        batch_size=int(raw["watch"].get("batch_size", 20)),
        state_file=raw["watch"].get("state_file", "./state/agent_state.json"),
        feishu_enabled=bool(raw.get("feishu", {}).get("enabled", False)),
        feishu_endpoint=raw.get("feishu", {}).get("endpoint", ""),
        feishu_token=raw.get("feishu", {}).get("token", ""),
        timesheet_enabled=bool(raw.get("timesheet", {}).get("enabled", False)),
        timesheet_endpoint=raw.get("timesheet", {}).get("endpoint", ""),
        timesheet_token=raw.get("timesheet", {}).get("token", ""),
    )


def post_json(url: str, token: str, payload: dict[str, Any]) -> tuple[int, str]:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.getcode(), resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as e:
        return 0, str(e)


def get_json(url: str, token: str, params: dict[str, str] | None = None) -> tuple[int, dict[str, Any] | str]:
    if params:
        query = "&".join(f"{k}={urllib.parse.quote(v)}" for k, v in params.items())
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}{query}"

    req = urllib.request.Request(
        url,
        method="GET",
        headers={"Authorization": f"Bearer {token}"},
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            text = resp.read().decode("utf-8", errors="replace")
            return resp.getcode(), json.loads(text)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as e:
        return 0, str(e)


def should_include_file(path: pathlib.Path, max_size_mb: int) -> bool:
    return path.suffix.lower() in SUPPORTED_EXTENSIONS and path.stat().st_size <= max_size_mb * 1024 * 1024


def is_success_status(code: int) -> bool:
    return 200 <= code < 300


def _build_file_payload(path: pathlib.Path, stat: os.stat_result, fingerprint: dict[str, Any], cfg: AgentConfig) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "path": str(path),
        "filename": path.name,
        "extension": path.suffix.lower(),
        "size": stat.st_size,
        "modified_time": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        "sha256": fingerprint["sha256"],
        "captured_at": utc_now_iso(),
    }
    if cfg.include_file_content and stat.st_size <= cfg.max_inline_file_size_mb * 1024 * 1024:
        payload["content_base64"] = base64.b64encode(path.read_bytes()).decode("ascii")
    return payload


def scan_files(cfg: AgentConfig, state: StateStore) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []

    for watch_dir in cfg.watch_dirs:
        root = pathlib.Path(watch_dir).expanduser().resolve()
        if not root.exists() or not root.is_dir():
            logging.warning("Watch directory missing: %s", root)
            continue

        for path in root.rglob("*"):
            if not path.is_file() or not should_include_file(path, cfg.max_file_size_mb):
                continue

            stat = path.stat()
            fingerprint = {
                "size": stat.st_size,
                "mtime": int(stat.st_mtime),
                "sha256": sha256_file(path),
            }
            last = state.get_file_fingerprint(str(path))
            if last == fingerprint:
                continue

            payload = _build_file_payload(path, stat, fingerprint, cfg)
            payload["_fingerprint"] = fingerprint
            changes.append(payload)

    return changes


def send_file_batches(cfg: AgentConfig, state: StateStore, items: list[dict[str, Any]]) -> None:
    if not items:
        return

    endpoint = f"{cfg.backend_base_url}/ingest/files"
    for i in range(0, len(items), cfg.batch_size):
        batch = items[i : i + cfg.batch_size]
        api_payload = [{k: v for k, v in item.items() if not k.startswith("_")} for item in batch]

        code, resp = post_json(endpoint, cfg.backend_token, {"files": api_payload})
        if not is_success_status(code):
            logging.error("Failed to send file batch (%s): %s", code, resp)
        else:
            logging.info("Sent file batch: %s records", len(batch))
            for item in batch:
                state.set_file_fingerprint(item["path"], item["_fingerprint"])


def sync_external_data(cfg: AgentConfig, state: StateStore) -> None:
    if cfg.feishu_enabled:
        last_sync = state.get_last_sync("last_feishu_sync")
        params = {"updated_since": last_sync} if last_sync else None
        code, data = get_json(cfg.feishu_endpoint, cfg.feishu_token, params=params)
        if is_success_status(code) and isinstance(data, dict):
            post_code, _ = post_json(
                f"{cfg.backend_base_url}/ingest/feishu",
                cfg.backend_token,
                {"payload": data, "synced_at": utc_now_iso()},
            )
            if is_success_status(post_code):
                state.set_last_sync("last_feishu_sync", utc_now_iso())
                logging.info("Feishu sync successful")
            else:
                logging.error("Feishu forward failed: %s", post_code)
        else:
            logging.error("Feishu fetch failed: %s %s", code, data)

    if cfg.timesheet_enabled:
        last_sync = state.get_last_sync("last_timesheet_sync")
        params = {"updated_since": last_sync} if last_sync else None
        code, data = get_json(cfg.timesheet_endpoint, cfg.timesheet_token, params=params)
        if is_success_status(code) and isinstance(data, dict):
            post_code, _ = post_json(
                f"{cfg.backend_base_url}/ingest/timesheet",
                cfg.backend_token,
                {"payload": data, "synced_at": utc_now_iso()},
            )
            if is_success_status(post_code):
                state.set_last_sync("last_timesheet_sync", utc_now_iso())
                logging.info("Timesheet sync successful")
            else:
                logging.error("Timesheet forward failed: %s", post_code)
        else:
            logging.error("Timesheet fetch failed: %s %s", code, data)


def run(cfg: AgentConfig) -> None:
    state = StateStore(cfg.state_file)

    while True:
        try:
            changed_files = scan_files(cfg, state)
            send_file_batches(cfg, state, changed_files)
            sync_external_data(cfg, state)
            state.save()
        except Exception as exc:  # noqa: BLE001
            logging.exception("Agent loop failed: %s", exc)
        time.sleep(cfg.scan_interval_seconds)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="HR data connector agent")
    parser.add_argument("--config", required=True, help="Path to config JSON")
    parser.add_argument("--log-level", default="INFO", help="DEBUG/INFO/WARNING/ERROR")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    cfg = load_config(args.config)
    run(cfg)


if __name__ == "__main__":
    main()
