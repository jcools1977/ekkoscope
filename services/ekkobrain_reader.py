"""
EkkoBrain Reader for EkkoScope.
Fetches relevant patterns from Pinecone before Genius Mode runs.
Returns context that can be injected into the Genius Mode prompt.
"""

import logging
from typing import Dict, Any, List, Optional

from .database import Business, derive_region_group
from .ekkobrain_pinecone import search_patterns, is_ekkobrain_enabled

logger = logging.getLogger(__name__)


def fetch_ekkobrain_context(
    business: Business,
    queries_with_intent: List[Dict[str, Any]],
    max_patterns: int = 10
) -> Dict[str, Any]:
    """
    Retrieve relevant EkkoBrain patterns for an audit.
    
    Args:
        business: The Business object being audited
        queries_with_intent: List of query dicts with 'query', 'intent'
        max_patterns: Maximum patterns to return per type
    
    Returns:
        Dict with 'blueprint_patterns' and 'task_patterns' lists
    """
    if not is_ekkobrain_enabled():
        return {"blueprint_patterns": [], "task_patterns": [], "enabled": False}
    
    try:
        industry = _extract_industry(business)
        business_type = _normalize_business_type(business.business_type or "")
        regions = business.get_regions()
        region_group = derive_region_group(regions)
        
        intents = list(set(q.get("intent", "informational") for q in queries_with_intent))
        intents_str = ", ".join(intents[:5])
        
        query_text = f"""Patterns for a {business_type} in {industry} serving {region_group},
focusing on intents: {intents_str}.
Looking for page blueprints and roadmap tasks that have worked for similar businesses."""
        
        filter_base = {
            "industry": {"$eq": industry}
        }
        
        all_results = search_patterns(
            query_text=query_text,
            top_k=max_patterns * 3,
            filter=filter_base
        )
        
        if len(all_results) < max_patterns:
            broader_results = search_patterns(
                query_text=query_text,
                top_k=max_patterns * 2,
                filter={"business_type": {"$eq": business_type}}
            )
            
            existing_ids = {r["id"] for r in all_results}
            for r in broader_results:
                if r["id"] not in existing_ids:
                    all_results.append(r)
        
        blueprint_patterns = []
        task_patterns = []
        
        for result in all_results:
            metadata = result.get("metadata", {})
            pattern_type = metadata.get("pattern_type", "")
            score = result.get("score", 0)
            
            if score < 0.5:
                continue
            
            if pattern_type == "blueprint":
                blueprint_patterns.append({
                    "score": score,
                    "industry": metadata.get("industry", ""),
                    "business_type": metadata.get("business_type", ""),
                    "region_group": metadata.get("region_group", ""),
                    "intent_cluster": metadata.get("intent_cluster", ""),
                    "page_type": metadata.get("page_type", "general_page"),
                    "section_count": metadata.get("section_count", 0),
                    "has_cta": metadata.get("has_cta", False)
                })
            elif pattern_type == "task":
                task_patterns.append({
                    "score": score,
                    "industry": metadata.get("industry", ""),
                    "business_type": metadata.get("business_type", ""),
                    "region_group": metadata.get("region_group", ""),
                    "week_number": metadata.get("week_number", 1),
                    "impact": metadata.get("impact", "medium"),
                    "effort": metadata.get("effort", "medium"),
                    "task_type": metadata.get("task_type", "general")
                })
        
        blueprint_patterns = blueprint_patterns[:max_patterns]
        task_patterns = task_patterns[:max_patterns]
        
        logger.info(
            "Fetched EkkoBrain context: %d blueprints, %d tasks",
            len(blueprint_patterns), len(task_patterns)
        )
        
        return {
            "blueprint_patterns": blueprint_patterns,
            "task_patterns": task_patterns,
            "enabled": True,
            "industry_searched": industry,
            "business_type_searched": business_type,
            "region_group_searched": region_group
        }
        
    except Exception as e:
        logger.warning("Failed to fetch EkkoBrain context (non-fatal): %s", e)
        return {"blueprint_patterns": [], "task_patterns": [], "enabled": False}


def format_ekkobrain_context_for_genius(
    ekkobrain_context: Dict[str, Any]
) -> str:
    """
    Format EkkoBrain context into a prompt section for Genius Mode.
    
    PRIVACY: Only abstract pattern types and metadata are included,
    never any tenant-identifying information.
    
    Args:
        ekkobrain_context: Output from fetch_ekkobrain_context()
    
    Returns:
        Formatted string to inject into the Genius Mode prompt
    """
    if not ekkobrain_context.get("enabled", False):
        return ""
    
    blueprint_patterns = ekkobrain_context.get("blueprint_patterns", [])
    task_patterns = ekkobrain_context.get("task_patterns", [])
    
    if not blueprint_patterns and not task_patterns:
        return ""
    
    lines = [
        "\n=== EKKOBRAIN MEMORY (ANONYMIZED PATTERNS) ===",
        "",
        "Here are abstract patterns from past audits of similar businesses.",
        "They contain only structural metadata - no specific business details.",
        "Use these patterns as HIGH-LEVEL INSPIRATION, not templates.",
        ""
    ]
    
    if blueprint_patterns:
        lines.append("BLUEPRINT PATTERNS:")
        for idx, bp in enumerate(blueprint_patterns[:5], 1):
            intent = bp.get("intent_cluster", "general")
            page_type = bp.get("page_type", "general_page")
            industry = bp.get("industry", "")
            btype = bp.get("business_type", "")
            section_count = bp.get("section_count", 0)
            has_cta = bp.get("has_cta", False)
            
            lines.append(f"  {idx}. [{intent}] Page type: {page_type}")
            lines.append(f"     Structure: {section_count} sections, CTA: {'yes' if has_cta else 'no'}")
            lines.append(f"     Context: {btype} in {industry}")
        lines.append("")
    
    if task_patterns:
        lines.append("TASK PATTERNS:")
        for idx, task in enumerate(task_patterns[:5], 1):
            task_type = task.get("task_type", "general")
            week = task.get("week_number", 1)
            impact = task.get("impact", "medium")
            effort = task.get("effort", "medium")
            industry = task.get("industry", "")
            
            lines.append(f"  {idx}. Week {week}: {task_type} task")
            lines.append(f"     Impact: {impact}, Effort: {effort} (from {industry} industry)")
        lines.append("")
    
    lines.extend([
        "USE THESE PATTERNS AS INSPIRATION TO:",
        "- Prioritize opportunities based on what worked for similar businesses",
        "- Shape page blueprints and roadmap structure",
        "But ALWAYS adapt them to THIS business' specific products, brand voice, and region.",
        ""
    ])
    
    return "\n".join(lines)


INDUSTRY_TAXONOMY = {
    "roofing": ["roofing", "roof", "roofer", "rooftop"],
    "hvac": ["hvac", "heating", "cooling", "air conditioning", "furnace"],
    "plumbing": ["plumbing", "plumber", "pipe", "drain", "sewer"],
    "electrical": ["electrical", "electrician", "wiring", "electric"],
    "landscaping": ["landscaping", "lawn", "garden", "tree", "yard"],
    "auto_repair": ["auto", "car", "mechanic", "automotive", "vehicle"],
    "dental": ["dental", "dentist", "orthodontist", "teeth"],
    "medical": ["medical", "doctor", "physician", "clinic", "healthcare"],
    "legal": ["legal", "lawyer", "attorney", "law firm", "paralegal"],
    "real_estate": ["real estate", "realtor", "property", "home buying", "rental"],
    "restaurant": ["restaurant", "food", "dining", "cafe", "catering"],
    "retail": ["retail", "store", "shop", "boutique", "ecommerce"],
    "technology": ["technology", "software", "tech", "it", "saas", "app"],
    "financial": ["financial", "accounting", "tax", "bookkeeping", "insurance"],
    "cleaning": ["cleaning", "janitorial", "maid", "housekeeping"],
    "construction": ["construction", "building", "contractor", "renovation"],
    "pest_control": ["pest", "exterminator", "termite", "rodent"],
    "moving": ["moving", "relocation", "movers", "packing"],
    "photography": ["photography", "photographer", "photo", "videography"],
    "fitness": ["fitness", "gym", "personal training", "yoga", "wellness"],
    "beauty": ["beauty", "salon", "spa", "hair", "nail", "makeup"],
    "education": ["education", "tutoring", "school", "training", "courses"],
    "marketing": ["marketing", "advertising", "seo", "digital marketing", "agency"],
    "home_services": ["home services", "handyman", "repair", "maintenance"],
}

BUSINESS_TYPE_TAXONOMY = {
    "local_service": ["local", "service", "in-person", "on-site"],
    "ecommerce": ["ecommerce", "online", "shop", "store", "product"],
    "saas": ["saas", "software", "platform", "subscription"],
    "b2b_service": ["b2b", "enterprise", "business", "corporate"],
    "brick_mortar": ["retail", "storefront", "location", "walk-in"],
    "franchise": ["franchise", "chain", "multi-location"],
    "professional_services": ["professional", "consulting", "advisory"],
    "healthcare": ["healthcare", "medical", "clinic", "practice"],
}


def _normalize_to_taxonomy(raw_value: str, taxonomy: dict, default: str) -> str:
    """Normalize a raw value to a controlled taxonomy term."""
    if not raw_value:
        return default
    
    raw_lower = raw_value.lower()
    
    for category, keywords in taxonomy.items():
        if any(kw in raw_lower for kw in keywords):
            return category
    
    return default


def _extract_industry(business: Business) -> str:
    """
    Extract and NORMALIZE industry from business categories.
    Returns a controlled taxonomy term, never raw tenant data.
    """
    categories = business.get_categories()
    if not categories:
        return "general"
    
    raw_category = categories[0].lower() if categories else ""
    return _normalize_to_taxonomy(raw_category, INDUSTRY_TAXONOMY, "general")


def _normalize_business_type(raw_type: str) -> str:
    """Normalize business type to a controlled taxonomy term."""
    if not raw_type:
        return "local_service"
    
    return _normalize_to_taxonomy(raw_type, BUSINESS_TYPE_TAXONOMY, "local_service")
