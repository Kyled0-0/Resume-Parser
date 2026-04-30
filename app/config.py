from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    anthropic_api_key: str
    log_level: str = "INFO"
    max_pdf_size_bytes: int = 10_485_760  # 10MB

    model_config = {"env_file": ".env"}


settings = Settings()
