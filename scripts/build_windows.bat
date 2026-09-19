@echo off
rem ==============================================================================
rem  ExamSplit AI - Windows Packaging Launcher
rem  Calls scripts\build.py with Python to avoid cmd.exe encoding bugs
rem ==============================================================================

cd /d "%~dp0\.."

rem Check Python
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python not found in system PATH.
    echo Please ensure Python 3.11+ is installed.
    pause
    exit /b 1
)

rem Run Python build script
python scripts\build.py
if %errorlevel% neq 0 (
    echo [ERROR] Build failed with exit code %errorlevel%.
    pause
    exit /b %errorlevel%
)

echo.
echo Build completed successfully.
pause
