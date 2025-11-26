"""
Configuration module for EkkoScope services.
Centralizes environment variable access and feature flags.
"""

import os


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")
PERPLEXITY_MODEL = os.getenv("PERPLEXITY_MODEL", "sonar-pro")
PERPLEXITY_ENABLED = bool(PERPLEXITY_API_KEY)


def is_perplexity_enabled() -> bool:
    """Check if Perplexity API is configured and enabled."""
    return PERPLEXITY_ENABLED


def is_openai_enabled() -> bool:
    """Check if OpenAI API is configured."""
    return bool(OPENAI_API_KEY)
