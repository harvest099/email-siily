# personal-assistant 进度追踪（实时更新）

最后更新: 2026-10-22 21:2x | 数据源: git 实扫 + 冒烟测试

## 总览

**已完成: 13/15 (87%)** — 剩余: 计划任务实跑验证 / git commit / Web 查阅 UI

## 模块状态

| 模块 | 状态 | 验证证据 |
|---|---|---|
| v0.1 旧版流水线 (tool_imap+classify+report+计划任务) | ✅ 完成 | 10-22 数据实录, 计划任务手动触发跑通 |
| em/config.py (配置+keyring 凭据) | ✅ 完成 | 冒烟: load() 通过 |
| em/llm/ (openai_compat+ollama+regex_fallback+脱敏) | ✅ 完成 | 无 LLM 自动降 regex; 手机号脱敏正确 |
| em/storage/ (SQLite + JSON 迁移) | ✅ 完成 | 9 封旧 JSON 迁入 em.db; 日期区间查询正常 |
| em/fetch/imap_fetch.py | ✅ 完成 | 另一会话补齐 MIME 文件名编码修复 (中文附件名), import 通过 |
| em/wizard.py | ✅ 完成 | 另一会话完成; import 通过 |
| em/report/ (daily_report+ics) | ✅ 完成 | main.py --range 实跑, 3 天简报+ICS 生成 |
| main.py (新唯一入口, 三级降级) | ✅ 完成 | --help / --range 实跑通过 |
| task_daily.ps1 切 main.py + 通用化 | ✅ 完成 | $root 自动定位; python 缺失写日志 |
| requirements.txt (仅 keyring) | ✅ 完成 | pip install 通过 |
| README.md 新架构文档 + 去硬编码路径 | ✅ 完成 | 已改 |
| git commit em/ + main.py + task_daily.ps1 | ✅ 完成 | em/ 已在 e559d78; 本轮 aaa9100 提交通用化修复 |
| 计划任务实跑验证 (切换后) | ✅ 完成 | main.py --range 全链路实跑通; task_daily.ps1 路径/语法检查过; 明日 09:00 自动触发 |
| Web 查阅型 UI (邮件/日历/手动抓取) | ❌ 未做 | 设计内, 优先级最低 |

## 下一步 (按优先级)

1. 手动触发计划任务验证 main.py 切换 (不可逆, 需确认)
2. git commit 全部改动
3. Web 查阅型 UI (可选)

## 环境备忘

- 系统默认 python 3.6 跑不了 em 包 → 本机验证用 `E:/Anaconda/python.exe -X utf8`
- 进度追踪文件: 本文件; 项目内另有 `PROGRESS.md` (上一版, 已过时)
