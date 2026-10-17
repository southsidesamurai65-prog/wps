@echo off
REM Windows one-click build: creates a private venv, installs deps, builds a onefile exe.
REM Requires Python >= 3.11 on PATH. Usage: double-click this file, or run packaging\build.bat
setlocal
cd /d "%~dp0.."

if exist ".venv-win\Scripts\python.exe" goto have_venv

echo [1/4] Creating Windows venv .venv-win ...
python -m venv .venv-win
if errorlevel 1 goto err

:have_venv
echo [2/4] Installing dependencies (first run is slow) ...
".venv-win\Scripts\python.exe" -m pip install --upgrade pip >nul
".venv-win\Scripts\python.exe" -m pip install -e ".[dev]"
if errorlevel 1 goto err

echo [3/4] Stopping any running wps-tool.exe ...
taskkill /F /IM wps-tool.exe >nul 2>&1
REM remove stale exe so PyInstaller can overwrite it (avoids WinError 5)
if exist "dist\wps-tool.exe" del /f /q "dist\wps-tool.exe" >nul 2>&1

echo [4/4] Building ...
".venv-win\Scripts\python.exe" -m PyInstaller packaging\wps_tool.spec --noconfirm
if errorlevel 1 goto err

echo.
echo Done. Executable: dist\wps-tool.exe
echo Send dist\wps-tool.exe alone. For PPT beautify, put .env next to the exe.
pause
exit /b 0

:err
echo.
echo Build failed. Common causes:
echo   - wps-tool.exe is still running: close it, then run this again.
echo   - Antivirus locking dist\wps-tool.exe: add the repo folder to the allow list.
echo   - If it still fails, send the error above to the developer.
pause
exit /b 1
