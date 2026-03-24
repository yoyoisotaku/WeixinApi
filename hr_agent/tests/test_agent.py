import pathlib
import tempfile
import unittest
from unittest import mock

from hr_agent import agent


class AgentTests(unittest.TestCase):
    def _cfg(self, watch_dirs):
        return agent.AgentConfig(
            backend_base_url="https://backend.example/api/v1",
            backend_token="tkn",
            watch_dirs=watch_dirs,
            scan_interval_seconds=60,
            max_file_size_mb=20,
            include_file_content=False,
            max_inline_file_size_mb=5,
            batch_size=10,
            state_file="state.json",
            feishu_enabled=False,
            feishu_endpoint="",
            feishu_token="",
            timesheet_enabled=False,
            timesheet_endpoint="",
            timesheet_token="",
        )

    def test_scan_files_detects_changes_without_content_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            file_path = pathlib.Path(tmp) / "payroll.xlsx"
            file_path.write_bytes(b"hello")
            state = agent.StateStore(str(pathlib.Path(tmp) / "state.json"))
            cfg = self._cfg([tmp])

            changes = agent.scan_files(cfg, state)
            self.assertEqual(len(changes), 1)
            self.assertNotIn("content_base64", changes[0])
            self.assertIn("_fingerprint", changes[0])

    def test_send_file_batches_updates_state_only_on_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            file_path = pathlib.Path(tmp) / "offer.pdf"
            file_path.write_bytes(b"abc")
            state = agent.StateStore(str(pathlib.Path(tmp) / "state.json"))
            cfg = self._cfg([tmp])
            changes = agent.scan_files(cfg, state)
            target = changes[0]["path"]

            with mock.patch("hr_agent.agent.post_json", return_value=(500, "err")):
                agent.send_file_batches(cfg, state, changes)
            self.assertIsNone(state.get_file_fingerprint(target))

            with mock.patch("hr_agent.agent.post_json", return_value=(201, "ok")):
                agent.send_file_batches(cfg, state, changes)
            self.assertIsNotNone(state.get_file_fingerprint(target))


if __name__ == "__main__":
    unittest.main()
