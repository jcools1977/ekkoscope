"""
Genius Insights Module v2 for EkkoScope GEO Visibility Analysis
Enhanced with site awareness, impact/effort scoring, and structured JSON output.
Now includes multi-LLM visibility data (OpenAI, Perplexity, Gemini) for enhanced insights.
Integrates EkkoBrain memory for pattern-based recommendations.
"""

import os
import json
from typing import Dict, Any, List, Optional
from openai import OpenAI
from services.site_inspector import summarize_site_content
from services.perplexity_visibility import format_perplexity_visibility_for_genius
from services.ekkobrain_reader import format_ekkobrain_context_for_genius


class GeniusInsightError(Exception):
    """Raised when genius insight generation fails"""
    pass


def get_openai_client() -> OpenAI:
    """Get OpenAI client with API key from environment."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise GeniusInsightError("OPENAI_API_KEY not configured")
    return OpenAI(api_key=api_key)


def generate_genius_insights(
    tenant: Dict[str, Any],
    analysis: Dict[str, Any],
    site_snapshot: Dict[str, Any] | None = None,
    perplexity_visibility: Optional[Dict[str, Any]] = None,
    multi_llm_visibility: Optional[Any] = None,
    ekkobrain_context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Use OpenAI to turn raw analysis + site snapshot + multi-LLM visibility into actionable genius insights:
    - Patterns in AI visibility with evidence
    - Prioritized opportunities with impact/effort scoring
    - Quick wins for next 30 days
    - Future AI answer previews
    
    Args:
        tenant: Tenant configuration (name, domains, aliases, geo, etc.)
        analysis: Normalized analysis result (queries, scores, competitors, etc.)
        site_snapshot: Optional site content snapshot from site_inspector
        perplexity_visibility: Optional Perplexity visibility probe results (legacy)
        multi_llm_visibility: Optional MultiLLMVisibilityResult from visibility hub
    
    Returns:
        JSON-serializable dict with enhanced genius insights
    """
    try:
        client = get_openai_client()
        
        tenant_name = tenant.get("display_name", "Unknown Business")
        domains = tenant.get("domains", [])
        geo_focus = tenant.get("geo_focus", [])
        brand_aliases = tenant.get("brand_aliases", [])
        
        results = analysis.get("results", [])
        queries_data = []
        all_competitors = []
        
        for result in results:
            query_info = {
                "query": result.get("query", ""),
                "score": result.get("score", 0),
                "mentioned": result.get("mentioned", False),
                "primary": result.get("primary_recommendation", False),
                "competitors": result.get("competitors", [])
            }
            queries_data.append(query_info)
            all_competitors.extend(result.get("competitors", []))
        
        from collections import Counter
        competitor_freq = Counter(all_competitors)
        top_competitors = [{"name": name, "count": count} for name, count in competitor_freq.most_common(10)]
        
        avg_score = analysis.get("avg_score", 0)
        total_queries = analysis.get("total_queries", len(results))
        mentioned_count = analysis.get("mentioned_count", 0)
        primary_count = analysis.get("primary_count", 0)
        
        site_content_summary = ""
        site_available = False
        if site_snapshot and site_snapshot.get("pages"):
            site_content_summary = summarize_site_content(site_snapshot)
            site_available = True
        
        site_note_instruction = "Analysis of existing content: what's missing in headings, geo terms, or CTA" if site_available else "Site content not available for detailed page analysis"
        
        perplexity_summary = format_perplexity_visibility_for_genius(perplexity_visibility)
        perplexity_available = perplexity_visibility and perplexity_visibility.get("enabled", False)
        
        multi_llm_summary = ""
        multi_llm_available = False
        if multi_llm_visibility:
            from services.visibility_hub import format_multi_llm_visibility_for_genius
            multi_llm_summary = format_multi_llm_visibility_for_genius(multi_llm_visibility, tenant_name)
            multi_llm_available = len(multi_llm_visibility.providers_used) > 0
        
        context_json = json.dumps({
            "tenant_name": tenant_name,
            "domains": [d for d in domains if not d.startswith("AD_") and "_SITE_URL" not in d],
            "geo_focus": geo_focus,
            "brand_aliases": brand_aliases,
            "summary": {
                "total_queries": total_queries,
                "avg_score": avg_score,
                "mentioned_count": mentioned_count,
                "primary_count": primary_count
            },
            "queries": queries_data,
            "top_competitors": top_competitors
        }, indent=2)
        
        multi_llm_input = ""
        if multi_llm_available:
            providers = multi_llm_visibility.providers_used if multi_llm_visibility else []
            multi_llm_input = f"4. MULTI-LLM VISIBILITY ANALYSIS: Results from {len(providers)} AI providers ({', '.join(providers)}) showing who each AI recommends"
        else:
            multi_llm_input = "4. Multi-LLM visibility data: NOT AVAILABLE"
        
        system_prompt = f"""You are an expert GEO (Generative Engine Optimization) strategist analyzing AI visibility data for {tenant_name}.

INPUTS PROVIDED:
1. Tenant info: name, domains, geo focus, brand aliases
2. Query analysis: each query tested, its score (0-2), and competitors that appeared
3. {"Current site content: actual headings, meta descriptions, and text from their website" if site_available else "Site content: NOT AVAILABLE for this analysis"}
{multi_llm_input}
5. {"PERPLEXITY WEB-GROUNDED VISIBILITY: Real-time web search results showing who currently appears for each query" if perplexity_available else "Perplexity visibility data: NOT AVAILABLE (covered in multi-LLM analysis if available)"}

YOUR TASK: Generate SPECIFIC, ACTIONABLE insights grounded in the actual data.

CRITICAL RULES:
1. Every pattern MUST reference at least one specific query from the data
2. Every pattern MUST reference at least one specific competitor name
3. Every insight MUST mention the tenant's geo ({', '.join(geo_focus) if geo_focus else 'their local area'}) when relevant
4. Impact scores MUST be 1-10 integers based on business value
5. Effort MUST be "low", "medium", or "high"
6. Quick wins MUST be completable in 30 days with specific actions
7. NO generic advice like "improve SEO" - everything must be specific to THIS business
{"8. Use the site content to identify missing phrases, weak headings, and content gaps" if site_available else "8. Note that site content review was not possible for this run"}
{"9. IMPORTANT: Cross-reference visibility across ALL AI providers (OpenAI, Perplexity, Gemini) to find where they agree/disagree on recommendations. Prioritize opportunities where the client is missing across multiple AIs." if multi_llm_available else "9. Note: Multi-LLM cross-referencing was not available for this run"}

Output ONLY valid JSON matching this exact structure:

{{
  "patterns": [
    {{
      "summary": "One-line pattern observation specific to this business",
      "evidence": [
        "Specific evidence citing query text and competitor names from the data",
        "Example: 'For query \"best roofing in Morehead City\", score=0 while East Coast Roofing appears as top recommendation'"
      ],
      "implication": "What this means for {tenant_name}'s marketing and funnel"
    }}
  ],
  "priority_opportunities": [
    {{
      "query": "Exact query text from the analysis",
      "current_score": 0,
      "top_competitors": ["Competitor A from data", "Competitor B from data"],
      "intent_type": "emergency | high-ticket | maintenance | informational",
      "intent_value": 8,
      "impact_score": 9,
      "effort": "low | medium | high",
      "money_reason": "Why this query is financially important for {tenant_name} specifically",
      "recommended_page": {{
        "slug": "/specific-url-slug",
        "seo_title": "SEO Title with {tenant_name} + service + location",
        "h1": "Clear H1 for the page",
        "outline": [
          "Section 1: ...",
          "Section 2: ...",
          "Section 3: ...",
          "CTA section"
        ],
        "internal_links": [
          "Link suggestion referencing actual or likely URLs"
        ],
        "note_on_current_site": "{site_note_instruction}"
      }}
    }}
  ],
  "quick_wins": [
    "Concrete 30-day action #1 referencing specific page or asset",
    "Concrete 30-day action #2 with exact details",
    "Concrete 30-day action #3 that can be done this week"
  ],
  "future_ai_answers": [
    {{
      "query": "Exact query text from analysis",
      "example_answer": "Realistic ChatGPT-style answer that explicitly recommends {tenant_name} in their geo area"
    }}
  ]
}}

Generate 2-3 patterns, 2-3 priority opportunities with full page blueprints, 3-5 quick wins, and 2 future AI answer previews."""

        ekkobrain_section = ""
        ekkobrain_enabled = False
        if ekkobrain_context and ekkobrain_context.get("enabled", False):
            ekkobrain_section = format_ekkobrain_context_for_genius(ekkobrain_context)
            ekkobrain_enabled = bool(ekkobrain_section)
        
        user_prompt = f"""Analyze this GEO visibility data and generate genius insights for {tenant_name}:

=== ANALYSIS DATA ===
{context_json}

{"=== CURRENT SITE CONTENT ===" if site_available else "=== SITE CONTENT ==="}
{site_content_summary if site_available else "Site content could not be retrieved. Focus insights on the query analysis and competitor data."}

{multi_llm_summary if multi_llm_available else "MULTI-LLM VISIBILITY: Not available for this run."}

{perplexity_summary if perplexity_available and not multi_llm_available else ""}

{ekkobrain_section if ekkobrain_enabled else ""}

=== REQUIREMENTS ===
- {tenant_name} operates in: {', '.join(geo_focus) if geo_focus else 'their local area'}
- Their domains: {', '.join([d for d in domains if not d.startswith('AD_') and '_SITE_URL' not in d]) if domains else 'not specified'}
- Reference the ACTUAL queries, scores, and competitors from the data above
- Make every recommendation specific to THIS business
- {"Identify content gaps based on what the site currently says vs what AI recommends" if site_available else "Note that site content analysis was not possible"}
- {"Cross-reference visibility across OpenAI, Perplexity, and Gemini to find consistent patterns and gaps" if multi_llm_available else "Multi-LLM cross-referencing was not available for this run"}
- {"Use EkkoBrain patterns as inspiration but adapt them specifically to THIS business" if ekkobrain_enabled else ""}"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            response_format={"type": "json_object"}
        )
        
        content = response.choices[0].message.content
        if not content:
            return _empty_genius_insights()
        
        insights = json.loads(content)
        
        return {
            "patterns": insights.get("patterns", []),
            "priority_opportunities": insights.get("priority_opportunities", []),
            "quick_wins": insights.get("quick_wins", []),
            "future_ai_answers": insights.get("future_ai_answers", []),
            "site_analyzed": site_available,
            "perplexity_used": perplexity_available,
            "multi_llm_used": multi_llm_available,
            "providers_used": multi_llm_visibility.providers_used if multi_llm_visibility else [],
            "ekkobrain_used": ekkobrain_enabled
        }
    
    except Exception as e:
        print(f"Error generating genius insights: {e}")
        return _empty_genius_insights()


def _empty_genius_insights() -> Dict[str, Any]:
    """Return empty genius insights structure when generation fails."""
    return {
        "patterns": [],
        "priority_opportunities": [],
        "quick_wins": [],
        "future_ai_answers": [],
        "site_analyzed": False,
        "perplexity_used": False,
        "multi_llm_used": False,
        "providers_used": [],
        "ekkobrain_used": False
    }


def generate_executive_summary(genius_insights: Dict[str, Any] | None, analysis: Dict[str, Any]) -> List[str]:
    """
    Generate 3-5 executive summary bullets from genius insights and analysis.
    Returns a list of bullet point strings.
    """
    bullets = []
    
    if not genius_insights:
        return ["Genius Mode insights unavailable for this run."]
    
    total_queries = analysis.get("total_queries", 0)
    mentioned_count = analysis.get("mentioned_count", 0)
    primary_count = analysis.get("primary_count", 0)
    avg_score = analysis.get("avg_score", 0)
    
    results = analysis.get("results", [])
    all_competitors = []
    for r in results:
        all_competitors.extend(r.get("competitors", []))
    
    from collections import Counter
    top_comps = Counter(all_competitors).most_common(3)
    
    if primary_count == 0 and mentioned_count == 0:
        bullets.append(f"You are not recommended in any of the {total_queries} queries tested.")
    elif primary_count == 0:
        bullets.append(f"You appear in {mentioned_count} of {total_queries} queries but never as the top recommendation.")
    else:
        bullets.append(f"You are the primary recommendation in {primary_count} of {total_queries} queries (avg score: {avg_score:.1f}/2).")
    
    if top_comps:
        comp_names = ", ".join([c[0] for c in top_comps[:2]])
        bullets.append(f"Top competitors dominating AI recommendations: {comp_names}.")
    
    patterns = genius_insights.get("patterns", [])
    if patterns and len(patterns) > 0:
        first_pattern = patterns[0]
        if isinstance(first_pattern, dict) and first_pattern.get("summary"):
            bullets.append(first_pattern["summary"])
    
    quick_wins = genius_insights.get("quick_wins", [])
    if quick_wins and len(quick_wins) >= 1:
        win1 = quick_wins[0] if isinstance(quick_wins[0], str) else str(quick_wins[0])
        bullets.append(f"Next 30 days focus: {win1}")
    
    priority_opps = genius_insights.get("priority_opportunities", [])
    if priority_opps and len(priority_opps) > 0:
        high_impact = [o for o in priority_opps if isinstance(o, dict) and o.get("impact_score", 0) >= 7]
        if high_impact:
            opp_word = "opportunity" if len(high_impact) == 1 else "opportunities"
            bullets.append(f"{len(high_impact)} high-impact {opp_word} identified with detailed page blueprints.")
    
    return bullets[:5]
