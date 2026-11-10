@echo off
cd /d "%~dp0"
echo Starting Remote-PC server...
echo.
echo 1) Open your browser to: http://127.0.0.1:8765
echo 2) Enter the password (default: admin)
echo 3) Click the screen to gain control
echo.
echo Press Ctrl+C to stop the server.
echo.
python server.py
pause
