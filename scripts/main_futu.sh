#!/bin/bash
# 富途牛牛 AI 交易系统启动脚本

set -e

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo "  富途牛牛 AI 交易系统"
echo "=========================================="

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}错误: 未找到 Python3${NC}"
    exit 1
fi

# 检查futu-api
if ! python3 -c "import futu" &> /dev/null 2>&1; then
    echo -e "${YELLOW}警告: futu-api 未安装${NC}"
    echo "正在安装 futu-api..."
    pip install futu-api
fi

# 加载环境变量
if [ -f ".env" ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# 默认配置
CONFIG_FILE="${1:-configs/futu_config.json}"
MARKET="${MARKET:-HK}"
TRADE_ENV="${TRADE_ENV:-SIMULATE}"

echo ""
echo "配置信息:"
echo "  - 配置文件: $CONFIG_FILE"
echo "  - 市场: $MARKET"
echo "  - 交易环境: $TRADE_ENV"
echo ""

# 检查富途OpenD
FUTU_HOST="${FUTU_HOST:-127.0.0.1}"
FUTU_PORT="${FUTU_PORT:-11111}"

echo "检查富途OpenD连接 ($FUTU_HOST:$FUTU_PORT)..."
if nc -z "$FUTU_HOST" "$FUTU_PORT" 2>/dev/null; then
    echo -e "${GREEN}✓ 富途OpenD已连接${NC}"
else
    echo -e "${YELLOW}⚠ 富途OpenD未运行${NC}"
    echo "请先启动富途牛牛OpenD客户端"
    echo ""
    echo "下载地址: https://openapi.futunn.com/futu-api-doc/"
    echo ""
    read -p "是否继续? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo ""
echo "=========================================="
echo "  启动 MCP 服务"
echo "=========================================="

# 启动MCP服务（后台运行）
echo "正在启动 MCP 服务..."
python3 agent_tools/start_mcp_services_futu.py &
MCP_PID=$!

# 等待服务启动
echo "等待服务启动..."
sleep 5

# 检查MCP服务是否成功启动
if ! kill -0 $MCP_PID 2>/dev/null; then
    echo -e "${RED}MCP服务启动失败${NC}"
    exit 1
fi

echo -e "${GREEN}MCP服务已启动 (PID: $MCP_PID)${NC}"

# 清理函数
cleanup() {
    echo ""
    echo "正在停止服务..."
    kill $MCP_PID 2>/dev/null || true
    wait $MCP_PID 2>/dev/null || true
    echo "服务已停止"
}
trap cleanup EXIT

echo ""
echo "=========================================="
echo "  启动交易代理"
echo "=========================================="

# 运行交易程序
python3 main_futu.py "$CONFIG_FILE" --market "$MARKET" --env "$TRADE_ENV"

echo ""
echo "=========================================="
echo "  交易完成"
echo "=========================================="
