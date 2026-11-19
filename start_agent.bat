@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Сначала запусти start_panel.bat
    pause
    exit /b 1
)

set TWKS_PANEL_URL=http://127.0.0.1:8000
if exist ".env" (
    for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
        if not "%%a"=="" if not "%%a:~0,1%"=="#" set "%%a=%%b"
    )
)

echo Агент запускается. Окна Окто: режим мок = %TWKS_OCTO_MOCK%
".venv\Scripts\python.exe" agent\agent.py
pause
