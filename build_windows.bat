@echo off
rem ==============================================================================
rem  ExamSplit AI - Windows Packaging Launcher (Root Level)
rem ==============================================================================

cd /d "%~dp0"

if exist "D:\examsplit_env\python.exe" (
    set "PYTHON_EXE=D:\examsplit_env\python.exe"
) else (
    where python >nul 2>nul
    if %errorlevel% neq 0 (
        echo [ERROR] Python not found in system PATH or D:\examsplit_env.
        echo Please ensure Python 3.11+ is installed.
        pause
        exit /b 1
    )
    set "PYTHON_EXE=python"
)

echo Using Python: %PYTHON_EXE%
"%PYTHON_EXE%" scripts\build.py
if %errorlevel% neq 0 (
    echo [ERROR] Build failed with exit code %errorlevel%.
    pause
    exit /b %errorlevel%
)

echo.
echo Build completed successfully.
pause
