#!/usr/bin/env python3
"""
富途牛牛定时交易调度器
支持定时运行交易策略，自动识别交易时段

功能:
1. 每小时自动运行一次交易分析
2. 自动识别美股/港股交易时段
3. 支持香港/美东/本地时区
"""

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv is optional for scheduler


# 时区定义
TZ_HK = ZoneInfo("Asia/Hong_Kong")
TZ_US = ZoneInfo("America/New_York")
TZ_LOCAL = ZoneInfo("Asia/Hong_Kong")  # 默认本地时区为香港


def get_market_hours(market: str) -> dict:
    """获取市场交易时间（返回当地时区的时间）"""
    if market == "US":
        return {
            "timezone": TZ_US,
            "pre_market": (4, 0, 9, 30),      # 04:00 - 09:30 ET
            "regular": (9, 30, 16, 0),         # 09:30 - 16:00 ET
            "after_hours": (16, 0, 20, 0),     # 16:00 - 20:00 ET
        }
    else:  # HK
        return {
            "timezone": TZ_HK,
            "morning": (9, 30, 12, 0),         # 09:30 - 12:00 HKT
            "afternoon": (13, 0, 16, 0),       # 13:00 - 16:00 HKT
        }


def get_market_status(market: str) -> dict:
    """获取市场状态"""
    now_utc = datetime.now(ZoneInfo("UTC"))
    hours = get_market_hours(market)
    tz = hours["timezone"]
    now_market = now_utc.astimezone(tz)
    now_hk = now_utc.astimezone(TZ_HK)

    current_time = now_market.hour * 60 + now_market.minute
    weekday = now_market.weekday()  # 0=Monday, 6=Sunday

    result = {
        "market": market,
        "market_time": now_market.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "hk_time": now_hk.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "weekday": weekday,
        "is_weekend": weekday >= 5,
        "session": "CLOSED",
        "is_trading": False,
    }

    if weekday >= 5:  # 周末
        result["session"] = "WEEKEND"
        return result

    if market == "US":
        pre_start = hours["pre_market"][0] * 60 + hours["pre_market"][1]
        pre_end = hours["pre_market"][2] * 60 + hours["pre_market"][3]
        reg_start = hours["regular"][0] * 60 + hours["regular"][1]
        reg_end = hours["regular"][2] * 60 + hours["regular"][3]
        after_start = hours["after_hours"][0] * 60 + hours["after_hours"][1]
        after_end = hours["after_hours"][2] * 60 + hours["after_hours"][3]

        if pre_start <= current_time < pre_end:
            result["session"] = "PRE_MARKET"
            result["is_trading"] = True
        elif reg_start <= current_time < reg_end:
            result["session"] = "REGULAR"
            result["is_trading"] = True
        elif after_start <= current_time < after_end:
            result["session"] = "AFTER_HOURS"
            result["is_trading"] = True
        else:
            result["session"] = "CLOSED"

    else:  # HK
        morning_start = hours["morning"][0] * 60 + hours["morning"][1]
        morning_end = hours["morning"][2] * 60 + hours["morning"][3]
        afternoon_start = hours["afternoon"][0] * 60 + hours["afternoon"][1]
        afternoon_end = hours["afternoon"][2] * 60 + hours["afternoon"][3]

        if morning_start <= current_time < morning_end:
            result["session"] = "MORNING"
            result["is_trading"] = True
        elif afternoon_start <= current_time < afternoon_end:
            result["session"] = "AFTERNOON"
            result["is_trading"] = True
        else:
            result["session"] = "CLOSED"

    return result


def load_config(config_path: str) -> dict:
    """加载配置文件"""
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


async def run_trading_once(config_path: str):
    """运行一次交易"""
    # 动态导入避免循环依赖
    from main_futu import run_trading
    await run_trading(config_path)


async def scheduler_loop(
    config_path: str,
    interval_minutes: int = 60,
    only_trading_hours: bool = True,
):
    """
    调度循环

    Args:
        config_path: 配置文件路径
        interval_minutes: 运行间隔（分钟）
        only_trading_hours: 是否只在交易时段运行
    """
    config = load_config(config_path)
    market = config.get("market", "HK")

    print("=" * 60)
    print("  富途牛牛 定时交易调度器")
    print("=" * 60)
    print(f"配置文件: {config_path}")
    print(f"市场: {market}")
    print(f"运行间隔: {interval_minutes} 分钟")
    print(f"仅交易时段: {only_trading_hours}")
    print("=" * 60)

    run_count = 0

    while True:
        try:
            # 获取市场状态
            status = get_market_status(market)

            print(f"\n{'='*60}")
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 检查市场状态")
            print(f"{'='*60}")
            print(f"香港时间: {status['hk_time']}")
            print(f"市场时间: {status['market_time']}")
            print(f"交易时段: {status['session']}")
            print(f"是否交易: {'是' if status['is_trading'] else '否'}")

            # 判断是否运行
            should_run = True
            if only_trading_hours and not status["is_trading"]:
                should_run = False
                print(f"\n⏸️  当前非交易时段，跳过本次运行")
                print(f"   下次检查: {interval_minutes} 分钟后")
            elif status["is_weekend"]:
                should_run = False
                print(f"\n⏸️  周末休市，跳过本次运行")

            if should_run:
                run_count += 1
                print(f"\n🚀 开始第 {run_count} 次交易运行...")
                print("-" * 60)

                try:
                    await run_trading_once(config_path)
                    print(f"\n✅ 第 {run_count} 次交易运行完成")
                except Exception as e:
                    print(f"\n❌ 交易运行出错: {e}")
                    import traceback
                    traceback.print_exc()

            # 等待下一次运行
            print(f"\n⏰ 等待 {interval_minutes} 分钟后进行下一次运行...")
            print(f"   按 Ctrl+C 停止调度器")

            await asyncio.sleep(interval_minutes * 60)

        except KeyboardInterrupt:
            print("\n\n🛑 收到停止信号，调度器退出")
            print(f"总运行次数: {run_count}")
            break
        except Exception as e:
            print(f"\n❌ 调度器错误: {e}")
            import traceback
            traceback.print_exc()
            # 出错后等待一段时间再重试
            await asyncio.sleep(60)


def show_market_status():
    """显示当前市场状态"""
    print("\n" + "=" * 60)
    print("  当前市场状态")
    print("=" * 60)

    for market in ["US", "HK"]:
        status = get_market_status(market)
        print(f"\n{market} 市场:")
        print(f"  市场时间: {status['market_time']}")
        print(f"  香港时间: {status['hk_time']}")
        print(f"  交易时段: {status['session']}")
        print(f"  是否交易: {'是' if status['is_trading'] else '否'}")

    print("\n" + "=" * 60)
    print("美股交易时间 (美东时间 ET):")
    print("  盘前:     04:00 - 09:30")
    print("  正常:     09:30 - 16:00")
    print("  盘后:     16:00 - 20:00")
    print("\n港股交易时间 (香港时间 HKT):")
    print("  上午:     09:30 - 12:00")
    print("  下午:     13:00 - 16:00")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="富途牛牛定时交易调度器")
    parser.add_argument(
        "config",
        nargs="?",
        default="configs/futu_config.json",
        help="配置文件路径",
    )
    parser.add_argument(
        "--interval", "-i",
        type=int,
        default=60,
        help="运行间隔（分钟），默认60分钟",
    )
    parser.add_argument(
        "--all-hours", "-a",
        action="store_true",
        help="全天候运行（不限制交易时段）",
    )
    parser.add_argument(
        "--status", "-s",
        action="store_true",
        help="仅显示市场状态",
    )
    parser.add_argument(
        "--once", "-o",
        action="store_true",
        help="只运行一次",
    )

    args = parser.parse_args()

    # 显示市场状态
    if args.status:
        show_market_status()
        return

    # 检查配置文件
    config_path = args.config
    if not os.path.isabs(config_path):
        config_path = os.path.join(project_root, config_path)

    if not os.path.exists(config_path):
        print(f"❌ 配置文件不存在: {config_path}")
        sys.exit(1)

    # 只运行一次
    if args.once:
        asyncio.run(run_trading_once(config_path))
        return

    # 启动调度器
    asyncio.run(scheduler_loop(
        config_path=config_path,
        interval_minutes=args.interval,
        only_trading_hours=not args.all_hours,
    ))


if __name__ == "__main__":
    main()
