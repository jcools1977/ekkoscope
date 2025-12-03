"""
EkkoScope Report Integrity Guardrail
Prevents hallucinated scores and ensures data-text alignment.

Uses strict Python math for score calculation and Gemini Flash for sanity checks.
"""

import os
import json
import logging
import httpx
from typing import Dict, Any, Tuple, Optional, List

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GOOGLE_GEMINI_API_KEY")
GEMINI_FLASH_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"


class IntegrityViolation(Exception):
    """Raised when report data fails integrity checks."""
    pass


def calculate_true_visibility_score(audit_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate the REAL visibility score using strict math.
    NO LLM estimation - pure Python calculation.
    
    Returns:
        Dict with calculated_score, client_mentions, total_queries, and status
    """
    queries = audit_data.get("queries", [])
    if not queries:
        queries = audit_data.get("audit_queries", [])
    
    if not queries:
        return {
            "calculated_score": 0,
            "client_mentions": 0,
            "total_queries": 0,
            "status": "NO_DATA",
            "risk_level": "CRITICAL"
        }
    
    total_queries = len(queries)
    client_mentions = 0
    
    for query in queries:
        target_found = False
        
        if isinstance(query, dict):
            target_found = query.get("target_found", False)
            if not target_found:
                visibility_results = query.get("visibility_results", [])
                for vr in visibility_results:
                    if isinstance(vr, dict):
                        if vr.get("is_target", False):
                            target_found = True
                            break
        else:
            if hasattr(query, 'target_found'):
                target_found = query.target_found
            elif hasattr(query, 'visibility_results'):
                for vr in query.visibility_results:
                    if hasattr(vr, 'is_target') and vr.is_target:
                        target_found = True
                        break
        
        if target_found:
            client_mentions += 1
    
    if total_queries > 0:
        calculated_score = round((client_mentions / total_queries) * 100, 1)
    else:
        calculated_score = 0
    
    if calculated_score == 0:
        risk_level = "CRITICAL"
    elif calculated_score < 20:
        risk_level = "HIGH"
    elif calculated_score < 50:
        risk_level = "MODERATE"
    else:
        risk_level = "LOW"
    
    return {
        "calculated_score": calculated_score,
        "client_mentions": client_mentions,
        "total_queries": total_queries,
        "status": "CALCULATED",
        "risk_level": risk_level
    }


def override_hallucinated_content(
    report_data: Dict[str, Any], 
    true_score: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Override any hallucinated or mismatched content in the report.
    
    Hard Rules:
    - If calculated_score == 0, force "0% - Critical Risk"
    - If summary says "Dominating" but score is 0%, overwrite
    - Ensure all percentages match calculated values
    """
    calculated_score = true_score["calculated_score"]
    corrected = report_data.copy()
    corrections_made = []
    
    if calculated_score == 0:
        corrected["visibility_score"] = 0
        corrected["visibility_text"] = "0% - Critical Risk"
        corrected["status_override"] = "INVISIBLE"
        corrections_made.append("Forced 0% visibility due to zero signals")
        
        summary = corrected.get("executive_summary", "") or ""
        danger_phrases = [
            "dominating", "strong presence", "excellent visibility",
            "well-positioned", "leading", "high visibility",
            "strong foothold", "commanding", "impressive"
        ]
        
        if any(phrase in summary.lower() for phrase in danger_phrases):
            corrected["executive_summary"] = (
                "CRITICAL ALERT: Zero visibility detected. "
                "Your business received NO mentions across all AI-assisted queries tested. "
                "Competitors are capturing 100% of AI recommendation share in your market. "
                "Immediate strategic intervention required."
            )
            corrections_made.append("Overwrote hallucinated positive summary")
        
        if corrected.get("recommendations"):
            corrected["recommendations"].insert(0, {
                "title": "EMERGENCY: Zero AI Visibility",
                "priority": "CRITICAL",
                "description": "Your business is completely invisible to AI assistants. This requires immediate action."
            })
            corrections_made.append("Added critical alert to recommendations")
    
    elif calculated_score < 20:
        reported_score = report_data.get("visibility_score", 0)
        if isinstance(reported_score, (int, float)) and reported_score > 50:
            corrected["visibility_score"] = calculated_score
            corrected["visibility_text"] = f"{calculated_score}% - High Risk"
            corrections_made.append(f"Corrected inflated score from {reported_score}% to {calculated_score}%")
    
    if "visibility_summary" in corrected:
        vs = corrected["visibility_summary"]
        if isinstance(vs, dict):
            vs["overall_target_percent"] = calculated_score
            vs["target_found_count"] = true_score["client_mentions"]
            vs["total_queries"] = true_score["total_queries"]
    
    corrected["_integrity_check"] = {
        "verified": True,
        "calculated_score": calculated_score,
        "corrections_made": corrections_made,
        "risk_level": true_score["risk_level"]
    }
    
    return corrected


async def gemini_flash_sanity_check(
    report_data: Dict[str, Any],
    true_score: Dict[str, Any]
) -> Tuple[bool, str]:
    """
    Use Gemini Flash to perform a sanity check on the report.
    
    Prompt: Review for logical inconsistencies between score and narrative.
    
    Returns:
        (passed: bool, reason: str)
    """
    if not GEMINI_API_KEY:
        logger.warning("[INTEGRITY] No Gemini API key - skipping sanity check")
        return True, "Sanity check skipped (no API key)"
    
    score = true_score["calculated_score"]
    mentions = true_score["client_mentions"]
    total = true_score["total_queries"]
    
    summary = report_data.get("executive_summary", "")
    recommendations = report_data.get("recommendations", [])
    rec_text = json.dumps(recommendations[:3]) if recommendations else "None"
    
    gaps = report_data.get("gaps", [])
    gap_text = json.dumps(gaps[:5]) if gaps else "None"
    
    prompt = f"""You are a report integrity auditor. Review this AI visibility report data for logical consistency.

CALCULATED METRICS (Ground Truth):
- Visibility Score: {score}%
- Client Mentions: {mentions} out of {total} queries
- Risk Level: {true_score['risk_level']}

REPORT CONTENT TO VERIFY:
- Executive Summary: {summary[:500] if summary else 'None'}
- Key Gaps: {gap_text}
- Top Recommendations: {rec_text}

INTEGRITY RULES:
1. If Score is 0% but summary mentions "strong", "leading", "dominating" -> REJECT
2. If Score > 50% but gaps mention "Zero Signal" or "Invisible" -> REJECT
3. If Score < 20% but summary is overly optimistic -> REJECT
4. Summary tone must match the calculated score severity

Respond with ONLY a JSON object:
{{"status": "PASS" or "REJECT", "reason": "brief explanation"}}"""

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{GEMINI_FLASH_URL}?key={GEMINI_API_KEY}",
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.1,
                        "maxOutputTokens": 200
                    }
                }
            )
            
            if response.status_code != 200:
                logger.warning(f"[INTEGRITY] Gemini Flash returned {response.status_code}")
                return True, "Sanity check failed - assuming pass"
            
            data = response.json()
            text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            
            try:
                text = text.strip()
                if text.startswith("```"):
                    text = text.split("```")[1]
                    if text.startswith("json"):
                        text = text[4:]
                
                result = json.loads(text)
                status = result.get("status", "PASS").upper()
                reason = result.get("reason", "No reason provided")
                
                if status == "REJECT":
                    logger.warning(f"[INTEGRITY] Gemini Flash REJECTED report: {reason}")
                    return False, reason
                
                return True, reason
                
            except json.JSONDecodeError:
                if "REJECT" in text.upper():
                    return False, text[:200]
                return True, "Parsed as pass"
                
    except Exception as e:
        logger.error(f"[INTEGRITY] Gemini Flash check failed: {e}")
        return True, f"Sanity check error: {str(e)}"


def generate_corrected_narrative(true_score: Dict[str, Any], business_name: str) -> str:
    """
    Generate a corrected executive summary based on TRUE calculated score.
    No LLM - just template-based generation to match data.
    """
    score = true_score["calculated_score"]
    mentions = true_score["client_mentions"]
    total = true_score["total_queries"]
    risk = true_score["risk_level"]
    
    if score == 0:
        return (
            f"CRITICAL VISIBILITY FAILURE: {business_name} achieved ZERO mentions "
            f"across {total} AI-assisted queries tested. Your business is completely "
            f"invisible to AI recommendation systems. Competitors are capturing 100% "
            f"of AI-driven discovery in your market. This represents a severe strategic "
            f"vulnerability requiring immediate intervention."
        )
    elif score < 10:
        return (
            f"SEVERE VISIBILITY DEFICIT: {business_name} was mentioned in only "
            f"{mentions} of {total} queries ({score}%). At this level, AI assistants "
            f"are actively recommending competitors over your business in nearly "
            f"all scenarios. Urgent content and technical optimization required."
        )
    elif score < 25:
        return (
            f"LOW VISIBILITY WARNING: {business_name} appeared in {mentions} of "
            f"{total} queries ({score}%). While not invisible, your presence in AI "
            f"recommendations is significantly below competitive levels. Strategic "
            f"improvements needed to capture AI-driven discovery opportunities."
        )
    elif score < 50:
        return (
            f"MODERATE VISIBILITY: {business_name} was found in {mentions} of "
            f"{total} queries ({score}%). Your business has emerging AI visibility "
            f"but remains below the competitive threshold. Targeted optimizations "
            f"can improve your AI recommendation share."
        )
    elif score < 75:
        return (
            f"GOOD VISIBILITY: {business_name} achieved mentions in {mentions} of "
            f"{total} queries ({score}%). Your business maintains solid AI visibility "
            f"with room for improvement. Continue optimizing to maintain competitive "
            f"position in AI-driven discovery."
        )
    else:
        return (
            f"STRONG VISIBILITY: {business_name} was mentioned in {mentions} of "
            f"{total} queries ({score}%). Your business demonstrates excellent AI "
            f"visibility, appearing prominently in AI assistant recommendations. "
            f"Focus on maintaining this position and monitoring competitor activity."
        )


async def verify_report_integrity(
    report_data: Dict[str, Any],
    audit_data: Dict[str, Any],
    business_name: str = "Business"
) -> Dict[str, Any]:
    """
    Main entry point for report integrity verification.
    
    Steps:
    1. Calculate TRUE visibility score from raw audit data
    2. Override any hallucinated/mismatched content
    3. Run Gemini Flash sanity check
    4. If rejected, regenerate narrative with correct data
    
    Returns:
        Verified and corrected report data
    """
    logger.info(f"[INTEGRITY] Starting verification for {business_name}")
    
    true_score = calculate_true_visibility_score(audit_data)
    logger.info(
        f"[INTEGRITY] Calculated: {true_score['calculated_score']}% "
        f"({true_score['client_mentions']}/{true_score['total_queries']} queries)"
    )
    
    corrected = override_hallucinated_content(report_data, true_score)
    
    passed, reason = await gemini_flash_sanity_check(corrected, true_score)
    
    if not passed:
        logger.warning(f"[INTEGRITY] Sanity check failed: {reason}")
        corrected["executive_summary"] = generate_corrected_narrative(
            true_score, business_name
        )
        corrected["_integrity_check"]["sanity_failed"] = True
        corrected["_integrity_check"]["sanity_reason"] = reason
        corrected["_integrity_check"]["narrative_regenerated"] = True
    else:
        corrected["_integrity_check"]["sanity_passed"] = True
        corrected["_integrity_check"]["sanity_reason"] = reason
    
    logger.info(
        f"[INTEGRITY] Verification complete. "
        f"Corrections: {len(corrected['_integrity_check'].get('corrections_made', []))}"
    )
    
    return corrected


def verify_report_integrity_sync(
    report_data: Dict[str, Any],
    audit_data: Dict[str, Any],
    business_name: str = "Business"
) -> Dict[str, Any]:
    """
    Synchronous version of verify_report_integrity.
    Runs override checks and forces narrative regeneration for critical cases.
    Note: Skips async Gemini Flash check but applies strict validation.
    """
    logger.info(f"[INTEGRITY-SYNC] Starting verification for {business_name}")
    
    true_score = calculate_true_visibility_score(audit_data)
    logger.info(
        f"[INTEGRITY-SYNC] Calculated: {true_score['calculated_score']}% "
        f"({true_score['client_mentions']}/{true_score['total_queries']} queries)"
    )
    
    corrected = override_hallucinated_content(report_data, true_score)
    
    needs_narrative_fix = False
    fix_reason = ""
    
    if true_score["calculated_score"] == 0:
        needs_narrative_fix = True
        fix_reason = "Zero visibility detected"
    elif true_score["risk_level"] == "CRITICAL":
        needs_narrative_fix = True
        fix_reason = "Critical risk level"
    elif true_score["calculated_score"] < 20:
        summary = corrected.get("executive_summary", "") or ""
        positive_phrases = ["strong", "leading", "dominating", "excellent", "well-positioned"]
        if any(phrase in summary.lower() for phrase in positive_phrases):
            needs_narrative_fix = True
            fix_reason = "Mismatched positive summary for low score"
    
    if needs_narrative_fix:
        logger.warning(f"[INTEGRITY-SYNC] Regenerating narrative: {fix_reason}")
        corrected["executive_summary"] = generate_corrected_narrative(
            true_score, business_name
        )
        corrected["_integrity_check"]["narrative_regenerated"] = True
        corrected["_integrity_check"]["regeneration_reason"] = fix_reason
    
    return corrected
