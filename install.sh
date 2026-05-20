#!/bin/bash

# AI智能教育课程平台 - 安装脚本 (Mac/Linux)
# 功能：检测环境、创建虚拟环境、安装依赖

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  AI智能教育课程平台 - 安装脚本${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 检查 Python 版本
echo -e "${YELLOW}[1/5] 检查 Python 环境...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}错误：未检测到 Python3${NC}"
    echo "请先安装 Python 3.10 或更高版本:"
    echo "  Mac: brew install python@3.10"
    echo "  Linux: sudo apt-get install python3.10"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 10 ]); then
    echo -e "${RED}错误：Python 版本 $PYTHON_VERSION 过低${NC}"
    echo "需要 Python 3.10 或更高版本"
    exit 1
fi

echo -e "${GREEN}✓ Python 版本: $PYTHON_VERSION${NC}"

# 检查 Node.js 版本
echo -e "${YELLOW}[2/5] 检查 Node.js 环境...${NC}"
if ! command -v node &> /dev/null; then
    echo -e "${RED}错误：未检测到 Node.js${NC}"
    echo "请先安装 Node.js 18 或更高版本:"
    echo "  https://nodejs.org/"
    exit 1
fi

NODE_VERSION=$(node --version | cut -d'v' -f2)
NODE_MAJOR=$(echo "$NODE_VERSION" | cut -d. -f1)

if [ "$NODE_MAJOR" -lt 18 ]; then
    echo -e "${RED}错误：Node.js 版本 $NODE_VERSION 过低${NC}"
    echo "需要 Node.js 18 或更高版本"
    exit 1
fi

echo -e "${GREEN}✓ Node.js 版本: $NODE_VERSION${NC}"

# 检查 npm
echo -e "${YELLOW}[3/5] 检查 npm...${NC}"
if ! command -v npm &> /dev/null; then
    echo -e "${RED}错误：未检测到 npm${NC}"
    exit 1
fi

NPM_VERSION=$(npm --version)
echo -e "${GREEN}✓ npm 版本: $NPM_VERSION${NC}"

# 创建 Python 虚拟环境
echo -e "${YELLOW}[4/5] 创建 Python 虚拟环境...${NC}"
if [ -d "$BACKEND_DIR/venv" ]; then
    echo -e "${YELLOW}虚拟环境已存在，跳过创建${NC}"
else
    cd "$BACKEND_DIR"
    python3 -m venv venv
    echo -e "${GREEN}✓ 虚拟环境创建成功${NC}"
fi

# 安装后端依赖
echo -e "${YELLOW}[5/5] 安装后端依赖...${NC}"
cd "$BACKEND_DIR"
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt --break-system-packages 2>/dev/null || pip install -r requirements.txt
echo -e "${GREEN}✓ 后端依赖安装完成${NC}"

# 安装前端依赖
echo -e "${YELLOW}     安装前端依赖...${NC}"
cd "$FRONTEND_DIR"
npm install
echo -e "${GREEN}✓ 前端依赖安装完成${NC}"

# 创建 .env 文件（如果不存在）
if [ ! -f "$PROJECT_ROOT/.env" ]; then
    echo -e "${YELLOW}     创建 .env 配置文件...${NC}"
    cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env"
    echo -e "${GREEN}✓ .env 文件已创建（请根据需要编辑配置）${NC}"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  安装完成！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "使用说明:"
echo "  1. 启动服务: ./start.sh"
echo "  2. 访问前端: http://localhost:5173"
echo "  3. 访问后端: http://localhost:8000"
echo "  4. API 文档: http://localhost:8000/docs"
echo ""
echo "可选配置:"
echo "  - 编辑 .env 文件配置 LLM API Key"
echo "  - 默认使用模拟模式，无需配置即可测试"
echo ""
