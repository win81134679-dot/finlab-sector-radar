@echo off
chcp 65001 > nul
echo ============================================
echo  FinLab 板塊偵測系統 — 環境建置
echo ============================================

REM 建立虛擬環境
if not exist venv (
    echo [1/3] 建立虛擬環境...
    python -m venv venv
) else (
    echo [1/3] 虛擬環境已存在，跳過建立
)

REM 升級 pip
echo [2/3] 升級 pip...
venv\Scripts\python.exe -m pip install --upgrade pip

REM 安裝套件
echo [3/3] 安裝所有套件...
venv\Scripts\pip.exe install -r requirements.txt

REM 設定 FinLab API Token
echo.
echo ============================================
echo  設定 API Keys
echo ============================================
if not exist .env (
    copy .env.example .env > nul
)

REM 建立必要目錄
if not exist output mkdir output
if not exist .cache mkdir .cache
if not exist src mkdir src
if not exist src\analyzers mkdir src\analyzers
if not exist src\reporters mkdir src\reporters

echo.
echo ✅ 環境建置完成！
echo.
echo 請用文字編輯器開啟 .env 檔案，填入你的 FinLab API Token：
echo   FINLAB_API_TOKEN=你的Token
echo.
echo 完成後執行 run.bat 啟動程式
pause
