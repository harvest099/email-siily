# 每日 09:00 自动跑邮箱管家：抓邮件 -> LLM 分类 -> 生成桌面简报
# 计划任务（Windows Task Scheduler）每天 09:00 调用本脚本
# 使用者注意: 下面两个路径改成你自己的 (项目目录 / python 绝对路径), 或用 main.py --wizard 重新生成
$ErrorActionPreference = "Continue"
$root = $PSScriptRoot                                  # ← 自动定位项目目录 (脚本所在处), 无需手改
$python = "E:\Anaconda\python.exe"                      # ← 你的 python.exe 绝对路径 (需 3.9+; 计划任务环境 PATH 里常没有 python)
$logDir = "$root\logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
# 找不到 python 不硬跑: 写日志提示, 退出 (避免明天 09:00 静默失败)
if (-not (Test-Path $python)) { "找不到 python: $python, 请修改 task_daily.ps1 里的 $python" | Out-File "$logDir\python_missing.log" -Encoding utf8; exit 1 }
$logFile = "$logDir\auto_run_$(Get-Date -Format 'yyyy-MM-dd').log"

Add-Content -Path $logFile -Value "=== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') 自动开始 ==="

Set-Location $root
# em 包重构后唯一入口: 抓取 + 三级降级分类 + 简报 + ICS 一次跑完
& $python -X utf8 main.py 2>&1 | Tee-Object -FilePath $logFile -Append

Add-Content -Path $logFile -Value "=== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') 自动结束 ==="
