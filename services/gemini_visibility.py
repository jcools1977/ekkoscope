"""
Gemini Simulated Assistant Visibility Provider for EkkoScope.
Asks Gemini to simulate an AI assistant answer to see which brands it would recommend.
"""

import json
import logging
from typing import List, Dict, Any

from services.gemini_client import gemini_generate_json, gemini_enabled
from services.visibility_models import BrandHit, ProviderVisibility

logger = logging.getLogger(__name__)


def build_gemini_visibility_prompt(
    business_name: str,
    primary_domain: str,
    regions: List[str],
    query: str
) -> str:
    """
    Build a prompt for Gemini to simulate an AI assistant recommendation.
    """
    regions_str = ", ".join(regions) if regions else "United States"
    
    prompt = f"""You are a helpful AI assistant answering user questions about businesses and services.

A user asks: "{query}"

Context: The user is in the {regions_str} area.

Please recommend businesses or brands that would help with this query. Provide up to 5 recommendations.

IMPORTANT: Respond in STRICT JSON format only, matching this exact structure:
{{
  "recommended_brands": [
    {{"name": "Business Name", "url": "https://example.com", "reason": "Brief reason why recommended"}}
  ],
  "target_business_mentioned": false,
  "target_position": null
}}

No markdown formatting, no extra text - just the JSON object."""

    return prompt


def parse_gemini_response(raw: str, business_name: str) -> Dict[str, Any]:
    """
    Parse Gemini's JSON response.
    """
    if not raw:
        return {"recommended_brands": [], "target_found": False}
    
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
        
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()
        
        data = json.loads(raw)
        
        recommended = data.get("recommended_brands", [])
        target_found = data.get("target_business_mentioned", False)
        target_position = data.get("target_position")
        
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
        logger.warning("Could not parse Gemini visibility JSON: %s - Raw: %r", e, raw[:200] if raw else "")
        return {"recommended_brands": [], "target_found": False}


def run_gemini_visibility_for_queries(
    business_name: str,
    primary_domain: str,
    regions: List[str],
    queries_with_intent: List[Dict[str, Any]]
) -> List[ProviderVisibility]:
    """
    Run Gemini simulated assistant visibility probe for each query.
    
    Args:
        business_name: Name of the target business
        primary_domain: Business website URL
        regions: Geographic regions
        queries_with_intent: List of dicts with 'query' and 'intent' keys
    
    Returns:
        List of ProviderVisibility objects
    """
    if not gemini_enabled():
        logger.info("Gemini visibility probe skipped - not enabled")
        return []
    
    results: List[ProviderVisibility] = []
    
    for item in queries_with_intent:
        query = item.get("query", "")
        intent = item.get("intent")
        
        if not query:
            continue
        
        try:
            prompt = build_gemini_visibility_prompt(
                business_name, primary_domain, regions, query
            )
            
            raw = gemini_generate_json(prompt)
            
            if raw is None:
                results.append(ProviderVisibility(
                    provider="gemini_sim",
                    query=query,
                    intent=intent,
                    recommended_brands=[],
                    target_found=False,
                    success=False
                ))
                continue
            
            parsed = parse_gemini_response(raw, business_name)
            
            recommended_brands = [
                BrandHit(
                    name=rec.get("name", "Unknown"),
                    url=rec.get("url"),
                    reason=rec.get("reason")
                )
                for rec in parsed.get("recommended_brands", [])
            ]
            
            results.append(ProviderVisibility(
                provider="gemini_sim",
                query=query,
                intent=intent,
                recommended_brands=recommended_brands,
                target_found=parsed.get("target_found", False),
                target_position=parsed.get("target_position"),
                raw_response=raw,
                success=True
            ))
            
        except Exception as e:
            logger.warning("Gemini visibility probe failed for query '%s': %s", query, e)
            results.append(ProviderVisibility(
                provider="gemini_sim",
                query=query,
                intent=intent,
                recommended_brands=[],
                target_found=False,
                success=False
            ))
    
    return results
