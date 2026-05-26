# ============================================================================
# CLI 命令解析模块
# ============================================================================
# 本模块是 knowledge-wiki 的命令行入口，负责解析用户输入的终端命令并路由到
# 对应的服务启动函数。使用 Python 标准库 argparse 实现子命令风格的 CLI。
#
# 流程：
#   终端输入 kw-server <子命令> [--host HOST] [--port PORT]
#     → cli() 解析参数并提取子命令名
#     → 子命令为 "serve"   → 懒加载 server 模块，启动 MCP Server
#     → 子命令为 "webhook" → 懒加载 webhook 模块，启动企业微信 Bot
#     → 无子命令           → 打印帮助信息，退出码 1
#
# 使用示例：
#   kw-server serve                    # 启动 MCP Server（默认 127.0.0.1:9300）
#   kw-server serve --port 9301        # 自定义端口
#   kw-server webhook --host 0.0.0.0   # 启动 Webhook（监听所有网卡）
# ============================================================================

# argparse：Python 标准库，用于解析命令行参数
import argparse

# sys：Python 标准库，提供 exit() 终止进程
import sys


def cli():
    """命令行解析入口。

    本函数由 pyproject.toml 的 [project.scripts] 注册为 kw-server 命令，
    终端执行 kw-server 时直接调用此函数。
    """
    # ---------- 根解析器 ----------
    # ArgumentParser 是命令行参数的顶层容器，负责解析原始 sys.argv
    parser = argparse.ArgumentParser(
        prog="kw-server",                      # 程序名，显示在 help 信息的第一行
        description="knowledge-wiki 服务管理",  # 描述文字，显示在 help 的 usage 下方
    )

    # 创建子命令注册器，dest="command" 表示选中的子命令名会存入 args.command
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # ---------- serve 子命令 ----------
    # 注册子命令 "serve"，用于启动 MCP Server（Model Context Protocol 服务端）
    serve_parser = subparsers.add_parser("serve", help="启动 MCP Server")

    # --host 参数：监听地址，字符串类型，不传则为 None（server 模块内部有默认值 127.0.0.1）
    serve_parser.add_argument(
        "--host", type=str, default=None, help="监听地址（默认 127.0.0.1）"
    )

    # --port 参数：监听端口，整数类型，不传则为 None（server 模块内部有默认值 9300）
    serve_parser.add_argument(
        "--port", type=int, default=None, help="监听端口（默认 9300）"
    )

    # ---------- webhook 子命令 ----------
    # 注册子命令 "webhook"，用于启动企业微信 Bot 的 webhook 服务
    webhook_parser = subparsers.add_parser("webhook", help="启动企业微信 Webhook")

    # --host 参数：webhook 的监听地址
    webhook_parser.add_argument(
        "--host", type=str, default=None, help="监听地址（默认 127.0.0.1）"
    )

    # --port 参数：webhook 的监听端口
    webhook_parser.add_argument(
        "--port", type=int, default=None, help="监听端口（默认 9400）"
    )

    # ---------- 参数解析 ----------
    # parse_args() 读取 sys.argv，匹配子命令和参数，返回 Namespace 对象
    args = parser.parse_args()

    # ---------- 命令路由 ----------
    if args.command == "serve":
        # 懒加载：只有用户执行 serve 命令时才导入 server 模块，
        # 避免启动时加载所有模块，降低 CLI 的冷启动延迟
        from knowledge_wiki.app.server import run_server

        # 将 None 或用户指定的值传入启动函数，由模块内部决定默认值
        run_server(host=args.host, port=args.port)

    elif args.command == "webhook":
        # 懒加载：只有用户执行 webhook 命令时才导入 webhook 模块
        from knowledge_wiki.app.webhook import run_webhook

        run_webhook(host=args.host, port=args.port)

    else:
        # 未提供任何子命令时，打印帮助信息并退出（退出码 1 表示异常终止）
        parser.print_help()
        sys.exit(1)
