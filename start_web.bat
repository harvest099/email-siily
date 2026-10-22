@echo off
rem 邮箱管家 Web 后台启动 - 双击即可, 不挂终端
cd /d C:\Users\86150\Desktop\personal-assistant

rem 先清掉 8765 上的僵尸进程, 避免多实例
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8765" ^| findstr "LISTENING"') do (
    taskkill /PID %%a /F >nul 2>&1
)

rem 后台起 Web (start "" 让进程与窗口分离, 关窗口不影响)
start "" /B E:\Anaconda\python.exe -X utf8 main.py --web >> logs\web_run.log 2>&1

timeout /t 3 >nul
echo 邮箱管家 Web 已在后台运行: http://127.0.0.1:8765/
echo (此窗口可关闭, 服务继续后台跑)
