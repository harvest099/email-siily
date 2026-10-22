@echo off
REM 手动测试入口: 跑旧版三件套验证 (计划任务仍走 task_daily.ps1 → main.py)
set "P=E:\Anaconda\python.exe"
%P% -X utf8 -m tools.tool_imap
%P% -X utf8 classify.py
%P% -X utf8 report.py
