@echo off
rem 邮箱管家 Web 后台启动 - 双击即可, 关此窗口服务继续跑
cd /d "C:\Users\86150\Desktop\personal-assistant"
if not exist logs mkdir logs

rem 清掉 8765 上的旧实例, 避免端口冲突
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8765" ^| findstr "LISTENING"') do (
    taskkill /PID %%a /F >nul 2>&1
)

rem 起 Web, 日志写 logs\web_run.log
start "" /B E:\Anaconda\python.exe -X utf8 main.py --web >> "logs\web_run.log" 2>&1
timeout /t 3 /nobreak >nul
echo 邮箱管家 Web 已在后台运行: http://127.0.0.1:8765/
echo 关此窗口不影响服务。日志: logs\web_run.log
