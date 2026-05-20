#!/bin/bash

# AI智能教育课程平台 - 停止脚本 (Mac/Linux)
# 功能：停止所有服务

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$PROJECT_ROOT/.service_pids"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  AI智能教育课程平台 - 停止脚本${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 检查 PID 文件
if [ ! -f "$PID_FILE" ]; then
    echo -e "${YELLOW}未找到运行中的服务${NC}"
    exit 0
fi

# 读取并停止所有服务
STOPPED=0
while IFS= read -r pid; do
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        echo -e "${YELLOW}停止服务 (PID: $pid)...${NC}"
        kill -TERM "$pid" 2>/dev/null || kill -KILL "$pid" 2>/dev/null
        STOPPED=$((STOPPED + 1))
    fi
done < "$PID_FILE"

# 额外检查并停止 uvicorn 和 npm 进程
echo -e "${YELLOW}检查残留进程...${NC}"

# 停止 uvicorn 进程
UVICORN_PIDS=$(pgrep -f "uvicorn app.main:app" 2>/dev/null || true)
if [ -n "$UVICORN_PIDS" ]; then
    for pid in $UVICORN_PIDS; do
        echo -e "${YELLOW}停止 uvicorn (PID: $pid)...${NC}"
        kill -TERM "$pid" 2>/dev/null || true
    done
fi

# 停止 npm 进程
NPM_PIDS=$(pgrep -f "npm start" 2>/dev/null || true)
if [ -n "$NPM_PIDS" ]; then
    for pid in $NPM_PIDS; do
        echo -e "${YELLOW}停止 npm (PID: $pid)...${NC}"
        kill -TERM "$pid" 2>/dev/null || true
    done
fi

# 清理 PID 文件
rm -f "$PID_FILE"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  所有服务已停止${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
