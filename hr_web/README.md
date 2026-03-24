# Growth HR Copilot - Web 预览版

这是一个“先跑业务流程”的 Web 原型，不依赖后端即可预览：

- 老板自由讲述（15-30分钟入口）
- 结构化问答
- 自动生成本轮组织建议
- localStorage 持久化，刷新后仍可继续

## 本地预览

在仓库根目录执行：

```bash
python3 -m http.server 8080
```

然后浏览器打开：

```text
http://localhost:8080/hr_web/
```

## 说明

这是预览版（前端原型），用于快速确认业务流程。
后续可逐步接入：

1. 飞书组织架构 API
2. timesheet API
3. 邮件推送与审批流程
4. 再封装为 Windows/Mac 客户端
