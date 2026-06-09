#!/bin/bash

# AI智能教育课程平台 - 停止脚本
# 默认只停止本项目前后端，PostgreSQL 保持运行。
# 如需同时停止 Homebrew PostgreSQL，可执行：./stop.sh --with-db

set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$PROJECT_ROOT/.service_pids"
WITH_DB="${1:-}"
BACKEND_SESSION="course_agent_backend"
FRONTEND_SESSION="course_agent_frontend"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  AI智能教育课程平台 - 停止服务${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

stop_pid() {
    local pid="$1"
    local label="${2:-process}"

    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        echo -e "${YELLOW}停止 ${label} (PID: $pid)...${NC}"
        kill -TERM "$pid" 2>/dev/null || true
        sleep 1
        if kill -0 "$pid" 2>/dev/null; then
            kill -KILL "$pid" 2>/dev/null || true
        fi
    fi
}

stop_screen_session() {
    local session="$1"
    local label="$2"

    if command -v screen >/dev/null 2>&1; then
        if screen -ls 2>/dev/null | grep -q "[.]${session}[[:space:]]"; then
            echo -e "${YELLOW}停止 ${label} screen 会话：${session}...${NC}"
            screen -S "$session" -X quit >/dev/null 2>&1 || true
        fi
    fi
}

stop_screen_session "$BACKEND_SESSION" "后端"
stop_screen_session "$FRONTEND_SESSION" "前端"

if [ -f "$PID_FILE" ]; then
    while IFS= read -r pid; do
        [[ "$pid" == screen:* ]] && continue
        stop_pid "$pid" "项目进程"
    done < "$PID_FILE"
    rm -f "$PID_FILE"
else
    echo -e "${YELLOW}未找到 .service_pids，继续检查残留前后端进程...${NC}"
fi

# 清理本项目 uvicorn / Vite 进程，避免端口残留。
UVICORN_PIDS=$(pgrep -f "uvicorn app.main:app" 2>/dev/null || true)
for pid in $UVICORN_PIDS; do
    stop_pid "$pid" "uvicorn"
done

VITE_PIDS=$(pgrep -f "vite --host" 2>/dev/null || true)
for pid in $VITE_PIDS; do
    stop_pid "$pid" "vite"
done

NPM_PIDS=$(pgrep -f "npm start" 2>/dev/null || true)
for pid in $NPM_PIDS; do
    stop_pid "$pid" "npm"
done

if [ "$WITH_DB" = "--with-db" ]; then
    echo -e "${YELLOW}尝试停止 Homebrew PostgreSQL...${NC}"
    if command -v brew >/dev/null 2>&1; then
        for formula in postgresql@16 postgresql@15 postgresql@14 postgresql; do
            if brew list "$formula" >/dev/null 2>&1; then
                brew services stop "$formula" >/dev/null 2>&1 || true
            fi
        done
    fi
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  前后端服务已停止${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
