@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo [1/3] Окружение...
if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv || goto :error
)

echo [2/3] Зависимости...
".venv\Scripts\python.exe" -m pip install -q -r requirements.txt || goto :error

echo [3/3] Конфиг...
if not exist ".env" copy ".env.example" ".env" >nul

echo.
echo Панель: http://127.0.0.1:8000
echo Пароль: см. .env (TWKS_ADMIN_PASSWORD)
echo.
".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
goto :eof

:error
echo.
echo Ошибка установки. Проверь, что Python 3.11+ установлен и есть интернет.
pause
