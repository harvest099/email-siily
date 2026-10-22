# 邮箱管家（Email Manager）v0.1

个人邮箱自动化管理工具：自动抓取新邮件，由 LLM 判定类别与截止时间，生成每日简报。

## 架构

分层设计，各层职责单一、单向数据流：

| 层 | 模块 | 职责 | 触发 |
|---|---|---|---|
| 收信 | 邮箱自动转发（一次性设置） | 各邮箱新邮件统一汇入主邮箱 | 一次性 |
| 调度 | Windows 计划任务 | 每日 09:00 触发流水线 | 每天 |
| 抓取 | `tools/tool_imap.py` | IMAP 读取新邮件 + 提取图片附件 | 被调度调用 |
| 决策 | `classify.py` | LLM 对每封邮件判定类别、截止时间、处理依据 | 被调度调用 |
| 输出 | `report.py` | 分类结果汇总为简报，写入桌面 | 被调度调用 |

```
 收信层（一次性）:  各邮箱 --自动转发--> 主邮箱(QQ)
                              | IMAP 只读
 Agent 核心 classify.py
   LLM(NVIDIA NIM) <--> tool_imap(读邮件+图片)
   输出: {类别, 截止时间, 原文依据, 是否需处理}
                              |
 简报层 report.py -> 桌面 daily_report.md
                              ^ 每天 09:00
 调度层 task_daily.ps1
```

## 文件结构

```
personal-assistant/
├── README.md
├── config.yaml             # 凭据配置（.gitignore，不提交）
├── config.yaml.example     # 配置模板（提交）
├── classify.py             # LLM 决策循环
├── report.py               # 简报生成
├── task_daily.ps1          # 流水线脚本
├── prompts/classify.md     # 分类 prompt
├── tools/tool_imap.py      # IMAP 抓取工具
├── data/                   # 邮件 JSON + 去重表 + 简报（gitignore）
└── logs/                   # 运行日志（gitignore）
```

## 运行流程

调度层依次调用三个环节，数据单向流动，每层可独立验证：

```
tool_imap.py -> data/YYYY-MM-DD.json
classify.py  -> data/classified_YYYY-MM-DD.json
report.py    -> data/daily_report.md -> 桌面 daily_report.md
```

1. **抓取**：`tool_imap.py` 拉过去 24 小时邮件，去重，输出 JSON + 图片附件
2. **决策**：`classify.py` 逐封交给 LLM，输出结构化判定（必须含原文依据）
3. **输出**：`report.py` 汇总成简报，桌面单文件覆盖

## 配置

复制模板并填入凭据：

```bash
cp config.yaml.example config.yaml
```

`config.yaml` 字段说明见模板内注释。凭据（邮箱授权码、API key）只存在于该文件，不进版本库。

API key 解析顺序：命令行参数 `--api-key` > 环境变量 `NVIDIA_API_KEY` > `config.yaml` 的 `llm.api_key` > 本地 `~/.pi/agent/models.json`。

## 安装计划任务

Windows 计划任务 `DailyEmailAgent`，每天 09:00 自动跑（抓邮件→分类→简报）。`_daily_run.cmd` 是计划任务指向的中间层，`task_daily.ps1` 里把 python 路径改成你自己的安装位置（默认 `E:\Anaconda\python.exe`）：

```powershell
schtasks /Create /TN DailyEmailAgent /TR "C:\\Users\\<你>\\Desktop\\personal-assistant\\_daily_run.cmd" /SC DAILY /ST 09:00 /F
```

## 换账号使用（其他人如何用）

**代码通用，只改 `config.yaml` 里 3 处个人数据，零代码改动**：

1. **邮箱 + 授权码**
   ```yaml
   imap:
     email: "你的qq邮箱@qq.com"   # 改成自己的邮箱
     password: "QQ邮箱IMAP授权码"  # QQ邮箱 设置→账户 开IMAP生成, 非登录密码
   ```
2. **简报输出路径**
   ```yaml
   report:
     output: "你的桌面/📬 每日简报.md"
   ```
3. **LLM key**（可选）
   ```yaml
   llm:
     key: ""            # 留空让脚本自动从 ~/.pi/agent/models.json 找
     model: ""         # 留空用默认 nvidia/nemotron-3.5-super-vl-120b-a12b
   ```

其他账号还需：装 Python + `pip install requests pyyaml`、重建设划任务（改脚本路径）、LLM 那步连 NVIDIA 代理。

**自动抓取要求**：电脑开机 + 网络通（连 `imap.qq.com`）+ IMAP 授权码有效。抓邮件**不需代理、不需开终端**；仅 LLM 分类那步需 Clash 代理（代理没开则简报退到上一天数据）。

## 安装计划任务（原方法）

## 安全设计

| 项 | 设计 |
|---|---|
| 凭据 | 邮箱授权码 / App Password，非主密码，可随时撤销 |
| 权限 | 只走 IMAP 只读，不配置 SMTP，不代发/不删/不改 |
| 密钥管理 | `config.yaml` 进 `.gitignore`，仓库仅含占位的 `.example` |
| 隐私 | 仅传"发件人+主题+正文前 800 字+图片"给 LLM，不传附件原文 |
| 去重 | `data/.processed` 记录已处理邮件 ID，断点续跑 |
| 可审计 | `logs/daily.log` 记录运行细节 |
| 可撤销 | 删除 `config.yaml` + 撤销授权码 + 删计划任务，即完全停止 |

## 已知边界与解决方案

- LLM 视觉分类依赖代理，无代理时自动降级为纯文本模式
- 计划任务 09:00 若 Clash 代理未开：IMAP 抓取照常，classify 失败，简报退到上一天数据；日志会记录 LLM 失败，可手动补跑 `python classify.py && python report.py`
- 只处理开启转发后的新邮件，历史邮件不迁移
- 不能用主邮箱地址回信，需回原邮箱
- 不追踪 24 小时前的待办

## License

MIT（见 [LICENSE](./LICENSE)）
