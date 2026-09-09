@echo off
chcp 65001 >nul
cd /d "%~dp0"
python -m pip install --upgrade pip
pip install -r requirements.txt
pyinstaller --noconfirm --clean --onefile --windowed --name VideoRecapCutter --add-binary "tools\ffmpeg.exe;." --add-binary "tools\ffprobe.exe;." --hidden-import selenium --hidden-import edge_tts --hidden-import google.generativeai app_v2.py
echo.
echo Neu build thanh cong, file nam trong dist\VideoRecapCutter.exe
pause
