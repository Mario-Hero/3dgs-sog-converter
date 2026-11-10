@echo off
chcp 65001 >nul 2>nul
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
    py -3 app.py
) else (
    python app.py
)

if %errorlevel% neq 0 (
    echo.
    echo [启动失败] 请确认已安装 Python 3.9+（含 tkinter）与 Node.js，
    echo 并执行过: npm install -g @playcanvas/splat-transform
    pause
)
