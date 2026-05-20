#!/bin/bash

# AI智能教育课程平台 - 启动脚本 (Mac/Linux)
# 功能：并行启动后端和前端服务

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"

# PID 文件（用于停止服务）
PID_FILE="$PROJECT_ROOT/.service_pids"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  AI智能教育课程平台 - 启动脚本${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 检查虚拟环境是否存在
if [ ! -d "$BACKEND_DIR/venv" ]; then
    echo -e "${RED}错误：未检测到虚拟环境${NC}"
    echo "请先运行安装脚本: ./install.sh"
    exit 1
fi

# 加载环境变量
if [ -f "$PROJECT_ROOT/.env" ]; then
    echo -e "${YELLOW}加载环境变量...${NC}"
    set -a
    source "$PROJECT_ROOT/.env"
    set +a
fi

# 清理之前的 PID 文件
rm -f "$PID_FILE"

# 启动后端服务
echo -e "${YELLOW}[1/2] 启动后端服务...${NC}"
cd "$BACKEND_DIR"
source venv/bin/activate

# 设置默认端口
PORT=${PORT:-8000}
HOST=${HOST:-0.0.0.0}

# 后台启动后端
python -m uvicorn app.main:app --host "$HOST" --port "$PORT" --reload --log-level info > "$PROJECT_ROOT/backend.log" 2>&1 &
BACKEND_PID=$!
echo $BACKEND_PID >> "$PID_FILE"
echo -e "${GREEN}✓ 后端服务已启动 (PID: $BACKEND_PID)${NC}"
echo -e "${CYAN}  日志: backend.log${NC}"
echo -e "${CYAN}  地址: http://$HOST:$PORT${NC}"
echo ""

# 等待后端启动
echo -e "${YELLOW}等待后端服务就绪...${NC}"
for i in {1..30}; do
    if curl -s "http://$HOST:$PORT/health" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ 后端服务就绪${NC}"
        break
    fi
    sleep 1
    if [ $i -eq 30 ]; then
        echo -e "${YELLOW}警告：后端服务启动较慢，请检查 backend.log${NC}"
    fi
done
echo ""

# 启动前端服务
echo -e "${YELLOW}[2/2] 启动前端服务...${NC}"
cd "$FRONTEND_DIR"

# 后台启动前端
npm start > "$PROJECT_ROOT/frontend.log" 2>&1 &
FRONTEND_PID=$!
echo $FRONTEND_PID >> "$PID_FILE"
echo -e "${GREEN}✓ 前端服务已启动 (PID: $FRONTEND_PID)${NC}"
echo -e "${CYAN}  日志: frontend.log${NC}"
echo -e "${CYAN}  地址: http://localhost:5173${NC}"
echo ""

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  所有服务已启动！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "访问地址:"
echo -e "  ${CYAN}前端界面: http://localhost:5173${NC}"
echo -e "  ${CYAN}后端API:  http://$HOST:$PORT${NC}"
echo -e "  ${CYAN}API文档:  http://$HOST:$PORT/docs${NC}"
echo ""
echo "日志文件:"
echo -e "  ${CYAN}后端日志: backend.log${NC}"
echo -e "  ${CYAN}前端日志: frontend.log${NC}"
echo ""
echo "操作命令:"
echo "  停止服务: ./stop.sh"
echo "  查看日志: tail -f backend.log 或 tail -f frontend.log"
echo ""
echo -e "${YELLOW}按 Ctrl+C 停止所有服务${NC}"
echo ""

# 捕获 Ctrl+C 信号，优雅退出
cleanup() {
    echo ""
    echo -e "${YELLOW}正在停止服务...${NC}"
    ./stop.sh
    exit 0
}
trap cleanup INT

# 保持脚本运行，同时输出日志
tail -f "$PROJECT_ROOT/backend.log" "$PROJECT_ROOT/frontend.log" 2>/dev/null &
TAIL_PID=$!

# 等待前端或后端任一退出
wait $BACKEND_PID $FRONTEND_PID
cleanup
