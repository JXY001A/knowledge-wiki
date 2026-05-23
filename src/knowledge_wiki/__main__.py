"""CLI 入口：python -m knowledge_wiki {serve|webhook}."""


def main():
    """CLI 入口，解析子命令并启动对应服务."""
    from knowledge_wiki.app.cli import cli

    cli()


if __name__ == "__main__":
    main()
