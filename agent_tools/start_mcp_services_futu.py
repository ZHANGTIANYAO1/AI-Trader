#!/usr/bin/env python3
"""
富途牛牛 MCP 服务启动脚本
启动富途交易和行情相关的MCP服务
"""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


class FutuMCPServiceManager:
    def __init__(self):
        self.services = {}
        self.running = True

        # 设置默认端口
        self.ports = {
            "math": int(os.getenv("MATH_HTTP_PORT", "8000")),
            "search": int(os.getenv("SEARCH_HTTP_PORT", "8004")),
            "futu_trade": int(os.getenv("FUTU_TRADE_HTTP_PORT", "8006")),
            "futu_price": int(os.getenv("FUTU_PRICE_HTTP_PORT", "8007")),
        }

        # 服务配置
        mcp_server_dir = os.path.dirname(os.path.abspath(__file__))
        self.service_configs = {
            "math": {
                "script": os.path.join(mcp_server_dir, "tool_math.py"),
                "name": "Math",
                "port": self.ports["math"],
            },
            "search": {
                "script": os.path.join(mcp_server_dir, "tool_alphavantage_news.py"),
                "name": "Search",
                "port": self.ports["search"],
            },
            "futu_trade": {
                "script": os.path.join(mcp_server_dir, "tool_futu_trade.py"),
                "name": "FutuTrade",
                "port": self.ports["futu_trade"],
            },
            "futu_price": {
                "script": os.path.join(mcp_server_dir, "tool_futu_price.py"),
                "name": "FutuPrice",
                "port": self.ports["futu_price"],
            },
        }

        # 创建日志目录
        self.log_dir = Path(os.path.dirname(mcp_server_dir)) / "logs"
        self.log_dir.mkdir(exist_ok=True)

        # 设置信号处理
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

    def signal_handler(self, signum, frame):
        """处理中断信号"""
        print("\n🛑 收到停止信号，正在关闭所有服务...")
        self.stop_all_services()
        sys.exit(0)

    def is_port_available(self, port):
        """检查端口是否可用"""
        import socket

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(("localhost", port))
            sock.close()
            return result != 0
        except:
            return False

    def check_futu_opend(self):
        """检查富途OpenD是否运行"""
        futu_host = os.getenv("FUTU_HOST", "127.0.0.1")
        futu_port = int(os.getenv("FUTU_PORT", "11111"))

        import socket

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((futu_host, futu_port))
            sock.close()
            return result == 0
        except:
            return False

    def check_port_conflicts(self):
        """检查端口冲突"""
        conflicts = []
        for service_id, config in self.service_configs.items():
            port = config["port"]
            if not self.is_port_available(port):
                conflicts.append((config["name"], port))

        if conflicts:
            print("⚠️  检测到端口冲突:")
            for name, port in conflicts:
                print(f"   - {name}: 端口 {port} 已被占用")

            response = input("\n❓ 是否自动查找可用端口? (y/n): ")
            if response.lower() == "y":
                for service_id, config in self.service_configs.items():
                    port = config["port"]
                    if not self.is_port_available(port):
                        new_port = port
                        while not self.is_port_available(new_port):
                            new_port += 1
                            if new_port > port + 100:
                                print(f"❌ 无法为 {config['name']} 找到可用端口")
                                return False
                        print(f"   ✅ {config['name']}: 端口从 {port} 改为 {new_port}")
                        config["port"] = new_port
                        self.ports[service_id] = new_port
                return True
            else:
                print("\n💡 提示: 请停止占用端口的服务或修改端口配置")
                return False
        return True

    def start_service(self, service_id, config):
        """启动单个服务"""
        script_path = config["script"]
        service_name = config["name"]
        port = config["port"]

        if not Path(script_path).exists():
            print(f"❌ 脚本文件不存在: {script_path}")
            return False

        try:
            log_file = self.log_dir / f"{service_id}.log"
            with open(log_file, "w") as f:
                process = subprocess.Popen(
                    [sys.executable, script_path],
                    stdout=f,
                    stderr=subprocess.STDOUT,
                    cwd=os.getcwd(),
                )

            self.services[service_id] = {
                "process": process,
                "name": service_name,
                "port": port,
                "log_file": log_file,
            }

            print(f"✅ {service_name} 服务已启动 (PID: {process.pid}, 端口: {port})")
            return True

        except Exception as e:
            print(f"❌ 启动 {service_name} 服务失败: {e}")
            return False

    def check_service_health(self, service_id):
        """检查服务健康状态"""
        if service_id not in self.services:
            return False

        service = self.services[service_id]
        process = service["process"]
        port = service["port"]

        if process.poll() is not None:
            return False

        try:
            import socket

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(("localhost", port))
            sock.close()
            return result == 0
        except:
            return False

    def start_all_services(self):
        """启动所有服务"""
        print("🚀 启动富途 MCP 服务...")
        print("=" * 50)

        # 检查富途OpenD
        print("\n🔍 检查富途OpenD连接...")
        if self.check_futu_opend():
            print("✅ 富途OpenD已连接")
        else:
            print("⚠️  警告: 富途OpenD未运行或无法连接")
            print("   请确保富途牛牛OpenD客户端已启动")
            print(f"   默认地址: {os.getenv('FUTU_HOST', '127.0.0.1')}:{os.getenv('FUTU_PORT', '11111')}")

        # 检查端口冲突
        if not self.check_port_conflicts():
            print("\n❌ 由于端口冲突无法启动服务")
            return

        print(f"\n📊 端口配置:")
        for service_id, config in self.service_configs.items():
            print(f"  - {config['name']}: {config['port']}")

        print("\n🔄 启动服务...")

        success_count = 0
        for service_id, config in self.service_configs.items():
            if self.start_service(service_id, config):
                success_count += 1

        if success_count == 0:
            print("\n❌ 没有服务启动成功")
            return

        print("\n⏳ 等待服务启动...")
        time.sleep(3)

        print("\n🔍 检查服务状态...")
        healthy_count = self.check_all_services()

        if healthy_count > 0:
            print(f"\n🎉 {healthy_count}/{len(self.services)} 个MCP服务正在运行!")
            self.print_service_info()
            self.keep_alive()
        else:
            print("\n❌ 所有服务启动失败")
            self.stop_all_services()

    def check_all_services(self):
        """检查所有服务状态"""
        healthy_count = 0
        for service_id, service in self.services.items():
            if self.check_service_health(service_id):
                print(f"✅ {service['name']} 服务运行正常")
                healthy_count += 1
            else:
                print(f"❌ {service['name']} 服务启动失败")
                print(f"   请查看日志: {service['log_file']}")
        return healthy_count

    def print_service_info(self):
        """打印服务信息"""
        print("\n📋 服务信息:")
        for service_id, service in self.services.items():
            print(f"  - {service['name']}: http://localhost:{service['port']} (PID: {service['process'].pid})")

        print(f"\n📁 日志文件位置: {self.log_dir.absolute()}")
        print("\n🛑 按 Ctrl+C 停止所有服务")

    def keep_alive(self):
        """保持服务运行"""
        try:
            while self.running:
                time.sleep(5)

                stopped_services = []
                for service_id, service in self.services.items():
                    if service["process"].poll() is not None:
                        stopped_services.append(service["name"])

                if stopped_services:
                    print(f"\n⚠️  以下服务意外停止: {', '.join(stopped_services)}")
                    print(f"📋 活跃服务: {len(self.services) - len(stopped_services)}/{len(self.services)}")

                    if len(stopped_services) == len(self.services):
                        print("❌ 所有服务已停止，正在关闭...")
                        self.running = False
                        break

        except KeyboardInterrupt:
            pass
        finally:
            self.stop_all_services()

    def stop_all_services(self):
        """停止所有服务"""
        print("\n🛑 停止所有服务...")

        for service_id, service in self.services.items():
            try:
                service["process"].terminate()
                service["process"].wait(timeout=5)
                print(f"✅ {service['name']} 服务已停止")
            except subprocess.TimeoutExpired:
                service["process"].kill()
                print(f"🔨 {service['name']} 服务强制停止")
            except Exception as e:
                print(f"❌ 停止 {service['name']} 服务时出错: {e}")

        print("✅ 所有服务已停止")

    def status(self):
        """显示服务状态"""
        print("📊 富途 MCP 服务状态检查")
        print("=" * 30)

        # 检查富途OpenD
        print("\n🔍 富途OpenD状态:")
        if self.check_futu_opend():
            print("   ✅ 已连接")
        else:
            print("   ❌ 未连接")

        print("\n🔍 MCP服务状态:")
        for service_id, config in self.service_configs.items():
            if service_id in self.services:
                if self.check_service_health(service_id):
                    print(f"   ✅ {config['name']} 运行正常 (端口: {config['port']})")
                else:
                    print(f"   ❌ {config['name']} 状态异常 (端口: {config['port']})")
            else:
                if not self.is_port_available(config["port"]):
                    print(f"   ⚠️  {config['name']} 端口被占用 (端口: {config['port']})")
                else:
                    print(f"   ❌ {config['name']} 未启动 (端口: {config['port']})")


def main():
    """主函数"""
    if len(sys.argv) > 1 and sys.argv[1] == "status":
        manager = FutuMCPServiceManager()
        manager.status()
    else:
        manager = FutuMCPServiceManager()
        manager.start_all_services()


if __name__ == "__main__":
    main()
