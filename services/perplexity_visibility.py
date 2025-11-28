"""
Perplexity Visibility Probe Service for EkkoScope.
Uses Perplexity's real-time web search to check current AI/web visibility.
"""

import json
import logging
from typing import List, Dict, Any, Optional

from services.perplexity_client import call_perplexity_chat
from services.config import PERPLEXITY_ENABLED
from services.visibility_models import BrandHit, ProviderVisibility

logger = logging.getLogger(__name__)


def build_perplexity_visibility_prompt(
    business_name: str,
    primary_domain: str,
    regions: List[str],
    query: str
) -> List[Dict[str, str]]:
    """
    Build a messages array for Perplexity that:
    - Explains that it should perform real-time web search
    - Asks it to answer in strict JSON describing which businesses appear and why
    
    Args:
        business_name: Name of the business being analyzed
        primary_domain: Primary website URL
        regions: Geographic regions the business operates in
        query: The GEO query to test
    
    Returns:
        List of message dicts for the Perplexity API
    """
    system_msg = {
        "role": "system",
        "content": (
            "You are an AI visibility analyst. Use real-time web search to see "
            "which businesses/websites are recommended for the user's query. "
            "Answer in STRICT JSON ONLY matching this exact structure:\n"
            "{\n"
            "  \"recommended_brands\": [{\"name\": \"Business Name\", \"url\": \"https://example.com\", \"reason\": \"Why recommended\"}],\n"
            "  \"target_business_found\": true,\n"
            "  \"target_position\": 2,\n"
            "  \"summary\": \"Brief summary of visibility findings\"\n"
            "}\n"
            "No extra commentary, just JSON."
        )
    }

    regions_str = ", ".join(regions) if regions else "unknown"
    user_content = (
        f"Business we are analyzing: {business_name} "
        f"(website: {primary_domain}). "
        f"Business regions: {regions_str}. "
        f"User query: \"{query}\"\n\n"
        "Question: Based on your real-time search, which businesses are most often "
        "recommended or visible for this query? Include the target business if it appears. "
        "List up to 5 top recommendations."
    )

    user_msg = {"role": "user", "content": user_content}
    return [system_msg, user_msg]


def parse_perplexity_response(raw: str) -> Optional[Dict[str, Any]]:
    """
    Parse Perplexity's JSON response, handling common formatting issues.
    
    Args:
        raw: Raw response string from Perplexity
    
    Returns:
        Parsed dict or None if parsing fails
    """
    if not raw:
        return None
    
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
        
        return json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning("Could not parse Perplexity JSON: %s - Raw: %r", e, raw[:200])
        return None


def run_perplexity_visibility_probe(
    business_name: str,
    primary_domain: str,
    regions: List[str],
    queries: List[str],
) -> Dict[str, Any]:
    """
    For each query, call Perplexity and try to parse the JSON result.
    
    Args:
        business_name: Name of the business being analyzed
        primary_domain: Primary website URL
        regions: Geographic regions the business operates in
        queries: List of GEO queries to test
    
    Returns:
        Dict with structure:
        {
            "enabled": bool,
            "queries": [
                {
                    "query": str,
                    "raw_answer": str or None,
                    "data": parsed dict or None,
                    "success": bool
                },
                ...
            ],
            "summary": {
                "total_queries": int,
                "successful_probes": int,
                "target_found_count": int,
                "top_competitors": [{"name": str, "count": int}, ...]
            }
        }
    """
    if not PERPLEXITY_ENABLED:
        logger.info("Perplexity visibility probe skipped - not enabled")
        return {
            "enabled": False,
            "queries": [],
            "summary": None
        }
    
    results: List[Dict[str, Any]] = []
    all_competitors: Dict[str, int] = {}
    target_found_count = 0
    successful_probes = 0

    for q in queries:
        messages = build_perplexity_visibility_prompt(
            business_name, primary_domain, regions, q
        )
        raw = call_perplexity_chat(messages)
        
        if raw is None:
            results.append({
                "query": q,
                "raw_answer": None,
                "data": None,
                "success": False
            })
            continue
        
        parsed = parse_perplexity_response(raw)
        success = parsed is not None
        
        if success:
            successful_probes += 1
            
            if parsed.get("target_business_found"):
                target_found_count += 1
            
            recommended = parsed.get("recommended_brands", [])
            for rec in recommended:
                name = rec.get("name", "Unknown")
                if name.lower() != business_name.lower():
                    all_competitors[name] = all_competitors.get(name, 0) + 1
        
        results.append({
            "query": q,
            "raw_answer": raw,
            "data": parsed,
            "success": success
        })

    top_competitors = sorted(
        [{"name": k, "count": v} for k, v in all_competitors.items()],
        key=lambda x: x["count"],
        reverse=True
    )[:10]

    return {
        "enabled": True,
        "queries": results,
        "summary": {
            "total_queries": len(queries),
            "successful_probes": successful_probes,
            "target_found_count": target_found_count,
            "top_competitors": top_competitors
        }
    }


def format_perplexity_visibility_for_genius(
    perplexity_data: Optional[Dict[str, Any]]
) -> str:
    """
    Format Perplexity visibility data into a readable summary for Genius Mode.
    
    Args:
        perplexity_data: Output from run_perplexity_visibility_probe
    
    Returns:
        Formatted string summary for inclusion in Genius Mode prompts
    """
    if not perplexity_data or not perplexity_data.get("enabled"):
        return "Perplexity web-grounded visibility data: NOT AVAILABLE"
    
    summary = perplexity_data.get("summary", {})
    queries = perplexity_data.get("queries", [])
    
    lines = [
        "=== PERPLEXITY WEB-GROUNDED VISIBILITY SNAPSHOT ===",
        f"Total queries probed: {summary.get('total_queries', 0)}",
        f"Successful web searches: {summary.get('successful_probes', 0)}",
        f"Target business found in results: {summary.get('target_found_count', 0)} times",
        "",
        "Top competitors appearing in real-time web/AI results:"
    ]
    
    top_comps = summary.get("top_competitors", [])
    if top_comps:
        for comp in top_comps[:5]:
            lines.append(f"  - {comp['name']}: appeared in {comp['count']} queries")
    else:
        lines.append("  (No competitors identified)")
    
    lines.append("")
    lines.append("Per-query web visibility findings:")
    
    for q_result in queries:
        query = q_result.get("query", "Unknown query")
        data = q_result.get("data")
        
        if not q_result.get("success") or not data:
            lines.append(f"  Query: \"{query}\" - Web search failed or no data")
            continue
        
        found = data.get("target_business_found", False)
        position = data.get("target_position")
        summary_text = data.get("summary", "")
        
        status = "FOUND" if found else "NOT FOUND"
        pos_str = f" (position #{position})" if position else ""
        
        lines.append(f"  Query: \"{query}\"")
        lines.append(f"    Target business: {status}{pos_str}")
        
        recommended = data.get("recommended_brands", [])
        if recommended:
            rec_names = [r.get("name", "?") for r in recommended[:3]]
            lines.append(f"    Top recommendations: {', '.join(rec_names)}")
        
        if summary_text:
            lines.append(f"    Insight: {summary_text[:150]}...")
        
        lines.append("")
    
    return "\n".join(lines)


def run_perplexity_visibility_for_queries(
    business_name: str,
    primary_domain: str,
    regions: List[str],
    queries_with_intent: List[Dict[str, Any]]
) -> List[ProviderVisibility]:
    """
    Run Perplexity web-grounded visibility probe for each query.
    Returns ProviderVisibility objects for the unified visibility system.
    
    Args:
        business_name: Name of the target business
        primary_domain: Business website URL
        regions: Geographic regions
        queries_with_intent: List of dicts with 'query' and 'intent' keys
    
    Returns:
        List of ProviderVisibility objects
    """
    import sys
    print(f"[PERPLEXITY VIS] run_perplexity_visibility_for_queries called, {len(queries_with_intent)} queries")
    sys.stdout.flush()
    
    if not PERPLEXITY_ENABLED:
        print("[PERPLEXITY VIS] Skipped - not enabled")
        sys.stdout.flush()
        logger.info("Perplexity visibility probe skipped - not enabled")
        return []
    
    print(f"[PERPLEXITY VIS] Starting for {len(queries_with_intent)} queries")
    sys.stdout.flush()
    
    results: List[ProviderVisibility] = []
    
    for item in queries_with_intent:
        query = item.get("query", "")
        intent = item.get("intent")
        
        if not query:
            continue
        
        messages = build_perplexity_visibility_prompt(
            business_name, primary_domain, regions, query
        )
        raw = call_perplexity_chat(messages)
        
        if raw is None:
            results.append(ProviderVisibility(
                provider="perplexity_web",
                query=query,
                intent=intent,
                recommended_brands=[],
                target_found=False,
                success=False
            ))
            continue
        
        parsed = parse_perplexity_response(raw)
        
        if parsed is None:
            results.append(ProviderVisibility(
                provider="perplexity_web",
                query=query,
                intent=intent,
                recommended_brands=[],
                target_found=False,
                raw_response=raw,
                success=False
            ))
            continue
        
        recommended_brands = [
            BrandHit(
                name=rec.get("name", "Unknown"),
                url=rec.get("url"),
                reason=rec.get("reason")
            )
            for rec in parsed.get("recommended_brands", [])
        ]
        
        target_found = parsed.get("target_business_found", False)
        target_position = parsed.get("target_position")
        
        if not target_found and recommended_brands:
            for i, brand in enumerate(recommended_brands):
                if business_name.lower() in brand.name.lower():
                    target_found = True
                    target_position = i + 1
                    break
        
        results.append(ProviderVisibility(
            provider="perplexity_web",
            query=query,
            intent=intent,
            recommended_brands=recommended_brands,
            target_found=target_found,
            target_position=target_position,
            raw_response=raw,
            success=True
        ))
    
    return results
