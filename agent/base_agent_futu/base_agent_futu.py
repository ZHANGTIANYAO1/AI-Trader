"""
BaseAgentFutu - 富途牛牛真实交易代理
支持港股(HK)和美股(US)真实交易，通过富途OpenD API实现
"""

import asyncio
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.globals import set_verbose, set_debug
from langchain_core.messages import AIMessage
from langchain_core.utils.function_calling import convert_to_openai_tool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI

# Console callback handler
try:
    from langchain.callbacks.stdout import StdOutCallbackHandler as _ConsoleHandler
except Exception:
    try:
        from langchain.callbacks import StdOutCallbackHandler as _ConsoleHandler
    except Exception:
        try:
            from langchain_core.callbacks.stdout import StdOutCallbackHandler as _ConsoleHandler
        except Exception:
            _ConsoleHandler = None

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from prompts.agent_prompt_futu import (
    STOP_SIGNAL,
    get_agent_system_prompt_futu,
    POPULAR_HK_STOCKS,
    POPULAR_US_STOCKS,
)
from tools.general_tools import (
    extract_conversation,
    extract_tool_messages,
    get_config_value,
    write_config_value,
)

load_dotenv()


class DeepSeekChatOpenAI(ChatOpenAI):
    """Custom ChatOpenAI wrapper for DeepSeek API compatibility.

    Handles DeepSeek-specific message format requirements:
    1. Converts tool_calls arguments from dict to JSON string
    2. Ensures message content is always a string (not a list)
    """

    def _convert_messages_for_deepseek(self, messages: list) -> list:
        """Convert messages to DeepSeek-compatible format."""
        converted = []
        for msg in messages:
            # Handle different message types
            if hasattr(msg, 'content'):
                content = msg.content
                # DeepSeek expects string content, not list
                if isinstance(content, list):
                    # Convert list content to string
                    text_parts = []
                    for item in content:
                        if isinstance(item, dict):
                            if item.get('type') == 'text':
                                text_parts.append(item.get('text', ''))
                            else:
                                text_parts.append(str(item))
                        else:
                            text_parts.append(str(item))
                    msg.content = '\n'.join(text_parts) if text_parts else ''
            converted.append(msg)
        return converted

    def _generate(self, messages: list, stop: Optional[list] = None, **kwargs):
        # Pre-process messages for DeepSeek compatibility
        messages = self._convert_messages_for_deepseek(messages)

        result = super()._generate(messages, stop, **kwargs)
        for generation in result.generations:
            for gen in generation:
                if hasattr(gen, "message") and hasattr(gen.message, "additional_kwargs"):
                    tool_calls = gen.message.additional_kwargs.get("tool_calls")
                    if tool_calls:
                        for tool_call in tool_calls:
                            if "function" in tool_call and "arguments" in tool_call["function"]:
                                args = tool_call["function"]["arguments"]
                                if isinstance(args, str):
                                    try:
                                        tool_call["function"]["arguments"] = json.loads(args)
                                    except json.JSONDecodeError:
                                        pass
        return result

    async def _agenerate(self, messages: list, stop: Optional[list] = None, **kwargs):
        # Pre-process messages for DeepSeek compatibility
        messages = self._convert_messages_for_deepseek(messages)

        result = await super()._agenerate(messages, stop, **kwargs)
        for generation in result.generations:
            for gen in generation:
                if hasattr(gen, "message") and hasattr(gen.message, "additional_kwargs"):
                    tool_calls = gen.message.additional_kwargs.get("tool_calls")
                    if tool_calls:
                        for tool_call in tool_calls:
                            if "function" in tool_call and "arguments" in tool_call["function"]:
                                args = tool_call["function"]["arguments"]
                                if isinstance(args, str):
                                    try:
                                        tool_call["function"]["arguments"] = json.loads(args)
                                    except json.JSONDecodeError:
                                        pass
        return result


class BaseAgentFutu:
    """
    富途牛牛真实交易代理

    支持:
    - 港股(HK)交易
    - 美股(US)交易
    - 实时行情获取
    - 真实/模拟交易环境切换

    主要功能:
    1. MCP工具管理和连接
    2. AI代理创建和配置
    3. 真实交易执行
    4. 持仓管理和记录
    """

    def __init__(
        self,
        signature: str,
        basemodel: str,
        market: str = "HK",
        stock_symbols: Optional[List[str]] = None,
        mcp_config: Optional[Dict[str, Dict[str, Any]]] = None,
        log_path: Optional[str] = None,
        max_steps: int = 10,
        max_retries: int = 3,
        base_delay: float = 0.5,
        openai_base_url: Optional[str] = None,
        openai_api_key: Optional[str] = None,
        initial_cash: float = 100000.0,
        trade_env: str = "SIMULATE",
        verbose: bool = False,
    ):
        """
        初始化富途交易代理

        Args:
            signature: 代理标识/名称
            basemodel: 使用的AI模型名称
            market: 市场类型 - "HK" 港股 或 "US" 美股
            stock_symbols: 关注的股票列表
            mcp_config: MCP工具配置
            log_path: 日志路径
            max_steps: 最大推理步数
            max_retries: 最大重试次数
            base_delay: 重试基础延迟
            openai_base_url: OpenAI API URL
            openai_api_key: OpenAI API密钥
            initial_cash: 初始资金（仅用于记录，实际资金来自富途账户）
            trade_env: 交易环境 - "SIMULATE" 模拟 或 "REAL" 真实
            verbose: 是否启用详细输出
        """
        self.signature = signature
        self.basemodel = basemodel
        self.market = market.upper()
        self.trade_env = trade_env.upper()

        # 根据市场选择默认股票列表
        if stock_symbols is None:
            if self.market == "HK":
                self.stock_symbols = POPULAR_HK_STOCKS
            else:
                self.stock_symbols = POPULAR_US_STOCKS
        else:
            self.stock_symbols = stock_symbols

        self.max_steps = max_steps
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.initial_cash = initial_cash
        self.verbose = verbose

        # MCP配置
        self.mcp_config = mcp_config or self._get_default_mcp_config()

        # 日志路径
        self.base_log_path = log_path or "./data/agent_data_futu"

        # OpenAI配置
        self.openai_base_url = openai_base_url or os.getenv("OPENAI_API_BASE")
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")

        # 组件初始化
        self.client: Optional[MultiServerMCPClient] = None
        self.tools: Optional[List] = None
        self.model: Optional[ChatOpenAI] = None
        self.agent: Optional[Any] = None

        # 数据路径
        self.data_path = os.path.join(self.base_log_path, self.signature)
        self.position_file = os.path.join(self.data_path, "position", "position.jsonl")

    def _get_default_mcp_config(self) -> Dict[str, Dict[str, Any]]:
        """获取默认MCP配置"""
        return {
            "math": {
                "transport": "streamable_http",
                "url": f"http://localhost:{os.getenv('MATH_HTTP_PORT', '8000')}/mcp",
            },
            "futu_trade": {
                "transport": "streamable_http",
                "url": f"http://localhost:{os.getenv('FUTU_TRADE_HTTP_PORT', '8006')}/mcp",
            },
            "futu_price": {
                "transport": "streamable_http",
                "url": f"http://localhost:{os.getenv('FUTU_PRICE_HTTP_PORT', '8007')}/mcp",
            },
            "search": {
                "transport": "streamable_http",
                "url": f"http://localhost:{os.getenv('SEARCH_HTTP_PORT', '8004')}/mcp",
            },
        }

    async def initialize(self) -> None:
        """初始化MCP客户端和AI模型"""
        print(f"🚀 初始化富途交易代理: {self.signature}")
        print(f"📊 市场: {self.market}")
        print(f"🔧 交易环境: {self.trade_env}")

        if self.verbose:
            set_verbose(True)
            try:
                set_debug(True)
            except Exception:
                pass
            print("🔍 详细模式已启用")

        # 验证OpenAI配置
        if not self.openai_api_key:
            raise ValueError("❌ OpenAI API密钥未设置")

        try:
            # 创建MCP客户端
            self.client = MultiServerMCPClient(self.mcp_config)
            self.tools = await self.client.get_tools()

            if not self.tools:
                print("⚠️ 警告: 未加载到MCP工具")
            else:
                print(f"✅ 已加载 {len(self.tools)} 个MCP工具")
                if self.verbose:
                    tool_names = [getattr(t, "name", "<unknown>") for t in self.tools]
                    print(f"🔧 工具: {', '.join(tool_names)}")
        except Exception as e:
            raise RuntimeError(
                f"❌ MCP客户端初始化失败: {e}\n"
                f"   请确保MCP服务已启动，运行: python agent_tools/start_mcp_services_futu.py"
            )

        try:
            # 创建AI模型
            if "deepseek" in self.basemodel.lower():
                self.model = DeepSeekChatOpenAI(
                    model=self.basemodel,
                    base_url=self.openai_base_url,
                    api_key=self.openai_api_key,
                    max_retries=3,
                    timeout=60,
                )
            else:
                self.model = ChatOpenAI(
                    model=self.basemodel,
                    base_url=self.openai_base_url,
                    api_key=self.openai_api_key,
                    max_retries=3,
                    timeout=60,
                )
        except Exception as e:
            raise RuntimeError(f"❌ AI模型初始化失败: {e}")

        print(f"✅ 代理 {self.signature} 初始化完成")

    def _setup_logging(self, session_id: str) -> str:
        """设置日志文件路径"""
        log_path = os.path.join(self.base_log_path, self.signature, "log", session_id)
        if not os.path.exists(log_path):
            os.makedirs(log_path)
        return os.path.join(log_path, "log.jsonl")

    def _log_message(self, log_file: str, new_messages: List[Dict[str, str]]) -> None:
        """记录消息到日志文件"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "signature": self.signature,
            "market": self.market,
            "new_messages": new_messages,
        }
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

    async def _ainvoke_with_retry(self, message: List[Dict[str, str]]) -> Any:
        """带重试的代理调用"""
        for attempt in range(1, self.max_retries + 1):
            try:
                if self.verbose:
                    print(f"🤖 调用LLM API ({self.basemodel})...")
                return await self.agent.ainvoke({"messages": message}, {"recursion_limit": 100})
            except Exception as e:
                if attempt == self.max_retries:
                    raise e
                print(f"⚠️ 第{attempt}次尝试失败，{self.base_delay * attempt}秒后重试...")
                await asyncio.sleep(self.base_delay * attempt)

    async def run_trading_session(self) -> None:
        """
        运行交易会话

        这是实时交易模式，不依赖历史数据
        """
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        print(f"📈 启动交易会话: {session_id}")
        print(f"💹 市场: {self.market}")
        print(f"🔒 交易环境: {self.trade_env}")

        # 设置日志
        log_file = self._setup_logging(session_id)
        write_config_value("LOG_FILE", log_file)
        write_config_value("SIGNATURE", self.signature)
        write_config_value("MARKET", self.market)
        write_config_value("FUTU_TRADE_ENV", self.trade_env)

        # 创建代理
        self.agent = create_agent(
            self.model,
            tools=self.tools,
            system_prompt=get_agent_system_prompt_futu(
                market=self.market,
                signature=self.signature,
                stock_symbols=self.stock_symbols,
                trade_env=self.trade_env,
            ),
        )

        if self.verbose and _ConsoleHandler is not None:
            try:
                handler = _ConsoleHandler()
                self.agent = self.agent.with_config({
                    "callbacks": [handler],
                    "tags": [self.signature, self.market],
                })
            except Exception:
                pass

        # 初始用户查询
        user_query = [{"role": "user", "content": f"请分析当前{self.market}市场行情并决定交易策略。"}]
        message = user_query.copy()
        self._log_message(log_file, user_query)

        # 交易循环
        current_step = 0
        while current_step < self.max_steps:
            current_step += 1
            print(f"🔄 步骤 {current_step}/{self.max_steps}")

            try:
                response = await self._ainvoke_with_retry(message)
                agent_response = extract_conversation(response, "final")

                if STOP_SIGNAL in agent_response:
                    print("✅ 收到停止信号，交易会话结束")
                    print(agent_response)
                    self._log_message(log_file, [{"role": "assistant", "content": agent_response}])
                    break

                tool_msgs = extract_tool_messages(response)
                tool_response = "\n".join([msg.content for msg in tool_msgs])

                new_messages = [
                    {"role": "assistant", "content": agent_response},
                    {"role": "user", "content": f"工具结果: {tool_response}"},
                ]

                message.extend(new_messages)
                self._log_message(log_file, new_messages[0])
                self._log_message(log_file, new_messages[1])

            except Exception as e:
                print(f"❌ 交易会话错误: {str(e)}")
                raise

        print(f"✅ 交易会话 {session_id} 完成")

    async def run_analysis_session(self, query: str) -> str:
        """
        运行分析会话（仅分析不交易）

        Args:
            query: 用户查询

        Returns:
            分析结果
        """
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        print(f"📊 启动分析会话: {session_id}")

        log_file = self._setup_logging(f"analysis_{session_id}")
        write_config_value("LOG_FILE", log_file)
        write_config_value("SIGNATURE", self.signature)
        write_config_value("MARKET", self.market)

        # 创建分析代理（禁用交易）
        analysis_prompt = get_agent_system_prompt_futu(
            market=self.market,
            signature=self.signature,
            stock_symbols=self.stock_symbols,
            trade_env="ANALYSIS_ONLY",  # 分析模式
        )

        self.agent = create_agent(
            self.model,
            tools=self.tools,
            system_prompt=analysis_prompt,
        )

        user_query = [{"role": "user", "content": query}]
        message = user_query.copy()
        self._log_message(log_file, user_query)

        final_response = ""
        current_step = 0

        while current_step < self.max_steps:
            current_step += 1

            try:
                response = await self._ainvoke_with_retry(message)
                agent_response = extract_conversation(response, "final")
                final_response = agent_response

                if STOP_SIGNAL in agent_response:
                    break

                tool_msgs = extract_tool_messages(response)
                tool_response = "\n".join([msg.content for msg in tool_msgs])

                new_messages = [
                    {"role": "assistant", "content": agent_response},
                    {"role": "user", "content": f"工具结果: {tool_response}"},
                ]
                message.extend(new_messages)

            except Exception as e:
                print(f"❌ 分析会话错误: {str(e)}")
                raise

        return final_response.replace(STOP_SIGNAL, "").strip()

    def register_agent(self) -> None:
        """注册新代理，创建初始持仓记录"""
        if os.path.exists(self.position_file):
            print(f"⚠️ 持仓文件已存在: {self.position_file}")
            return

        position_dir = os.path.join(self.data_path, "position")
        if not os.path.exists(position_dir):
            os.makedirs(position_dir)
            print(f"📁 创建持仓目录: {position_dir}")

        init_position = {"CASH": self.initial_cash}
        for symbol in self.stock_symbols:
            init_position[symbol] = 0

        with open(self.position_file, "w") as f:
            f.write(json.dumps({
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "id": 0,
                "market": self.market,
                "trade_env": self.trade_env,
                "positions": init_position,
            }) + "\n")

        currency = "HKD" if self.market == "HK" else "USD"
        print(f"✅ 代理 {self.signature} 注册完成")
        print(f"📁 持仓文件: {self.position_file}")
        print(f"💰 初始资金: {currency} {self.initial_cash:,.2f}")
        print(f"📊 关注股票数: {len(self.stock_symbols)}")

    def get_position_summary(self) -> Dict[str, Any]:
        """获取持仓摘要"""
        if not os.path.exists(self.position_file):
            return {"error": "持仓文件不存在"}

        positions = []
        with open(self.position_file, "r") as f:
            for line in f:
                positions.append(json.loads(line))

        if not positions:
            return {"error": "无持仓记录"}

        latest = positions[-1]
        return {
            "signature": self.signature,
            "market": self.market,
            "trade_env": self.trade_env,
            "latest_date": latest.get("date"),
            "positions": latest.get("positions", {}),
            "total_records": len(positions),
        }

    async def check_market_status(self) -> Dict[str, Any]:
        """检查市场状态"""
        try:
            from futu import OpenQuoteContext, Market

            config = {
                "host": get_config_value("FUTU_HOST", "127.0.0.1"),
                "port": int(get_config_value("FUTU_PORT", "11111")),
            }

            quote_ctx = OpenQuoteContext(host=config["host"], port=config["port"])
            ret, data = quote_ctx.get_global_state()
            quote_ctx.close()

            if ret == 0:
                return {
                    "connected": True,
                    "market_state": data,
                }
            else:
                return {"connected": False, "error": str(data)}
        except Exception as e:
            return {"connected": False, "error": str(e)}

    def __str__(self) -> str:
        return (
            f"BaseAgentFutu(signature='{self.signature}', "
            f"market='{self.market}', "
            f"trade_env='{self.trade_env}', "
            f"stocks={len(self.stock_symbols)})"
        )

    def __repr__(self) -> str:
        return self.__str__()
