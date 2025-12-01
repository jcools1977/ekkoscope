"""
AI-Powered Fix Planner for EkkoScope v4
Uses GPT-4o to analyze extracted issues and generate comprehensive remediation plans.
"""

import os
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from services.ekkoscope_sentinel import log_ai_query

try:
    from openai import OpenAI
    client = OpenAI()
    OPENAI_AVAILABLE = bool(os.getenv("OPENAI_API_KEY"))
except Exception:
    client = None
    OPENAI_AVAILABLE = False


SYSTEM_PROMPT = """You are EkkoScope FixEngine, an expert AI visibility remediation specialist. 
You analyze business visibility issues identified by AI audits and generate precise, actionable fix plans.

Your expertise covers:
- SEO optimization for AI assistants (ChatGPT, Gemini, Perplexity)
- Schema markup and structured data for AI comprehension
- Content optimization for natural language understanding
- Local SEO signals for geographic relevance
- Meta tag optimization for AI snippets
- FAQ and knowledge base structuring

CRITICAL RULES:
1. Generate SPECIFIC, IMPLEMENTABLE fixes - not generic advice
2. Include actual code, content, and markup that can be deployed
3. Prioritize fixes by impact on AI visibility
4. Consider the specific business type and industry
5. All content must be factually accurate for the business
6. Generate complete, production-ready solutions

Output JSON format for each fix."""


def generate_fix_plan(
    parsed_report: Dict[str, Any],
    business_context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Generate a comprehensive fix plan based on parsed GEO report.
    
    Args:
        parsed_report: Output from pdf_parser.parse_geo_report()
        business_context: Optional additional business information
    
    Returns:
        Complete fix plan with actionable items for each agent
    """
    business_info = parsed_report.get("business_info", {})
    business_name = business_info.get("business_name", "Unknown Business")
    visibility_score = parsed_report.get("visibility_score", {})
    
    if not OPENAI_AVAILABLE or client is None:
        return _generate_fallback_fix_plan(parsed_report, business_context, business_name, visibility_score)
    
    issues = parsed_report.get("issues", [])
    competitors = parsed_report.get("competitors", [])
    queries = parsed_report.get("queries", [])
    recommendations = parsed_report.get("recommendations", [])
    blueprints = parsed_report.get("page_blueprints", [])
    
    business_name = business_info.get("business_name", "Unknown Business")
    business_type = business_context.get("business_type", "") if business_context else ""
    domain = business_info.get("domain", "")
    
    zero_score_queries = [q for q in queries if q.get("score", 0) == 0]
    
    prompt = f"""Analyze this AI visibility report and generate a complete fix plan.

BUSINESS PROFILE:
- Name: {business_name}
- Type: {business_type}
- Domain: {domain}
- Current Visibility Score: {visibility_score.get('overall_score', 0):.2f}/2 ({visibility_score.get('visibility_percentage', 0)}%)
- Queries Analyzed: {visibility_score.get('total_queries', 0)}
- Mentioned Count: {visibility_score.get('mentioned_count', 0)}
- Primary Recommendation Count: {visibility_score.get('primary_count', 0)}

IDENTIFIED ISSUES:
{json.dumps(issues, indent=2)}

ZERO-VISIBILITY QUERIES (Critical - Need Immediate Fix):
{json.dumps(zero_score_queries[:10], indent=2)}

TOP COMPETITORS (What They're Doing Right):
{json.dumps(competitors[:5], indent=2)}

EXISTING RECOMMENDATIONS:
{json.dumps(recommendations[:10], indent=2)}

PAGE BLUEPRINTS SUGGESTED:
{json.dumps(blueprints, indent=2)}

Generate a comprehensive fix plan in this JSON format:
{{
    "fix_summary": "Brief overview of the remediation strategy",
    "estimated_visibility_gain": "Projected visibility improvement (e.g., '0% -> 65%')",
    "priority_order": ["list of fixes in priority order"],
    "content_fixes": [
        {{
            "fix_id": "content_001",
            "type": "meta_description",
            "target_page": "homepage",
            "current_issue": "Description of the problem",
            "fix_content": "The actual optimized content to deploy",
            "keywords_targeted": ["keyword1", "keyword2"],
            "expected_impact": "high/medium/low"
        }}
    ],
    "seo_fixes": [
        {{
            "fix_id": "seo_001",
            "type": "schema_markup",
            "target_page": "homepage",
            "schema_type": "LocalBusiness",
            "schema_json": {{}},
            "expected_impact": "high/medium/low"
        }}
    ],
    "new_pages": [
        {{
            "fix_id": "page_001",
            "page_title": "Page title",
            "page_slug": "/url-slug",
            "page_purpose": "Why this page helps visibility",
            "content_outline": ["Section 1", "Section 2"],
            "target_queries": ["query this page targets"],
            "meta_description": "SEO meta description",
            "expected_impact": "high/medium/low"
        }}
    ],
    "quick_wins": [
        {{
            "fix_id": "quick_001",
            "action": "Specific quick action",
            "implementation_time": "15 minutes",
            "expected_impact": "medium"
        }}
    ]
}}

Generate specific, implementable fixes for {business_name}. Include actual content, not placeholders."""

    try:
        log_ai_query("gpt-4o", prompt[:200], business_name)
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=4000,
            response_format={"type": "json_object"}
        )
        
        fix_plan = json.loads(response.choices[0].message.content)
        
        fix_plan["generated_at"] = datetime.utcnow().isoformat() + "Z"
        fix_plan["business_name"] = business_name
        fix_plan["original_score"] = visibility_score.get("overall_score", 0)
        fix_plan["original_percentage"] = visibility_score.get("visibility_percentage", 0)
        
        return fix_plan
        
    except Exception as e:
        return {
            "error": str(e),
            "fix_summary": "Failed to generate fix plan",
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "business_name": business_name,
            "content_fixes": [],
            "seo_fixes": [],
            "new_pages": [],
            "quick_wins": []
        }


def _generate_fallback_fix_plan(
    parsed_report: Dict[str, Any],
    business_context: Optional[Dict[str, Any]],
    business_name: str,
    visibility_score: Dict[str, Any]
) -> Dict[str, Any]:
    """Generate a template-based fix plan when OpenAI is not available."""
    business_type = business_context.get("business_type", "") if business_context else ""
    
    return {
        "fix_summary": f"Template-based remediation plan for {business_name} ({business_type})",
        "estimated_visibility_gain": "0% -> 60%",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "business_name": business_name,
        "original_score": visibility_score.get("overall_score", 0),
        "original_percentage": visibility_score.get("visibility_percentage", 0),
        "priority_order": ["meta_description", "schema_markup", "faq_section", "service_page"],
        "content_fixes": [
            {
                "fix_id": "content_001",
                "type": "meta_description",
                "target_page": "homepage",
                "current_issue": "Meta description not optimized for AI visibility",
                "fix_content": f"{business_name} - Your trusted {business_type} provider. Quality service, competitive pricing, and expert solutions.",
                "keywords_targeted": [business_type.lower(), "service", "provider"],
                "expected_impact": "high"
            }
        ],
        "seo_fixes": [
            {
                "fix_id": "seo_001",
                "type": "schema_markup",
                "target_page": "homepage",
                "schema_type": "LocalBusiness",
                "expected_impact": "high"
            }
        ],
        "new_pages": [
            {
                "fix_id": "page_001",
                "page_title": f"FAQ - {business_name}",
                "page_slug": "/faq",
                "page_purpose": "Answer common questions for AI assistants",
                "content_outline": ["About Us", "Our Services", "Pricing", "Contact"],
                "target_queries": ["frequently asked questions"],
                "meta_description": f"Find answers to common questions about {business_name}",
                "expected_impact": "medium"
            }
        ],
        "quick_wins": [
            {
                "fix_id": "quick_001",
                "action": "Add business to Google Business Profile",
                "implementation_time": "30 minutes",
                "expected_impact": "high"
            }
        ]
    }


def generate_content_fix(
    fix_type: str,
    business_name: str,
    business_type: str,
    target_queries: List[str],
    context: Optional[str] = None
) -> Dict[str, Any]:
    """Generate specific content fix for a single issue."""
    
    prompt = f"""Generate optimized content for {business_name} ({business_type}).

Fix Type: {fix_type}
Target Queries to Rank For: {json.dumps(target_queries)}
Additional Context: {context or 'None'}

Generate the specific content fix as JSON:
{{
    "content_type": "{fix_type}",
    "content": "The actual optimized content",
    "keywords": ["targeted", "keywords"],
    "word_count": 150,
    "ai_visibility_optimizations": ["What makes this AI-friendly"]
}}"""

    try:
        log_ai_query("gpt-4o", f"Content fix: {fix_type}", business_name)
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are an AI visibility content specialist. Generate production-ready content optimized for AI assistant recommendations."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=1500,
            response_format={"type": "json_object"}
        )
        
        return json.loads(response.choices[0].message.content)
        
    except Exception as e:
        return {"error": str(e), "content_type": fix_type, "content": ""}


def generate_schema_markup(
    business_name: str,
    business_type: str,
    business_info: Dict[str, Any]
) -> Dict[str, Any]:
    """Generate comprehensive schema markup for AI visibility."""
    
    prompt = f"""Generate comprehensive JSON-LD schema markup for {business_name}.

Business Type: {business_type}
Business Info: {json.dumps(business_info)}

Generate complete, valid JSON-LD schema that maximizes AI visibility:
{{
    "schemas": [
        {{
            "schema_type": "LocalBusiness",
            "jsonld": {{...complete valid JSON-LD...}}
        }},
        {{
            "schema_type": "FAQPage", 
            "jsonld": {{...complete valid JSON-LD with real FAQs...}}
        }}
    ],
    "implementation_notes": "How to add these to the website"
}}"""

    try:
        log_ai_query("gpt-4o", "Schema markup generation", business_name)
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a schema markup expert. Generate valid, comprehensive JSON-LD that helps AI assistants understand and recommend businesses."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
            max_tokens=2000,
            response_format={"type": "json_object"}
        )
        
        return json.loads(response.choices[0].message.content)
        
    except Exception as e:
        return {"error": str(e), "schemas": []}


def estimate_post_fix_score(
    original_score: float,
    fixes_applied: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Estimate the visibility score after fixes are applied."""
    
    impact_values = {
        "high": 0.4,
        "medium": 0.2,
        "low": 0.1
    }
    
    total_impact = 0
    for fix in fixes_applied:
        impact = fix.get("expected_impact", "medium")
        total_impact += impact_values.get(impact, 0.2)
    
    total_impact = min(total_impact, 1.5)
    
    estimated_score = min(original_score + total_impact, 2.0)
    estimated_percentage = int(estimated_score / 2 * 100)
    
    return {
        "original_score": original_score,
        "original_percentage": int(original_score / 2 * 100),
        "estimated_score": round(estimated_score, 2),
        "estimated_percentage": estimated_percentage,
        "improvement": f"{int(original_score / 2 * 100)}% -> {estimated_percentage}%",
        "fixes_counted": len(fixes_applied)
    }
