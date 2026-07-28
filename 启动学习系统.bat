@echo off
chcp 65001 >nul
cd /d "%~dp0"

REM 启动前先拉取最新学习进度（断网时静默跳过）
git pull --rebase >nul 2>&1

set "PYTHON="

where py >nul 2>&1
if %errorlevel%==0 (
  for /f "delims=" %%i in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do set "PYTHON=%%i"
)

if not defined PYTHON (
  where python >nul 2>&1
  if %errorlevel%==0 (
    for /f "delims=" %%i in ('where python') do (
      if not defined PYTHON set "PYTHON=%%i"
    )
  )
)

if not defined PYTHON if exist "%LocalAppData%\Programs\Python\Python314\python.exe" set "PYTHON=%LocalAppData%\Programs\Python\Python314\python.exe"
if not defined PYTHON if exist "%LocalAppData%\Programs\Python\Python313\python.exe" set "PYTHON=%LocalAppData%\Programs\Python\Python313\python.exe"
if not defined PYTHON if exist "D:\software\Programs\Python\Python314\python.exe" set "PYTHON=D:\software\Programs\Python\Python314\python.exe"
if not defined PYTHON if exist "E:\software\Python\Python314\python.exe" set "PYTHON=E:\software\Python\Python314\python.exe"

if not defined PYTHON (
  echo [错误] 未找到 Python。请安装 Python 3，并勾选 Add python.exe to PATH。
  echo https://www.python.org/downloads/
  pause
  exit /b 1
)

if not exist "server.py" (
  echo [错误] 未找到 server.py
  pause
  exit /b 1
)

echo 使用 Python: %PYTHON%
echo.
echo 提示：手机访问前请保证本窗口不要关；若手机打不开，请在防火墙放行端口 5000。
echo.
"%PYTHON%" server.py
if errorlevel 1 (
  echo.
  echo [错误] 服务器启动失败，错误码: %errorlevel%
)
pause
