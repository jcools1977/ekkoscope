"""
Visibility Hub - Orchestrates multi-LLM visibility analysis.
Aggregates results from OpenAI, Perplexity, and Gemini into unified visibility data.
"""

import logging
from typing import List, Dict, Any
from collections import Counter

from services.config import (
    OPENAI_ENABLED, PERPLEXITY_ENABLED, GEMINI_ENABLED,
    MAX_VISIBILITY_QUERIES_PER_PROVIDER, get_enabled_providers
)
from services.visibility_models import (
    QueryVisibilityAggregate, ProviderVisibility, 
    VisibilitySummary, MultiLLMVisibilityResult
)
from services.openai_visibility import run_openai_visibility_for_queries
from services.perplexity_visibility import run_perplexity_visibility_for_queries
from services.gemini_visibility import run_gemini_visibility_for_queries
from services.ekkoscope_sentinel import log_ai_query

logger = logging.getLogger(__name__)


def compute_visibility_summary(
    aggregates: List[QueryVisibilityAggregate],
    business_name: str
) -> VisibilitySummary:
    """
    Compute summary statistics across all queries and providers.
    
    Args:
        aggregates: List of QueryVisibilityAggregate objects
        business_name: Name of the target business
    
    Returns:
        VisibilitySummary with computed stats
    """
    total_queries = len(aggregates)
    
    provider_stats: Dict[str, Dict[str, Any]] = {}
    competitor_counts: Dict[str, int] = {}
    competitor_by_provider: Dict[str, Dict[str, int]] = {}
    intent_breakdown: Dict[str, int] = {}
    overall_target_found = 0
    
    provider_names = ["openai_sim", "perplexity_web", "gemini_sim"]
    for pname in provider_names:
        provider_stats[pname] = {
            "total_probes": 0,
            "successful_probes": 0,
            "target_found": 0,
            "target_percent": 0.0
        }
        competitor_by_provider[pname] = {}
    
    for agg in aggregates:
        if agg.intent:
            intent_breakdown[agg.intent] = intent_breakdown.get(agg.intent, 0) + 1
        
        query_target_found = False
        
        for pv in agg.providers:
            provider = pv.provider
            if provider not in provider_stats:
                provider_stats[provider] = {
                    "total_probes": 0,
                    "successful_probes": 0,
                    "target_found": 0,
                    "target_percent": 0.0
                }
                competitor_by_provider[provider] = {}
            
            provider_stats[provider]["total_probes"] += 1
            
            if pv.success:
                provider_stats[provider]["successful_probes"] += 1
            
            if pv.target_found:
                provider_stats[provider]["target_found"] += 1
                query_target_found = True
            
            for brand in pv.recommended_brands:
                name = brand.name
                if name.lower() != business_name.lower():
                    competitor_counts[name] = competitor_counts.get(name, 0) + 1
                    if provider not in competitor_by_provider:
                        competitor_by_provider[provider] = {}
                    competitor_by_provider[provider][name] = competitor_by_provider[provider].get(name, 0) + 1
        
        if query_target_found:
            overall_target_found += 1
    
    for pname, stats in provider_stats.items():
        if stats["successful_probes"] > 0:
            stats["target_percent"] = round(
                (stats["target_found"] / stats["successful_probes"]) * 100, 1
            )
    
    top_competitors = [
        {"name": name, "count": count, "percent": round((count / total_queries) * 100, 1) if total_queries > 0 else 0}
        for name, count in sorted(competitor_counts.items(), key=lambda x: -x[1])[:10]
    ]
    
    competitor_by_provider_formatted: Dict[str, List[Dict[str, Any]]] = {}
    for pname, counts in competitor_by_provider.items():
        competitor_by_provider_formatted[pname] = [
            {"name": name, "count": count}
            for name, count in sorted(counts.items(), key=lambda x: -x[1])[:10]
        ]
    
    return VisibilitySummary(
        total_queries=total_queries,
        provider_stats=provider_stats,
        overall_target_found=overall_target_found,
        overall_target_percent=round((overall_target_found / total_queries) * 100, 1) if total_queries > 0 else 0.0,
        top_competitors=top_competitors,
        competitor_by_provider=competitor_by_provider_formatted,
        intent_breakdown=intent_breakdown
    )


def run_multi_llm_visibility(
    business_name: str,
    primary_domain: str,
    regions: List[str],
    queries_with_intent: List[Dict[str, Any]],
    run_openai: bool = True,
    run_perplexity: bool = True,
    run_gemini: bool = True
) -> MultiLLMVisibilityResult:
    """
    Run visibility probes across all enabled LLM providers.
    
    Args:
        business_name: Name of the business being analyzed
        primary_domain: Business website URL
        regions: Geographic regions
        queries_with_intent: List of dicts with 'query', 'intent', 'intent_value' keys
        run_openai: Whether to run OpenAI visibility (if enabled)
        run_perplexity: Whether to run Perplexity visibility (if enabled)
        run_gemini: Whether to run Gemini visibility (if enabled)
    
    Returns:
        MultiLLMVisibilityResult with aggregated data from all providers
    """
    import sys
    queries_to_probe = queries_with_intent[:MAX_VISIBILITY_QUERIES_PER_PROVIDER]
    
    print(f"[VISIBILITY HUB] Starting with {len(queries_to_probe)} queries for {business_name}")
    sys.stdout.flush()
    
    logger.info(
        "Running multi-LLM visibility for %s with %d queries across providers: %s",
        business_name, len(queries_to_probe), get_enabled_providers()
    )
    
    agg_by_query: Dict[str, QueryVisibilityAggregate] = {}
    for item in queries_to_probe:
        q = item.get("query", "")
        if q:
            agg_by_query[q] = QueryVisibilityAggregate(
                query=q,
                intent=item.get("intent"),
                intent_value=item.get("intent_value"),
                providers=[]
            )
    
    providers_used = []
    
    if run_openai and OPENAI_ENABLED:
        print("[VISIBILITY HUB] Starting OpenAI visibility probe...")
        sys.stdout.flush()
        logger.info("Running OpenAI simulated visibility probe...")
        try:
            openai_results = run_openai_visibility_for_queries(
                business_name, primary_domain, regions, queries_to_probe
            )
            print(f"[VISIBILITY HUB] OpenAI complete: {len(openai_results) if openai_results else 0} results")
            sys.stdout.flush()
            if openai_results and len(openai_results) > 0:
                successful_count = sum(1 for r in openai_results if r.success)
                print(f"[VISIBILITY HUB] OpenAI results: {len(openai_results)} total, {successful_count} successful")
                sys.stdout.flush()
                if successful_count > 0:
                    for vis in openai_results:
                        if vis.query in agg_by_query:
                            agg_by_query[vis.query].providers.append(vis)
                        log_ai_query(model="chatgpt", prompt=vis.query, business_name=business_name)
                    providers_used.append("openai_sim")
                    print(f"[VISIBILITY HUB] Added 'openai_sim' to providers_used")
                    sys.stdout.flush()
                    logger.info("OpenAI visibility: %d results (%d successful)", len(openai_results), successful_count)
                else:
                    logger.warning("OpenAI visibility: all %d probes failed", len(openai_results))
            else:
                logger.info("OpenAI visibility: no results returned")
        except Exception as e:
            print(f"[VISIBILITY HUB] OpenAI FAILED: {e}")
            sys.stdout.flush()
            logger.error("OpenAI visibility probe failed: %s", e)
    
    print(f"[VISIBILITY HUB] Perplexity check: run={run_perplexity}, ENABLED={PERPLEXITY_ENABLED}")
    sys.stdout.flush()
    
    if run_perplexity and PERPLEXITY_ENABLED:
        print("[VISIBILITY HUB] Starting Perplexity visibility probe...")
        sys.stdout.flush()
        logger.info("Running Perplexity web-grounded visibility probe...")
        try:
            perplexity_results = run_perplexity_visibility_for_queries(
                business_name, primary_domain, regions, queries_to_probe
            )
            if perplexity_results and len(perplexity_results) > 0:
                successful_count = sum(1 for r in perplexity_results if r.success)
                print(f"[VISIBILITY HUB] Perplexity results: {len(perplexity_results)} total, {successful_count} successful")
                sys.stdout.flush()
                if successful_count > 0:
                    for vis in perplexity_results:
                        if vis.query in agg_by_query:
                            agg_by_query[vis.query].providers.append(vis)
                        log_ai_query(model="perplexity", prompt=vis.query, business_name=business_name)
                    providers_used.append("perplexity_web")
                    print(f"[VISIBILITY HUB] Added 'perplexity_web' to providers_used")
                    sys.stdout.flush()
                    logger.info("Perplexity visibility: %d results (%d successful)", len(perplexity_results), successful_count)
                else:
                    logger.warning("Perplexity visibility: all %d probes failed", len(perplexity_results))
            else:
                logger.info("Perplexity visibility: no results returned")
        except Exception as e:
            logger.error("Perplexity visibility probe failed: %s", e)
    
    print(f"[VISIBILITY HUB] Gemini check: run={run_gemini}, ENABLED={GEMINI_ENABLED}")
    sys.stdout.flush()
    
    if run_gemini and GEMINI_ENABLED:
        print("[VISIBILITY HUB] Starting Gemini visibility probe...")
        sys.stdout.flush()
        logger.info("Running Gemini simulated visibility probe...")
        try:
            gemini_results = run_gemini_visibility_for_queries(
                business_name, primary_domain, regions, queries_to_probe
            )
            print(f"[VISIBILITY HUB] Gemini complete: {len(gemini_results) if gemini_results else 0} results")
            sys.stdout.flush()
            if gemini_results and len(gemini_results) > 0:
                successful_count = sum(1 for r in gemini_results if r.success)
                print(f"[VISIBILITY HUB] Gemini results: {len(gemini_results)} total, {successful_count} successful")
                sys.stdout.flush()
                if successful_count > 0:
                    for vis in gemini_results:
                        if vis.query in agg_by_query:
                            agg_by_query[vis.query].providers.append(vis)
                        log_ai_query(model="gemini", prompt=vis.query, business_name=business_name)
                    providers_used.append("gemini_sim")
                    print(f"[VISIBILITY HUB] Added 'gemini_sim' to providers_used")
                    sys.stdout.flush()
                    logger.info("Gemini visibility: %d results (%d successful)", len(gemini_results), successful_count)
                else:
                    print(f"[VISIBILITY HUB] Gemini: all {len(gemini_results)} probes failed (success=False)")
                    sys.stdout.flush()
                    logger.warning("Gemini visibility: all %d probes failed", len(gemini_results))
            else:
                print("[VISIBILITY HUB] Gemini: no results returned")
                sys.stdout.flush()
                logger.info("Gemini visibility: no results returned")
        except Exception as e:
            print(f"[VISIBILITY HUB] Gemini FAILED: {e}")
            sys.stdout.flush()
            logger.error("Gemini visibility probe failed: %s", e)
    else:
        print(f"[VISIBILITY HUB] Gemini skipped: run_gemini={run_gemini}, GEMINI_ENABLED={GEMINI_ENABLED}")
        sys.stdout.flush()
    
    aggregates = list(agg_by_query.values())
    
    summary = compute_visibility_summary(aggregates, business_name)
    
    print(f"[VISIBILITY HUB] FINAL providers_used: {providers_used} (count: {len(providers_used)})")
    sys.stdout.flush()
    
    return MultiLLMVisibilityResult(
        queries=aggregates,
        summary=summary,
        providers_used=providers_used
    )


def format_multi_llm_visibility_for_genius(
    visibility_result: MultiLLMVisibilityResult,
    business_name: str
) -> str:
    """
    Format multi-LLM visibility data into a readable summary for Genius Mode.
    
    Args:
        visibility_result: The MultiLLMVisibilityResult from run_multi_llm_visibility
        business_name: Name of the target business
    
    Returns:
        Formatted string summary for inclusion in Genius Mode prompts
    """
    if not visibility_result or not visibility_result.queries:
        return "MULTI-LLM VISIBILITY SNAPSHOT: NOT AVAILABLE (no queries probed)"
    
    summary = visibility_result.summary
    queries = visibility_result.queries
    providers = visibility_result.providers_used
    
    lines = [
        "=== MULTI-LLM VISIBILITY SNAPSHOT ===",
        f"Providers used: {', '.join(providers) if providers else 'None'}",
        f"Total queries probed: {summary.total_queries}",
        f"Queries where {business_name} was found: {summary.overall_target_found} ({summary.overall_target_percent}%)",
        ""
    ]
    
    lines.append("VISIBILITY BY PROVIDER:")
    for provider, stats in summary.provider_stats.items():
        if stats.get("total_probes", 0) > 0:
            provider_label = {
                "openai_sim": "OpenAI (ChatGPT simulation)",
                "perplexity_web": "Perplexity (web-grounded)",
                "gemini_sim": "Gemini (AI simulation)"
            }.get(provider, provider)
            lines.append(
                f"  {provider_label}: Found in {stats['target_found']}/{stats['successful_probes']} queries ({stats['target_percent']}%)"
            )
    
    lines.append("")
    lines.append("TOP COMPETITORS (across all AI channels):")
    for comp in summary.top_competitors[:8]:
        lines.append(f"  - {comp['name']}: appeared in {comp['count']} queries ({comp['percent']}%)")
    
    lines.append("")
    lines.append("QUERIES WHERE CLIENT IS NEVER MENTIONED:")
    never_mentioned = [
        agg for agg in queries 
        if not any(p.target_found for p in agg.providers)
    ]
    for agg in never_mentioned[:10]:
        lines.append(f"  - \"{agg.query}\" (intent: {agg.intent or 'unknown'})")
    
    if len(never_mentioned) > 10:
        lines.append(f"  ... and {len(never_mentioned) - 10} more")
    
    lines.append("")
    lines.append("Use this data to:")
    lines.append("  - Identify where the client is never mentioned")
    lines.append("  - Prioritize opportunities where competitors dominate across multiple assistants")
    lines.append("  - Suggest pages and actions that will improve recommendations across ALL AI channels")
    
    return "\n".join(lines)


def get_provider_display_name(provider: str) -> str:
    """Get human-readable display name for a provider."""
    return {
        "openai_sim": "OpenAI",
        "perplexity_web": "Perplexity",
        "gemini_sim": "Gemini"
    }.get(provider, provider)


def get_provider_description(provider: str) -> str:
    """Get description of what each provider does."""
    return {
        "openai_sim": "ChatGPT-style simulated assistant",
        "perplexity_web": "Web-grounded real-time search",
        "gemini_sim": "Gemini AI simulated assistant"
    }.get(provider, provider)


def run_teaser_visibility(
    business_name: str,
    primary_domain: str,
    regions: List[str],
    teaser_queries: List[Dict[str, Any]],
    early_exit_on_zero: bool = True
) -> Dict[str, Any]:
    """
    Run a lightweight teaser visibility probe for Sales Mode.
    
    Uses only 3 high-impact queries and exits early if 0% visibility is detected.
    Returns a simplified result structure for sales packets.
    
    Args:
        business_name: Name of the business being analyzed
        primary_domain: Business website URL
        regions: Geographic regions
        teaser_queries: Exactly 3 queries from generate_teaser_queries()
        early_exit_on_zero: If True, stop after first query shows 0% visibility
    
    Returns:
        Dict with teaser-specific results for sales packet generation
    """
    import sys
    
    print(f"[TEASER MODE] Starting teaser visibility for {business_name}")
    sys.stdout.flush()
    
    result = {
        "business_name": business_name,
        "domain": primary_domain,
        "score": 0,
        "score_percent": "0%",
        "total_probes": 0,
        "hits": 0,
        "queries_tested": [],
        "top_competitor": None,
        "missing_query": None,
        "providers_used": [],
        "early_exit": False
    }
    
    all_competitors: Dict[str, int] = {}
    
    for idx, query_item in enumerate(teaser_queries[:3]):
        query = query_item.get("query", "")
        intent = query_item.get("intent_type", "informational")
        
        if not query:
            continue
        
        print(f"[TEASER MODE] Query {idx+1}/3: {query}")
        sys.stdout.flush()
        
        query_result = {
            "query": query,
            "intent": intent,
            "provider_results": [],
            "target_found": False
        }
        
        queries_with_intent = [{"query": query, "intent": intent, "intent_value": query_item.get("intent_value", 8)}]
        
        if OPENAI_ENABLED:
            try:
                openai_results = run_openai_visibility_for_queries(
                    business_name, primary_domain, regions, queries_with_intent
                )
                if openai_results:
                    for vis in openai_results:
                        result["total_probes"] += 1
                        if vis.success:
                            if vis.target_found:
                                result["hits"] += 1
                                query_result["target_found"] = True
                            
                            for brand in vis.recommended_brands:
                                if brand.name.lower() != business_name.lower():
                                    all_competitors[brand.name] = all_competitors.get(brand.name, 0) + 1
                            
                            query_result["provider_results"].append({
                                "provider": "openai_sim",
                                "target_found": vis.target_found,
                                "competitors": [b.name for b in vis.recommended_brands[:3]]
                            })
                    
                    if "openai_sim" not in result["providers_used"]:
                        result["providers_used"].append("openai_sim")
                        
            except Exception as e:
                logger.warning(f"Teaser OpenAI probe failed: {e}")
        
        if GEMINI_ENABLED:
            try:
                from services.gemini_visibility import run_gemini_visibility_for_queries
                gemini_results = run_gemini_visibility_for_queries(
                    business_name, primary_domain, regions, queries_with_intent
                )
                if gemini_results:
                    for vis in gemini_results:
                        result["total_probes"] += 1
                        if vis.success:
                            if vis.target_found:
                                result["hits"] += 1
                                query_result["target_found"] = True
                            
                            for brand in vis.recommended_brands:
                                if brand.name.lower() != business_name.lower():
                                    all_competitors[brand.name] = all_competitors.get(brand.name, 0) + 1
                            
                            query_result["provider_results"].append({
                                "provider": "gemini_sim",
                                "target_found": vis.target_found,
                                "competitors": [b.name for b in vis.recommended_brands[:3]]
                            })
                    
                    if "gemini_sim" not in result["providers_used"]:
                        result["providers_used"].append("gemini_sim")
                        
            except Exception as e:
                logger.warning(f"Teaser Gemini probe failed: {e}")
        
        result["queries_tested"].append(query_result)
        
        if early_exit_on_zero and not query_result["target_found"] and result["hits"] == 0:
            result["early_exit"] = True
            result["missing_query"] = query
            print(f"[TEASER MODE] Early exit - 0% visibility confirmed on query: {query}")
            sys.stdout.flush()
            break
    
    successful_probes = sum(
        1 for qt in result["queries_tested"] 
        for pr in qt.get("provider_results", [])
    )
    
    if successful_probes == 0:
        result["error"] = "No providers available - cannot determine visibility"
        result["score_percent"] = "N/A"
        print(f"[TEASER MODE] FAILED: No successful provider probes - cannot claim 0% visibility")
        sys.stdout.flush()
        return result
    
    if result["total_probes"] > 0:
        score_pct = round((result["hits"] / result["total_probes"]) * 100, 1)
        result["score"] = score_pct
        result["score_percent"] = f"{score_pct}%"
    
    if all_competitors:
        top_comp = max(all_competitors.keys(), key=lambda k: all_competitors[k])
        result["top_competitor"] = {
            "name": top_comp,
            "mentions": all_competitors[top_comp]
        }
    
    if not result["missing_query"] and result["queries_tested"]:
        for qt in result["queries_tested"]:
            if not qt["target_found"]:
                result["missing_query"] = qt["query"]
                break
    
    print(f"[TEASER MODE] Complete: {result['score_percent']} visibility, {len(result['providers_used'])} providers, {successful_probes} successful probes")
    sys.stdout.flush()
    
    return result
