@echo off
cd /d "%~dp0"
echo Starting Remote-PC server with a TEMPORARY PUBLIC LINK...
echo.
echo 1) Wait for the "TEMPORARY PUBLIC LINK" to appear below
echo 2) Open that link in any browser, anywhere
echo 3) Enter the password (default: admin - set REMOTE_PC_PASSWORD to change it)
echo.
echo The link stops working when you close this window.
echo Press Ctrl+C to stop.
echo.
python server.py --tunnel
pause
