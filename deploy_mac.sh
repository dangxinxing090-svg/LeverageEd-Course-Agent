#!/bin/bash
#
# AI智能教育课程平台 - Mac 一键部署脚本
# 用法: bash deploy_mac.sh
# 功能: 检查依赖、创建虚拟环境、安装依赖、配置数据库、启动服务
#

set -e

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

BACKEND_PORT=8000
FRONTEND_PORT=5173

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  AI智能教育课程平台 - Mac 部署脚本${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# ==================== 工具函数 ====================

fail() {
    echo -e "${RED}✗ $1${NC}"
    exit 1
}

info() {
    echo -e "${YELLOW}[INFO] $1${NC}"
}

success() {
    echo -e "${GREEN}✓ $1${NC}"
}

wait_for_url() {
    local url="$1" name="$2" max_wait="${3:-60}"
    for ((i = 1; i <= max_wait; i++)); do
        # 对 /health 端点使用 -f 跟随重定向，对其他端点允许 401/403 等状态码
        if [[ "$url" == */health ]]; then
            if curl -fsS "$url" >/dev/null 2>&1; then
                success "$name 可用"
                return 0
            fi
        else
            # 前端页面只要返回 HTTP 响应即可（即使是 401）
            if curl -sS "$url" >/dev/null 2>&1; then
                success "$name 可用"
                return 0
            fi
        fi
        sleep 1
    done
    fail "$name 启动超时"
}

# ==================== 步骤 1: 检查系统依赖 ====================
info "[1/8] 检查系统依赖..."

# 检查 Python 3
if ! command -v python3 >/dev/null 2>&1; then
    fail "未找到 python3，请先安装: brew install python"
fi
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
success "Python 版本: $PYTHON_VERSION"

# 检查 Node.js
if ! command -v node >/dev/null 2>&1; then
    fail "未找到 node，请先安装: brew install node"
fi
NODE_VERSION=$(node --version)
success "Node.js 版本: $NODE_VERSION"

# 检查 npm
if ! command -v npm >/dev/null 2>&1; then
    fail "未找到 npm"
fi

# 检查 PostgreSQL
if ! command -v psql >/dev/null 2>&1; then
    info "未找到 PostgreSQL，尝试安装..."
    if command -v brew >/dev/null 2>&1; then
        brew install postgresql@14
        brew services start postgresql@14
    else
        fail "请先安装 Homebrew: https://brew.sh"
    fi
fi

# 检查 PostgreSQL 是否运行
if pg_isready -h 127.0.0.1 -p 5432 >/dev/null 2>&1; then
    success "PostgreSQL 运行中"
else
    info "启动 PostgreSQL..."
    if command -v brew >/dev/null 2>&1; then
        brew services start postgresql@14 2>/dev/null || brew services start postgresql 2>/dev/null || true
    fi
    sleep 3
    if ! pg_isready -h 127.0.0.1 -p 5432 >/dev/null 2>&1; then
        fail "PostgreSQL 启动失败，请手动检查"
    fi
    success "PostgreSQL 已启动"
fi

# ==================== 步骤 2: 创建数据库和用户 ====================
info "[2/8] 配置 PostgreSQL 数据库..."

DB_NAME="education"
DB_USER="edu_user"
DB_PASS="edu123456"

# 创建用户（如果不存在）
psql -h 127.0.0.1 -U postgres -tc "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'" | grep -q 1 || \
    psql -h 127.0.0.1 -U postgres -c "CREATE USER $DB_USER WITH SUPERUSER PASSWORD '$DB_PASS';" 2>/dev/null || true

# 创建数据库（如果不存在）
psql -h 127.0.0.1 -U postgres -tc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" | grep -q 1 || \
    psql -h 127.0.0.1 -U postgres -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;" 2>/dev/null || true

# 授权
psql -h 127.0.0.1 -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;" 2>/dev/null || true

success "数据库配置完成"

# ==================== 步骤 3: 配置后端环境变量 ====================
info "[3/8] 配置后端环境..."

if [ ! -f "$PROJECT_ROOT/.env" ]; then
    cat > "$PROJECT_ROOT/.env" << EOF
DATABASE_URL=postgresql://$DB_USER:$DB_PASS@127.0.0.1:5432/$DB_NAME
POSTGRES_ADMIN_URL=postgresql://postgres@127.0.0.1:5432/postgres
EOF
    success "已创建 .env 文件"
else
    info ".env 文件已存在，跳过"
fi

# ==================== 步骤 4: 创建 Python 虚拟环境 ====================
info "[4/8] 创建 Python 虚拟环境..."

if [ -d "$BACKEND_DIR/venv" ]; then
    info "虚拟环境已存在，检查可用性..."
    if ! "$BACKEND_DIR/venv/bin/python" --version >/dev/null 2>&1; then
        info "虚拟环境损坏，重新创建..."
        rm -rf "$BACKEND_DIR/venv"
        python3 -m venv "$BACKEND_DIR/venv"
    fi
else
    python3 -m venv "$BACKEND_DIR/venv"
fi

success "虚拟环境就绪"

# ==================== 步骤 5: 安装后端依赖 ====================
info "[5/8] 安装后端依赖（可能需要几分钟）..."

"$BACKEND_DIR/venv/bin/pip" install --upgrade pip -q
"$BACKEND_DIR/venv/bin/pip" install -r "$BACKEND_DIR/requirements.txt" -q

success "后端依赖安装完成"

# ==================== 步骤 6: 初始化数据库表 ====================
info "[6/8] 初始化数据库表..."

cd "$BACKEND_DIR"
"$BACKEND_DIR/venv/bin/python" init_database.py 2>/dev/null || \
    "$BACKEND_DIR/venv/bin/python" -c "
import os
os.chdir('$BACKEND_DIR')
from app.db.database import Base, engine
Base.metadata.create_all(bind=engine)
print('数据库表初始化完成')
"

success "数据库表初始化完成"

# ==================== 步骤 7: 安装前端依赖 ====================
info "[7/8] 安装前端依赖（可能需要几分钟）..."

cd "$FRONTEND_DIR"
if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
    npm install --legacy-peer-deps
else
    info "前端依赖已安装，跳过"
fi

success "前端依赖安装完成"

# ==================== 步骤 8: 启动服务 ====================
info "[8/8] 启动服务..."

# 清理旧进程
pkill -f "uvicorn app.main:app" 2>/dev/null || true
pkill -f "vite" 2>/dev/null || true
sleep 1

# 启动后端
: > "$BACKEND_LOG"
cd "$BACKEND_DIR"
"$BACKEND_DIR/venv/bin/python" -m uvicorn app.main:app --host 127.0.0.1 --port $BACKEND_PORT > "$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!
echo $BACKEND_PID > "$PID_FILE"

wait_for_url "http://127.0.0.1:$BACKEND_PORT/health" "后端服务" 45

# 启动前端
: > "$FRONTEND_LOG"
cd "$FRONTEND_DIR"
npm start > "$FRONTEND_LOG" 2>&1 &
FRONTEND_PID=$!
echo $FRONTEND_PID >> "$PID_FILE"

wait_for_url "http://127.0.0.1:$FRONTEND_PORT" "前端页面" 45

# 打开浏览器
if command -v open >/dev/null 2>&1; then
    open "http://127.0.0.1:$FRONTEND_PORT/"
fi

# ==================== 完成 ====================
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  🎉 部署成功！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "  前端地址：${CYAN}http://127.0.0.1:$FRONTEND_PORT/${NC}"
echo -e "  后端 API：${CYAN}http://127.0.0.1:$BACKEND_PORT/docs${NC}"
echo ""
echo -e "${YELLOW}常用命令：${NC}"
echo "  停止服务：./stop.sh"
echo "  查看日志：tail -f backend.log frontend.log"
echo "  数据库：psql -U $DB_USER -d $DB_NAME"
echo ""
