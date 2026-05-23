"""企业微信 Webhook 入口 — Flask app 启动."""


def run_webhook(host: str | None = None, port: int | None = None):
    """启动企业微信 Webhook 服务."""
    from knowledge_wiki.config import settings

    host = host or settings.webhook_host
    port = port or settings.webhook_port

    from knowledge_wiki.webhook.app import create_app

    app = create_app()
    app.run(host=host, port=port, debug=False)
