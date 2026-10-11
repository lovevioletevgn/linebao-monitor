@echo off
rem 供 Windows 计划任务调用的静默版：不暂停、输出写日志
chcp 65001 >nul
cd /d "%~dp0"

set PY="C:\Users\Violet Evergarden\.workbuddy\binaries\python\envs\default\Scripts\python.exe"

if not exist "data" mkdir "data"
%PY% run.py >> "data\run.log" 2>&1

rem 日志超过 1MB 就归档，防止无限增长
for %%F in ("data\run.log") do if %%~zF GTR 1048576 move /y "data\run.log" "data\run.log.old" >nul 2>&1
