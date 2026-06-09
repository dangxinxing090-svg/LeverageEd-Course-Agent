#!/bin/bash

# AI智能教育课程平台 - 一键启动脚本 (macOS/Linux)
# 启动 PostgreSQL、后端、前端，完成可用性自检后打开浏览器。

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
PID_FILE="$PROJECT_ROOT/.service_pids"
BACKEND_LOG="$PROJECT_ROOT/backend.log"
FRONTEND_LOG="$PROJECT_ROOT/frontend.log"
BACKEND_SESSION="course_agent_backend"
FRONTEND_SESSION="course_agent_frontend"

BACKEND_HOST="${HOST:-127.0.0.1}"
BACKEND_PORT="${PORT:-8000}"
FRONTEND_HOST="${FRONTEND_HOST:-127.0.0.1}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
BACKEND_URL="http://${BACKEND_HOST}:${BACKEND_PORT}"
FRONTEND_URL="http://${FRONTEND_HOST}:${FRONTEND_PORT}"
PROXY_CHECK_URL="${FRONTEND_URL}/api/v1/sessions?user_id=anonymous&status=active&limit=1"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  AI智能教育课程平台 - 一键启动${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

if [ -f "$PROJECT_ROOT/.env" ]; then
    echo -e "${YELLOW}加载 .env 配置...${NC}"
    set -a
    # shellcheck disable=SC1091
    source "$PROJECT_ROOT/.env"
    set +a
fi

DATABASE_URL="${DATABASE_URL:-postgresql://edu_user:123456@127.0.0.1:5432/education}"
POSTGRES_ADMIN_URL="${POSTGRES_ADMIN_URL:-postgresql://postgres:123456@127.0.0.1:5432/postgres}"
export DATABASE_URL POSTGRES_ADMIN_URL
export BACKEND_DIR FRONTEND_DIR BACKEND_LOG FRONTEND_LOG
export BACKEND_HOST BACKEND_PORT FRONTEND_HOST FRONTEND_PORT

fail() {
    echo -e "${RED}$1${NC}"
    exit 1
}

require_path() {
    [ -e "$1" ] || fail "缺少必要文件或目录：$1。请先运行 ./install.sh 安装依赖。"
}

require_command() {
    command -v "$1" >/dev/null 2>&1 || fail "缺少命令：$1。请先安装后再启动。"
}

wait_for_url() {
    local url="$1"
    local name="$2"
    local seconds="${3:-45}"

    for ((i = 1; i <= seconds; i++)); do
        if curl -fsS "$url" >/dev/null 2>&1; then
            echo -e "${GREEN}✓ ${name} 可用${NC}"
            return 0
        fi
        sleep 1
    done

    echo -e "${RED}${name} 启动或检查超时：$url${NC}"
    echo "后端日志：$BACKEND_LOG"
    echo "前端日志：$FRONTEND_LOG"
    return 1
}

stop_pid() {
    local pid="$1"
    local label="${2:-process}"

    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        echo -e "${YELLOW}停止旧的 ${label} (PID: $pid)...${NC}"
        kill -TERM "$pid" 2>/dev/null || true
        sleep 1
        if kill -0 "$pid" 2>/dev/null; then
            kill -KILL "$pid" 2>/dev/null || true
        fi
    fi
}

stop_old_services() {
    echo -e "${YELLOW}[1/7] 清理旧的前后端进程...${NC}"

    if command -v screen >/dev/null 2>&1; then
        screen -S "$BACKEND_SESSION" -X quit >/dev/null 2>&1 || true
        screen -S "$FRONTEND_SESSION" -X quit >/dev/null 2>&1 || true
    fi

    if [ -f "$PID_FILE" ]; then
        while IFS= read -r pid; do
            [[ "$pid" == screen:* ]] && continue
            stop_pid "$pid" "项目进程"
        done < "$PID_FILE"
        rm -f "$PID_FILE"
    fi

    if command -v pgrep >/dev/null 2>&1; then
        for pid in $(pgrep -f "uvicorn app.main:app" 2>/dev/null || true); do
            stop_pid "$pid" "uvicorn"
        done
        for pid in $(pgrep -f "vite --host" 2>/dev/null || true); do
            stop_pid "$pid" "vite"
        done
        for pid in $(pgrep -f "npm start" 2>/dev/null || true); do
            stop_pid "$pid" "npm"
        done
    fi

    : > "$PID_FILE"
    echo -e "${GREEN}✓ 旧的前后端进程已清理${NC}"
}

check_backend_env() {
    echo -e "${YELLOW}[2/7] 检查后端环境...${NC}"
    require_path "$BACKEND_DIR/venv/bin/python"

    if ! "$BACKEND_DIR/venv/bin/python" -c "import fastapi, uvicorn, sqlalchemy, psycopg2, openai" >/dev/null 2>&1; then
        fail "后端依赖不完整。请运行：cd backend && venv/bin/python -m pip install -r requirements.txt"
    fi

    echo -e "${GREEN}✓ 后端虚拟环境可用${NC}"
}

postgres_ready() {
    (
        cd "$BACKEND_DIR"
        POSTGRES_ADMIN_URL="$POSTGRES_ADMIN_URL" venv/bin/python - <<'PY'
import os
from sqlalchemy import create_engine, text

try:
    engine = create_engine(
        os.environ["POSTGRES_ADMIN_URL"],
        pool_pre_ping=True,
        connect_args={"connect_timeout": 2},
    )
    with engine.connect() as conn:
        conn.execute(text("select 1"))
except Exception:
    raise SystemExit(1)
PY
    ) >/dev/null 2>&1
}

ensure_postgres() {
    echo -e "${YELLOW}[3/7] 检查 PostgreSQL...${NC}"

    if postgres_ready; then
        echo -e "${GREEN}✓ PostgreSQL 已运行${NC}"
        return 0
    fi

    echo -e "${YELLOW}PostgreSQL 未响应，尝试启动本机服务...${NC}"
    if command -v brew >/dev/null 2>&1; then
        for formula in postgresql@16 postgresql@15 postgresql@14 postgresql; do
            if brew list "$formula" >/dev/null 2>&1; then
                echo -e "${CYAN}使用 Homebrew 启动 $formula...${NC}"
                brew services start "$formula" >/dev/null 2>&1 || true
                break
            fi
        done
    fi

    for _ in {1..20}; do
        if postgres_ready; then
            echo -e "${GREEN}✓ PostgreSQL 启动成功${NC}"
            return 0
        fi
        sleep 1
    done

    fail "PostgreSQL 未启动或不可连接。请确认本机 PostgreSQL 正在监听 127.0.0.1:5432。"
}

ensure_database() {
    echo -e "${YELLOW}[4/7] 初始化 PostgreSQL 数据库...${NC}"

    (
        cd "$BACKEND_DIR"
        PROJECT_ROOT="$PROJECT_ROOT" DATABASE_URL="$DATABASE_URL" POSTGRES_ADMIN_URL="$POSTGRES_ADMIN_URL" venv/bin/python - <<'PY'
import os
import re
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

database_url = os.environ["DATABASE_URL"]
admin_url = os.environ["POSTGRES_ADMIN_URL"]
target = make_url(database_url)

if target.drivername.split("+", 1)[0] != "postgresql":
    raise SystemExit("DATABASE_URL 必须是 postgresql:// 连接串")

db_name = target.database
db_user = target.username
db_password = target.password or ""

if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", db_name or ""):
    raise SystemExit("数据库名只能包含字母、数字和下划线")
if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", db_user or ""):
    raise SystemExit("数据库用户名只能包含字母、数字和下划线")

admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT", pool_pre_ping=True)
with admin_engine.connect() as conn:
    role_exists = conn.execute(
        text("select 1 from pg_roles where rolname = :role"),
        {"role": db_user},
    ).scalar() is not None
    if role_exists:
        conn.execute(text(f"alter user {db_user} with password :password"), {"password": db_password})
    else:
        conn.execute(text(f"create user {db_user} with password :password"), {"password": db_password})

    db_exists = conn.execute(
        text("select 1 from pg_database where datname = :dbname"),
        {"dbname": db_name},
    ).scalar() is not None
    if not db_exists:
        conn.execute(text(f"create database {db_name} owner {db_user}"))
    else:
        conn.execute(text(f"alter database {db_name} owner to {db_user}"))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.environ["PROJECT_ROOT"], ".env"))
from app.db.database import Base, engine
from app.models.teaching_session import TeachingSession, ChatMessage
from app.models.user import UserProfile
from app.models.behavior import BehaviorLog
from app.models.exercise import ExerciseHistory
from app.models.progress import LearningProgress

Base.metadata.create_all(bind=engine)
tables = inspect(engine).get_table_names()
print("database_ready", ",".join(sorted(tables)))
PY
    )

    echo -e "${GREEN}✓ PostgreSQL 数据库已就绪${NC}"
}

start_backend() {
    echo -e "${YELLOW}[5/7] 启动后端服务...${NC}"
    : > "$BACKEND_LOG"

    screen -dmS "$BACKEND_SESSION" bash -lc \
        'cd "$BACKEND_DIR" && exec venv/bin/python -m uvicorn app.main:app --host "$BACKEND_HOST" --port "$BACKEND_PORT" --log-level info > "$BACKEND_LOG" 2>&1'
    echo "screen:$BACKEND_SESSION" >> "$PID_FILE"

    wait_for_url "$BACKEND_URL/health" "后端服务" 45
}

start_frontend() {
    echo -e "${YELLOW}[6/7] 启动前端服务...${NC}"
    require_path "$FRONTEND_DIR/node_modules"
    : > "$FRONTEND_LOG"

    screen -dmS "$FRONTEND_SESSION" bash -lc \
        'cd "$FRONTEND_DIR" && exec npm start -- --host "$FRONTEND_HOST" --port "$FRONTEND_PORT" > "$FRONTEND_LOG" 2>&1'
    echo "screen:$FRONTEND_SESSION" >> "$PID_FILE"

    wait_for_url "$FRONTEND_URL" "前端页面" 45
}

verify_app() {
    echo -e "${YELLOW}[7/7] 验证前端到后端的 API 链路...${NC}"
    wait_for_url "$PROXY_CHECK_URL" "前端代理 API" 45
}

open_browser() {
    echo -e "${YELLOW}打开浏览器...${NC}"
    if command -v open >/dev/null 2>&1; then
        open "$FRONTEND_URL" >/dev/null 2>&1 || true
    elif command -v xdg-open >/dev/null 2>&1; then
        xdg-open "$FRONTEND_URL" >/dev/null 2>&1 || true
    else
        echo -e "${YELLOW}未找到浏览器打开命令，请手动访问：$FRONTEND_URL${NC}"
    fi
}

require_command curl
require_command npm
require_command screen

stop_old_services
check_backend_env
ensure_postgres
ensure_database
start_backend
start_frontend
verify_app
open_browser

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  项目已启动并通过自检${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "前端界面：${CYAN}${FRONTEND_URL}${NC}"
echo -e "后端 API： ${CYAN}${BACKEND_URL}${NC}"
echo -e "API 文档： ${CYAN}${BACKEND_URL}/docs${NC}"
echo ""
echo "停止服务：./stop.sh"
echo "查看日志：tail -f backend.log frontend.log"
echo ""
