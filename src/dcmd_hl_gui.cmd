@echo off
rem Double Commander file-type highlight - GUI launcher (double-click me)
cd /d "%~dp0"
title Double Commander file type highlight

where pythonw >nul 2>nul
if not errorlevel 1 (
  start "DCMD file type highlight" pythonw "%~dp0dcmd_hl_gui.py" %*
  exit /b 0
)

where python >nul 2>nul
if errorlevel 1 goto nopython

python "%~dp0dcmd_hl_gui.py" %*
if errorlevel 1 pause
exit /b 0

:nopython
echo.
echo [ERROR] Python 3.8 or newer was not found on PATH.
echo.
echo Install Python from https://www.python.org/downloads/windows/
echo and check "Add python.exe to PATH" during setup, then run this file again.
echo (Chinese README: filetypes-highlight\README.md)
echo.
pause
exit /b 1
