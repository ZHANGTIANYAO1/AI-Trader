"""
富途牛牛实时行情工具 - Futu OpenD API Quote Integration
支持港股(HK)和美股(US)实时行情获取

使用前需要:
1. 安装并运行富途OpenD客户端
2. 设置环境变量: FUTU_HOST, FUTU_PORT
"""

import os
import sys
from typing import Any, Dict, List, Optional
from datetime import datetime
import json

from fastmcp import FastMCP

# Add project root directory to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from tools.general_tools import get_config_value

# Futu API imports
try:
    from futu import OpenQuoteContext, SubType, KLType, KL_FIELD
    from futu import RET_OK, RET_ERROR
    FUTU_AVAILABLE = True
except ImportError:
    FUTU_AVAILABLE = False
    print("警告: futu-api 未安装。请运行 pip install futu-api")


mcp = FastMCP("FutuPriceTools")


# 全局连接管理
_quote_ctx: Optional[Any] = None


def get_futu_config() -> Dict[str, Any]:
    """获取富途API配置"""
    return {
        "host": get_config_value("FUTU_HOST", "127.0.0.1"),
        "port": int(get_config_value("FUTU_PORT", "11111")),
    }


def get_quote_context():
    """获取行情连接"""
    global _quote_ctx
    if not FUTU_AVAILABLE:
        return None
    if _quote_ctx is None:
        config = get_futu_config()
        _quote_ctx = OpenQuoteContext(host=config["host"], port=config["port"])
    return _quote_ctx


def convert_symbol_to_futu(symbol: str, market: str) -> str:
    """转换股票代码为富途格式"""
    market = market.upper()
    if market == "HK":
        code = symbol.lstrip("0").zfill(5)
        return f"HK.{code}"
    else:
        return f"US.{symbol.upper()}"


def convert_symbols_to_futu(symbols: List[str], market: str) -> List[str]:
    """批量转换股票代码"""
    return [convert_symbol_to_futu(s, market) for s in symbols]


@mcp.tool()
def get_futu_realtime_quote(symbols: List[str], market: str = "HK") -> Dict[str, Any]:
    """
    获取实时行情报价

    Args:
        symbols: 股票代码列表
                 港股: ["00700", "09988"]
                 美股: ["AAPL", "NVDA"]
        market: 市场 - "HK" 港股 或 "US" 美股

    Returns:
        实时行情数据
    """
    if not FUTU_AVAILABLE:
        return {"error": "futu-api 未安装，请运行 pip install futu-api"}

    quote_ctx = get_quote_context()
    if quote_ctx is None:
        return {"error": "无法连接到富途OpenD"}

    futu_symbols = convert_symbols_to_futu(symbols, market)

    # 获取快照行情
    ret, data = quote_ctx.get_market_snapshot(futu_symbols)
    if ret != RET_OK:
        return {"error": f"获取行情失败: {data}"}

    quotes = []
    for _, row in data.iterrows():
        quotes.append({
            "code": row.get("code", ""),
            "name": row.get("name", ""),
            "last_price": row.get("last_price", 0),
            "open_price": row.get("open_price", 0),
            "high_price": row.get("high_price", 0),
            "low_price": row.get("low_price", 0),
            "prev_close_price": row.get("prev_close_price", 0),
            "volume": row.get("volume", 0),
            "turnover": row.get("turnover", 0),
            "turnover_rate": row.get("turnover_rate", 0),
            "amplitude": row.get("amplitude", 0),
            "change_rate": row.get("update_time", ""),
            "update_time": row.get("update_time", ""),
        })

    return {
        "market": market,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "quotes": quotes,
    }


@mcp.tool()
def get_futu_stock_price(symbol: str, market: str = "HK") -> Dict[str, Any]:
    """
    获取单只股票的当前价格

    Args:
        symbol: 股票代码
        market: 市场 - "HK" 港股 或 "US" 美股

    Returns:
        价格信息
    """
    if not FUTU_AVAILABLE:
        return {"error": "futu-api 未安装，请运行 pip install futu-api"}

    quote_ctx = get_quote_context()
    if quote_ctx is None:
        return {"error": "无法连接到富途OpenD"}

    futu_symbol = convert_symbol_to_futu(symbol, market)

    ret, data = quote_ctx.get_market_snapshot([futu_symbol])
    if ret != RET_OK:
        return {"error": f"获取行情失败: {data}"}

    if len(data) == 0:
        return {"error": f"未找到股票: {futu_symbol}"}

    row = data.iloc[0]
    return {
        "code": row.get("code", ""),
        "name": row.get("name", ""),
        "last_price": row.get("last_price", 0),
        "open_price": row.get("open_price", 0),
        "high_price": row.get("high_price", 0),
        "low_price": row.get("low_price", 0),
        "prev_close_price": row.get("prev_close_price", 0),
        "change_rate": round((row.get("last_price", 0) - row.get("prev_close_price", 0)) / row.get("prev_close_price", 1) * 100, 2) if row.get("prev_close_price", 0) != 0 else 0,
        "volume": row.get("volume", 0),
        "turnover": row.get("turnover", 0),
        "market": market,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


@mcp.tool()
def get_futu_kline(symbol: str, market: str = "HK", kl_type: str = "DAY", count: int = 30) -> Dict[str, Any]:
    """
    获取K线数据

    Args:
        symbol: 股票代码
        market: 市场 - "HK" 港股 或 "US" 美股
        kl_type: K线类型 - "DAY" 日K, "WEEK" 周K, "MONTH" 月K, "MIN_60" 60分钟
        count: 获取数量

    Returns:
        K线数据
    """
    if not FUTU_AVAILABLE:
        return {"error": "futu-api 未安装，请运行 pip install futu-api"}

    quote_ctx = get_quote_context()
    if quote_ctx is None:
        return {"error": "无法连接到富途OpenD"}

    futu_symbol = convert_symbol_to_futu(symbol, market)

    # 转换K线类型
    kl_type_map = {
        "DAY": KLType.K_DAY,
        "WEEK": KLType.K_WEEK,
        "MONTH": KLType.K_MON,
        "MIN_60": KLType.K_60M,
        "MIN_30": KLType.K_30M,
        "MIN_15": KLType.K_15M,
        "MIN_5": KLType.K_5M,
        "MIN_1": KLType.K_1M,
    }
    kl = kl_type_map.get(kl_type.upper(), KLType.K_DAY)

    ret, data, _ = quote_ctx.request_history_kline(
        futu_symbol,
        ktype=kl,
        max_count=count,
    )

    if ret != RET_OK:
        return {"error": f"获取K线失败: {data}"}

    klines = []
    for _, row in data.iterrows():
        klines.append({
            "time_key": row.get("time_key", ""),
            "open": row.get("open", 0),
            "high": row.get("high", 0),
            "low": row.get("low", 0),
            "close": row.get("close", 0),
            "volume": row.get("volume", 0),
            "turnover": row.get("turnover", 0),
            "change_rate": row.get("change_rate", 0),
        })

    return {
        "code": futu_symbol,
        "market": market,
        "kl_type": kl_type,
        "klines": klines,
    }


@mcp.tool()
def get_futu_order_book(symbol: str, market: str = "HK") -> Dict[str, Any]:
    """
    获取实时买卖盘（Level 2行情）

    Args:
        symbol: 股票代码
        market: 市场 - "HK" 港股 或 "US" 美股

    Returns:
        买卖盘数据
    """
    if not FUTU_AVAILABLE:
        return {"error": "futu-api 未安装，请运行 pip install futu-api"}

    quote_ctx = get_quote_context()
    if quote_ctx is None:
        return {"error": "无法连接到富途OpenD"}

    futu_symbol = convert_symbol_to_futu(symbol, market)

    ret, data = quote_ctx.get_order_book(futu_symbol, num=10)
    if ret != RET_OK:
        return {"error": f"获取买卖盘失败: {data}"}

    return {
        "code": futu_symbol,
        "market": market,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "bid": [
            {"price": b[0], "volume": b[1], "order_num": b[2]}
            for b in data.get("Bid", [])
        ],
        "ask": [
            {"price": a[0], "volume": a[1], "order_num": a[2]}
            for a in data.get("Ask", [])
        ],
    }


@mcp.tool()
def search_futu_stock(keyword: str, market: str = "HK") -> Dict[str, Any]:
    """
    搜索股票

    Args:
        keyword: 搜索关键词（股票代码或名称）
        market: 市场 - "HK" 港股, "US" 美股, "ALL" 全部

    Returns:
        搜索结果
    """
    if not FUTU_AVAILABLE:
        return {"error": "futu-api 未安装，请运行 pip install futu-api"}

    quote_ctx = get_quote_context()
    if quote_ctx is None:
        return {"error": "无法连接到富途OpenD"}

    # 市场映射
    from futu import SecurityType
    market_map = {
        "HK": "HK",
        "US": "US",
        "ALL": None,
    }
    mkt = market_map.get(market.upper(), "HK")

    ret, data = quote_ctx.get_stock_basicinfo(mkt, SecurityType.STOCK)
    if ret != RET_OK:
        return {"error": f"搜索失败: {data}"}

    # 过滤匹配的股票
    results = []
    keyword_upper = keyword.upper()
    for _, row in data.iterrows():
        code = row.get("code", "")
        name = row.get("name", "")
        if keyword_upper in code.upper() or keyword_upper in name.upper():
            results.append({
                "code": code,
                "name": name,
                "lot_size": row.get("lot_size", 0),
                "stock_type": row.get("stock_type", ""),
            })
            if len(results) >= 20:  # 限制结果数量
                break

    return {
        "keyword": keyword,
        "market": market,
        "count": len(results),
        "results": results,
    }


@mcp.tool()
def get_futu_market_state(market: str = "HK") -> Dict[str, Any]:
    """
    获取市场状态（是否开盘）

    Args:
        market: 市场 - "HK" 港股 或 "US" 美股

    Returns:
        市场状态信息
    """
    if not FUTU_AVAILABLE:
        return {"error": "futu-api 未安装，请运行 pip install futu-api"}

    quote_ctx = get_quote_context()
    if quote_ctx is None:
        return {"error": "无法连接到富途OpenD"}

    from futu import Market

    market_map = {
        "HK": Market.HK,
        "US": Market.US,
    }
    mkt = market_map.get(market.upper(), Market.HK)

    ret, data = quote_ctx.get_global_state()
    if ret != RET_OK:
        return {"error": f"获取市场状态失败: {data}"}

    # 解析市场状态
    market_state = data.get("market_" + market.lower(), "UNKNOWN")

    return {
        "market": market,
        "state": market_state,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "raw_data": data,
    }


@mcp.tool()
def get_futu_stock_list(market: str = "HK", stock_type: str = "STOCK") -> Dict[str, Any]:
    """
    获取股票列表

    Args:
        market: 市场 - "HK" 港股 或 "US" 美股
        stock_type: 证券类型 - "STOCK" 股票, "ETF" ETF

    Returns:
        股票列表
    """
    if not FUTU_AVAILABLE:
        return {"error": "futu-api 未安装，请运行 pip install futu-api"}

    quote_ctx = get_quote_context()
    if quote_ctx is None:
        return {"error": "无法连接到富途OpenD"}

    from futu import SecurityType

    type_map = {
        "STOCK": SecurityType.STOCK,
        "ETF": SecurityType.ETF,
        "WARRANT": SecurityType.WARRANT,
        "BOND": SecurityType.BOND,
    }
    sec_type = type_map.get(stock_type.upper(), SecurityType.STOCK)

    ret, data = quote_ctx.get_stock_basicinfo(market.upper(), sec_type)
    if ret != RET_OK:
        return {"error": f"获取股票列表失败: {data}"}

    stocks = []
    for _, row in data.iterrows():
        stocks.append({
            "code": row.get("code", ""),
            "name": row.get("name", ""),
            "lot_size": row.get("lot_size", 0),
            "stock_type": row.get("stock_type", ""),
        })

    return {
        "market": market,
        "stock_type": stock_type,
        "count": len(stocks),
        "stocks": stocks[:100],  # 限制返回数量
    }


def cleanup():
    """清理连接"""
    global _quote_ctx
    if _quote_ctx:
        _quote_ctx.close()
        _quote_ctx = None


if __name__ == "__main__":
    import atexit
    atexit.register(cleanup)

    port = int(os.getenv("FUTU_PRICE_HTTP_PORT", "8007"))
    print(f"启动富途行情服务 on port {port}")
    mcp.run(transport="streamable-http", port=port)
