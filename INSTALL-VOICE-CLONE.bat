@echo off
chcp 65001 >nul
title Cai Voice Clone XTTS cho Video Recap Cutter
cd /d "%~dp0"
echo ============================================================
echo  CAI VOICE CLONE XTTS - CHAY MOT LAN
echo ============================================================
echo.
echo Phan nay la tuy chon. Edge TTS va Piper Offline khong can cai.
echo XTTS se tao moi truong rieng va tai model lon khi dung lan dau.
echo Uu tien Python 3.11, neu khong co se dung Python 3.10.
echo.
pause

where py >nul 2>nul
if errorlevel 1 (
  echo Khong tim thay Python Launcher.
  echo Hay cai Python 3.10 hoac 3.11 va tick Add Python to PATH.
  pause
  exit /b 1
)

set "PYVER="
py -3.11 -c "import sys" >nul 2>nul
if not errorlevel 1 set "PYVER=-3.11"

if not defined PYVER (
  py -3.10 -c "import sys" >nul 2>nul
  if not errorlevel 1 set "PYVER=-3.10"
)

if not defined PYVER (
  echo.
  echo Khong tim thay Python 3.10 hoac 3.11 tu Python Launcher.
  echo Cac ban Python dang duoc py nhan:
  py -0p
  echo.
  echo Python 3.12 hien khong duoc dung cho bo XTTS nay.
  pause
  exit /b 1
)

echo Dang dung Python %PYVER%

if not exist voice_clone_env (
  py %PYVER% -m venv voice_clone_env
  if errorlevel 1 (
    echo Khong tao duoc moi truong voice_clone_env bang Python %PYVER%.
    pause
    exit /b 1
  )
)

call voice_clone_env\Scripts\activate.bat
python --version
python -m pip install --upgrade pip setuptools wheel
pip install "TTS==0.22.0"
if errorlevel 1 (
  echo.
  echo Cai XTTS that bai. Xem loi o tren.
  pause
  exit /b 1
)

echo.
echo DA CAI XONG VOICE CLONE XTTS.
echo Mo lai VideoRecapCutter.exe va chon giọng trong Kho giong mau.
pause
