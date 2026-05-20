@echo off
chcp 65001 >nul

REM AI智能教育课程平台 - 启动脚本 (Windows)
REM 功能：并行启动后端和前端服务

echo ========================================
echo   AI智能教育课程平台 - 启动脚本
echo ========================================
echo.

REM 项目根目录
set "PROJECT_ROOT=%~dp0"
set "BACKEND_DIR=%PROJECT_ROOT%backend"
set "FRONTEND_DIR=%PROJECT_ROOT%frontend"
set "PID_FILE=%PROJECT_ROOT%.service_pids"

REM 检查虚拟环境是否存在
if not exist "%BACKEND_DIR%\venv" (
    echo 错误：未检测到虚拟环境
    echo 请先运行安装脚本: install.bat
    exit /b 1
)

REM 加载环境变量
if exist "%PROJECT_ROOT%\.env" (
    echo 加载环境变量...
    for /f "usebackq tokens=*" %%a in ("%PROJECT_ROOT%\.env") do (
        echo %%a | findstr /b "#" >nul || set "%%a"
    )
)

REM 清理之前的 PID 文件
del /f /q "%PID_FILE%" 2>nul

REM 设置默认端口
if "%PORT%"=="" set PORT=8000
if "%HOST%"=="" set HOST=0.0.0.0

REM 启动后端服务
echo [1/2] 启动后端服务...
cd /d "%BACKEND_DIR%"
call venv\Scripts\activate.bat

REM 后台启动后端（使用 start 命令）
start /b cmd /c "python -m uvicorn app.main:app --host %HOST% --port %PORT% --reload --log-level info ^> "%PROJECT_ROOT%backend.log" 2^>^&1"
for /f "tokens=2" %%a in ('tasklist ^| findstr "python.exe"') do (
    set BACKEND_PID=%%a
    echo %%a >> "%PID_FILE%"
    goto :backend_started
)
:backend_started
echo √ 后端服务已启动 (PID: %BACKEND_PID%)
echo   日志: backend.log
echo   地址: http://%HOST%:%PORT%
echo.

REM 等待后端启动
echo 等待后端服务就绪...
for /l %%i in (1,1,30) do (
    timeout /t 1 /nobreak >nul
    curl -s "http://%HOST%:%PORT%/health" >nul 2>&1
    if not errorlevel 1 (
        echo √ 后端服务就绪
        goto :backend_ready
    )
)
echo 警告：后端服务启动较慢，请检查 backend.log
:backend_ready
echo.

REM 启动前端服务
echo [2/2] 启动前端服务...
cd /d "%FRONTEND_DIR%"

REM 后台启动前端
start /b cmd /c "npm start ^> "%PROJECT_ROOT%frontend.log" 2^>^&1"
timeout /t 2 /nobreak >nul
for /f "tokens=2" %%a in ('tasklist ^| findstr "node.exe"') do (
    set FRONTEND_PID=%%a
    echo %%a >> "%PID_FILE%"
    goto :frontend_started
)
:frontend_started
echo √ 前端服务已启动
echo   日志: frontend.log
echo   地址: http://localhost:5173
echo.

echo ========================================
echo   所有服务已启动！
echo ========================================
echo.
echo 访问地址:
echo   前端界面: http://localhost:5173
echo   后端API:  http://%HOST%:%PORT%
echo   API文档:  http://%HOST%:%PORT%/docs
echo.
echo 日志文件:
echo   后端日志: backend.log
echo   前端日志: frontend.log
echo.
echo 操作命令:
echo   停止服务: stop.bat
echo   查看日志: type backend.log 或 type frontend.log
echo.
echo 按任意键停止所有服务...
pause >nul

REM 停止服务
call stop.bat
