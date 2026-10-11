@echo off
chcp 65001 >nul
cd /d "%~dp0"

rem 项目自带的隔离 Python（跑之前确保依赖已装）
set PY="C:\Users\Violet Evergarden\.workbuddy\binaries\python\envs\default\Scripts\python.exe"

%PY% run.py %*

rem 跑完自动打开结果网页，不用自己去翻文件
if exist "data\preview.html" start "" "data\preview.html"

echo.
echo ===== 结束，按任意键关闭 =====
pause >nul
