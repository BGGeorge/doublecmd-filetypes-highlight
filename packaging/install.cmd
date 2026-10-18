@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Double Commander file-type highlight - one-click install

echo ============================================================
echo  Double Commander  file-type highlight  -  one-click install
echo ============================================================
echo.

set "TOOL=dcmd_hl_cli.exe"
if not exist "%TOOL%" set "TOOL=dcmd_hl.py"
if not exist "%TOOL%" goto notool

set "PYCMD="
if /i not "%TOOL%"=="dcmd_hl.py" goto havetool
where python >nul 2>nul
if not errorlevel 1 set "PYCMD=python"
if defined PYCMD goto havetool
where py >nul 2>nul
if not errorlevel 1 set "PYCMD=py"
if not defined PYCMD goto nopython

:havetool
set /a tries=0
:attempt
set /a tries+=1
echo Running installer (attempt %tries%) ...
echo.
if /i "%TOOL%"=="dcmd_hl.py" (
  %PYCMD% -X utf8 "%TOOL%" install %*
) else (
  "%TOOL%" install %*
)
if not errorlevel 1 goto success

echo.
echo [NOTICE] Install did not finish.
echo   1) If Double Commander is running, close it completely, then retry.
echo   2) If the config folder was not found, run it with an explicit path:
echo        dcmd_hl_cli.exe install -c "C:\Users\you\AppData\Roaming\doublecmd"
echo      Portable DC:
echo        dcmd_hl_cli.exe install -c "...\doublecmd\settings"
echo        dcmd_hl_cli.exe install --exe "...\doublecmd.exe"
echo   3) More details: README.md (section "FAQ")
echo.
if %tries% GEQ 2 goto manual
echo Press any key to try again, or close this window to cancel.
pause >nul
goto attempt

:success
echo.
echo [DONE] Rules installed. Start Double Commander to see the colors.
echo        Run dcmd_hl_gui.exe later to tweak colors / disable categories.
echo.
pause
exit /b 0

:manual
echo See README.md for manual steps. Press any key to close.
pause >nul
exit /b 1

:notool
echo [ERROR] Neither dcmd_hl_cli.exe nor dcmd_hl.py was found next to this script.
echo         Extract the whole package first, then run install.cmd again.
echo.
pause
exit /b 1

:nopython
echo [ERROR] dcmd_hl_cli.exe is missing and Python is not installed.
echo         Please use the full package (it contains dcmd_hl_cli.exe),
echo         or install Python 3.8+ from https://www.python.org/downloads/windows/
echo.
pause
exit /b 1
