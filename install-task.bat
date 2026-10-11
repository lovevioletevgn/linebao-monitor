@echo off
chcp 65001 >nul
cd /d "%~dp0"

set TASK=LinebaoMonitor

echo 正在创建计划任务：%TASK%（每 30 分钟自动跑一次）...

schtasks /create /tn "%TASK%" /sc MINUTE /mo 30 ^
  /tr "\"%~dp0run-silent.bat\"" /f

if %errorlevel%==0 (
  echo.
  echo [OK] 创建成功。
  echo   查看/修改：Win+R 输入 taskschd.msc，搜索 %TASK%
  echo   删除任务 ：schtasks /delete /tn "%TASK%" /f
) else (
  echo.
  echo [失败] 可能权限不足 —— 右键这个文件选「以管理员身份运行」再试一次。
)
echo.
pause
