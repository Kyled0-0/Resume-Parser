import anthropic

from app.config import settings


def get_anthropic_client() -> anthropic.Anthropic:
    """Provide a fresh Anthropic client instance for dependency injection."""
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)
