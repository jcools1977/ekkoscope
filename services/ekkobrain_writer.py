"""
EkkoBrain Writer for EkkoScope.
Stores audit artifacts in the database and pushes anonymized patterns to Pinecone.
Called after each successful audit completion.
"""

import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from sqlalchemy.orm import Session

from .database import (
    Business, Audit, AuditQuery, QueryVisibilityResult,
    PageBlueprint, RoadmapTask, derive_region_group
)
from .ekkobrain_pinecone import (
    upsert_patterns, embed_text, generate_pattern_id, is_ekkobrain_enabled
)

logger = logging.getLogger(__name__)


def log_audit_to_ekkobrain(
    db: Session,
    audit: Audit,
    business: Business,
    queries_with_intent: List[Dict[str, Any]],
    visibility_data: Optional[Dict[str, Any]],
    genius_payload: Optional[Dict[str, Any]]
) -> bool:
    """
    Log audit artifacts to database and push anonymized patterns to Pinecone.
    
    Args:
        db: SQLAlchemy database session
        audit: The completed Audit object
        business: The Business object
        queries_with_intent: List of query dicts with 'query', 'intent', 'intent_value'
        visibility_data: Multi-LLM visibility results
        genius_payload: Genius Mode output with blueprints and roadmap
    
    Returns:
        True if successful, False if any errors occurred
    """
    try:
        industry = _extract_industry(business)
        business_type = _normalize_business_type(business.business_type or "")
        regions = business.get_regions()
        region_group = derive_region_group(regions)
        
        _log_queries_to_db(db, audit, business, queries_with_intent, visibility_data, region_group)
        
        blueprint_ids = []
        task_ids = []
        
        if genius_payload:
            blueprint_ids = _log_blueprints_to_db(
                db, audit, business, genius_payload, 
                industry, business_type, region_group
            )
            task_ids = _log_roadmap_to_db(
                db, audit, business, genius_payload,
                industry, business_type, region_group
            )
        
        db.commit()
        logger.info("Logged audit artifacts to DB: audit_id=%d", audit.id)
        
        if is_ekkobrain_enabled() and genius_payload:
            _push_patterns_to_pinecone(
                audit, genius_payload, blueprint_ids, task_ids,
                industry, business_type, region_group
            )
        
        return True
        
    except Exception as e:
        logger.warning("Failed to log audit to EkkoBrain (non-fatal): %s", e)
        db.rollback()
        return False


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
    """
    Normalize a raw value to a controlled taxonomy term.
    This strips any tenant-identifying information.
    """
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
    """
    Normalize business type to a controlled taxonomy term.
    Returns a controlled taxonomy term, never raw tenant data.
    """
    if not raw_type:
        return "local_service"
    
    return _normalize_to_taxonomy(raw_type, BUSINESS_TYPE_TAXONOMY, "local_service")


def _log_queries_to_db(
    db: Session,
    audit: Audit,
    business: Business,
    queries_with_intent: List[Dict[str, Any]],
    visibility_data: Optional[Dict[str, Any]],
    region_group: str
):
    """Log queries and visibility results to database."""
    visibility_by_query = {}
    if visibility_data and "queries" in visibility_data:
        for q in visibility_data["queries"]:
            query_text = q.get("query", "")
            visibility_by_query[query_text] = q.get("providers", [])
    
    for q_data in queries_with_intent:
        query_text = q_data.get("query", "")
        intent = q_data.get("intent", "informational")
        
        audit_query = AuditQuery(
            audit_id=audit.id,
            query_text=query_text,
            intent=intent,
            region=region_group
        )
        db.add(audit_query)
        db.flush()
        
        providers = visibility_by_query.get(query_text, [])
        for provider_data in providers:
            provider = provider_data.get("provider", "unknown")
            brands = provider_data.get("recommended_brands", [])
            
            for rank, brand in enumerate(brands[:5], 1):
                if isinstance(brand, dict):
                    brand_name = brand.get("name", "")
                    brand_url = brand.get("url", "")
                    reason = brand.get("reason", "")
                else:
                    brand_name = str(brand)
                    brand_url = ""
                    reason = ""
                
                if brand_name:
                    vis_result = QueryVisibilityResult(
                        audit_query_id=audit_query.id,
                        provider=provider,
                        brand_name=brand_name,
                        brand_url=brand_url,
                        reason=reason,
                        rank=rank
                    )
                    db.add(vis_result)


def _log_blueprints_to_db(
    db: Session,
    audit: Audit,
    business: Business,
    genius_payload: Dict[str, Any],
    industry: str,
    business_type: str,
    region_group: str
) -> List[int]:
    """Log page blueprints to database. Returns list of blueprint IDs."""
    blueprint_ids = []
    opportunities = genius_payload.get("priority_opportunities", [])
    
    for opp in opportunities:
        if not isinstance(opp, dict):
            continue
        
        rec_page = opp.get("recommended_page", {})
        if not rec_page:
            continue
        
        intent_type = opp.get("intent_type", "informational")
        query = opp.get("query", "")
        intent_cluster = f"{intent_type}_{_slugify(query[:30])}" if query else intent_type
        
        outline = rec_page.get("outline", [])
        outline_json = json.dumps(outline) if outline else "[]"
        
        keywords = opp.get("keywords", [])
        if not keywords:
            keywords = [query] if query else []
        target_keywords = ",".join(keywords) if isinstance(keywords, list) else str(keywords)
        
        blueprint = PageBlueprint(
            audit_id=audit.id,
            business_id=business.id,
            intent_cluster=intent_cluster,
            url_slug=rec_page.get("slug", ""),
            seo_title=rec_page.get("seo_title", ""),
            meta_description=rec_page.get("meta_description", ""),
            h1=rec_page.get("h1", ""),
            outline_json=outline_json,
            target_keywords=target_keywords,
            industry=industry,
            business_type=business_type,
            region_group=region_group
        )
        db.add(blueprint)
        db.flush()
        blueprint_ids.append(blueprint.id)
    
    return blueprint_ids


def _log_roadmap_to_db(
    db: Session,
    audit: Audit,
    business: Business,
    genius_payload: Dict[str, Any],
    industry: str,
    business_type: str,
    region_group: str
) -> List[int]:
    """Log roadmap tasks to database. Returns list of task IDs."""
    task_ids = []
    quick_wins = genius_payload.get("quick_wins", [])
    
    for idx, task_text in enumerate(quick_wins):
        if not task_text:
            continue
        
        if isinstance(task_text, dict):
            text = task_text.get("text", "") or task_text.get("task", "") or str(task_text)
            impact = task_text.get("impact", "medium")
            effort = task_text.get("effort", "medium")
            owner = task_text.get("owner", "content_writer")
        else:
            text = str(task_text)
            impact = "high" if idx == 0 else "medium"
            effort = "low" if idx < 2 else "medium"
            owner = "content_writer"
        
        week = 1 if idx < 2 else (2 if idx < 4 else 3)
        
        task = RoadmapTask(
            audit_id=audit.id,
            business_id=business.id,
            week_number=week,
            task_text=text,
            intent_cluster=None,
            impact=impact,
            effort=effort,
            owner_role=owner,
            industry=industry,
            business_type=business_type,
            region_group=region_group
        )
        db.add(task)
        db.flush()
        task_ids.append(task.id)
    
    return task_ids


def _anonymize_text(text: str) -> str:
    """
    Remove tenant-identifying information from text for Pinecone storage.
    Strips business names, URLs, domains, and specific identifiers.
    """
    if not text:
        return ""
    
    import re
    
    text = re.sub(r'https?://[^\s]+', '[URL]', text)
    text = re.sub(r'\b[a-zA-Z0-9-]+\.(com|net|org|io|co|us|biz)\b', '[DOMAIN]', text)
    text = re.sub(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b', '[BRAND]', text)
    
    return text[:100]


def _categorize_page_type(h1: str, slug: str, outline: List[str]) -> str:
    """Categorize page type from blueprint structure without exposing specifics."""
    h1_lower = h1.lower() if h1 else ""
    slug_lower = slug.lower() if slug else ""
    outline_text = " ".join(outline).lower() if outline else ""
    
    if any(kw in h1_lower or kw in slug_lower for kw in ["emergency", "urgent", "24/7", "same-day"]):
        return "emergency_service_page"
    if any(kw in h1_lower or kw in slug_lower for kw in ["guide", "how-to", "tips", "learn"]):
        return "educational_content"
    if any(kw in h1_lower or kw in slug_lower for kw in ["service", "solution", "offer"]):
        return "service_page"
    if any(kw in h1_lower or kw in slug_lower for kw in ["about", "team", "who we are"]):
        return "about_page"
    if any(kw in h1_lower or kw in slug_lower for kw in ["contact", "quote", "estimate"]):
        return "conversion_page"
    if any(kw in h1_lower or kw in slug_lower for kw in ["faq", "question", "answer"]):
        return "faq_page"
    if "comparison" in h1_lower or "vs" in slug_lower:
        return "comparison_page"
    
    return "general_landing_page"


def _categorize_task_type(task_text: str) -> str:
    """Categorize task type without exposing specific task details."""
    task_lower = task_text.lower() if task_text else ""
    
    if any(kw in task_lower for kw in ["create page", "new page", "landing page", "build page"]):
        return "page_creation"
    if any(kw in task_lower for kw in ["update", "revise", "rewrite", "improve"]):
        return "content_update"
    if any(kw in task_lower for kw in ["schema", "structured data", "markup"]):
        return "schema_optimization"
    if any(kw in task_lower for kw in ["link", "backlink", "authority"]):
        return "link_building"
    if any(kw in task_lower for kw in ["faq", "question", "answer"]):
        return "faq_creation"
    if any(kw in task_lower for kw in ["testimonial", "review", "case study"]):
        return "social_proof"
    if any(kw in task_lower for kw in ["local", "geo", "location", "city"]):
        return "local_optimization"
    if any(kw in task_lower for kw in ["image", "video", "media"]):
        return "media_optimization"
    
    return "general_optimization"


ALLOWED_INDUSTRIES = set(INDUSTRY_TAXONOMY.keys()) | {"general"}
ALLOWED_BUSINESS_TYPES = set(BUSINESS_TYPE_TAXONOMY.keys()) | {"local_service"}
ALLOWED_REGION_GROUPS = {
    "US_northeast", "US_southeast", "US_midwest", "US_southwest", "US_west", "US_national"
}
ALLOWED_INTENTS = {
    "emergency", "high_ticket", "replenishment", "transactional", "informational"
}
ALLOWED_PAGE_TYPES = {
    "emergency_service_page", "educational_content", "service_page", "about_page",
    "conversion_page", "faq_page", "comparison_page", "general_landing_page"
}
ALLOWED_TASK_TYPES = {
    "page_creation", "content_update", "schema_optimization", "link_building",
    "faq_creation", "social_proof", "local_optimization", "media_optimization",
    "general_optimization"
}


def _validate_privacy_safe(
    industry: str, 
    business_type: str, 
    region_group: str,
    intent_cluster: str = None,
    page_type: str = None,
    task_type: str = None
) -> bool:
    """
    Validate that all values are from controlled vocabularies.
    Returns False if any value could leak tenant information.
    """
    if industry not in ALLOWED_INDUSTRIES:
        logger.warning("Privacy check failed: industry '%s' not in allowed list", industry)
        return False
    
    if business_type not in ALLOWED_BUSINESS_TYPES:
        logger.warning("Privacy check failed: business_type '%s' not in allowed list", business_type)
        return False
    
    if region_group not in ALLOWED_REGION_GROUPS:
        logger.warning("Privacy check failed: region_group '%s' not in allowed list", region_group)
        return False
    
    if intent_cluster and intent_cluster not in ALLOWED_INTENTS:
        logger.warning("Privacy check failed: intent_cluster '%s' not in allowed list", intent_cluster)
        return False
    
    if page_type and page_type not in ALLOWED_PAGE_TYPES:
        logger.warning("Privacy check failed: page_type '%s' not in allowed list", page_type)
        return False
    
    if task_type and task_type not in ALLOWED_TASK_TYPES:
        logger.warning("Privacy check failed: task_type '%s' not in allowed list", task_type)
        return False
    
    return True


def _push_patterns_to_pinecone(
    audit: Audit,
    genius_payload: Dict[str, Any],
    blueprint_ids: List[int],
    task_ids: List[int],
    industry: str,
    business_type: str,
    region_group: str
):
    """
    Push FULLY ANONYMIZED patterns to Pinecone for semantic retrieval.
    
    PRIVACY CRITICAL: No tenant-identifying information is stored:
    - No business names, domains, or URLs
    - No raw query text or page titles
    - Only abstract categories, intent types, and structural metadata
    - All values are validated against controlled vocabularies before push
    """
    if not _validate_privacy_safe(industry, business_type, region_group):
        logger.error("Aborting Pinecone push: privacy validation failed for base fields")
        return
    
    vectors = []
    
    opportunities = genius_payload.get("priority_opportunities", [])
    for idx, opp in enumerate(opportunities):
        if not isinstance(opp, dict):
            continue
        
        rec_page = opp.get("recommended_page", {})
        if not rec_page:
            continue
        
        intent_type = opp.get("intent_type", "informational")
        if intent_type not in ALLOWED_INTENTS:
            intent_type = "informational"
        
        outline = rec_page.get("outline", [])
        page_type = _categorize_page_type(
            rec_page.get("h1", ""),
            rec_page.get("slug", ""),
            outline
        )
        
        if not _validate_privacy_safe(industry, business_type, region_group, intent_type, page_type):
            continue
        
        section_count = len(outline)
        has_cta = any('cta' in s.lower() for s in outline)
        
        content = f"""Blueprint pattern: {page_type} page for {intent_type} intent.
Industry: {industry}. Business type: {business_type}. Region: {region_group}.
Sections: {section_count}. Has CTA: {'yes' if has_cta else 'no'}."""
        
        embedding = embed_text(content)
        if embedding:
            bp_id = blueprint_ids[idx] if idx < len(blueprint_ids) else idx
            pattern_id = generate_pattern_id("bp", audit.id, bp_id)
            
            vectors.append({
                "id": pattern_id,
                "values": embedding,
                "metadata": {
                    "pattern_type": "blueprint",
                    "industry": industry,
                    "business_type": business_type,
                    "region_group": region_group,
                    "intent_cluster": intent_type,
                    "page_type": page_type,
                    "section_count": section_count,
                    "has_cta": has_cta
                }
            })
    
    quick_wins = genius_payload.get("quick_wins", [])
    for idx, task_data in enumerate(quick_wins):
        if isinstance(task_data, dict):
            task_text = task_data.get("text", "") or task_data.get("task", "") or str(task_data)
            impact = task_data.get("impact", "medium")
            effort = task_data.get("effort", "medium")
            owner = task_data.get("owner", "content_writer")
        else:
            task_text = str(task_data) if task_data else ""
            impact = "high" if idx == 0 else "medium"
            effort = "low" if idx < 2 else "medium"
            owner = "content_writer"
        
        if not task_text:
            continue
        
        week = 1 if idx < 2 else (2 if idx < 4 else 3)
        task_type = _categorize_task_type(task_text)
        
        if impact not in {"high", "medium", "low"}:
            impact = "medium"
        if effort not in {"high", "medium", "low"}:
            effort = "medium"
        
        if not _validate_privacy_safe(industry, business_type, region_group, task_type=task_type):
            continue
        
        content = f"""Week {week} task: {task_type}.
Industry: {industry}. Business type: {business_type}. Region: {region_group}.
Impact: {impact}. Effort: {effort}."""
        
        embedding = embed_text(content)
        if embedding:
            task_id = task_ids[idx] if idx < len(task_ids) else idx
            pattern_id = generate_pattern_id("task", audit.id, task_id)
            
            vectors.append({
                "id": pattern_id,
                "values": embedding,
                "metadata": {
                    "pattern_type": "task",
                    "industry": industry,
                    "business_type": business_type,
                    "region_group": region_group,
                    "week_number": week,
                    "impact": impact,
                    "effort": effort,
                    "task_type": task_type
                }
            })
    
    if vectors:
        upsert_patterns(vectors)
        logger.info("Pushed %d anonymized patterns to EkkoBrain Pinecone", len(vectors))


def _slugify(text: str) -> str:
    """Convert text to a slug-like format."""
    return "".join(c if c.isalnum() else "_" for c in text.lower()).strip("_")[:30]
