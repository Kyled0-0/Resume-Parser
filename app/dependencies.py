from functools import lru_cache

import anthropic

from app.config import settings


@lru_cache(maxsize=1)
def get_anthropic_client() -> anthropic.AsyncAnthropic:
    """Return a shared async Anthropic client."""
    return anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
