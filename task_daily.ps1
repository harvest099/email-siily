# 每日 09:00 自动跑邮箱管家：抓邮件 -> LLM 分类 -> 生成桌面简报
# 计划任务（Windows Task Scheduler）每天 09:00 调用本脚本
$ErrorActionPreference = "Continue"
$root = "C:\Users\86150\Desktop\personal-assistant"
$python = "E:\Anaconda\python.exe"          # 绝对路径: 计划任务环境 PATH 不一定有 python
$logDir = "$root\logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
$logFile = "$logDir\auto_run_$(Get-Date -Format 'yyyy-MM-dd').log"

Add-Content -Path $logFile -Value "=== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') 自动开始 ==="

Set-Location $root
# em 包重构后唯一入口: 抓取 + 三级降级分类 + 简报 + ICS 一次跑完
& $python -X utf8 main.py 2>&1 | Tee-Object -FilePath $logFile -Append

Add-Content -Path $logFile -Value "=== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') 自动结束 ==="
