@echo off
cd /d "%~dp0"
python runtime\control_server.py --simulate --port 8088
pause
