#!/usr/bin/env python3
"""
富途牛牛模拟交易测试脚本
用于测试API连接、行情获取、模拟买卖等功能

使用前请确保:
1. 富途OpenD客户端已启动
2. 已安装 futu-api: pip install futu-api
"""

import os
import sys
import time
from datetime import datetime
from typing import Optional

# 添加项目根目录
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from dotenv import load_dotenv
load_dotenv()

# 尝试导入futu-api
try:
    from futu import (
        OpenQuoteContext, OpenSecTradeContext,
        TrdEnv, TrdSide, OrderType, TrdMarket,
        RET_OK, RET_ERROR, KLType, SubType
    )
    FUTU_AVAILABLE = True
except ImportError:
    FUTU_AVAILABLE = False
    print("❌ futu-api 未安装")
    print("请运行: pip install futu-api")
    sys.exit(1)


class FutuSimulateTest:
    """富途模拟交易测试类"""

    def __init__(self, host: str = "127.0.0.1", port: int = 11111):
        self.host = host
        self.port = port
        self.quote_ctx: Optional[OpenQuoteContext] = None
        self.trade_ctx_hk: Optional[OpenSecTradeContext] = None
        self.trade_ctx_us: Optional[OpenSecTradeContext] = None

    def connect(self) -> bool:
        """连接到富途OpenD"""
        print(f"\n{'='*50}")
        print("🔌 连接富途OpenD")
        print(f"{'='*50}")
        print(f"地址: {self.host}:{self.port}")

        try:
            # 连接行情
            self.quote_ctx = OpenQuoteContext(host=self.host, port=self.port)
            ret, data = self.quote_ctx.get_global_state()
            if ret != RET_OK:
                print(f"❌ 连接失败: {data}")
                return False
            print("✅ 行情连接成功")
            print(f"   服务器状态: {data}")

            # 连接港股交易
            self.trade_ctx_hk = OpenSecTradeContext(
                host=self.host,
                port=self.port,
                filter_trdmarket=TrdMarket.HK
            )
            print("✅ 港股交易连接成功")

            # 连接美股交易
            self.trade_ctx_us = OpenSecTradeContext(
                host=self.host,
                port=self.port,
                filter_trdmarket=TrdMarket.US
            )
            print("✅ 美股交易连接成功")

            return True

        except Exception as e:
            print(f"❌ 连接异常: {e}")
            return False

    def test_quote(self, market: str = "HK") -> bool:
        """测试行情获取"""
        print(f"\n{'='*50}")
        print(f"📊 测试{market}行情获取")
        print(f"{'='*50}")

        if market == "HK":
            symbols = ["HK.00700", "HK.09988", "HK.03690"]  # 腾讯、阿里、美团
        else:
            symbols = ["US.AAPL", "US.NVDA", "US.TSLA"]  # 苹果、英伟达、特斯拉

        try:
            # 获取快照行情
            ret, data = self.quote_ctx.get_market_snapshot(symbols)
            if ret != RET_OK:
                print(f"❌ 获取行情失败: {data}")
                return False

            print("\n实时行情:")
            print("-" * 70)
            print(f"{'代码':<15} {'名称':<15} {'最新价':>10} {'涨跌幅':>10}")
            print("-" * 70)

            for _, row in data.iterrows():
                code = row['code']
                name = row['name'][:10] if row['name'] else 'N/A'
                price = row['last_price']
                change = row.get('price_spread', 0)
                prev_close = row.get('prev_close_price', price)
                change_pct = ((price - prev_close) / prev_close * 100) if prev_close else 0

                print(f"{code:<15} {name:<15} {price:>10.2f} {change_pct:>9.2f}%")

            print("-" * 70)
            print("✅ 行情获取成功")
            return True

        except Exception as e:
            print(f"❌ 行情获取异常: {e}")
            return False

    def test_kline(self, symbol: str = "HK.00700") -> bool:
        """测试K线获取"""
        print(f"\n{'='*50}")
        print(f"📈 测试K线获取 ({symbol})")
        print(f"{'='*50}")

        try:
            ret, data, _ = self.quote_ctx.request_history_kline(
                symbol,
                ktype=KLType.K_DAY,
                max_count=5
            )

            if ret != RET_OK:
                print(f"❌ 获取K线失败: {data}")
                return False

            print("\n最近5日K线:")
            print("-" * 80)
            print(f"{'日期':<12} {'开盘':>10} {'最高':>10} {'最低':>10} {'收盘':>10} {'成交量':>15}")
            print("-" * 80)

            for _, row in data.iterrows():
                date = row['time_key'][:10]
                print(f"{date:<12} {row['open']:>10.2f} {row['high']:>10.2f} "
                      f"{row['low']:>10.2f} {row['close']:>10.2f} {row['volume']:>15,.0f}")

            print("-" * 80)
            print("✅ K线获取成功")
            return True

        except Exception as e:
            print(f"❌ K线获取异常: {e}")
            return False

    def test_account(self, market: str = "HK") -> bool:
        """测试账户信息获取"""
        print(f"\n{'='*50}")
        print(f"💰 测试{market}模拟账户信息")
        print(f"{'='*50}")

        trade_ctx = self.trade_ctx_hk if market == "HK" else self.trade_ctx_us

        try:
            # 获取账户列表
            ret, acc_list = trade_ctx.get_acc_list()
            if ret != RET_OK:
                print(f"❌ 获取账户列表失败: {acc_list}")
                return False

            print("\n账户列表:")
            for _, acc in acc_list.iterrows():
                print(f"   账户ID: {acc['acc_id']}, 类型: {acc['acc_type']}")

            # 获取模拟账户资金
            ret, funds = trade_ctx.accinfo_query(trd_env=TrdEnv.SIMULATE)
            if ret != RET_OK:
                print(f"❌ 获取资金信息失败: {funds}")
                return False

            if len(funds) > 0:
                f = funds.iloc[0]
                currency = "HKD" if market == "HK" else "USD"
                print(f"\n模拟账户资金 ({currency}):")
                print("-" * 40)
                print(f"   总资产:     {f.get('total_assets', 0):>15,.2f}")
                print(f"   现金:       {f.get('cash', 0):>15,.2f}")
                print(f"   持仓市值:   {f.get('market_val', 0):>15,.2f}")
                print(f"   可用资金:   {f.get('avl_withdrawal_cash', 0):>15,.2f}")
                print("-" * 40)

            # 获取持仓
            ret, positions = trade_ctx.position_list_query(trd_env=TrdEnv.SIMULATE)
            if ret == RET_OK and len(positions) > 0:
                print(f"\n持仓列表:")
                print("-" * 70)
                print(f"{'代码':<15} {'名称':<12} {'数量':>10} {'成本价':>10} {'市值':>12}")
                print("-" * 70)
                for _, p in positions.iterrows():
                    print(f"{p['code']:<15} {p['stock_name'][:10]:<12} "
                          f"{p['qty']:>10.0f} {p['cost_price']:>10.2f} {p['market_val']:>12,.2f}")
                print("-" * 70)
            else:
                print("\n持仓: 无")

            print("✅ 账户信息获取成功")
            return True

        except Exception as e:
            print(f"❌ 账户信息获取异常: {e}")
            return False

    def test_simulate_trade(self, market: str = "HK") -> bool:
        """测试模拟交易"""
        print(f"\n{'='*50}")
        print(f"🔄 测试{market}模拟交易")
        print(f"{'='*50}")

        trade_ctx = self.trade_ctx_hk if market == "HK" else self.trade_ctx_us

        # 选择测试股票
        if market == "HK":
            symbol = "HK.00700"  # 腾讯
            qty = 100  # 一手
        else:
            symbol = "US.AAPL"  # 苹果
            qty = 1  # 一股

        try:
            # 获取当前价格
            ret, quote = self.quote_ctx.get_market_snapshot([symbol])
            if ret != RET_OK:
                print(f"❌ 获取行情失败: {quote}")
                return False

            current_price = quote.iloc[0]['last_price']
            print(f"\n测试股票: {symbol}")
            print(f"当前价格: {current_price:.2f}")
            print(f"测试数量: {qty}")

            # 确认测试
            print("\n⚠️  即将进行模拟交易测试 (买入后立即卖出)")
            confirm = input("是否继续? (y/n): ").strip().lower()
            if confirm != 'y':
                print("已取消测试")
                return True

            # 测试买入 (限价单)
            print(f"\n📥 测试买入...")
            ret, data = trade_ctx.place_order(
                price=current_price,
                qty=qty,
                code=symbol,
                trd_side=TrdSide.BUY,
                order_type=OrderType.NORMAL,  # 限价单
                trd_env=TrdEnv.SIMULATE
            )

            if ret != RET_OK:
                print(f"❌ 买入下单失败: {data}")
                return False

            order_info = data.iloc[0] if len(data) > 0 else {}
            buy_order_id = order_info.get('order_id', '')
            print(f"✅ 买入订单已提交")
            print(f"   订单ID: {buy_order_id}")
            print(f"   状态: {order_info.get('order_status', 'N/A')}")

            # 等待成交
            print("\n⏳ 等待成交...")
            time.sleep(2)

            # 查询订单状态
            ret, orders = trade_ctx.order_list_query(trd_env=TrdEnv.SIMULATE)
            if ret == RET_OK:
                for _, o in orders.iterrows():
                    if o['order_id'] == buy_order_id:
                        print(f"   订单状态: {o['order_status']}")
                        print(f"   已成交: {o['dealt_qty']:.0f} / {o['qty']:.0f}")
                        break

            # 测试卖出
            print(f"\n📤 测试卖出...")
            ret, data = trade_ctx.place_order(
                price=current_price,
                qty=qty,
                code=symbol,
                trd_side=TrdSide.SELL,
                order_type=OrderType.NORMAL,
                trd_env=TrdEnv.SIMULATE
            )

            if ret != RET_OK:
                print(f"❌ 卖出下单失败: {data}")
                # 尝试取消买入订单
                trade_ctx.modify_order(
                    modify_order_op=2,  # CANCEL
                    order_id=buy_order_id,
                    qty=0, price=0,
                    trd_env=TrdEnv.SIMULATE
                )
                return False

            sell_order_info = data.iloc[0] if len(data) > 0 else {}
            print(f"✅ 卖出订单已提交")
            print(f"   订单ID: {sell_order_info.get('order_id', 'N/A')}")
            print(f"   状态: {sell_order_info.get('order_status', 'N/A')}")

            # 等待成交
            time.sleep(2)

            # 最终账户状态
            print("\n📊 最终账户状态:")
            self.test_account(market)

            print("\n✅ 模拟交易测试完成")
            return True

        except Exception as e:
            print(f"❌ 模拟交易异常: {e}")
            import traceback
            traceback.print_exc()
            return False

    def test_order_book(self, symbol: str = "HK.00700") -> bool:
        """测试买卖盘获取"""
        print(f"\n{'='*50}")
        print(f"📋 测试买卖盘 ({symbol})")
        print(f"{'='*50}")

        try:
            ret, data = self.quote_ctx.get_order_book(symbol, num=5)
            if ret != RET_OK:
                print(f"❌ 获取买卖盘失败: {data}")
                return False

            bid = data.get('Bid', [])
            ask = data.get('Ask', [])

            print("\n买卖盘 (前5档):")
            print("-" * 50)
            print(f"{'卖盘':^25} | {'买盘':^25}")
            print("-" * 50)

            for i in range(min(5, max(len(bid), len(ask)))):
                ask_str = ""
                bid_str = ""
                if i < len(ask):
                    ask_str = f"{ask[i][0]:>10.2f} x {ask[i][1]:>8.0f}"
                if i < len(bid):
                    bid_str = f"{bid[i][0]:>10.2f} x {bid[i][1]:>8.0f}"
                print(f"{ask_str:^25} | {bid_str:^25}")

            print("-" * 50)
            print("✅ 买卖盘获取成功")
            return True

        except Exception as e:
            print(f"❌ 买卖盘获取异常: {e}")
            return False

    def close(self):
        """关闭连接"""
        if self.quote_ctx:
            self.quote_ctx.close()
        if self.trade_ctx_hk:
            self.trade_ctx_hk.close()
        if self.trade_ctx_us:
            self.trade_ctx_us.close()
        print("\n✅ 连接已关闭")

    def run_all_tests(self, market: str = "HK", include_trade: bool = False):
        """运行所有测试"""
        print("\n" + "=" * 60)
        print("  富途牛牛 模拟交易测试")
        print("=" * 60)
        print(f"测试市场: {market}")
        print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        results = {}

        # 1. 连接测试
        if not self.connect():
            print("\n❌ 连接失败，无法继续测试")
            return
        results['连接'] = True

        # 2. 行情测试
        results['行情'] = self.test_quote(market)

        # 3. K线测试
        symbol = "HK.00700" if market == "HK" else "US.AAPL"
        results['K线'] = self.test_kline(symbol)

        # 4. 买卖盘测试
        results['买卖盘'] = self.test_order_book(symbol)

        # 5. 账户测试
        results['账户'] = self.test_account(market)

        # 6. 模拟交易测试（可选）
        if include_trade:
            results['模拟交易'] = self.test_simulate_trade(market)

        # 测试结果汇总
        print("\n" + "=" * 60)
        print("  测试结果汇总")
        print("=" * 60)

        all_passed = True
        for test_name, passed in results.items():
            status = "✅ 通过" if passed else "❌ 失败"
            print(f"  {test_name}: {status}")
            if not passed:
                all_passed = False

        print("=" * 60)
        if all_passed:
            print("🎉 所有测试通过！系统已准备就绪。")
        else:
            print("⚠️  部分测试未通过，请检查配置。")

        # 关闭连接
        self.close()


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="富途牛牛模拟交易测试")
    parser.add_argument(
        "--market", "-m",
        choices=["HK", "US"],
        default="HK",
        help="测试市场 (默认: HK)"
    )
    parser.add_argument(
        "--host",
        default=os.getenv("FUTU_HOST", "127.0.0.1"),
        help="OpenD地址 (默认: 127.0.0.1)"
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=int(os.getenv("FUTU_PORT", "11111")),
        help="OpenD端口 (默认: 11111)"
    )
    parser.add_argument(
        "--trade", "-t",
        action="store_true",
        help="包含模拟交易测试"
    )
    parser.add_argument(
        "--quick", "-q",
        action="store_true",
        help="快速测试（仅测试连接和行情）"
    )

    args = parser.parse_args()

    tester = FutuSimulateTest(host=args.host, port=args.port)

    if args.quick:
        # 快速测试
        if tester.connect():
            tester.test_quote(args.market)
            tester.close()
    else:
        # 完整测试
        tester.run_all_tests(market=args.market, include_trade=args.trade)


if __name__ == "__main__":
    main()
