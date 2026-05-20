@echo off
chcp 65001 >nul

REM AI智能教育课程平台 - 安装脚本 (Windows)
REM 功能：检测环境、创建虚拟环境、安装依赖

echo ========================================
echo   AI智能教育课程平台 - 安装脚本
echo ========================================
echo.

REM 项目根目录
set "PROJECT_ROOT=%~dp0"
set "BACKEND_DIR=%PROJECT_ROOT%backend"
set "FRONTEND_DIR=%PROJECT_ROOT%frontend"

REM 检查 Python 版本
echo [1/5] 检查 Python 环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误：未检测到 Python
    echo 请先安装 Python 3.10 或更高版本:
    echo   https://www.python.org/downloads/
    exit /b 1
)

for /f "tokens=2" %%a in ('python --version 2^>^&1') do set PYTHON_VERSION=%%a
for /f "tokens=1,2 delims=." %%a in ("%PYTHON_VERSION%") do (
    set PYTHON_MAJOR=%%a
    set PYTHON_MINOR=%%b
)

if %PYTHON_MAJOR% LSS 3 (
    echo 错误：Python 版本 %PYTHON_VERSION% 过低
    echo 需要 Python 3.10 或更高版本
    exit /b 1
)
if %PYTHON_MAJOR% EQU 3 (
    if %PYTHON_MINOR% LSS 10 (
        echo 错误：Python 版本 %PYTHON_VERSION% 过低
        echo 需要 Python 3.10 或更高版本
        exit /b 1
    )
)

echo √ Python 版本: %PYTHON_VERSION%

REM 检查 Node.js 版本
echo [2/5] 检查 Node.js 环境...
node --version >nul 2>&1
if errorlevel 1 (
    echo 错误：未检测到 Node.js
    echo 请先安装 Node.js 18 或更高版本:
    echo   https://nodejs.org/
    exit /b 1
)

for /f "tokens=1 delims=v" %%a in ('node --version') do set NODE_VERSION=%%a
for /f "tokens=1 delims=." %%a in ("%NODE_VERSION%") do set NODE_MAJOR=%%a

if %NODE_MAJOR% LSS 18 (
    echo 错误：Node.js 版本 %NODE_VERSION% 过低
    echo 需要 Node.js 18 或更高版本
    exit /b 1
)

echo √ Node.js 版本: %NODE_VERSION%

REM 检查 npm
echo [3/5] 检查 npm...
npm --version >nul 2>&1
if errorlevel 1 (
    echo 错误：未检测到 npm
    exit /b 1
)

for /f "tokens=*" %%a in ('npm --version') do set NPM_VERSION=%%a
echo √ npm 版本: %NPM_VERSION%

REM 创建 Python 虚拟环境
echo [4/5] 创建 Python 虚拟环境...
if exist "%BACKEND_DIR%\venv" (
    echo 虚拟环境已存在，跳过创建
) else (
    cd /d "%BACKEND_DIR%"
    python -m venv venv
    echo √ 虚拟环境创建成功
)

REM 安装后端依赖
echo [5/5] 安装后端依赖...
cd /d "%BACKEND_DIR%"
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
echo √ 后端依赖安装完成

REM 安装前端依赖
echo      安装前端依赖...
cd /d "%FRONTEND_DIR%"
npm install
echo √ 前端依赖安装完成

REM 创建 .env 文件（如果不存在）
if not exist "%PROJECT_ROOT%\.env" (
    echo      创建 .env 配置文件...
    copy "%PROJECT_ROOT%\.env.example" "%PROJECT_ROOT%\.env" >nul
    echo √ .env 文件已创建（请根据需要编辑配置）
)

echo.
echo ========================================
echo   安装完成！
echo ========================================
echo.
echo 使用说明:
echo   1. 启动服务: start.bat
echo   2. 访问前端: http://localhost:5173
echo   3. 访问后端: http://localhost:8000
echo   4. API 文档: http://localhost:8000/docs
echo.
echo 可选配置:
echo   - 编辑 .env 文件配置 LLM API Key
echo   - 默认使用模拟模式，无需配置即可测试
echo.

pause
