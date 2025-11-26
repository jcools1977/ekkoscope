"""
Genius Insights Module for EchoScope GEO Visibility Analysis
Generates deeper, non-obvious insights and concrete, prioritized actions.
"""

import os
import json
from typing import Dict, Any, List
from openai import OpenAI


class GeniusInsightError(Exception):
    """Raised when genius insight generation fails"""
    pass


def get_openai_client() -> OpenAI:
    """Get OpenAI client with API key from environment."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise GeniusInsightError("OPENAI_API_KEY not configured")
    return OpenAI(api_key=api_key)


def generate_genius_insights(tenant: Dict[str, Any], analysis: Dict[str, Any]) -> Dict[str, Any]:
    """
    Use OpenAI to turn raw analysis into actionable genius insights:
    - Patterns in AI visibility
    - Prioritized opportunities with content blueprints
    - Quick wins for immediate action
    - Future AI answer previews
    
    Args:
        tenant: Tenant configuration (name, domains, aliases, geo, etc.)
        analysis: Normalized analysis result (queries, scores, competitors, etc.)
    
    Returns:
        JSON-serializable dict with genius insights
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
        
        context_json = json.dumps({
            "tenant_name": tenant_name,
            "domains": domains,
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
        
        system_prompt = """You are an expert GEO (Generative Engine Optimization) strategist analyzing AI visibility data for a specific business.

Your job is to produce SPECIFIC, ACTIONABLE insights that reference:
- The actual business name, domains, and geographic focus
- The actual queries tested and their scores
- The actual competitors that appeared

CRITICAL RULES:
1. NO generic advice like "improve SEO" or "create better content"
2. Every insight MUST reference specific queries, competitors, or data from the analysis
3. Page blueprints MUST include real slugs, titles, and outlines specific to this business
4. Quick wins MUST be concrete actions that can be done this week
5. Future AI answers MUST explicitly name the tenant as the recommended business

Output ONLY valid JSON matching this exact structure:

{
  "patterns": [
    {
      "summary": "One-line pattern observation",
      "evidence": ["Specific evidence from queries/scores"],
      "implication": "What this means for the business"
    }
  ],
  "priority_opportunities": [
    {
      "query": "The exact query text",
      "current_score": 0,
      "top_competitors": ["Competitor names from data"],
      "intent_value": 8,
      "difficulty": "low|medium|high",
      "reason": "Why this matters for this specific business",
      "recommended_page": {
        "slug": "/specific-slug-for-this-content",
        "seo_title": "Title with business name and location",
        "h1": "H1 heading",
        "outline": ["Section 1", "Section 2", "Section 3", "Section 4", "CTA"],
        "internal_links": ["Link suggestion 1", "Link suggestion 2"]
      }
    }
  ],
  "quick_wins": [
    "Specific action 1 with exact details",
    "Specific action 2 with exact details"
  ],
  "future_ai_answers": [
    {
      "query": "Exact query text",
      "example_answer": "A realistic AI response that recommends this business by name..."
    }
  ]
}

Generate 2-3 patterns, 2-3 priority opportunities with full page blueprints, 3-5 quick wins, and 2 future AI answer previews."""

        user_prompt = f"""Analyze this GEO visibility data and generate genius insights:

{context_json}

Remember:
- {tenant_name} operates in {', '.join(geo_focus) if geo_focus else 'their local area'}
- Their domains are: {', '.join(domains) if domains else 'not specified'}
- Reference the ACTUAL queries and competitors from the data above
- Make every recommendation specific to THIS business"""

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
            "future_ai_answers": insights.get("future_ai_answers", [])
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
        "future_ai_answers": []
    }
