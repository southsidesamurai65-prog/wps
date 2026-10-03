@echo off
REM Windows 一键打包：自动建独立 venv、装依赖、出单文件 exe。需已装 Python >= 3.11。
REM 用法：在资源管理器里双击本文件，或在命令行运行 packaging\build.bat
setlocal
cd /d "%~dp0.."

if not exist ".venv-win\Scripts\python.exe" (
    echo [1/3] 创建 Windows 虚拟环境 .venv-win ...
    python -m venv .venv-win || goto :err
)

echo [2/3] 安装依赖（首次较慢）...
".venv-win\Scripts\python.exe" -m pip install --upgrade pip >nul
".venv-win\Scripts\python.exe" -m pip install -e ".[dev]" || goto :err

echo [3/3] 打包 ...
".venv-win\Scripts\python.exe" -m PyInstaller packaging\wps_tool.spec --noconfirm || goto :err

echo.
echo 完成！可执行文件：dist\wps-tool.exe
echo 把它单独发给别人即可双击运行；如需 PPT 美化，把 .env 放到 exe 同目录。
pause
exit /b 0

:err
echo.
echo 出错了，请把上面的报错发给开发者。
pause
exit /b 1
