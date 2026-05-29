@echo off
REM Double-click this to push every file you've edited since the last run.
cd /d "%~dp0"

if exist "venv\Scripts\activate.bat" (
    call "venv\Scripts\activate.bat"
)

python push_recent.py
set EXITCODE=%ERRORLEVEL%

echo.
echo Press any key to close...
pause >nul
exit /b %EXITCODE%
