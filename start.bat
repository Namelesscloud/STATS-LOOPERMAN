@echo off
cd /d "%~dp0"

set VENV_PYTHON=%~dp0.venv\Scripts\python.exe
if exist "%VENV_PYTHON%" (
    set PYTHON="%VENV_PYTHON%"
) else (
    where python >nul 2>nul
    if errorlevel 1 (
        echo Python est introuvable.
        echo.
        echo Installe Python et coche "Add Python to PATH".
        echo.
        pause
        exit /b
    )
    set PYTHON=python
)

start "Looperman Tracker" %PYTHON% looperman_stats.py
start "Looperman Dashboard Server" %PYTHON% -m http.server 8000

timeout /t 2 >nul

start http://localhost:8000/dashboard.html
