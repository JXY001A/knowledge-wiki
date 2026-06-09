# ============================================================================
# CLI 命令解析模块
# ============================================================================
# 本模块是 knowledge-wiki 的命令行入口，负责解析用户输入的终端命令并路由到
# 对应的服务启动函数。使用 Python 标准库 argparse 实现子命令风格的 CLI。
#
# 三函数结构：
#   build_parser() → 纯函数，定义接口（可独立测试）
#   handle(args)   → 纯路由，根据解析结果分发（可独立测试）
#   cli()          → 入口，组装前两步
#
# 流程：
#   终端输入 kw-server <子命令> [--host HOST] [--port PORT]
#     → cli() 调用 build_parser().parse_args()
#     → 子命令为 "serve"   → handle() 懒加载 server 模块，启动 MCP Server
#     → 子命令为 "webhook" → handle() 懒加载 webhook 模块，启动企业微信 Bot
#     → 无子命令           → handle() 打印帮助信息，退出码 1
#
# 使用示例：
#   kw-server serve                    # 启动 MCP Server（默认 127.0.0.1:9300）
#   kw-server serve --port 9301        # 自定义端口
#   kw-server webhook --host 0.0.0.0   # 启动 Webhook（监听所有网卡）
# ============================================================================

# argparse：Python 标准库，用于定义并解析命令行参数
import argparse

# sys：Python 标准库，提供 exit() 终止进程
import sys


def build_parser() -> argparse.ArgumentParser:
    """构建 CLI 参数解析器。

    纯函数：只定义接口形状，不解析参数，不执行任何副作用。
    返回值可独立用于单元测试，验证参数定义是否正确。
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

    # ---------- scheduler 子命令 ----------
    scheduler_parser = subparsers.add_parser("scheduler", help="启动定时任务调度器")
    scheduler_parser.add_argument(
        "--no-start", action="store_true", help="仅验证配置，不启动"
    )

    # ---------- db 子命令 ----------
    db_parser = subparsers.add_parser("db", help="数据库管理")
    db_sub = db_parser.add_subparsers(dest="db_action", help="操作")

    db_init = db_sub.add_parser("init", help="初始化 assistant 数据库 schema")
    db_backup = db_sub.add_parser("backup", help="手动备份数据库（SQL dump）")
    db_stats = db_sub.add_parser("stats", help="查看助理数据库统计")
    db_migrate = db_sub.add_parser("migrate", help="执行数据库迁移")

    return parser


def handle(args: argparse.Namespace) -> None:
    """根据解析后的参数路由到对应的服务启动函数。

    纯路由函数：接收已解析的参数对象，执行对应的服务入口。
    模块导入使用懒加载，避免冷启动时加载所有依赖。
    """
    if args.command == "serve":
        # 懒加载：只有用户执行 serve 命令时才导入 server 模块，
        # 避免启动时加载所有模块，降低 CLI 的冷启动延迟
        from knowledge_wiki.entrypoint.server import run_server

        # 将 None 或用户指定的值传入启动函数，由模块内部决定默认值
        run_server(host=args.host, port=args.port)

    elif args.command == "webhook":
        # 懒加载：只有用户执行 webhook 命令时才导入 webhook 模块
        from knowledge_wiki.entrypoint.webhook import run_webhook

        run_webhook(host=args.host, port=args.port)

    elif args.command == "scheduler":
        # 懒加载：调度器 + 后台任务
        from knowledge_wiki.assistant.scheduler import start_scheduler, stop_scheduler, get_scheduler

        if args.no_start:
            scheduler = get_scheduler()
            jobs = scheduler.get_jobs()
            print(f"调度器就绪，{len(jobs)} 个预置 job：")
            for j in sorted(jobs, key=lambda j: j.id):
                print(f"  [{j.id}] {j.name} — {j.next_run_time}")
        else:
            import signal
            import time

            start_scheduler()
            scheduler = get_scheduler()
            jobs = scheduler.get_jobs()
            print(f"调度器已启动，{len(jobs)} 个 job")
            for j in sorted(jobs, key=lambda j: j.id):
                print(f"  [{j.id}] {j.name} — next: {j.next_run_time}")

            # 优雅关闭
            def _shutdown(signum, frame):
                print("\n正在停止调度器...")
                stop_scheduler()
                import sys
                sys.exit(0)

            signal.signal(signal.SIGINT, _shutdown)
            signal.signal(signal.SIGTERM, _shutdown)

            try:
                while True:
                    time.sleep(60)
            except (KeyboardInterrupt, SystemExit):
                pass

    elif args.command == "db":
        # 懒加载：数据库管理操作
        from knowledge_wiki.assistant.db import get_db, init_schema as init_assistant_db

        if args.db_action == "init":
            conn = get_db()
            ver = init_assistant_db(conn)
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
            print(f"数据库 schema 已初始化（v{ver}）")
            print(f"表列表：{', '.join(r[0] for r in tables)}")
            conn.close()

        elif args.db_action == "backup":
            from knowledge_wiki.assistant.backup import backup_database
            print(backup_database())

        elif args.db_action == "stats":
            conn = get_db()
            init_assistant_db(conn)
            tables = ["todos", "reminders", "notes", "bookmarks", "habits"]
            for t in tables:
                count = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                print(f"  {t}: {count}")
            conn.close()

        elif args.db_action == "migrate":
            conn = get_db()
            ver = init_assistant_db(conn)
            print(f"迁移完成，当前版本：v{ver}")
            conn.close()

        else:
            print("用法：kw-server db [init|backup|stats|migrate]")

    else:
        # 未提供任何子命令时，打印帮助信息并退出（退出码 1 表示异常终止）
        # 注意：argparse 在用户输入错误子命令时会在 parse_args() 阶段拦截并 exit，
        # 此分支只处理"没有任何子命令"的情况
        build_parser().print_help()
        sys.exit(1)


def cli():
    """命令行入口。

    本函数由 pyproject.toml 的 [project.scripts] 注册为 kw-server 命令，
    终端执行 kw-server 时直接调用此函数。职责仅是将 build_parser 和 handle
    串联起来。
    """
    # 构建解析器 → 解析 sys.argv → 路由执行
    args = build_parser().parse_args()
    handle(args)
