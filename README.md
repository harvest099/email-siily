# 邮箱管家（Email Manager）v0.2 · em 包

个人邮箱自动化管理工具：抓取新邮件 → LLM 三级降级分类（云端 OpenAI / 本地 Ollama / 正则）→ 生成每日简报 + `.ics` 日历 → 本机只读 Web 查阅。

**原则**：开箱即用（首次运行向导）、隐私安全（凭据走系统 keyring、发云前脱敏 PII）、永不崩（LLM 全关也能正则兜底跑完）、只读声明（不代发、不删除、不移动邮件）。

## 快速开始

```powershell
# 1. 装唯一依赖 (其余全标准库)
pip install -r requirements.txt

# 2. 首次运行 → 自动向导 (填邮箱/授权码, 选 LLM 开关)
E:\Anaconda\python.exe -X utf8 main.py

# 3. 之后任意一次: 抓取 + 分类 + 简报 + ICS
E:\Anaconda\python.exe -X utf8 main.py
```

> Windows 控制台是 GBK，直接 `python` 跑含中文/emoji 会 `UnicodeEncodeError`。用 `E:\Anaconda\python.exe -X utf8` 强制 UTF-8。

### 子命令

```powershell
E:\Anaconda\python.exe -X utf8 main.py                 # 抓 24h + 分类 + 当天简报+ICS
E:\Anaconda\python.exe -X utf8 main.py --fetch 48      # 抓过去 48h
E:\Anaconda\python.exe -X utf8 main.py --range 2026-10-20 2026-10-22  # 按日期生成简报+ICS
E:\Anaconda\python.exe -X utf8 main.py --web           # 本机只读 Web (127.0.0.1:8765)
```

Web 界面：`http://127.0.0.1:8765`（仅本机可访问）。`/` 邮件列表（分类着色）、`/mail/<uid>` 单封、`/calendar/<day>.ics` 下载、`/fetch` 手动抓取按钮。**只读**——无删除/代发接口。

## 目录结构（em 包）

```
personal-assistant/
├── main.py                 # 唯一入口: 抓取 → 分类 → 简报+ICS → 桌面同步
├── em/                     # 核心包, 按域解耦
│   ├── config.py           # 配置模型: 非敏感读 yaml, 敏感读 keyring (系统凭据管理器)
│   ├── wizard.py           # 首次运行交互向导 (邮箱 + LLM 开关)
│   ├── storage/            # SQLite 主存储 (em.db) + 旧 JSON 一次性迁移
│   ├── fetch/              # IMAP 只读抓取 (imaplib, utf-8 解码, 图片附件落 data/)
│   ├── llm/                # 三级降级分类 + PII 脱敏
│   │   ├── openai_compat.py#   云端 OpenAI 兼容 (base_url+model+key, 走代理)
│   │   ├── ollama.py       #   本地 Ollama 原生接口
│   │   ├── regex_fallback.py#  正则关键词兜底 (规则表可扩展, 永不崩)
│   │   └── desensitize.py  #   手机/银行卡/身份证/邮箱 打码 (只在发云前调)
│   ├── report/
│   │   ├── daily_report.py #   查 SQLite 某天 → markdown 简报
│   │   └── ics_export.py   #   需处理且有截止时间的事项 → .ics (带提醒)
│   └── web/                # 标准库 http.server 只读界面 (127.0.0.1)
│       ├── server.py
│       └── templates.py
├── prompts/classify.md     # 分类提示词 (LLM 用; 正则兜底不依赖它)
├── config.yaml             # 非敏感配置 (gitignore, 可明文)
├── data/
│   ├── em.db               # SQLite 主存储 (uid 去重, 支持历史日期检索)
│   ├── daily_report_*.md   # 每日简报
│   └── calendar_*.ics      # 每日日历
├── task_daily.ps1          # Windows 计划任务 09:00 → 调 main.py
└── requirements.txt        # 唯一新增依赖: keyring
```

## LLM 三级降级（永不崩）

```
1. 云端 OpenAI 兼容   配了 base_url+model+key   → 走本地代理 7897
2. 本地 Ollama        配了 backend=ollama+model  → localhost:11434
3. 正则关键词         前两者全关/失败           → 兜底, 流程照样跑完
```

每级失败自动降到下一级；全失败落到正则，正则永不抛异常。脱敏（手机/银行卡/身份证/邮箱打码）只在**发往云端**前执行，Ollama 与正则都不脱敏（本地不泄露）。

## 隐私与安全

- **凭据不落地**：邮箱授权码 / LLM API Key 存系统 keyring（服务名 `em-email-manager`），`config.yaml` 只存非敏感项（host/port/型号/开关）。
- **PII 脱敏**：发往云端前正则打码，云侧看不到完整手机号/卡号/身份证。
- **只读声明**：全程 IMAP 只读（`imaplib` SELECT + FETCH），SMTP 关闭，从不代发/删除/移动邮件。
- **本机 Web**：只绑 `127.0.0.1`，无鉴权也仅限本机进程可访问。

## 存储（打破 24h 限制）

旧版 JSON 只能存当天 24h。新版 SQLite 按 `uid` 去重长期累积，`--range` 支持任意历史日期检索并出简报/ICS。启动时自动把旧 `data/*.json` 一次性迁入 `em.db`。

## 验证回路（CI 精神）

改动后跑：

```powershell
# 语法自检 (全 em 包 + main.py)
E:\Anaconda\python.exe -X utf8 -c "import ast,pathlib;[ast.parse(f.read_text(encoding='utf-8')) for f in list(pathlib.Path('em').rglob('*.py'))+[pathlib.Path('main.py')]]"

# 失败路径: LLM 全关走正则不崩
E:\Anaconda\python.exe -X utf8 -c "from em import config;from em.llm import classify;cfg=config.Config();cfg.llm_enabled=False;r,b=classify(cfg,[{'uid':'1','subject':'账单续费到期','body':'请缴费'}]);print(b,r['categories'].keys())"
```

## 已验证（截至 v0.2）

- [x] em 包 19 文件语法全过
- [x] 抓取 → 三级降级分类 → 简报 + ICS → 桌面同步 全链路通
- [x] `--range` 跨天生成多日简报+ICS
- [x] 只读 Web：列表 / 单封 / ICS 下载 / 手动抓取按钮
- [x] 失败路径：LLM 全关 → 正则兜底不崩，脱敏 4 类 PII 全打码
- [x] 旧 JSON 一次性迁移进 SQLite
