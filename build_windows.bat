@echo off
setlocal
cd /d %~dp0
py -m pip install --upgrade pip
py -m pip install -r requirements.txt
if not exist tools mkdir tools
if not exist tools\ffmpeg.exe (
  echo FFmpeg chua co trong tools. Neu may da cai FFmpeg, build van hoat dong nhung EXE se dung FFmpeg he thong.
)
set ADD=
if exist tools\ffmpeg.exe set ADD=%ADD% --add-binary "tools\ffmpeg.exe;."
if exist tools\ffprobe.exe set ADD=%ADD% --add-binary "tools\ffprobe.exe;."
py -m PyInstaller --noconfirm --clean --onefile --windowed --name VideoRecapCutter %ADD% --hidden-import selenium --hidden-import edge_tts --hidden-import google.generativeai app.py
if errorlevel 1 goto :err
echo.
echo XONG: dist\VideoRecapCutter.exe
pause
exit /b 0
:err
echo BUILD LOI
pause
exit /b 1
