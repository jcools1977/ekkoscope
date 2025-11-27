"""
OpenAI Simulated Assistant Visibility Provider for EkkoScope.
Asks OpenAI to simulate a ChatGPT-style answer to see which brands it would recommend.
"""

import json
import logging
from typing import List, Dict, Any, Optional
from openai import OpenAI

from services.config import OPENAI_API_KEY, OPENAI_MODEL, OPENAI_ENABLED
from services.visibility_models import BrandHit, ProviderVisibility

logger = logging.getLogger(__name__)


def get_openai_client() -> Optional[OpenAI]:
    """Get an OpenAI client. Returns None if not configured."""
    if not OPENAI_ENABLED:
        return None
    return OpenAI(api_key=OPENAI_API_KEY)


def build_openai_visibility_prompt(
    business_name: str,
    primary_domain: str,
    regions: List[str],
    query: str
) -> List[Dict[str, str]]:
    """
    Build messages for OpenAI to simulate a ChatGPT-style recommendation.
    """
    regions_str = ", ".join(regions) if regions else "United States"
    
    system_msg = {
        "role": "system",
        "content": (
            "You are a helpful AI assistant answering user questions about businesses and services. "
            "When asked for recommendations, provide helpful suggestions based on your knowledge. "
            "Always respond in STRICT JSON format matching this structure:\n"
            "{\n"
            "  \"recommended_brands\": [{\"name\": \"Business Name\", \"url\": \"https://example.com\", \"reason\": \"Brief reason\"}],\n"
            "  \"target_business_mentioned\": false,\n"
            "  \"target_position\": null\n"
            "}\n"
            "List up to 5 recommendations. No extra commentary, just JSON."
        )
    }
    
    user_msg = {
        "role": "user",
        "content": (
            f"I'm looking for help with this: \"{query}\"\n\n"
            f"Context: I'm in the {regions_str} area. "
            "Which businesses or brands would you recommend for this? "
            "Please list the top recommendations with their websites if known."
        )
    }
    
    return [system_msg, user_msg]


def parse_openai_response(raw: str, business_name: str) -> Dict[str, Any]:
    """
    Parse OpenAI's JSON response.
    """
    if not raw:
        return {"recommended_brands": [], "target_found": False, "target_position": None}
    
    try:
        if "```json" in raw:
            start = raw.find("```json") + 7
            end = raw.find("```", start)
            if end > start:
                raw = raw[start:end].strip()
        elif "```" in raw:
            start = raw.find("```") + 3
            end = raw.find("```", start)
            if end > start:
                raw = raw[start:end].strip()
        
        data = json.loads(raw)
        
        recommended = data.get("recommended_brands", [])
        target_found = data.get("target_business_mentioned", False)
        target_position = data.get("target_position")
        
        if target_position is not None:
            if isinstance(target_position, int):
                pass
            elif isinstance(target_position, str) and target_position.isdigit():
                target_position = int(target_position)
            else:
                target_position = None
        
        if not target_found and recommended:
            for i, rec in enumerate(recommended):
                name = rec.get("name", "").lower()
                url = rec.get("url", "").lower()
                if business_name.lower() in name or business_name.lower() in url:
                    target_found = True
                    target_position = i + 1
                    break
        
        return {
            "recommended_brands": recommended,
            "target_found": target_found,
            "target_position": target_position
        }
    except json.JSONDecodeError as e:
        logger.warning("Could not parse OpenAI visibility JSON: %s", e)
        return {"recommended_brands": [], "target_found": False, "target_position": None}


def run_openai_visibility_for_queries(
    business_name: str,
    primary_domain: str,
    regions: List[str],
    queries_with_intent: List[Dict[str, Any]]
) -> List[ProviderVisibility]:
    """
    Run OpenAI simulated assistant visibility probe for each query.
    
    Args:
        business_name: Name of the target business
        primary_domain: Business website URL
        regions: Geographic regions
        queries_with_intent: List of dicts with 'query' and 'intent' keys
    
    Returns:
        List of ProviderVisibility objects
    """
    if not OPENAI_ENABLED:
        logger.info("OpenAI visibility probe skipped - not enabled")
        return []
    
    client = get_openai_client()
    if not client:
        return []
    
    results: List[ProviderVisibility] = []
    
    for item in queries_with_intent:
        query = item.get("query", "")
        intent = item.get("intent")
        
        if not query:
            continue
        
        try:
            messages = build_openai_visibility_prompt(
                business_name, primary_domain, regions, query
            )
            
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=messages,
                temperature=0.3,
                max_tokens=500
            )
            
            raw = response.choices[0].message.content if response.choices else None
            parsed = parse_openai_response(raw, business_name)
            
            recommended_brands = [
                BrandHit(
                    name=rec.get("name", "Unknown"),
                    url=rec.get("url"),
                    reason=rec.get("reason")
                )
                for rec in parsed.get("recommended_brands", [])
            ]
            
            results.append(ProviderVisibility(
                provider="openai_sim",
                query=query,
                intent=intent,
                recommended_brands=recommended_brands,
                target_found=parsed.get("target_found", False),
                target_position=parsed.get("target_position"),
                raw_response=raw,
                success=True
            ))
            
        except Exception as e:
            logger.warning("OpenAI visibility probe failed for query '%s': %s", query, e)
            results.append(ProviderVisibility(
                provider="openai_sim",
                query=query,
                intent=intent,
                recommended_brands=[],
                target_found=False,
                success=False
            ))
    
    return results
