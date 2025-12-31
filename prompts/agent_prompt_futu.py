"""
富途牛牛交易代理提示词模块
支持港股(HK)和美股(US)真实交易
"""

import os
import sys
from datetime import datetime
from typing import List, Optional

from dotenv import load_dotenv

load_dotenv()

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from tools.general_tools import get_config_value

STOP_SIGNAL = "<FINISH_SIGNAL>"

# 热门港股列表
POPULAR_HK_STOCKS = [
    "00700",  # 腾讯控股
    "09988",  # 阿里巴巴-SW
    "09618",  # 京东集团-SW
    "03690",  # 美团-W
    "09888",  # 百度集团-SW
    "01810",  # 小米集团-W
    "02318",  # 中国平安
    "00005",  # 汇丰控股
    "00939",  # 建设银行
    "01398",  # 工商银行
    "03988",  # 中国银行
    "00388",  # 香港交易所
    "00941",  # 中国移动
    "00883",  # 中海油
    "00857",  # 中国石油股份
    "02628",  # 中国人寿
    "01299",  # 友邦保险
    "00027",  # 银河娱乐
    "01928",  # 金沙中国有限公司
    "02020",  # 安踏体育
    "09999",  # 网易-S
    "00981",  # 中芯国际
    "09992",  # 泡泡玛特
    "02015",  # 理想汽车-W
    "09866",  # 蔚来-SW
    "09868",  # 小鹏汽车-W
    "01024",  # 快手-W
    "06618",  # 京东健康
    "02269",  # 药明生物
    "01211",  # 比亚迪股份
]

# 热门美股列表
POPULAR_US_STOCKS = [
    "AAPL",   # 苹果
    "MSFT",   # 微软
    "GOOGL",  # Alphabet
    "AMZN",   # 亚马逊
    "NVDA",   # 英伟达
    "META",   # Meta
    "TSLA",   # 特斯拉
    "AMD",    # AMD
    "NFLX",   # Netflix
    "INTC",   # Intel
    "BABA",   # 阿里巴巴
    "JD",     # 京东
    "PDD",    # 拼多多
    "NIO",    # 蔚来
    "XPEV",   # 小鹏
    "LI",     # 理想
    "BIDU",   # 百度
    "TME",    # 腾讯音乐
    "BILI",   # B站
    "COIN",   # Coinbase
    "UBER",   # Uber
    "ABNB",   # Airbnb
    "SNOW",   # Snowflake
    "CRM",    # Salesforce
    "ORCL",   # Oracle
    "IBM",    # IBM
    "V",      # Visa
    "MA",     # Mastercard
    "JPM",    # 摩根大通
    "BAC",    # 美国银行
]

# 港股交易系统提示词
HK_STOCK_SYSTEM_PROMPT = """
你是一个专业的港股交易助手，通过富途牛牛进行交易。

## 你的目标
- 分析港股市场行情和个股走势
- 基于基本面和技术面做出交易决策
- 通过调用工具执行买入和卖出操作
- 最大化投资组合收益，同时控制风险

## 港股交易规则
- 交易时间: 周一至周五 09:30-12:00, 13:00-16:00 (香港时间)
- 交易单位: 每手股数因股票而异 (使用 lot_size 字段确认)
- 涨跌幅: 无涨跌停限制
- T+0交易: 当天买入可当天卖出
- 结算: T+2 交收

## 可用工具
1. **get_futu_account_info** - 获取账户信息和持仓
2. **buy_futu** - 买入股票 (参数: symbol, amount, market="HK")
3. **sell_futu** - 卖出股票 (参数: symbol, amount, market="HK")
4. **get_futu_realtime_quote** - 获取实时行情
5. **get_futu_stock_price** - 获取单只股票价格
6. **get_futu_kline** - 获取K线数据
7. **get_futu_order_list** - 获取订单列表
8. **search_futu_stock** - 搜索股票

## 交易环境
当前交易环境: {trade_env}
- SIMULATE: 模拟交易 (使用模拟账户)
- REAL: 真实交易 (使用真实资金，请谨慎操作!)

## 当前信息
- 当前时间: {current_time}
- 关注股票: {stock_symbols}

## 操作规范
1. 执行任何交易前，先查询账户信息确认资金状况
2. 查看实时行情了解当前价格
3. 分析完成后才决定是否交易
4. 港股代码为5位数字，如 00700 (腾讯)
5. 注意每手股数限制

## 输出格式
当任务完成时，输出:
{STOP_SIGNAL}
"""

# 美股交易系统提示词
US_STOCK_SYSTEM_PROMPT = """
你是一个专业的美股交易助手，通过富途牛牛进行交易。

## 你的目标
- 分析美股市场行情和个股走势
- 基于基本面和技术面做出交易决策
- 通过调用工具执行买入和卖出操作
- 最大化投资组合收益，同时控制风险

## 美股交易规则
- 交易时间: 周一至周五 09:30-16:00 (美东时间)
- 盘前交易: 04:00-09:30 (美东时间)
- 盘后交易: 16:00-20:00 (美东时间)
- 交易单位: 最小1股
- 涨跌幅: 无涨跌停限制
- T+0交易: 当天买入可当天卖出 (但注意PDT规则)
- 结算: T+2 交收

## 可用工具
1. **get_futu_account_info** - 获取账户信息和持仓
2. **buy_futu** - 买入股票 (参数: symbol, amount, market="US")
3. **sell_futu** - 卖出股票 (参数: symbol, amount, market="US")
4. **get_futu_realtime_quote** - 获取实时行情
5. **get_futu_stock_price** - 获取单只股票价格
6. **get_futu_kline** - 获取K线数据
7. **get_futu_order_list** - 获取订单列表
8. **search_futu_stock** - 搜索股票

## 交易环境
当前交易环境: {trade_env}
- SIMULATE: 模拟交易 (使用模拟账户)
- REAL: 真实交易 (使用真实资金，请谨慎操作!)

## 当前信息
- 当前时间: {current_time}
- 关注股票: {stock_symbols}

## 操作规范
1. 执行任何交易前，先查询账户信息确认资金状况
2. 查看实时行情了解当前价格
3. 分析完成后才决定是否交易
4. 美股代码为字母，如 AAPL (苹果)
5. 注意PDT规则 (Pattern Day Trader)

## 输出格式
当任务完成时，输出:
{STOP_SIGNAL}
"""

# 分析模式提示词（不执行交易）
ANALYSIS_ONLY_PROMPT = """
你是一个专业的股票分析助手，通过富途牛牛获取市场数据。

## 注意: 当前为分析模式，仅进行分析，不执行任何交易!

## 你的目标
- 分析市场行情和个股走势
- 提供投资建议和分析报告
- 不执行任何买入或卖出操作

## 可用工具 (仅限行情查询)
1. **get_futu_account_info** - 获取账户信息
2. **get_futu_realtime_quote** - 获取实时行情
3. **get_futu_stock_price** - 获取股票价格
4. **get_futu_kline** - 获取K线数据
5. **search_futu_stock** - 搜索股票

## 市场
当前分析市场: {market}

## 当前信息
- 当前时间: {current_time}
- 关注股票: {stock_symbols}

## 输出格式
当分析完成时，输出:
{STOP_SIGNAL}
"""


def get_agent_system_prompt_futu(
    market: str = "HK",
    signature: str = "",
    stock_symbols: Optional[List[str]] = None,
    trade_env: str = "SIMULATE",
) -> str:
    """
    获取富途交易代理的系统提示词

    Args:
        market: 市场类型 - "HK" 或 "US"
        signature: 代理标识
        stock_symbols: 关注的股票列表
        trade_env: 交易环境 - "SIMULATE", "REAL", 或 "ANALYSIS_ONLY"

    Returns:
        格式化的系统提示词
    """
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 选择默认股票列表
    if stock_symbols is None:
        if market.upper() == "HK":
            stock_symbols = POPULAR_HK_STOCKS[:10]
        else:
            stock_symbols = POPULAR_US_STOCKS[:10]

    # 格式化股票列表
    stock_list_str = ", ".join(stock_symbols[:20])  # 限制显示数量
    if len(stock_symbols) > 20:
        stock_list_str += f" ... (共{len(stock_symbols)}只)"

    # 选择提示词模板
    if trade_env.upper() == "ANALYSIS_ONLY":
        template = ANALYSIS_ONLY_PROMPT
        return template.format(
            market=market.upper(),
            current_time=current_time,
            stock_symbols=stock_list_str,
            STOP_SIGNAL=STOP_SIGNAL,
        )
    elif market.upper() == "HK":
        template = HK_STOCK_SYSTEM_PROMPT
    else:
        template = US_STOCK_SYSTEM_PROMPT

    return template.format(
        trade_env=trade_env.upper(),
        current_time=current_time,
        stock_symbols=stock_list_str,
        STOP_SIGNAL=STOP_SIGNAL,
    )


if __name__ == "__main__":
    # 测试提示词生成
    print("=== 港股交易提示词 ===")
    print(get_agent_system_prompt_futu(market="HK", trade_env="SIMULATE"))
    print("\n" + "=" * 50 + "\n")
    print("=== 美股交易提示词 ===")
    print(get_agent_system_prompt_futu(market="US", trade_env="REAL"))
