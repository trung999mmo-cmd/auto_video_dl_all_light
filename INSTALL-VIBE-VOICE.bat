@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
title Vibe Video - Cai Voice Clone XTTS
cd /d "%~dp0"

echo ============================================================
echo  VIBE VIDEO - CAI VOICE CLONE XTTS
echo ============================================================
echo.
echo Chi can chay MOT LAN neu ban dung giong mau / VietVoice.
echo Vibe se tao moi truong rieng, KHONG anh huong Python khac tren may.
echo.
pause

where py >nul 2>nul
if errorlevel 1 (
  echo Khong tim thay Python Launcher.
  echo Hay cai Python 3.10 hoac 3.11 64-bit.
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
  echo Khong tim thay Python 3.10/3.11.
  py -0p
  pause
  exit /b 1
)

echo Dang dung Python %PYVER%
py %PYVER% --version

if exist "voice_clone_env\Scripts\python.exe" (
  "voice_clone_env\Scripts\python.exe" -c "import sys; assert sys.version_info[:2] in [(3,10),(3,11)]" >nul 2>nul
  if errorlevel 1 (
    echo Moi truong cu sai Python, dang tao lai...
    rmdir /s /q voice_clone_env
  )
)

if not exist voice_clone_env (
  py %PYVER% -m venv voice_clone_env
  if errorlevel 1 goto :FAIL
)

call voice_clone_env\Scripts\activate.bat
python -m pip install --upgrade "pip<27" setuptools wheel
if errorlevel 1 goto :FAIL

echo.
echo [1/4] Cai PyTorch 2.5.1 on dinh cho XTTS...
python -m pip install --upgrade --force-reinstall "torch==2.5.1" "torchaudio==2.5.1"
if errorlevel 1 goto :FAIL

echo.
echo [2/4] Cai Coqui TTS...
python -m pip install --upgrade "numpy==1.26.4" "coqui-tts==0.27.5"
if errorlevel 1 goto :FAIL

echo.
echo [3/4] Khoa Transformers tuong thich XTTS...
python -m pip install --upgrade --force-reinstall "transformers==4.57.6" "huggingface-hub>=0.36.2,<1.0" "numpy==1.26.4"
if errorlevel 1 goto :FAIL

echo.
echo [4/4] Kiem tra bo Voice Clone...
python -m pip check
if errorlevel 1 echo CANH BAO: pip check co canh bao, Vibe se van kiem tra import tiep.
python -c "from TTS.api import TTS; import torch, transformers, numpy; print('VIBE VOICE READY - Python OK | torch',torch.__version__,'| transformers',transformers.__version__,'| numpy',numpy.__version__)"
if errorlevel 1 goto :FAIL

>VOICE-INSTALL-OK.txt echo Vibe Voice Clone installed successfully.

echo.
echo ============================================================
echo  VIBE VOICE DA CAI XONG
echo ============================================================
echo Bay gio mo "Vibe Video.exe".
echo Chon giong mau va bam "Nghe thu giong".
echo Lan dau XTTS se hoi dieu khoan va tai model; day la binh thuong.
pause
exit /b 0

:FAIL
echo.
echo ============================================================
echo  CAI VIBE VOICE THAT BAI
echo ============================================================
echo Chup 30 dong CUOI CUNG cua cua so nay gui lai.
pause
exit /b 1
