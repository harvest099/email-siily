"""em — 个人邮箱管理工具包。

各子域:
- config:  配置模型 (非敏感读 yaml, 敏感读 keyring)
- storage: SQLite 主存储 + 旧 JSON 迁移
- fetch:   IMAP 抓取
- llm:     OpenAI 兼容 / Ollama / 正则降级 三级分类 + PII 脱敏
- report:  简报 + ICS 导出
- web:     本地只读查询 Web UI
- wizard:  首次运行交互向导
"""
__version__ = "0.2"
