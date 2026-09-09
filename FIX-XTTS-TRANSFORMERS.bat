@echo off
chcp 65001 >nul
title Sua loi XTTS Transformers
cd /d "%~dp0"
echo ============================================================
echo  SUA LOI XTTS - TRANSFORMERS KHONG TUONG THICH
echo ============================================================
echo.
if not exist voice_clone_env\Scripts\python.exe (
  echo Khong thay voice_clone_env.
  echo Hay chay INSTALL-VOICE-CLONE.bat truoc.
  pause
  exit /b 1
)

call voice_clone_env\Scripts\activate.bat
echo Dang sua Transformers...
python -m pip install --upgrade --force-reinstall "transformers==4.57.6" "huggingface-hub>=0.36.2,<1.0"
if errorlevel 1 goto :FAIL

echo.
echo Dang kiem tra XTTS...
python -c "from TTS.api import TTS; import torch, transformers; print('XTTS READY - torch', torch.__version__, '- transformers', transformers.__version__)"
if errorlevel 1 goto :FAIL

echo.
echo ============================================================
echo  XTTS DA SUA XONG
echo ============================================================
echo Bay gio mo VideoRecapCutter.exe va thu Nghe thu giong.
pause
exit /b 0

:FAIL
echo.
echo ============================================================
echo  SUA XTTS THAT BAI
echo ============================================================
echo Chup phan loi CUOI CUNG gui lai.
pause
exit /b 1
