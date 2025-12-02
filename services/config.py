"""
Configuration module for EkkoScope services.
Centralizes environment variable access and feature flags.
"""

import os


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_ENABLED = bool(OPENAI_API_KEY)

PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")
PERPLEXITY_MODEL = os.getenv("PERPLEXITY_MODEL", "sonar-pro")
PERPLEXITY_ENABLED = bool(PERPLEXITY_API_KEY)

GEMINI_API_KEY = os.getenv("GOOGLE_GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
GEMINI_ENABLED = bool(GEMINI_API_KEY)

MAX_VISIBILITY_QUERIES_PER_PROVIDER = int(os.getenv("MAX_VISIBILITY_QUERIES", "10"))

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "ekkobrain")
PINECONE_ENABLED = bool(PINECONE_API_KEY)

EKKOBRAIN_EMBED_MODEL = os.getenv("EKKOBRAIN_EMBED_MODEL", "text-embedding-3-large")
EKKOBRAIN_EMBED_DIMENSIONS = 3072

PINECONE_NAMESPACES = {
    "business": "business-content",
    "competitor": "competitor-content", 
    "patterns": "audit-patterns",
    "missions": "gap-missions",
    "insights": "strategic-insights"
}


def is_perplexity_enabled() -> bool:
    """Check if Perplexity API is configured and enabled."""
    return PERPLEXITY_ENABLED


def is_openai_enabled() -> bool:
    """Check if OpenAI API is configured."""
    return OPENAI_ENABLED


def is_gemini_enabled() -> bool:
    """Check if Gemini API is configured."""
    return GEMINI_ENABLED


def get_enabled_providers() -> list:
    """Get list of enabled visibility providers."""
    providers = []
    if OPENAI_ENABLED:
        providers.append("openai_sim")
    if PERPLEXITY_ENABLED:
        providers.append("perplexity_web")
    if GEMINI_ENABLED:
        providers.append("gemini_sim")
    return providers
