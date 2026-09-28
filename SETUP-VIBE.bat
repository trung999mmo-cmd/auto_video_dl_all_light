@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
title Vibe Video - Cai dat lan dau
cd /d "%~dp0"

echo ============================================================
echo  VIBE VIDEO - CAI DAT LAN DAU
echo ============================================================
echo.
echo Buoc 1: cai FFmpeg/FFprobe vao chinh thu muc Vibe Video.
echo Buoc 2: cai Voice Clone XTTS vao moi truong rieng.
echo Chi can chay file nay MOT LAN.
echo.
pause

if exist "ffmpeg.exe" if exist "ffprobe.exe" goto :VOICE

echo.
echo [1/2] Dang tai FFmpeg...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop';" ^
  "$zip=Join-Path $PWD '_vibe_ffmpeg.zip';" ^
  "$tmp=Join-Path $PWD '_vibe_ffmpeg_tmp';" ^
  "if(Test-Path $zip){Remove-Item $zip -Force};" ^
  "if(Test-Path $tmp){Remove-Item $tmp -Recurse -Force};" ^
  "Invoke-WebRequest -Uri 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip' -OutFile $zip;" ^
  "Expand-Archive $zip -DestinationPath $tmp -Force;" ^
  "$ff=Get-ChildItem $tmp -Recurse -Filter ffmpeg.exe | Select-Object -First 1;" ^
  "$fp=Get-ChildItem $tmp -Recurse -Filter ffprobe.exe | Select-Object -First 1;" ^
  "if(-not $ff -or -not $fp){throw 'Khong tim thay ffmpeg/ffprobe trong goi tai ve'};" ^
  "Copy-Item $ff.FullName (Join-Path $PWD 'ffmpeg.exe') -Force;" ^
  "Copy-Item $fp.FullName (Join-Path $PWD 'ffprobe.exe') -Force;" ^
  "Remove-Item $zip -Force;" ^
  "Remove-Item $tmp -Recurse -Force;"
if errorlevel 1 goto :FAIL

if not exist "ffmpeg.exe" goto :FAIL
if not exist "ffprobe.exe" goto :FAIL
echo FFmpeg da cai xong.

:VOICE
echo.
echo [2/2] Cai Voice Clone XTTS...
call "INSTALL-VIBE-VOICE.bat"
if errorlevel 1 goto :FAIL

echo.
echo ============================================================
echo  VIBE VIDEO DA CAI DAT XONG
echo ============================================================
echo Bay gio mo "Vibe Video.exe".
echo.
pause
exit /b 0

:FAIL
echo.
echo ============================================================
echo  CAI DAT VIBE VIDEO THAT BAI
echo ============================================================
echo Chup 30 dong CUOI CUNG cua cua so nay gui lai.
pause
exit /b 1
