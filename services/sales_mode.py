"""
Sales Mode Orchestrator for EkkoScope.
Provides headless teaser audits for cold outreach campaigns.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from services.auto_configure import auto_configure_business
from services.query_generator import generate_teaser_queries
from services.visibility_hub import run_teaser_visibility

logger = logging.getLogger(__name__)


def run_teaser_audit(url: str) -> Dict[str, Any]:
    """
    Run a complete headless teaser audit for a URL.
    
    This is the main entry point for Sales Mode:
    1. Auto-configures business from URL (scrape + LLM inference)
    2. Generates 3 high-impact queries
    3. Runs teaser visibility probe with early exit on 0%
    4. Returns sales packet JSON
    
    Args:
        url: The business website URL to analyze
    
    Returns:
        Sales packet dict ready for cold outreach
    """
    logger.info(f"[SALES MODE] Starting teaser audit for: {url}")
    
    result = {
        "success": False,
        "url": url,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "business_config": None,
        "visibility_result": None,
        "sales_packet": None,
        "error": None
    }
    
    try:
        config = auto_configure_business(url)
        
        if not config.get("success"):
            result["error"] = config.get("error", "Failed to auto-configure business")
            return result
        
        result["business_config"] = config
        
        teaser_queries = generate_teaser_queries(
            category=config.get("category", "services"),
            region=config.get("service_area", "United States"),
            business_type=config.get("business_type", "local_service")
        )
        
        visibility = run_teaser_visibility(
            business_name=config.get("business_name", "Unknown Business"),
            primary_domain=config.get("domain", ""),
            regions=[config.get("service_area", "United States")],
            teaser_queries=teaser_queries,
            early_exit_on_zero=True
        )
        
        result["visibility_result"] = visibility
        
        if visibility.get("error"):
            result["error"] = visibility["error"]
            result["success"] = False
            return result
        
        result["sales_packet"] = build_sales_packet(config, visibility)
        result["success"] = True
        
        logger.info(
            f"[SALES MODE] Complete: {config.get('business_name')} - "
            f"{visibility.get('score_percent', '0%')} visibility"
        )
        
    except Exception as e:
        logger.error(f"[SALES MODE] Teaser audit failed: {e}")
        result["error"] = str(e)
    
    return result


def build_sales_packet(
    config: Dict[str, Any],
    visibility: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Build the lightweight sales packet JSON for cold outreach.
    
    This is the deliverable for sales teams - a minimal JSON
    showing the 0% visibility hook for the prospect.
    
    Args:
        config: Business configuration from auto_configure_business()
        visibility: Results from run_teaser_visibility()
    
    Returns:
        Sales-ready JSON packet
    """
    packet = {
        "business_name": config.get("business_name", "Unknown"),
        "industry": config.get("industry", ""),
        "category": config.get("category", ""),
        "service_area": config.get("service_area", ""),
        "website": config.get("url", config.get("domain", "")),
        "phone": config.get("phone", ""),
        
        "score": visibility.get("score_percent", "0%"),
        "score_numeric": visibility.get("score", 0),
        
        "verdict": _get_verdict(visibility.get("score", 0)),
        
        "competitor_found": None,
        "competitor_screenshot": None,
        
        "missing_query": visibility.get("missing_query"),
        
        "queries_tested": len(visibility.get("queries_tested", [])),
        "providers_used": visibility.get("providers_used", []),
        
        "hook_message": _generate_hook_message(config, visibility),
        
        "inference_confidence": config.get("confidence", "MEDIUM")
    }
    
    top_comp = visibility.get("top_competitor")
    if top_comp:
        packet["competitor_found"] = top_comp.get("name")
    
    return packet


def _get_verdict(score: float) -> str:
    """Get a verdict label based on visibility score."""
    if score == 0:
        return "INVISIBLE"
    elif score < 10:
        return "CRITICAL"
    elif score < 25:
        return "LOW"
    elif score < 50:
        return "MODERATE"
    else:
        return "VISIBLE"


def _generate_hook_message(
    config: Dict[str, Any],
    visibility: Dict[str, Any]
) -> str:
    """
    Generate a compelling hook message for cold outreach.
    """
    business_name = config.get("business_name", "Your business")
    category = config.get("category", "your services")
    service_area = config.get("service_area", "your area")
    score = visibility.get("score", 0)
    competitor = visibility.get("top_competitor", {}).get("name")
    missing_query = visibility.get("missing_query", "")
    
    if score == 0:
        if competitor:
            return (
                f"When customers ask AI assistants for {category} in {service_area}, "
                f"{competitor} is getting recommended — but {business_name} isn't mentioned at all. "
                f"We ran 3 high-value queries and found 0% AI visibility for your business."
            )
        else:
            return (
                f"We tested how AI assistants like ChatGPT respond when customers ask for "
                f"{category} in {service_area}. {business_name} has 0% visibility — "
                f"meaning potential customers using AI search won't find you."
            )
    elif score < 25:
        return (
            f"{business_name} appeared in only {score}% of AI assistant recommendations "
            f"for {category} in {service_area}. Your competitors are capturing the majority "
            f"of AI-driven discovery."
        )
    else:
        return (
            f"{business_name} has {score}% AI visibility for {category} in {service_area}. "
            f"There's opportunity to improve your position in AI recommendations."
        )


def run_batch_teaser_audit(urls: List[str]) -> List[Dict[str, Any]]:
    """
    Run teaser audits for multiple URLs.
    
    Used for batch cold outreach campaigns.
    
    Args:
        urls: List of business website URLs
    
    Returns:
        List of sales packets for each URL
    """
    results = []
    
    for idx, url in enumerate(urls):
        logger.info(f"[SALES MODE] Batch audit {idx+1}/{len(urls)}: {url}")
        
        try:
            result = run_teaser_audit(url)
            results.append(result)
        except Exception as e:
            logger.error(f"[SALES MODE] Batch item failed for {url}: {e}")
            results.append({
                "success": False,
                "url": url,
                "error": str(e)
            })
    
    return results
