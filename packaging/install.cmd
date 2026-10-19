@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Double Commander file-type highlight - one-click install

echo ============================================================
echo  Double Commander  file-type highlight  -  one-click install
echo ============================================================
echo.

rem ---- architecture check (the win64 package cannot run on 32-bit Windows) ----
set "ARCH_TAG="
if exist "arch.txt" for /f "usebackq delims=" %%A in ("arch.txt") do set "ARCH_TAG=%%A"
set "OS_IS_64=1"
if /i "%PROCESSOR_ARCHITECTURE%"=="x86" if not defined PROCESSOR_ARCHITEW6432 set "OS_IS_64=0"
if /i "%ARCH_TAG%"=="win64" if "%OS_IS_64%"=="0" goto wrongarch

set "TOOL=dcmd_hl_cli.exe"
if not exist "%TOOL%" set "TOOL=python-src\dcmd_hl.py"
if not exist "%TOOL%" goto notool

set "PYCMD="
if /i not "%TOOL%"=="python-src\dcmd_hl.py" goto havetool
where python >nul 2>nul
if not errorlevel 1 set "PYCMD=python"
if defined PYCMD goto havetool
where py >nul 2>nul
if not errorlevel 1 set "PYCMD=py"
if not defined PYCMD goto nopython

:havetool
rem ---- arguments passed to install.cmd go straight to the tool ----
if not "%~1"=="" goto runargs

echo Detecting the Double Commander config folder ...
echo.
call :runtool detect
if errorlevel 1 goto askpath
echo.
echo [i] The detection result is shown above.
echo     - Press ENTER to install into the suggested folder, or
echo     - drag your Double Commander program folder (or doublecmd.exe, or its
echo       "settings" folder) into this window, then press ENTER to use it.
echo.
set "USERPATH="
set /p "USERPATH=Path (optional): "
if defined USERPATH goto runuser
goto runplain

:askpath
echo.
echo [i] Could not auto-detect the config folder.
echo     Portable Double Commander keeps its config in the "settings" folder
echo     next to doublecmd.exe. Program folders WITHOUT a settings folder use
echo     the per-user location %%APPDATA%%\doublecmd instead.
echo     - Drag the Double Commander program folder (or doublecmd.exe, or its
echo       "settings" folder) into this window, then press ENTER to use it; or
echo     - press ENTER with nothing typed to open a folder picker.
echo.
set "USERPATH="
set /p "USERPATH=Path (optional): "
if defined USERPATH goto runuser
goto pickfolder

:pickfolder
echo Opening the folder picker ...
set "USERPATH="
for /f "usebackq delims=" %%P in (`powershell -NoProfile -STA -ExecutionPolicy Bypass -File "pick-folder.ps1" 2^>nul`) do set "USERPATH=%%P"
if defined USERPATH goto runuser
goto manual

:runargs
set "ARGS=%*"
goto retry
:runuser
set "ARGS=%USERPATH%"
goto retry
:runplain
set "ARGS="

:retry
set /a tries=0
:retry_next
set /a tries+=1
echo.
echo Running the installer (attempt %tries%) ...
echo.
call :runtool install %ARGS%
if not errorlevel 1 goto success
echo.
echo [NOTICE] The installer did not finish.
echo   1) If Double Commander is running, close it completely (tray icon too), then retry.
echo   2) You can pass the folder explicitly, for example:
echo        dcmd_hl_cli.exe install "D:\Tools\doublecmd"             portable DC program folder
echo        dcmd_hl_cli.exe install "D:\Tools\doublecmd\settings"    portable DC settings folder
echo        dcmd_hl_cli.exe install -c "C:\Users\you\AppData\Roaming\doublecmd"
echo   3) More details: README.md (section ^"FAQ^").
echo.
if %tries% GEQ 2 goto manual
echo Press any key to try again, or close this window to cancel.
pause >nul
goto retry_next

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

:wrongarch
echo [ERROR] This package is for 64-bit Windows (win64), but this Windows is 32-bit.
echo         Please download the "win32" package from the Releases page:
echo           https://github.com/BGGeorge/doublecmd-filetypes-highlight/releases
echo.
pause
exit /b 1

:notool
echo [ERROR] Neither dcmd_hl_cli.exe nor python-src\dcmd_hl.py was found next to this script.
echo         Extract the WHOLE package first, then run install.cmd again.
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

:runtool
if /i "%TOOL%"=="python-src\dcmd_hl.py" (
  %PYCMD% -X utf8 "%TOOL%" %*
) else (
  "%TOOL%" %*
)
exit /b %errorlevel%
