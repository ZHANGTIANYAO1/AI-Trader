"""
富途牛牛真实交易工具 - Futu OpenD API Integration
支持港股(HK)和美股(US)真实交易

使用前需要:
1. 安装并运行富途OpenD客户端
2. 设置环境变量: FUTU_HOST, FUTU_PORT, FUTU_TRADE_PASSWORD, FUTU_TRADE_ENV
3. 确保已在富途牛牛APP中完成交易解锁
"""

import os
import sys
from typing import Any, Dict, Optional
from datetime import datetime
import json
import fcntl
from pathlib import Path

from fastmcp import FastMCP

# Add project root directory to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from tools.general_tools import get_config_value, write_config_value

# Futu API imports
try:
    from futu import OpenQuoteContext, OpenSecTradeContext
    from futu import TrdEnv, TrdSide, OrderType, TrdMarket
    from futu import RET_OK, RET_ERROR
    FUTU_AVAILABLE = True
except ImportError:
    FUTU_AVAILABLE = False
    print("警告: futu-api 未安装。请运行 pip install futu-api")


mcp = FastMCP("FutuTradeTools")


# 全局连接管理
_quote_ctx: Optional[Any] = None
_trade_ctx_hk: Optional[Any] = None
_trade_ctx_us: Optional[Any] = None


def get_futu_config() -> Dict[str, Any]:
    """获取富途API配置"""
    return {
        "host": get_config_value("FUTU_HOST", "127.0.0.1"),
        "port": int(get_config_value("FUTU_PORT", "11111")),
        "trade_password": get_config_value("FUTU_TRADE_PASSWORD", ""),
        "trade_env": get_config_value("FUTU_TRADE_ENV", "SIMULATE"),  # SIMULATE 或 REAL
    }


def get_trade_env():
    """获取交易环境"""
    if not FUTU_AVAILABLE:
        return None
    config = get_futu_config()
    if config["trade_env"].upper() == "REAL":
        return TrdEnv.REAL
    return TrdEnv.SIMULATE


def get_quote_context():
    """获取行情连接"""
    global _quote_ctx
    if not FUTU_AVAILABLE:
        return None
    if _quote_ctx is None:
        config = get_futu_config()
        _quote_ctx = OpenQuoteContext(host=config["host"], port=config["port"])
    return _quote_ctx


def get_trade_context(market: str):
    """获取交易连接

    Args:
        market: 'HK' 港股 或 'US' 美股
    """
    global _trade_ctx_hk, _trade_ctx_us
    if not FUTU_AVAILABLE:
        return None

    config = get_futu_config()
    trade_env = get_trade_env()

    if market.upper() == "HK":
        if _trade_ctx_hk is None:
            _trade_ctx_hk = OpenSecTradeContext(
                host=config["host"],
                port=config["port"],
                filter_trdmarket=TrdMarket.HK
            )
            # 解锁交易
            if config["trade_password"]:
                ret, data = _trade_ctx_hk.unlock_trade(config["trade_password"])
                if ret != RET_OK:
                    print(f"港股交易解锁失败: {data}")
        return _trade_ctx_hk
    else:  # US
        if _trade_ctx_us is None:
            _trade_ctx_us = OpenSecTradeContext(
                host=config["host"],
                port=config["port"],
                filter_trdmarket=TrdMarket.US
            )
            # 解锁交易
            if config["trade_password"]:
                ret, data = _trade_ctx_us.unlock_trade(config["trade_password"])
                if ret != RET_OK:
                    print(f"美股交易解锁失败: {data}")
        return _trade_ctx_us


def convert_symbol_to_futu(symbol: str, market: str) -> str:
    """转换股票代码为富途格式

    Examples:
        HK市场: 00700 -> HK.00700
        US市场: AAPL -> US.AAPL
    """
    market = market.upper()
    if market == "HK":
        # 确保是5位数字
        code = symbol.lstrip("0").zfill(5)
        return f"HK.{code}"
    else:  # US
        return f"US.{symbol.upper()}"


def _position_lock(signature: str):
    """Context manager for file-based lock to serialize position updates per signature."""
    class _Lock:
        def __init__(self, name: str):
            log_path = get_config_value("LOG_PATH", "./data/agent_data_futu")
            if os.path.isabs(log_path):
                base_dir = Path(log_path) / name
            else:
                if log_path.startswith("./data/"):
                    log_rel = log_path[7:]
                else:
                    log_rel = log_path
                base_dir = Path(project_root) / "data" / log_rel / name
            base_dir.mkdir(parents=True, exist_ok=True)
            self.lock_path = base_dir / ".position.lock"
            self._fh = open(self.lock_path, "a+")

        def __enter__(self):
            fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX)
            return self

        def __exit__(self, exc_type, exc, tb):
            try:
                fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
            finally:
                self._fh.close()

    return _Lock(signature)


def record_trade_to_file(signature: str, action: str, symbol: str, amount: int,
                         price: float, market: str, order_id: str, positions: Dict):
    """记录交易到本地文件"""
    log_path = get_config_value("LOG_PATH", "./data/agent_data_futu")
    if log_path.startswith("./data/"):
        log_path = log_path[7:]

    position_dir = Path(project_root) / "data" / log_path / signature / "position"
    position_dir.mkdir(parents=True, exist_ok=True)
    position_file = position_dir / "position.jsonl"

    # 读取当前最大ID
    current_id = 0
    if position_file.exists():
        with open(position_file, "r") as f:
            for line in f:
                if line.strip():
                    try:
                        record = json.loads(line)
                        current_id = max(current_id, record.get("id", 0))
                    except:
                        pass

    # 写入新记录
    record = {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "id": current_id + 1,
        "this_action": {
            "action": action,
            "symbol": symbol,
            "amount": amount,
            "price": price,
            "market": market,
            "order_id": order_id,
        },
        "positions": positions,
    }

    with open(position_file, "a") as f:
        f.write(json.dumps(record) + "\n")

    print(f"交易记录已保存: {record}")


@mcp.tool()
def get_futu_account_info(market: str = "HK") -> Dict[str, Any]:
    """
    获取富途账户信息

    Args:
        market: 市场类型 - "HK" 港股 或 "US" 美股

    Returns:
        账户信息字典，包含总资产、现金、持仓等
    """
    if not FUTU_AVAILABLE:
        return {"error": "futu-api 未安装，请运行 pip install futu-api"}

    trade_ctx = get_trade_context(market)
    if trade_ctx is None:
        return {"error": "无法连接到富途OpenD"}

    trade_env = get_trade_env()

    # 获取账户列表
    ret, data = trade_ctx.get_acc_list()
    if ret != RET_OK:
        return {"error": f"获取账户列表失败: {data}"}

    # 获取资金信息
    ret, funds = trade_ctx.accinfo_query(trd_env=trade_env)
    if ret != RET_OK:
        return {"error": f"获取资金信息失败: {funds}"}

    # 获取持仓
    ret, positions = trade_ctx.position_list_query(trd_env=trade_env)
    if ret != RET_OK:
        return {"error": f"获取持仓信息失败: {positions}"}

    # 格式化返回
    funds_dict = funds.to_dict('records')[0] if len(funds) > 0 else {}
    positions_list = positions.to_dict('records') if len(positions) > 0 else []

    return {
        "market": market,
        "trade_env": "REAL" if trade_env == TrdEnv.REAL else "SIMULATE",
        "funds": {
            "total_assets": funds_dict.get("total_assets", 0),
            "cash": funds_dict.get("cash", 0),
            "market_val": funds_dict.get("market_val", 0),
            "frozen_cash": funds_dict.get("frozen_cash", 0),
            "available_funds": funds_dict.get("avl_withdrawal_cash", 0),
        },
        "positions": [
            {
                "code": p.get("code", ""),
                "stock_name": p.get("stock_name", ""),
                "qty": p.get("qty", 0),
                "can_sell_qty": p.get("can_sell_qty", 0),
                "cost_price": p.get("cost_price", 0),
                "market_val": p.get("market_val", 0),
                "pl_ratio": p.get("pl_ratio", 0),
            }
            for p in positions_list
        ],
    }


@mcp.tool()
def buy_futu(symbol: str, amount: int, market: str = "HK", order_type: str = "MARKET") -> Dict[str, Any]:
    """
    富途真实买入股票

    Args:
        symbol: 股票代码
                港股: 5位数字，如 "00700" (腾讯)
                美股: 股票代码，如 "AAPL"
        amount: 买入数量
                港股: 必须是一手的倍数 (不同股票手数不同)
                美股: 最小1股
        market: 市场 - "HK" 港股 或 "US" 美股
        order_type: 订单类型 - "MARKET" 市价单 或 "LIMIT" 限价单

    Returns:
        交易结果字典
    """
    if not FUTU_AVAILABLE:
        return {"error": "futu-api 未安装，请运行 pip install futu-api"}

    signature = get_config_value("SIGNATURE")
    if signature is None:
        return {"error": "SIGNATURE 环境变量未设置"}

    # 参数验证
    try:
        amount = int(amount)
    except ValueError:
        return {"error": f"无效的数量格式: {amount}"}

    if amount <= 0:
        return {"error": f"数量必须为正数: {amount}"}

    # 转换股票代码
    futu_symbol = convert_symbol_to_futu(symbol, market)

    # 获取交易连接
    trade_ctx = get_trade_context(market)
    if trade_ctx is None:
        return {"error": "无法连接到富途OpenD"}

    trade_env = get_trade_env()

    # 获取当前价格
    quote_ctx = get_quote_context()
    ret, quote_data = quote_ctx.get_market_snapshot([futu_symbol])
    if ret != RET_OK:
        return {"error": f"获取行情失败: {quote_data}"}

    current_price = quote_data.iloc[0]['last_price'] if len(quote_data) > 0 else 0

    # 确定订单类型
    if order_type.upper() == "LIMIT":
        futu_order_type = OrderType.NORMAL
        price = current_price
    else:
        futu_order_type = OrderType.MARKET
        price = 0  # 市价单不需要价格

    with _position_lock(signature):
        # 下单
        ret, data = trade_ctx.place_order(
            price=price,
            qty=amount,
            code=futu_symbol,
            trd_side=TrdSide.BUY,
            order_type=futu_order_type,
            trd_env=trade_env,
        )

        if ret != RET_OK:
            return {
                "error": f"下单失败: {data}",
                "symbol": futu_symbol,
                "amount": amount,
                "market": market,
            }

        order_info = data.to_dict('records')[0] if len(data) > 0 else {}
        order_id = order_info.get("order_id", "")

        # 获取更新后的持仓
        ret, positions = trade_ctx.position_list_query(trd_env=trade_env)
        positions_dict = {}
        if ret == RET_OK and len(positions) > 0:
            for _, row in positions.iterrows():
                positions_dict[row['code']] = row['qty']

        # 获取现金
        ret, funds = trade_ctx.accinfo_query(trd_env=trade_env)
        if ret == RET_OK and len(funds) > 0:
            positions_dict["CASH"] = funds.iloc[0]['cash']

        # 记录交易
        record_trade_to_file(
            signature=signature,
            action="buy",
            symbol=futu_symbol,
            amount=amount,
            price=current_price,
            market=market,
            order_id=str(order_id),
            positions=positions_dict,
        )

        write_config_value("IF_TRADE", True)

        return {
            "success": True,
            "action": "buy",
            "symbol": futu_symbol,
            "amount": amount,
            "price": current_price,
            "order_id": order_id,
            "order_status": order_info.get("order_status", ""),
            "market": market,
            "trade_env": "REAL" if trade_env == TrdEnv.REAL else "SIMULATE",
            "positions": positions_dict,
        }


@mcp.tool()
def sell_futu(symbol: str, amount: int, market: str = "HK", order_type: str = "MARKET") -> Dict[str, Any]:
    """
    富途真实卖出股票

    Args:
        symbol: 股票代码
                港股: 5位数字，如 "00700" (腾讯)
                美股: 股票代码，如 "AAPL"
        amount: 卖出数量
        market: 市场 - "HK" 港股 或 "US" 美股
        order_type: 订单类型 - "MARKET" 市价单 或 "LIMIT" 限价单

    Returns:
        交易结果字典
    """
    if not FUTU_AVAILABLE:
        return {"error": "futu-api 未安装，请运行 pip install futu-api"}

    signature = get_config_value("SIGNATURE")
    if signature is None:
        return {"error": "SIGNATURE 环境变量未设置"}

    # 参数验证
    try:
        amount = int(amount)
    except ValueError:
        return {"error": f"无效的数量格式: {amount}"}

    if amount <= 0:
        return {"error": f"数量必须为正数: {amount}"}

    # 转换股票代码
    futu_symbol = convert_symbol_to_futu(symbol, market)

    # 获取交易连接
    trade_ctx = get_trade_context(market)
    if trade_ctx is None:
        return {"error": "无法连接到富途OpenD"}

    trade_env = get_trade_env()

    # 检查持仓
    ret, positions = trade_ctx.position_list_query(trd_env=trade_env)
    if ret != RET_OK:
        return {"error": f"获取持仓失败: {positions}"}

    # 查找目标股票持仓
    position_qty = 0
    can_sell_qty = 0
    for _, row in positions.iterrows():
        if row['code'] == futu_symbol:
            position_qty = row['qty']
            can_sell_qty = row['can_sell_qty']
            break

    if position_qty == 0:
        return {
            "error": f"没有持有 {futu_symbol}",
            "symbol": futu_symbol,
            "market": market,
        }

    if can_sell_qty < amount:
        return {
            "error": f"可卖数量不足，持有 {position_qty} 股，可卖 {can_sell_qty} 股",
            "symbol": futu_symbol,
            "position_qty": position_qty,
            "can_sell_qty": can_sell_qty,
            "want_to_sell": amount,
            "market": market,
        }

    # 获取当前价格
    quote_ctx = get_quote_context()
    ret, quote_data = quote_ctx.get_market_snapshot([futu_symbol])
    if ret != RET_OK:
        return {"error": f"获取行情失败: {quote_data}"}

    current_price = quote_data.iloc[0]['last_price'] if len(quote_data) > 0 else 0

    # 确定订单类型
    if order_type.upper() == "LIMIT":
        futu_order_type = OrderType.NORMAL
        price = current_price
    else:
        futu_order_type = OrderType.MARKET
        price = 0

    with _position_lock(signature):
        # 下单卖出
        ret, data = trade_ctx.place_order(
            price=price,
            qty=amount,
            code=futu_symbol,
            trd_side=TrdSide.SELL,
            order_type=futu_order_type,
            trd_env=trade_env,
        )

        if ret != RET_OK:
            return {
                "error": f"下单失败: {data}",
                "symbol": futu_symbol,
                "amount": amount,
                "market": market,
            }

        order_info = data.to_dict('records')[0] if len(data) > 0 else {}
        order_id = order_info.get("order_id", "")

        # 获取更新后的持仓
        ret, positions = trade_ctx.position_list_query(trd_env=trade_env)
        positions_dict = {}
        if ret == RET_OK and len(positions) > 0:
            for _, row in positions.iterrows():
                positions_dict[row['code']] = row['qty']

        # 获取现金
        ret, funds = trade_ctx.accinfo_query(trd_env=trade_env)
        if ret == RET_OK and len(funds) > 0:
            positions_dict["CASH"] = funds.iloc[0]['cash']

        # 记录交易
        record_trade_to_file(
            signature=signature,
            action="sell",
            symbol=futu_symbol,
            amount=amount,
            price=current_price,
            market=market,
            order_id=str(order_id),
            positions=positions_dict,
        )

        write_config_value("IF_TRADE", True)

        return {
            "success": True,
            "action": "sell",
            "symbol": futu_symbol,
            "amount": amount,
            "price": current_price,
            "order_id": order_id,
            "order_status": order_info.get("order_status", ""),
            "market": market,
            "trade_env": "REAL" if trade_env == TrdEnv.REAL else "SIMULATE",
            "positions": positions_dict,
        }


@mcp.tool()
def get_futu_order_list(market: str = "HK") -> Dict[str, Any]:
    """
    获取当日订单列表

    Args:
        market: 市场 - "HK" 港股 或 "US" 美股

    Returns:
        订单列表
    """
    if not FUTU_AVAILABLE:
        return {"error": "futu-api 未安装，请运行 pip install futu-api"}

    trade_ctx = get_trade_context(market)
    if trade_ctx is None:
        return {"error": "无法连接到富途OpenD"}

    trade_env = get_trade_env()

    ret, data = trade_ctx.order_list_query(trd_env=trade_env)
    if ret != RET_OK:
        return {"error": f"获取订单列表失败: {data}"}

    orders = data.to_dict('records') if len(data) > 0 else []

    return {
        "market": market,
        "trade_env": "REAL" if trade_env == TrdEnv.REAL else "SIMULATE",
        "orders": [
            {
                "order_id": o.get("order_id", ""),
                "code": o.get("code", ""),
                "stock_name": o.get("stock_name", ""),
                "trd_side": o.get("trd_side", ""),
                "order_type": o.get("order_type", ""),
                "qty": o.get("qty", 0),
                "price": o.get("price", 0),
                "dealt_qty": o.get("dealt_qty", 0),
                "dealt_avg_price": o.get("dealt_avg_price", 0),
                "order_status": o.get("order_status", ""),
                "create_time": o.get("create_time", ""),
            }
            for o in orders
        ],
    }


@mcp.tool()
def cancel_futu_order(order_id: str, market: str = "HK") -> Dict[str, Any]:
    """
    取消订单

    Args:
        order_id: 订单ID
        market: 市场 - "HK" 港股 或 "US" 美股

    Returns:
        取消结果
    """
    if not FUTU_AVAILABLE:
        return {"error": "futu-api 未安装，请运行 pip install futu-api"}

    trade_ctx = get_trade_context(market)
    if trade_ctx is None:
        return {"error": "无法连接到富途OpenD"}

    trade_env = get_trade_env()

    ret, data = trade_ctx.modify_order(
        modify_order_op=2,  # CANCEL
        order_id=order_id,
        qty=0,
        price=0,
        trd_env=trade_env,
    )

    if ret != RET_OK:
        return {"error": f"取消订单失败: {data}"}

    return {
        "success": True,
        "order_id": order_id,
        "message": "订单已取消",
    }


def cleanup():
    """清理连接"""
    global _quote_ctx, _trade_ctx_hk, _trade_ctx_us
    if _quote_ctx:
        _quote_ctx.close()
        _quote_ctx = None
    if _trade_ctx_hk:
        _trade_ctx_hk.close()
        _trade_ctx_hk = None
    if _trade_ctx_us:
        _trade_ctx_us.close()
        _trade_ctx_us = None


if __name__ == "__main__":
    import atexit
    atexit.register(cleanup)

    port = int(os.getenv("FUTU_TRADE_HTTP_PORT", "8006"))
    print(f"启动富途交易服务 on port {port}")
    print(f"交易环境: {get_futu_config()['trade_env']}")
    mcp.run(transport="streamable-http", port=port)
