"""
RETORNA — Configuración de la aplicación.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Supabase
    supabase_url: str = ""
    supabase_key: str = ""

    # Anthropic
    anthropic_api_key: str = ""

    # Telegram Bot
    telegram_bot_token: str = ""
    telegram_bot_token_gerencia: str = ""
    telegram_webhook_secret: str = ""
    clave_gerencia: str = "gerencia2026"
    admin_telegram_ids: str = ""

    # Aplicación
    app_env: str = "dev"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "info"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
