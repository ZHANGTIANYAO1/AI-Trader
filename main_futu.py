#!/usr/bin/env python3
"""
富途牛牛真实交易主程序
支持港股(HK)和美股(US)交易

使用前请确保:
1. 富途牛牛OpenD客户端已启动
2. 已安装 futu-api: pip install futu-api
3. 已配置环境变量或配置文件
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

load_dotenv()


def load_config(config_path: str) -> dict:
    """加载配置文件"""
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_agent_class(agent_type: str):
    """动态获取Agent类"""
    if agent_type == "BaseAgentFutu":
        from agent.base_agent_futu import BaseAgentFutu
        return BaseAgentFutu
    else:
        raise ValueError(f"未知的Agent类型: {agent_type}")


async def run_trading(config_path: str):
    """运行交易会话"""
    print("=" * 60)
    print("🚀 富途牛牛 AI 交易系统")
    print("=" * 60)

    # 加载配置
    config = load_config(config_path)
    print(f"📋 配置文件: {config_path}")

    agent_type = config.get("agent_type", "BaseAgentFutu")
    market = config.get("market", "HK")
    trade_env = config.get("trade_env", "SIMULATE")
    log_path = config.get("log_config", {}).get("log_path", "./data/agent_data_futu")

    print(f"📊 市场: {market}")
    print(f"🔒 交易环境: {trade_env}")

    # 获取Agent类
    AgentClass = get_agent_class(agent_type)

    # 获取启用的模型
    enabled_models = [m for m in config.get("models", []) if m.get("enabled", False)]

    if not enabled_models:
        print("❌ 没有启用的模型，请在配置文件中启用至少一个模型")
        return

    print(f"🤖 启用的模型: {[m['name'] for m in enabled_models]}")

    # 获取股票列表
    stock_symbols = config.get("stock_symbols", {}).get(market, [])
    if not stock_symbols:
        print(f"⚠️  未配置{market}市场股票列表，使用默认列表")
        stock_symbols = None

    # Agent配置
    agent_config = config.get("agent_config", {})
    futu_config = config.get("futu_config", {})

    # 设置富途环境变量
    os.environ["FUTU_HOST"] = futu_config.get("host", "127.0.0.1")
    os.environ["FUTU_PORT"] = str(futu_config.get("port", 11111))
    os.environ["FUTU_TRADE_PASSWORD"] = futu_config.get("trade_password", "")
    os.environ["FUTU_TRADE_ENV"] = futu_config.get("trade_env", trade_env)

    # 运行每个启用的模型
    for model_config in enabled_models:
        print(f"\n{'=' * 60}")
        print(f"🤖 启动模型: {model_config['name']}")
        print(f"{'=' * 60}")

        try:
            # 获取API配置 (支持DeepSeek等不同模型)
            model_name = model_config.get("name", "").lower()
            if "deepseek" in model_name or "deepseek" in model_config.get("basemodel", "").lower():
                # DeepSeek模型使用专用配置
                api_base = model_config.get("openai_base_url") or os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com/v1")
                api_key = model_config.get("openai_api_key") or os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
            else:
                # 其他模型使用OpenAI配置
                api_base = model_config.get("openai_base_url") or os.getenv("OPENAI_API_BASE")
                api_key = model_config.get("openai_api_key") or os.getenv("OPENAI_API_KEY")

            if not api_key:
                print(f"❌ 未配置API密钥，请设置环境变量或配置文件")
                if "deepseek" in model_name:
                    print(f"   DeepSeek模型需要设置 DEEPSEEK_API_KEY 环境变量")
                continue

            # 创建Agent
            agent = AgentClass(
                signature=model_config["signature"],
                basemodel=model_config["basemodel"],
                market=market,
                stock_symbols=stock_symbols,
                log_path=log_path,
                max_steps=agent_config.get("max_steps", 30),
                max_retries=agent_config.get("max_retries", 3),
                base_delay=agent_config.get("base_delay", 1.0),
                openai_base_url=api_base,
                openai_api_key=api_key,
                initial_cash=agent_config.get("initial_cash", 100000.0),
                trade_env=trade_env,
                verbose=True,
            )

            # 初始化Agent
            await agent.initialize()

            # 注册Agent（创建初始持仓记录）
            agent.register_agent()

            # 检查市场状态
            print("\n🔍 检查市场状态...")
            market_status = await agent.check_market_status()
            print(f"市场状态: {market_status}")

            # 运行交易会话
            print("\n📈 开始交易会话...")
            await agent.run_trading_session()

            # 显示持仓摘要
            summary = agent.get_position_summary()
            print(f"\n📊 持仓摘要:")
            print(json.dumps(summary, indent=2, ensure_ascii=False))

        except Exception as e:
            print(f"❌ 模型 {model_config['name']} 运行失败: {e}")
            import traceback
            traceback.print_exc()
            continue

    print("\n" + "=" * 60)
    print("✅ 所有交易会话完成")
    print("=" * 60)


async def run_analysis(config_path: str, query: str):
    """运行分析会话（不交易）"""
    print("=" * 60)
    print("📊 富途牛牛 AI 分析系统")
    print("=" * 60)

    config = load_config(config_path)
    market = config.get("market", "HK")
    log_path = config.get("log_config", {}).get("log_path", "./data/agent_data_futu")

    AgentClass = get_agent_class(config.get("agent_type", "BaseAgentFutu"))

    enabled_models = [m for m in config.get("models", []) if m.get("enabled", False)]
    if not enabled_models:
        print("❌ 没有启用的模型")
        return

    model_config = enabled_models[0]  # 使用第一个启用的模型
    agent_config = config.get("agent_config", {})
    futu_config = config.get("futu_config", {})

    # 设置富途环境变量
    os.environ["FUTU_HOST"] = futu_config.get("host", "127.0.0.1")
    os.environ["FUTU_PORT"] = str(futu_config.get("port", 11111))

    # 获取API配置 (支持DeepSeek等不同模型)
    model_name = model_config.get("name", "").lower()
    if "deepseek" in model_name or "deepseek" in model_config.get("basemodel", "").lower():
        api_base = model_config.get("openai_base_url") or os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com/v1")
        api_key = model_config.get("openai_api_key") or os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
    else:
        api_base = model_config.get("openai_base_url") or os.getenv("OPENAI_API_BASE")
        api_key = model_config.get("openai_api_key") or os.getenv("OPENAI_API_KEY")

    if not api_key:
        print(f"❌ 未配置API密钥")
        return

    agent = AgentClass(
        signature=f"{model_config['signature']}-analysis",
        basemodel=model_config["basemodel"],
        market=market,
        log_path=log_path,
        max_steps=agent_config.get("max_steps", 30),
        openai_base_url=api_base,
        openai_api_key=api_key,
        trade_env="ANALYSIS_ONLY",
        verbose=True,
    )

    await agent.initialize()

    print(f"\n🔍 分析查询: {query}")
    print("-" * 60)

    result = await agent.run_analysis_session(query)

    print("\n📋 分析结果:")
    print("-" * 60)
    print(result)


def main():
    """主入口"""
    parser = argparse.ArgumentParser(description="富途牛牛 AI 交易系统")
    parser.add_argument(
        "config",
        nargs="?",
        default="configs/futu_config.json",
        help="配置文件路径 (默认: configs/futu_config.json)",
    )
    parser.add_argument(
        "--mode",
        choices=["trade", "analyze"],
        default="trade",
        help="运行模式: trade(交易) 或 analyze(分析)",
    )
    parser.add_argument(
        "--query",
        type=str,
        default="请分析当前市场行情",
        help="分析查询 (仅在analyze模式下使用)",
    )
    parser.add_argument(
        "--market",
        choices=["HK", "US"],
        help="覆盖配置文件中的市场设置",
    )
    parser.add_argument(
        "--env",
        choices=["SIMULATE", "REAL"],
        help="覆盖配置文件中的交易环境",
    )

    args = parser.parse_args()

    # 检查配置文件
    config_path = args.config
    if not os.path.isabs(config_path):
        config_path = os.path.join(project_root, config_path)

    if not os.path.exists(config_path):
        print(f"❌ 配置文件不存在: {config_path}")
        print("\n可用的配置文件:")
        configs_dir = os.path.join(project_root, "configs")
        for f in os.listdir(configs_dir):
            if f.endswith(".json") and "futu" in f:
                print(f"  - configs/{f}")
        sys.exit(1)

    # 覆盖配置
    if args.market or args.env:
        config = load_config(config_path)
        if args.market:
            config["market"] = args.market
        if args.env:
            config["trade_env"] = args.env
        # 写入临时配置
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config, f, indent=2)
            config_path = f.name

    # 运行
    if args.mode == "trade":
        asyncio.run(run_trading(config_path))
    else:
        asyncio.run(run_analysis(config_path, args.query))


if __name__ == "__main__":
    main()
