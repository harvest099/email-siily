# 邮箱管家 · 交付清单 v0.1

## 交付物

| # | 项目 | 状态 | 说明 |
|---|---|---|---|
| 1 | Agent 架构文档 | 完成 | `README.md`（分层架构 + 运行流程 + 安全设计） |
| 2 | 抓取脚本 | 完成 | `tools/tool_imap.py`（IMAP 只读 + 图片附件提取） |
| 3 | 决策脚本 | 完成 | `classify.py`（LLM 分类，NVIDIA NIM 免费额度） |
| 4 | 简报生成 | 完成 | `report.py`（桌面单文件覆盖） |
| 5 | 计划任务 | 完成 | `task_daily.ps1` + Windows `DailyEmailAgent`（09:00） |
| 6 | 运行验证 | 完成 | `data/` 含 10-20、10-22 实录，桌面 `每日简报.md` 为当前输出 |

## 目录

```
personal-assistant/
├── README.md             # 架构 + 流程 + 安全设计
├── config.yaml.example   # 配置模板（密钥全占位）
├── classify.py           # LLM 决策循环
├── report.py             # 简报生成
├── task_daily.ps1        # 流水线脚本
├── prompts/classify.md   # 分类 prompt
├── tools/tool_imap.py    # IMAP 抓取工具
├── data/                 # 运行数据（gitignore）
└── logs/                 # 运行日志（gitignore）
```

## 验证记录

1. **抓取**：`tool_imap.py` 拉取 QQ 邮箱过去 24h 邮件，去重，输出 `data/YYYY-MM-DD.json`，图片附件存 `data/attachments/`
2. **决策**：`classify.py` 对每封邮件调用 LLM，输出 `data/classified_*.json`，每条含类别 + 原文依据
3. **简报**：`report.py` 汇总生成桌面 `每日简报.md`
4. **调度**：Windows 计划任务 `DailyEmailAgent` 每日 09:00 触发，已手动验证跑通（10-22 数据已生成）

## 可选扩展

- 多邮箱统一收件：各邮箱新邮件自动转发到主邮箱（Gmail/QQ/163 均在设置页可配）
- 简报推送到 IM 软件

## License

MIT
