@echo off
REM Windows one-click build: creates a private venv, installs deps, builds a onefile exe.
REM Requires Python >= 3.11 on PATH. Usage: double-click this file, or run packaging\build.bat
setlocal
cd /d "%~dp0.."

if exist ".venv-win\Scripts\python.exe" goto have_venv

echo [1/3] Creating Windows venv .venv-win ...
python -m venv .venv-win
if errorlevel 1 goto err

:have_venv
echo [2/3] Installing dependencies (first run is slow) ...
".venv-win\Scripts\python.exe" -m pip install --upgrade pip >nul
".venv-win\Scripts\python.exe" -m pip install -e ".[dev]"
if errorlevel 1 goto err

echo [3/3] Building ...
".venv-win\Scripts\python.exe" -m PyInstaller packaging\wps_tool.spec --noconfirm
if errorlevel 1 goto err

echo.
echo Done. Executable: dist\wps-tool.exe
echo Send dist\wps-tool.exe alone. For PPT beautify, put .env next to the exe.
pause
exit /b 0

:err
echo.
echo Build failed. Please send the error above to the developer.
pause
exit /b 1
