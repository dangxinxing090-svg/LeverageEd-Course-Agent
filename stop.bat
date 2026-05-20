@echo off
chcp 65001 >nul

REM AI智能教育课程平台 - 停止脚本 (Windows)
REM 功能：停止所有服务

echo ========================================
echo   AI智能教育课程平台 - 停止脚本
echo ========================================
echo.

REM 项目根目录
set "PROJECT_ROOT=%~dp0"
set "PID_FILE=%PROJECT_ROOT%.service_pids"

REM 检查 PID 文件
if not exist "%PID_FILE%" (
    echo 未找到运行中的服务
    exit /b 0
)

REM 读取并停止所有服务
echo 停止服务...
for /f "tokens=*" %%a in (%PID_FILE%) do (
    echo 停止进程 (PID: %%a)...
    taskkill /PID %%a /F >nul 2>&1
)

REM 额外检查并停止 uvicorn 和 npm 进程
echo 检查残留进程...

REM 停止 uvicorn 进程
taskkill /F /IM python.exe /FI "WINDOWTITLE eq uvicorn*" >nul 2>&1

REM 停止 node 进程
taskkill /F /IM node.exe >nul 2>&1

REM 清理 PID 文件
del /f /q "%PID_FILE%" 2>nul

echo.
echo ========================================
echo   所有服务已停止
echo ========================================
echo.
