"""CLI 命令解析."""

import argparse
import sys


def cli():
    """命令行解析入口."""
    parser = argparse.ArgumentParser(
        prog="kw-server",
        description="knowledge-wiki 服务管理",
    )
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # serve — 启动 MCP Server
    serve_parser = subparsers.add_parser("serve", help="启动 MCP Server")
    serve_parser.add_argument(
        "--host", type=str, default=None, help="监听地址（默认 127.0.0.1）"
    )
    serve_parser.add_argument(
        "--port", type=int, default=None, help="监听端口（默认 9300）"
    )

    # webhook — 启动企业微信 Webhook
    webhook_parser = subparsers.add_parser("webhook", help="启动企业微信 Webhook")
    webhook_parser.add_argument(
        "--host", type=str, default=None, help="监听地址（默认 127.0.0.1）"
    )
    webhook_parser.add_argument(
        "--port", type=int, default=None, help="监听端口（默认 9400）"
    )

    args = parser.parse_args()

    if args.command == "serve":
        from knowledge_wiki.app.server import run_server

        run_server(host=args.host, port=args.port)

    elif args.command == "webhook":
        from knowledge_wiki.app.webhook import run_webhook

        run_webhook(host=args.host, port=args.port)

    else:
        parser.print_help()
        sys.exit(1)
