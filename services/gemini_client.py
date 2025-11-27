"""
Gemini API Client Module for EkkoScope.
Provides a clean interface to Google's Gemini generative AI.
"""

import logging
from typing import Optional

from services.config import GEMINI_API_KEY, GEMINI_MODEL, GEMINI_ENABLED

logger = logging.getLogger(__name__)

_genai = None
_configured = False


def _configure_gemini():
    """Configure the Gemini client if not already done."""
    global _genai, _configured
    
    if _configured:
        return _genai
    
    if not GEMINI_ENABLED:
        _configured = True
        return None
    
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        _genai = genai
        _configured = True
        logger.info("Gemini API configured successfully")
        return _genai
    except ImportError:
        logger.warning("google-generativeai package not installed. Gemini disabled.")
        _configured = True
        return None
    except Exception as e:
        logger.warning("Failed to configure Gemini: %s", e)
        _configured = True
        return None


def gemini_enabled() -> bool:
    """Check if Gemini is configured and enabled."""
    return GEMINI_ENABLED and _configure_gemini() is not None


def get_gemini_model():
    """Get a Gemini generative model instance."""
    genai = _configure_gemini()
    if genai is None:
        return None
    
    try:
        return genai.GenerativeModel(GEMINI_MODEL)
    except Exception as e:
        logger.warning("Failed to create Gemini model: %s", e)
        return None


def gemini_generate_content(prompt: str) -> Optional[str]:
    """
    Generate content using Gemini.
    
    Args:
        prompt: The prompt to send to Gemini
    
    Returns:
        The generated text content, or None on error
    """
    if not gemini_enabled():
        logger.info("Gemini is disabled. Skipping generation.")
        return None
    
    model = get_gemini_model()
    if model is None:
        return None
    
    try:
        response = model.generate_content(prompt)
        
        if hasattr(response, 'text'):
            return response.text
        
        if hasattr(response, 'candidates') and response.candidates:
            candidate = response.candidates[0]
            if hasattr(candidate, 'content') and candidate.content:
                parts = candidate.content.parts
                if parts:
                    return parts[0].text
        
        logger.warning("Gemini response had unexpected structure")
        return None
        
    except Exception as e:
        logger.warning("Gemini generation failed: %s", e)
        return None


def gemini_generate_json(prompt: str) -> Optional[str]:
    """
    Generate JSON content using Gemini.
    Same as gemini_generate_content but with semantic naming for JSON use cases.
    
    Args:
        prompt: The prompt requesting JSON output
    
    Returns:
        The generated text (should be JSON), or None on error
    """
    return gemini_generate_content(prompt)
