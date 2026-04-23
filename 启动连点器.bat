@echo off
chcp 65001 >nul
echo 正在启动连点器...
python "%~dp0autoclicker.py"
if errorlevel 1 (
    echo.
    echo 启动失败，正在安装依赖...
    pip install pyautogui pynput -q
    python "%~dp0autoclicker.py"
)
pause
