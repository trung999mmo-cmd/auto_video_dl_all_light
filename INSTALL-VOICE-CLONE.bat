@echo off
chcp 65001 >nul
title Cai Voice Clone XTTS cho Video Recap Cutter
cd /d "%~dp0"
echo ============================================================
echo  CAI VOICE CLONE XTTS - CHAY MOT LAN
echo ============================================================
echo.
echo Phan nay chi can khi dung GIONG MAU / Voice Clone.
echo Edge TTS va Piper Offline khong can cai phan nay.
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
  echo Khong tim thay Python 3.10 hoac 3.11.
  py -0p
  pause
  exit /b 1
)

echo Dang dung Python %PYVER%

if not exist voice_clone_env (
  py %PYVER% -m venv voice_clone_env
  if errorlevel 1 (
    echo Khong tao duoc voice_clone_env.
    pause
    exit /b 1
  )
)

call voice_clone_env\Scripts\activate.bat
python --version
python -m pip install --upgrade pip setuptools wheel
if errorlevel 1 goto :FAIL

echo.
echo [1/4] Cai PyTorch / torchaudio...
python -m pip install --upgrade torch torchaudio
if errorlevel 1 goto :FAIL

echo.
echo [2/4] Cai torchcodec neu can...
python -m pip install --upgrade torchcodec
if errorlevel 1 echo Canh bao: torchcodec khong cai duoc, tiep tuc.

echo.
echo [3/4] Cai Coqui TTS ban moi co wheel Windows...
python -m pip uninstall -y TTS >nul 2>nul
python -m pip install --upgrade "coqui-tts==0.27.5"
if errorlevel 1 goto :FAIL

echo.
echo [4/4] Sua tuong thich Transformers cho XTTS...
python -m pip install --upgrade --force-reinstall "transformers==4.57.6" "huggingface-hub>=0.36.2,<1.0"
if errorlevel 1 goto :FAIL

echo.
echo Dang kiem tra XTTS...
python -c "from TTS.api import TTS; import torch, transformers; print('XTTS READY - torch', torch.__version__, '- transformers', transformers.__version__)"
if errorlevel 1 goto :FAIL

echo.
echo ============================================================
echo  DA CAI XONG VOICE CLONE XTTS
echo ============================================================
echo Mo lai VideoRecapCutter.exe, vao Kho giong mau va chon giong.
echo Lan dau bam Nghe thu / Chay, XTTS se tai model xtts_v2 lon.
pause
exit /b 0

:FAIL
echo.
echo ============================================================
echo  CAI XTTS THAT BAI
echo ============================================================
echo Chup phan loi CUOI CUNG cua cua so nay gui lai de sua tiep.
pause
exit /b 1
