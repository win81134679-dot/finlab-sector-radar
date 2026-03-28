@echo off
chcp 65001 > nul
if not exist venv (
    echo [錯誤] 找不到虛擬環境，請先執行 setup.bat
    pause
    exit /b 1
)
call venv\Scripts\activate.bat
python src\main.py
