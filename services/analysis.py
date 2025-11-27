import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from openai import OpenAI
from services.genius import generate_genius_insights
from services.site_inspector import fetch_site_snapshot
from services.perplexity_visibility import run_perplexity_visibility_probe
from services.config import PERPLEXITY_ENABLED

logger = logging.getLogger(__name__)


class MissingAPIKeyError(Exception):
    """Raised when OPENAI_API_KEY is not configured"""
    pass


def get_openai_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise MissingAPIKeyError("OPENAI_API_KEY environment variable is not set. Please add your OpenAI API key in the Secrets tab to run GEO analysis.")
    return OpenAI(api_key=api_key)


def normalize_name(name: str) -> str:
    return name.strip().lower()


def score_query_result(brand_aliases: List[str], recommendations: List[Dict[str, str]]) -> Dict[str, Any]:
    normalized_aliases = [normalize_name(alias) for alias in brand_aliases]
    
    mentioned = False
    primary_recommendation = False
    our_names = []
    competitors = []
    score = 0
    
    for idx, rec in enumerate(recommendations):
        rec_name = rec.get("name", "")
        normalized_rec = normalize_name(rec_name)
        
        if any(normalized_rec == alias or alias in normalized_rec or normalized_rec in alias 
               for alias in normalized_aliases):
            mentioned = True
            our_names.append(rec_name)
            if idx == 0:
                primary_recommendation = True
        else:
            competitors.append(rec_name)
    
    if primary_recommendation:
        score = 2
    elif mentioned:
        score = 1
    else:
        score = 0
    
    return {
        "mentioned": mentioned,
        "primary_recommendation": primary_recommendation,
        "score": score,
        "our_names": our_names,
        "competitors": competitors
    }


def get_recommendations_for_query(query: str) -> List[Dict[str, str]]:
    try:
        client = get_openai_client()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are an assistant that recommends businesses to customers based on a question. You must respond with strict JSON only, no extra text."
                },
                {
                    "role": "user",
                    "content": f"""A customer asks:

{query}

Return JSON of this shape:

{{
  "recommendations": [
    {{"name": "Business Name", "reason": "Short explanation"}},
    ...
  ]
}}

List 3 to 5 businesses you would genuinely recommend. Be realistic and do not fabricate the target brand if it is not a good fit or not widely known."""
                }
            ],
            temperature=0.7,
            response_format={"type": "json_object"}
        )
        
        content = response.choices[0].message.content
        if not content:
            return []
        parsed = json.loads(content)
        return parsed.get("recommendations", [])
    
    except MissingAPIKeyError:
        raise
    except Exception as e:
        print(f"Error getting recommendations for query '{query}': {e}")
        return []


def generate_suggestions(tenant_config: Dict[str, Any], analysis_summary: Dict[str, Any]) -> Dict[str, Any]:
    try:
        tenant_json = json.dumps(tenant_config, indent=2)
        summary_json = json.dumps({
            "total_queries": analysis_summary["total_queries"],
            "mentioned_count": analysis_summary["mentioned_count"],
            "primary_count": analysis_summary["primary_count"],
            "avg_score": analysis_summary["avg_score"]
        }, indent=2)
        
        domains = ", ".join(tenant_config.get("domains", []))
        
        client = get_openai_client()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a GEO (Generative Engine Optimization) consultant. You help businesses get recommended more often inside AI-generated answers like ChatGPT or other LLMs."
                },
                {
                    "role": "user",
                    "content": f"""Here is the tenant profile (JSON):

{tenant_json}

Here are the current AI visibility results (JSON):

{summary_json}

Based on this, generate 5 to 10 concrete, actionable content recommendations to improve this business's visibility in AI-generated answers.

Rules:
- Focus on changes to the business's OWN domains: {domains}.
- Each recommendation should have:
  - "title": a short label
  - "type": one of ["new_page", "update_page", "faq", "authority", "branding"]
  - "details": 2–4 sentences explaining WHAT to create/change and WHY it helps AI mention them more.
- Output strict JSON of this structure:

{{
  "visibility_summary": "One-paragraph human-readable summary",
  "suggestions": [
    {{"title": "...", "type": "...", "details": "..."}},
    ...
  ]
}}"""
                }
            ],
            temperature=0.7,
            response_format={"type": "json_object"}
        )
        
        content = response.choices[0].message.content
        if not content:
            return {
                "visibility_summary": "Unable to generate suggestions at this time.",
                "suggestions": []
            }
        return json.loads(content)
    
    except MissingAPIKeyError:
        raise
    except Exception as e:
        print(f"Error generating suggestions: {e}")
        return {
            "visibility_summary": "Unable to generate suggestions at this time.",
            "suggestions": []
        }


def run_analysis(tenant_config: Dict[str, Any]) -> Dict[str, Any]:
    tenant_id = tenant_config["id"]
    tenant_name = tenant_config["display_name"]
    brand_aliases = tenant_config["brand_aliases"]
    queries = tenant_config["priority_queries"]
    domains = tenant_config.get("domains", [])
    geo_focus = tenant_config.get("geo_focus", [])
    
    from services.query_generator import get_query_intent_map
    query_intent_map = get_query_intent_map(
        name=tenant_name,
        categories=tenant_config.get("categories", []),
        regions=geo_focus,
        business_type=tenant_config.get("business_type", ""),
        max_queries=len(queries)
    )
    
    primary_domain = domains[0] if domains else ""
    
    perplexity_visibility = None
    if PERPLEXITY_ENABLED:
        logger.info("Running Perplexity visibility probe for %s", tenant_name)
        try:
            perplexity_visibility = run_perplexity_visibility_probe(
                business_name=tenant_name,
                primary_domain=primary_domain,
                regions=geo_focus,
                queries=queries
            )
            summary = (perplexity_visibility or {}).get("summary") or {}
            successful = summary.get("successful_probes", 0)
            logger.info("Perplexity probe complete: %d/%d queries successful", successful, len(queries))
        except Exception as e:
            logger.warning("Perplexity visibility probe failed (non-fatal): %s", e)
            perplexity_visibility = {"enabled": False, "queries": [], "summary": None}
    else:
        logger.info("Perplexity not enabled, skipping visibility probe")
    
    results = []
    
    for query in queries:
        recommendations = get_recommendations_for_query(query)
        
        scoring = score_query_result(brand_aliases, recommendations)
        
        intent_info = query_intent_map.get(query, {})
        
        result = {
            "query": query,
            "mentioned": scoring["mentioned"],
            "primary_recommendation": scoring["primary_recommendation"],
            "score": scoring["score"],
            "our_names": scoring["our_names"],
            "competitors": scoring["competitors"],
            "raw_recommendations": recommendations,
            "intent_type": intent_info.get("intent_type", "informational"),
            "intent_value": intent_info.get("intent_value", 5),
            "category_focus": intent_info.get("category_focus", "")
        }
        
        results.append(result)
    
    total_queries = len(results)
    mentioned_count = sum(1 for r in results if r["mentioned"])
    primary_count = sum(1 for r in results if r["primary_recommendation"])
    avg_score = sum(r["score"] for r in results) / total_queries if total_queries > 0 else 0
    
    summary = {
        "tenant_id": tenant_id,
        "tenant_name": tenant_name,
        "run_at": datetime.utcnow().isoformat() + "Z",
        "total_queries": total_queries,
        "mentioned_count": mentioned_count,
        "primary_count": primary_count,
        "avg_score": round(avg_score, 2),
        "results": results,
        "perplexity_visibility": perplexity_visibility
    }
    
    suggestions_data = generate_suggestions(tenant_config, summary)
    summary["visibility_summary"] = suggestions_data.get("visibility_summary", "")
    summary["suggestions"] = suggestions_data.get("suggestions", [])
    
    try:
        site_snapshot = fetch_site_snapshot(tenant_config)
        summary["site_snapshot"] = site_snapshot
    except Exception as e:
        logger.warning("Error fetching site snapshot (non-fatal): %s", e)
        site_snapshot = {"pages": [], "fetch_status": "error"}
        summary["site_snapshot"] = site_snapshot
    
    try:
        genius_data = generate_genius_insights(
            tenant_config, 
            summary, 
            site_snapshot,
            perplexity_visibility=perplexity_visibility
        )
        summary["genius_insights"] = genius_data
    except Exception as e:
        logger.warning("Error generating genius insights (non-fatal): %s", e)
        summary["genius_insights"] = None
    
    return summary
