# 富途牛牛真实交易集成指南

本项目支持通过富途牛牛(Futu OpenD API)进行港股和美股的真实交易。

## 功能特点

- **港股交易**: 支持港股市场买卖操作
- **美股交易**: 支持美股市场买卖操作
- **实时行情**: 通过富途API获取实时股票价格
- **模拟/真实环境**: 支持模拟交易和真实交易切换
- **AI驱动决策**: 使用LLM进行交易分析和决策

## 前置条件

### 1. 安装富途OpenD

下载并安装富途OpenD客户端:
- 官方下载: https://openapi.futunn.com/futu-api-doc/

### 2. 安装Python依赖

```bash
pip install futu-api>=9.0.0
```

或者安装所有依赖:
```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

复制 `.env.example` 为 `.env` 并填写配置:

```bash
# 富途OpenD连接
FUTU_HOST=127.0.0.1
FUTU_PORT=11111

# 交易密码
FUTU_TRADE_PASSWORD=你的交易密码

# 交易环境: SIMULATE(模拟) 或 REAL(真实)
FUTU_TRADE_ENV=SIMULATE
```

## 快速开始

### 1. 启动富途OpenD

确保富途牛牛OpenD客户端已启动并登录。

### 2. 启动MCP服务

```bash
python agent_tools/start_mcp_services_futu.py
```

### 3. 运行交易系统

**港股交易 (模拟环境):**
```bash
python main_futu.py configs/futu_config.json --market HK --env SIMULATE
```

**美股交易 (模拟环境):**
```bash
python main_futu.py configs/futu_us_config.json --market US --env SIMULATE
```

**使用启动脚本:**
```bash
./scripts/main_futu.sh configs/futu_config.json
```

## 配置文件说明

### configs/futu_config.json (港股)

```json
{
    "agent_type": "BaseAgentFutu",
    "market": "HK",
    "trade_env": "SIMULATE",
    "models": [...],
    "futu_config": {
        "host": "127.0.0.1",
        "port": 11111,
        "trade_password": "",
        "trade_env": "SIMULATE"
    }
}
```

### configs/futu_us_config.json (美股)

同上，但 `market` 设置为 `"US"`。

## 可用工具

### 交易工具 (tool_futu_trade.py)

| 工具名 | 功能 |
|-------|------|
| `buy_futu` | 买入股票 |
| `sell_futu` | 卖出股票 |
| `get_futu_account_info` | 获取账户信息 |
| `get_futu_order_list` | 获取订单列表 |
| `cancel_futu_order` | 取消订单 |

### 行情工具 (tool_futu_price.py)

| 工具名 | 功能 |
|-------|------|
| `get_futu_realtime_quote` | 获取实时行情 |
| `get_futu_stock_price` | 获取股票价格 |
| `get_futu_kline` | 获取K线数据 |
| `get_futu_order_book` | 获取买卖盘 |
| `search_futu_stock` | 搜索股票 |
| `get_futu_market_state` | 获取市场状态 |

## 交易规则

### 港股
- 交易时间: 09:30-12:00, 13:00-16:00 (香港时间)
- 交易单位: 每手股数因股票而异
- T+0交易: 当天买入可当天卖出
- 无涨跌停限制

### 美股
- 交易时间: 09:30-16:00 (美东时间)
- 盘前/盘后交易可用
- 最小交易单位: 1股
- T+0交易

## 安全提示

1. **首次使用请使用模拟环境** (`FUTU_TRADE_ENV=SIMULATE`)
2. **真实交易前充分测试策略**
3. **妥善保管交易密码**
4. **设置合理的止损策略**

## 文件结构

```
AI-Trader/
├── agent/
│   └── base_agent_futu/
│       ├── __init__.py
│       └── base_agent_futu.py      # 富途交易Agent
├── agent_tools/
│   ├── tool_futu_trade.py          # 交易MCP服务
│   ├── tool_futu_price.py          # 行情MCP服务
│   └── start_mcp_services_futu.py  # 服务启动管理
├── configs/
│   ├── futu_config.json            # 港股配置
│   └── futu_us_config.json         # 美股配置
├── prompts/
│   └── agent_prompt_futu.py        # 提示词模块
├── scripts/
│   └── main_futu.sh                # 启动脚本
├── main_futu.py                    # 主程序
└── data/
    └── agent_data_futu/            # 交易数据存储
```

## 常见问题

### Q: 无法连接到富途OpenD?

确保:
1. OpenD客户端已启动
2. 端口配置正确 (默认11111)
3. 防火墙未阻止连接

### Q: 交易失败?

检查:
1. 账户资金是否充足
2. 交易密码是否正确
3. 是否在交易时间内
4. 股票代码格式是否正确

### Q: 如何切换到真实交易?

修改 `.env` 文件:
```bash
FUTU_TRADE_ENV=REAL
```

**警告**: 真实交易使用真实资金，请确保充分测试后再使用!
