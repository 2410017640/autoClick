@echo off
chcp 65001 >nul
echo 正在启动连点器 Pro...
python "%~dp0autoclicker_pro.py"
if errorlevel 1 (
    echo.
    echo 启动失败，正在安装依赖...
    pip install pyautogui pynput Pillow opencv-python numpy -q
    python "%~dp0autoclicker_pro.py"
)
pause
