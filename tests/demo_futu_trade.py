#!/usr/bin/env python3
"""
富途牛牛模拟交易交互式演示
提供简单的命令行界面进行模拟交易测试

命令:
  quote <代码>     - 获取行情 (如: quote 00700)
  buy <代码> <数量> - 买入股票 (如: buy 00700 100)
  sell <代码> <数量> - 卖出股票
  account          - 查看账户
  positions        - 查看持仓
  orders           - 查看今日订单
  cancel <订单ID>  - 取消订单
  market [HK/US]   - 切换市场
  help             - 显示帮助
  quit             - 退出
"""

import os
import sys
import readline  # 支持命令行历史

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from dotenv import load_dotenv
load_dotenv()

try:
    from futu import (
        OpenQuoteContext, OpenSecTradeContext,
        TrdEnv, TrdSide, OrderType, TrdMarket,
        RET_OK
    )
except ImportError:
    print("❌ 请先安装 futu-api: pip install futu-api")
    sys.exit(1)


class FutuTradeDemo:
    """富途交易演示"""

    def __init__(self):
        self.host = os.getenv("FUTU_HOST", "127.0.0.1")
        self.port = int(os.getenv("FUTU_PORT", "11111"))
        self.market = "HK"
        self.quote_ctx = None
        self.trade_ctx = None

    def connect(self):
        """连接"""
        print(f"连接到 {self.host}:{self.port}...")
        try:
            self.quote_ctx = OpenQuoteContext(host=self.host, port=self.port)
            self._connect_trade()
            print("✅ 连接成功")
            return True
        except Exception as e:
            print(f"❌ 连接失败: {e}")
            return False

    def _connect_trade(self):
        """连接交易"""
        market = TrdMarket.HK if self.market == "HK" else TrdMarket.US
        self.trade_ctx = OpenSecTradeContext(
            host=self.host,
            port=self.port,
            filter_trdmarket=market
        )

    def _format_symbol(self, code: str) -> str:
        """格式化股票代码"""
        if '.' in code:
            return code
        if self.market == "HK":
            return f"HK.{code.zfill(5)}"
        else:
            return f"US.{code.upper()}"

    def cmd_quote(self, code: str):
        """获取行情"""
        symbol = self._format_symbol(code)
        ret, data = self.quote_ctx.get_market_snapshot([symbol])
        if ret != RET_OK:
            print(f"❌ 失败: {data}")
            return

        if len(data) == 0:
            print(f"❌ 未找到: {symbol}")
            return

        row = data.iloc[0]
        prev_close = row.get('prev_close_price', 0)
        change = ((row['last_price'] - prev_close) / prev_close * 100) if prev_close else 0

        print(f"\n{'='*40}")
        print(f"  {row['code']} - {row['name']}")
        print(f"{'='*40}")
        print(f"  最新价:   {row['last_price']:.2f}")
        print(f"  涨跌幅:   {change:+.2f}%")
        print(f"  开盘价:   {row['open_price']:.2f}")
        print(f"  最高价:   {row['high_price']:.2f}")
        print(f"  最低价:   {row['low_price']:.2f}")
        print(f"  昨收价:   {prev_close:.2f}")
        print(f"  成交量:   {row['volume']:,.0f}")
        print(f"{'='*40}")

    def cmd_buy(self, code: str, qty: int):
        """买入"""
        symbol = self._format_symbol(code)

        # 获取价格
        ret, data = self.quote_ctx.get_market_snapshot([symbol])
        if ret != RET_OK or len(data) == 0:
            print(f"❌ 无法获取 {symbol} 的行情")
            return

        price = data.iloc[0]['last_price']
        name = data.iloc[0]['name']

        print(f"\n买入确认:")
        print(f"  股票: {symbol} ({name})")
        print(f"  数量: {qty}")
        print(f"  价格: {price:.2f}")
        print(f"  金额: {price * qty:,.2f}")

        confirm = input("\n确认买入? (y/n): ").strip().lower()
        if confirm != 'y':
            print("已取消")
            return

        ret, data = self.trade_ctx.place_order(
            price=price,
            qty=qty,
            code=symbol,
            trd_side=TrdSide.BUY,
            order_type=OrderType.NORMAL,
            trd_env=TrdEnv.SIMULATE
        )

        if ret != RET_OK:
            print(f"❌ 下单失败: {data}")
            return

        order = data.iloc[0]
        print(f"\n✅ 买入订单已提交")
        print(f"   订单ID: {order['order_id']}")
        print(f"   状态: {order['order_status']}")

    def cmd_sell(self, code: str, qty: int):
        """卖出"""
        symbol = self._format_symbol(code)

        # 获取价格
        ret, data = self.quote_ctx.get_market_snapshot([symbol])
        if ret != RET_OK or len(data) == 0:
            print(f"❌ 无法获取 {symbol} 的行情")
            return

        price = data.iloc[0]['last_price']
        name = data.iloc[0]['name']

        print(f"\n卖出确认:")
        print(f"  股票: {symbol} ({name})")
        print(f"  数量: {qty}")
        print(f"  价格: {price:.2f}")
        print(f"  金额: {price * qty:,.2f}")

        confirm = input("\n确认卖出? (y/n): ").strip().lower()
        if confirm != 'y':
            print("已取消")
            return

        ret, data = self.trade_ctx.place_order(
            price=price,
            qty=qty,
            code=symbol,
            trd_side=TrdSide.SELL,
            order_type=OrderType.NORMAL,
            trd_env=TrdEnv.SIMULATE
        )

        if ret != RET_OK:
            print(f"❌ 下单失败: {data}")
            return

        order = data.iloc[0]
        print(f"\n✅ 卖出订单已提交")
        print(f"   订单ID: {order['order_id']}")
        print(f"   状态: {order['order_status']}")

    def cmd_account(self):
        """查看账户"""
        ret, funds = self.trade_ctx.accinfo_query(trd_env=TrdEnv.SIMULATE)
        if ret != RET_OK:
            print(f"❌ 获取失败: {funds}")
            return

        if len(funds) == 0:
            print("无账户信息")
            return

        f = funds.iloc[0]
        currency = "HKD" if self.market == "HK" else "USD"

        print(f"\n{'='*40}")
        print(f"  模拟账户 ({self.market})")
        print(f"{'='*40}")
        print(f"  总资产:     {f.get('total_assets', 0):>15,.2f} {currency}")
        print(f"  现金:       {f.get('cash', 0):>15,.2f} {currency}")
        print(f"  持仓市值:   {f.get('market_val', 0):>15,.2f} {currency}")
        print(f"  可用资金:   {f.get('avl_withdrawal_cash', 0):>15,.2f} {currency}")
        print(f"{'='*40}")

    def cmd_positions(self):
        """查看持仓"""
        ret, positions = self.trade_ctx.position_list_query(trd_env=TrdEnv.SIMULATE)
        if ret != RET_OK:
            print(f"❌ 获取失败: {positions}")
            return

        if len(positions) == 0:
            print("无持仓")
            return

        print(f"\n{'='*70}")
        print(f"  持仓列表 ({self.market})")
        print(f"{'='*70}")
        print(f"{'代码':<12} {'名称':<10} {'数量':>8} {'可卖':>8} {'成本':>10} {'盈亏%':>8}")
        print(f"{'-'*70}")

        for _, p in positions.iterrows():
            name = p['stock_name'][:8] if p['stock_name'] else 'N/A'
            print(f"{p['code']:<12} {name:<10} {p['qty']:>8.0f} {p['can_sell_qty']:>8.0f} "
                  f"{p['cost_price']:>10.2f} {p['pl_ratio']:>7.2f}%")

        print(f"{'='*70}")

    def cmd_orders(self):
        """查看订单"""
        ret, orders = self.trade_ctx.order_list_query(trd_env=TrdEnv.SIMULATE)
        if ret != RET_OK:
            print(f"❌ 获取失败: {orders}")
            return

        if len(orders) == 0:
            print("今日无订单")
            return

        print(f"\n{'='*90}")
        print(f"  今日订单 ({self.market})")
        print(f"{'='*90}")
        print(f"{'订单ID':<15} {'代码':<12} {'方向':<6} {'数量':>8} {'价格':>10} {'状态':<15}")
        print(f"{'-'*90}")

        for _, o in orders.iterrows():
            side = "买入" if "BUY" in str(o['trd_side']) else "卖出"
            print(f"{o['order_id']:<15} {o['code']:<12} {side:<6} "
                  f"{o['qty']:>8.0f} {o['price']:>10.2f} {o['order_status']:<15}")

        print(f"{'='*90}")

    def cmd_cancel(self, order_id: str):
        """取消订单"""
        ret, data = self.trade_ctx.modify_order(
            modify_order_op=2,  # CANCEL
            order_id=order_id,
            qty=0, price=0,
            trd_env=TrdEnv.SIMULATE
        )

        if ret != RET_OK:
            print(f"❌ 取消失败: {data}")
            return

        print(f"✅ 订单 {order_id} 已取消")

    def cmd_market(self, market: str):
        """切换市场"""
        market = market.upper()
        if market not in ["HK", "US"]:
            print("❌ 无效市场，请使用 HK 或 US")
            return

        self.market = market
        self._connect_trade()
        print(f"✅ 已切换到 {market} 市场")

    def cmd_help(self):
        """显示帮助"""
        print(__doc__)

    def run(self):
        """运行交互式界面"""
        print("\n" + "=" * 50)
        print("  富途牛牛 模拟交易演示")
        print("=" * 50)
        print("输入 'help' 查看命令列表")
        print("输入 'quit' 退出")

        if not self.connect():
            return

        while True:
            try:
                prompt = f"[{self.market}] > "
                cmd_line = input(prompt).strip()

                if not cmd_line:
                    continue

                parts = cmd_line.split()
                cmd = parts[0].lower()
                args = parts[1:]

                if cmd in ['quit', 'exit', 'q']:
                    break
                elif cmd == 'help':
                    self.cmd_help()
                elif cmd == 'quote' and len(args) >= 1:
                    self.cmd_quote(args[0])
                elif cmd == 'buy' and len(args) >= 2:
                    self.cmd_buy(args[0], int(args[1]))
                elif cmd == 'sell' and len(args) >= 2:
                    self.cmd_sell(args[0], int(args[1]))
                elif cmd == 'account':
                    self.cmd_account()
                elif cmd in ['positions', 'pos']:
                    self.cmd_positions()
                elif cmd == 'orders':
                    self.cmd_orders()
                elif cmd == 'cancel' and len(args) >= 1:
                    self.cmd_cancel(args[0])
                elif cmd == 'market' and len(args) >= 1:
                    self.cmd_market(args[0])
                else:
                    print("❌ 无效命令，输入 'help' 查看帮助")

            except KeyboardInterrupt:
                print("\n")
                break
            except ValueError as e:
                print(f"❌ 参数错误: {e}")
            except Exception as e:
                print(f"❌ 错误: {e}")

        # 关闭连接
        if self.quote_ctx:
            self.quote_ctx.close()
        if self.trade_ctx:
            self.trade_ctx.close()
        print("\n再见!")


def main():
    demo = FutuTradeDemo()
    demo.run()


if __name__ == "__main__":
    main()
