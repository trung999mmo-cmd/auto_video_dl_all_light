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
echo Mot so ngon ngu/model co the co dieu khoan su dung rieng.
echo.
pause
where py >nul 2>nul
if errorlevel 1 (
  echo Khong tim thay Python Launcher. Hay cai Python 3.11 tu python.org va tick Add Python to PATH.
  pause
  exit /b 1
)
if not exist voice_clone_env (
  py -3.11 -m venv voice_clone_env
  if errorlevel 1 (
    echo Khong tao duoc moi truong Python 3.11.
    pause
    exit /b 1
  )
)
call voice_clone_env\Scripts\activate.bat
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
echo Quay lai tool, chon He giong = Voice Clone XTTS va chon Audio giong mau.
pause
