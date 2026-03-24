# HR Connector Agent (Windows + Mac)

这是一个跨平台（Windows + macOS）的轻量本地连接器原型，用于“会成长的 AI HR 系统”：

- 自动扫描老板授权目录里的工资表/offer/合同文件（xls/xlsx/doc/docx/pdf/csv）
- 增量同步新文件或变更文件到后端
- 对接飞书组织架构 API
- 对接 timesheet API（日更数据）

> 设计目标：先跑通数据闭环，再迭代 GUI、权限中心和企业级部署。

## 1) 运行环境

- Python 3.10+
- 无第三方依赖

## 2) 快速开始

```bash
cp hr_agent/config.example.json hr_agent/config.json
python3 hr_agent/agent.py --config hr_agent/config.json
```

## 3) 配置说明

`config.json` 关键字段：

- `backend.base_url`: AI HR 后端地址
- `backend.token`: 后端 ingestion token
- `watch.directories`: 授权扫描目录列表（最小权限原则）
- `watch.scan_interval_seconds`: 扫描周期
- `watch.max_file_size_mb`: 扫描时允许的最大文件
- `watch.include_file_content`: 是否上传文件原文（默认 `false`）
- `watch.max_inline_file_size_mb`: 上传原文时的最大内联尺寸
- `watch.batch_size`: 批次大小
- `watch.state_file`: 增量同步状态文件
- `feishu.*`: 飞书 API 配置
- `timesheet.*`: timesheet API 配置

## 4) 后端接口约定（建议）

- `POST /ingest/files`
- `POST /ingest/feishu`
- `POST /ingest/timesheet`

## 5) 可靠性改进（本次已实现）

1. 仅在后端写入成功（2xx）后，才更新本地文件指纹状态，避免失败批次“丢增量”。
2. 支持全部 2xx 返回作为成功，不限于 200。
3. 默认不上传文件原文，仅上传元数据 + 哈希，降低敏感信息暴露面。
4. `state_file` 为相对路径时，不再因空目录名导致保存异常。

## 6) 生产化建议

为支持“上万人企业”，建议后续加入：

1. 本地 SQLite 队列与断点重传
2. 分块上传（大文件）
3. 文件内容本地脱敏（可选）
4. SSO + 设备证书 + 审计日志
5. 多租户限流与重试退避
6. UI 客户端（Tauri）用于可视化授权与状态查看

## 7) 安全边界（当前原型）

- 仅扫描配置中指定目录
- 默认 Bearer Token 认证
- 传输需通过 HTTPS
- 默认不上传文件原文（可按策略开启）

## 8) 运行测试

```bash
python3 -m unittest hr_agent.tests.test_agent
```
