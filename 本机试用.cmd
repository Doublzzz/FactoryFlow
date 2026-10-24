@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo 缺少本项目已准备的 Python 环境。此入口不自动安装依赖。
  pause
  exit /b 1
)
if not "%~1"=="" (
  ".venv\Scripts\python.exe" scripts\local-trial.py %*
  exit /b
)
:menu
echo.
echo FactoryFlow 本机合成试用
echo 1. 启动或打开试用
echo 2. 查看状态
echo 3. 创建并验证备份
echo 4. 停止服务，保留数据
echo 5. 验证最新备份恢复，保留当前环境
echo 6. 从最新备份创建新环境并切换（旧环境保留）
echo 7. 首次准备（已有环境会拒绝）
echo 0. 退出
choice /c 12345670 /n /m "选择："
if errorlevel 8 exit /b 0
if errorlevel 7 goto prepare
if errorlevel 6 goto restore
if errorlevel 5 goto verify
if errorlevel 4 goto stop
if errorlevel 3 goto backup
if errorlevel 2 goto status
goto start
:start
".venv\Scripts\python.exe" scripts\local-trial.py start --open-browser
goto menu
:status
".venv\Scripts\python.exe" scripts\local-trial.py status
goto menu
:backup
".venv\Scripts\python.exe" scripts\local-trial.py backup
goto menu
:stop
".venv\Scripts\python.exe" scripts\local-trial.py stop
goto menu
:verify
".venv\Scripts\python.exe" scripts\local-trial.py restore
goto menu
:restore
".venv\Scripts\python.exe" scripts\local-trial.py restore --activate
if errorlevel 1 goto menu
goto start
:prepare
".venv\Scripts\python.exe" scripts\local-trial.py prepare
goto menu
