from functools import lru_cache

import google.generativeai as genai

from app.config import settings


@lru_cache(maxsize=1)
def get_gemini_model() -> genai.GenerativeModel:
    """Return a shared Gemini generative model."""
    genai.configure(api_key=settings.gemini_api_key)
    return genai.GenerativeModel("models/gemini-2.0-flash-lite")
