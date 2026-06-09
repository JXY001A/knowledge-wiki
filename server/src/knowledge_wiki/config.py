"""集中环境变量管理，pydantic-settings 校验."""

from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """全局配置，从环境变量 / .env 文件加载."""

    # wiki 根目录
    wiki_root: Path = Path.home() / "code" / "knowledge-wiki"

    # 企业微信
    wecom_token: str = ""
    wecom_aes_key: str = ""  # Base64 编码的 AES Key
    wecom_corp_id: str = ""
    wecom_secret: str = ""
    wecom_agent_id: str = "1000002"

    # DeepSeek API
    deepseek_api_key: str = ""

    # MCP Server
    mcp_host: str = "127.0.0.1"
    mcp_port: int = 9300

    # Webhook
    webhook_host: str = "0.0.0.0"
    webhook_port: int = 9400

    # Ollama
    ollama_base_url: str = "http://localhost:11434"

    # LLM 模型选择（统一配置，避免各模块硬编码）
    ollama_model_query: str = "qwen2.5:3b"      # 知识问答
    ollama_model_classify: str = "llama3.2:1b"   # 意图分类（小模型快）
    deepseek_model_ingest: str = "deepseek-v4-pro"  # 内容摄取（高质量）
    deepseek_model_eval: str = "deepseek-chat"   # 回答评估

    # Retrieval v2 — 新检索流水线开关（False 时回退旧实现）
    use_new_retrieval: bool = True

    model_config = {"env_prefix": "", "extra": "ignore", "env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
