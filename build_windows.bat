@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Creating the build environment. This does not download local models.
  py -3.12 -m venv .venv
  if errorlevel 1 exit /b 1
)
".venv\Scripts\python.exe" -m pip install -r requirements-build.txt
if errorlevel 1 exit /b %errorlevel%
".venv\Scripts\python.exe" build_windows.py
if errorlevel 1 exit /b %errorlevel%
echo.
echo Windows build ready: dist\JARVIS\JARVIS.exe
echo Copy the complete dist\JARVIS folder to the target PC. Python does not need to be installed or on PATH.
endlocal
