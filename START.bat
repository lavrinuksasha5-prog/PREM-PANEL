@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set TWKS_PANEL_URL=https://web-production-38df1bc6.up.railway.app
set TWKS_AGENT_TOKEN=1111
set TWKS_ADSPOWER_KEY=41ffc48a75d27a3494b0d5ce966980a8008432dd7a3bdf93
py -3.10 -u ads_agent.py
pause
