"""
Perplexity API Client Module for EkkoScope.
Uses OpenAI-compatible interface with Perplexity's base URL.
"""

import logging
from typing import List, Dict, Optional, Any
from openai import OpenAI

from services.config import PERPLEXITY_API_KEY, PERPLEXITY_MODEL, PERPLEXITY_ENABLED

logger = logging.getLogger(__name__)


def get_perplexity_client() -> Optional[OpenAI]:
    """
    Get a Perplexity API client using OpenAI-compatible interface.
    Returns None if Perplexity is not configured.
    """
    if not PERPLEXITY_ENABLED:
        return None
    return OpenAI(
        api_key=PERPLEXITY_API_KEY,
        base_url="https://api.perplexity.ai"
    )


def call_perplexity_chat(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    **kwargs
) -> Optional[str]:
    """
    Call Perplexity chat completions and return the assistant's message content.
    
    Args:
        messages: List of message dicts with 'role' and 'content' keys
        model: Optional model override (defaults to PERPLEXITY_MODEL)
        **kwargs: Additional parameters to pass to the API
    
    Returns:
        The assistant's response content, or None on error/disabled
    """
    if not PERPLEXITY_ENABLED:
        logger.info("Perplexity is disabled (no API key). Skipping call.")
        return None

    client = get_perplexity_client()
    if client is None:
        return None

    try:
        call_kwargs = {
            "model": model or PERPLEXITY_MODEL,
            "messages": messages,
            "temperature": 0,
            **kwargs
        }
        resp = client.chat.completions.create(**call_kwargs)
        choice = resp.choices[0] if resp.choices else None
        return choice.message.content if choice and choice.message else None
    except Exception as e:
        logger.warning("Perplexity call failed: %s", e, exc_info=True)
        return None


def call_perplexity_chat_with_citations(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    **kwargs
) -> Optional[Dict[str, Any]]:
    """
    Call Perplexity and return both content and citations if available.
    
    Returns:
        Dict with 'content' and 'citations' keys, or None on error
    """
    if not PERPLEXITY_ENABLED:
        logger.info("Perplexity is disabled (no API key). Skipping call.")
        return None

    client = get_perplexity_client()
    if client is None:
        return None

    try:
        resp = client.chat.completions.create(
            model=model or PERPLEXITY_MODEL,
            messages=messages,
            **kwargs
        )
        choice = resp.choices[0] if resp.choices else None
        if not choice or not choice.message:
            return None
        
        result = {
            "content": choice.message.content,
            "citations": []
        }
        
        if hasattr(resp, 'citations'):
            result["citations"] = resp.citations or []
        
        return result
    except Exception as e:
        logger.warning("Perplexity call failed: %s", e, exc_info=True)
        return None
