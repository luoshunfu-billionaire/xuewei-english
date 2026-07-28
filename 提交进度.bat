@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo 正在提交学习进度...
git add users/

git diff --cached --quiet
if %errorlevel%==0 (
  echo 进度没有变化，无需提交。
  pause
  exit /b 0
)

git commit -m "学习进度 %date:~0,10% %time:~0,8%"
if errorlevel 1 (
  echo [错误] 提交失败
  pause
  exit /b 1
)

REM 先拉取远端（其他电脑可能也提交过），再推送
git pull --rebase
if errorlevel 1 (
  echo [错误] 拉取远端进度冲突，请手动执行 git status 查看
  pause
  exit /b 1
)

git push
if errorlevel 1 (
  echo [错误] 推送失败，请检查网络
  pause
  exit /b 1
)

echo.
echo 进度已同步到 GitHub，其他电脑启动时会自动拉取。
pause
