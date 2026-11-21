@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Follow the Fake
set "PY="
py -3 --version >nul 2>nul && set "PY=py -3"
if not defined PY python --version >nul 2>nul && set "PY=python"
if not defined PY (
  echo Brak Pythona. Instaluje Python 3.12...
  winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
  echo.
  echo Zamknij to okno i uruchom START.bat ponownie.
  pause
  exit /b
)
if not exist ".venv\Scripts\python.exe" (
  echo Tworze srodowisko i instaluje biblioteki - za pierwszym razem 1-3 minuty...
  %PY% -m venv .venv
  ".venv\Scripts\python.exe" -m pip install --upgrade pip
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
)
if not exist "data\demo\manifest.json" ".venv\Scripts\python.exe" tools\make_demo.py
where tesseract >nul 2>nul
if errorlevel 1 if exist "C:\Program Files\Tesseract-OCR\tesseract.exe" set "TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe"
start "" http://localhost:8000
".venv\Scripts\python.exe" app.py
pause
