#!/bin/bash
# 项目服务启动脚本
# 自动检查并启动PostgreSQL、后端API、前端服务

set -e

echo "=========================================="
echo "AI智能教育课程平台 - 服务启动脚本"
echo "=========================================="

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# PostgreSQL配置
PG_HOME="/usr/local/pgsql"
PG_DATA="$PG_HOME/data"
PG_LOG="$PG_HOME/logfile"

# 检查PostgreSQL状态
check_postgres() {
    export PATH=$PG_HOME/bin:$PATH
    if pg_isready -h 127.0.0.1 -p 5432 > /dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# 启动PostgreSQL
start_postgres() {
    echo -e "${YELLOW}检查PostgreSQL...${NC}"
    if check_postgres; then
        echo -e "${GREEN}PostgreSQL 已运行${NC}"
        return 0
    fi
    
    echo -e "${YELLOW}启动PostgreSQL...${NC}"
    su - postgres -c "export PATH=$PG_HOME/bin:\$PATH; pg_ctl -D $PG_DATA start -l $PG_LOG" 2>&1 | grep -v "Permission denied" || true
    
    # 等待启动
    for i in {1..10}; do
        if check_postgres; then
            echo -e "${GREEN}PostgreSQL 启动成功${NC}"
            return 0
        fi
        sleep 1
    done
    
    echo -e "${RED}PostgreSQL 启动失败${NC}"
    return 1
}

# 检查后端状态
check_backend() {
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# 启动后端
start_backend() {
    echo -e "${YELLOW}检查后端API...${NC}"
    if check_backend; then
        echo -e "${GREEN}后端API 已运行${NC}"
        return 0
    fi
    
    echo -e "${YELLOW}启动后端API...${NC}"
    cd /sessions/6a1177758b0ed9aae363c1e4/workspace/backend
    source venv_new/bin/activate
    nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/backend.log 2>&1 &
    echo $! > /tmp/backend.pid
    
    # 等待启动
    for i in {1..10}; do
        if check_backend; then
            echo -e "${GREEN}后端API 启动成功 (PID: $(cat /tmp/backend.pid))${NC}"
            return 0
        fi
        sleep 1
    done
    
    echo -e "${RED}后端API 启动失败${NC}"
    return 1
}

# 检查前端状态
check_frontend() {
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:5173 | grep -q "200"; then
        return 0
    else
        return 1
    fi
}

# 启动前端
start_frontend() {
    echo -e "${YELLOW}检查前端服务...${NC}"
    if check_frontend; then
        echo -e "${GREEN}前端服务 已运行${NC}"
        return 0
    fi
    
    echo -e "${YELLOW}启动前端服务...${NC}"
    cd /sessions/6a1177758b0ed9aae363c1e4/workspace/frontend
    nohup npm start -- --host 0.0.0.0 --port 5173 > /tmp/frontend.log 2>&1 &
    echo $! > /tmp/frontend.pid
    
    # 等待启动
    for i in {1..15}; do
        if check_frontend; then
            echo -e "${GREEN}前端服务 启动成功 (PID: $(cat /tmp/frontend.pid))${NC}"
            return 0
        fi
        sleep 1
    done
    
    echo -e "${RED}前端服务 启动失败${NC}"
    return 1
}

# 显示状态
show_status() {
    echo ""
    echo "=========================================="
    echo "服务状态"
    echo "=========================================="
    
    if check_postgres; then
        echo -e "PostgreSQL: ${GREEN}运行中${NC} (localhost:5432)"
    else
        echo -e "PostgreSQL: ${RED}未运行${NC}"
    fi
    
    if check_backend; then
        echo -e "后端API:    ${GREEN}运行中${NC} (localhost:8000)"
    else
        echo -e "后端API:    ${RED}未运行${NC}"
    fi
    
    if check_frontend; then
        echo -e "前端服务:   ${GREEN}运行中${NC} (localhost:5173)"
    else
        echo -e "前端服务:   ${RED}未运行${NC}"
    fi
    
    echo ""
    echo "访问地址: http://localhost:5173"
    echo "=========================================="
}

# 主流程
main() {
    # 启动PostgreSQL
    if ! start_postgres; then
        echo -e "${RED}PostgreSQL启动失败，退出${NC}"
        exit 1
    fi
    
    # 启动后端
    if ! start_backend; then
        echo -e "${RED}后端API启动失败，退出${NC}"
        exit 1
    fi
    
    # 启动前端
    if ! start_frontend; then
        echo -e "${RED}前端服务启动失败，退出${NC}"
        exit 1
    fi
    
    # 显示状态
    show_status
    
    echo ""
    echo -e "${GREEN}所有服务启动成功！${NC}"
}

# 执行主流程
main
