@echo off
REM =============================================================================
REM Agentic Brain - Windows Auto-Start Installer (Batch Wrapper)
REM =============================================================================
REM This batch file calls the PowerShell installation script with proper
REM execution policy and administrator elevation.
REM
REM Usage:
REM   install-autostart-windows.bat                    [Install auto-start]
REM   install-autostart-windows.bat uninstall          [Remove auto-start]
REM
REM =============================================================================

setlocal enabledelayedexpansion

REM Get script directory
set "SCRIPT_DIR=%~dp0"
set "PS_SCRIPT=%SCRIPT_DIR%install-autostart-windows.ps1"

REM Check if PowerShell script exists
if not exist "%PS_SCRIPT%" (
    echo.
    echo ERROR: install-autostart-windows.ps1 not found
    echo Looking for: %PS_SCRIPT%
    echo.
    pause
    exit /b 1
)

REM Parse arguments
set "PS_ARGS="
if not "%1"=="" (
    if /i "%1"=="uninstall" (
        set "PS_ARGS=-Uninstall"
    ) else if /i "%1"=="/?" (
        echo Agentic Brain - Windows Auto-Start Installer
        echo.
        echo Usage:
        echo   install-autostart-windows.bat              [Install auto-start]
        echo   install-autostart-windows.bat uninstall   [Remove auto-start]
        echo.
        pause
        exit /b 0
    ) else (
        echo Unknown option: %1
        echo Run: install-autostart-windows.bat /? for help
        echo.
        pause
        exit /b 1
    )
)

REM Run PowerShell script with proper execution policy
REM Uses "Bypass" scope to avoid affecting system-wide policies
powershell -NoProfile -ExecutionPolicy Bypass -File "%PS_SCRIPT%" %PS_ARGS%

if %ERRORLEVEL% neq 0 (
    echo.
    echo ERROR: PowerShell script failed with exit code %ERRORLEVEL%
    echo.
    pause
    exit /b %ERRORLEVEL%
)

pause
exit /b 0
