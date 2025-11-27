"""
Audit Runner Service for EkkoScope Sprint 1.
Orchestrates the full audit pipeline using existing v0.3 logic.
Now integrates EkkoBrain for pattern-based learning.
"""

import os
import json
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from services.database import Business, Audit
from services.analysis import run_analysis, MissingAPIKeyError
from services.reporting import build_ekkoscope_pdf
from services.ekkobrain_reader import fetch_ekkobrain_context
from services.ekkobrain_writer import log_audit_to_ekkobrain

logger = logging.getLogger(__name__)


REPORTS_DIR = "reports"


def ensure_reports_dir():
    """Ensure reports directory exists."""
    if not os.path.exists(REPORTS_DIR):
        os.makedirs(REPORTS_DIR)


def run_audit_for_business(business: Business, audit: Audit, db_session: Session) -> Audit:
    """
    Run a complete EkkoScope audit for a business.
    
    Uses existing v0.3 logic:
    - Generates queries from the business profile
    - Calls the visibility engine (OpenAI) with those queries
    - Calls Site Inspector to fetch/analyze site content
    - Calls Genius Mode v2 to generate patterns and priority opportunities
    - Generates the PDF report
    
    Now integrates EkkoBrain:
    - Fetches relevant patterns before Genius Mode
    - Logs audit artifacts after completion for future pattern learning
    
    Args:
        business: The Business model instance
        audit: The Audit model instance (must be created with status='pending')
        db_session: SQLAlchemy database session
    
    Returns:
        Updated Audit instance
    """
    import sys
    print(f"[RUNNER DEBUG] Starting run_audit_for_business for audit {audit.id}")
    sys.stdout.flush()
    
    try:
        audit.status = "running"
        db_session.commit()
        print(f"[RUNNER DEBUG] Set status to running for audit {audit.id}")
        sys.stdout.flush()
        
        tenant_config = business.to_tenant_config()
        print(f"[RUNNER DEBUG] Got tenant config for audit {audit.id}")
        sys.stdout.flush()
        
        print(f"[RUNNER DEBUG] Calling run_analysis for audit {audit.id}...")
        sys.stdout.flush()
        analysis = run_analysis(tenant_config, business=business)
        print(f"[RUNNER DEBUG] run_analysis completed for audit {audit.id}")
        sys.stdout.flush()
        
        visibility_summary = {
            "tenant_id": analysis.get("tenant_id"),
            "tenant_name": analysis.get("tenant_name"),
            "run_at": analysis.get("run_at"),
            "total_queries": analysis.get("total_queries"),
            "mentioned_count": analysis.get("mentioned_count"),
            "primary_count": analysis.get("primary_count"),
            "avg_score": analysis.get("avg_score"),
            "visibility_summary": analysis.get("visibility_summary", ""),
            "results": analysis.get("results", [])
        }
        
        suggestions_data = {
            "suggestions": analysis.get("suggestions", []),
            "genius_insights": analysis.get("genius_insights"),
            "site_snapshot": analysis.get("site_snapshot")
        }
        
        audit.set_visibility_summary(visibility_summary)
        audit.set_suggestions(suggestions_data)
        
        site_snapshot = analysis.get("site_snapshot", {})
        audit.site_inspector_used = bool(
            site_snapshot and 
            site_snapshot.get("pages") and 
            len(site_snapshot.get("pages", [])) > 0
        )
        
        ensure_reports_dir()
        
        pdf_bytes = build_ekkoscope_pdf(tenant_config, analysis)
        
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        safe_name = "".join(c if c.isalnum() else "_" for c in business.name)
        pdf_filename = f"ekkoscope_{safe_name}_{audit.id}_{timestamp}.pdf"
        pdf_path = os.path.join(REPORTS_DIR, pdf_filename)
        
        with open(pdf_path, "wb") as f:
            f.write(pdf_bytes)
        
        audit.pdf_path = pdf_path
        audit.status = "done"
        audit.completed_at = datetime.utcnow()
        
        db_session.commit()
        
        _log_audit_artifacts_to_ekkobrain(
            db_session=db_session,
            audit=audit,
            business=business,
            analysis=analysis
        )
        
        return audit
        
    except MissingAPIKeyError as e:
        audit.status = "error"
        audit.set_visibility_summary({"error": str(e)})
        db_session.commit()
        raise
        
    except Exception as e:
        audit.status = "error"
        audit.set_visibility_summary({"error": str(e)})
        db_session.commit()
        raise


def _log_audit_artifacts_to_ekkobrain(
    db_session: Session,
    audit: Audit,
    business: Business,
    analysis: Dict[str, Any]
):
    """
    Log audit artifacts to EkkoBrain for pattern learning.
    This runs after the audit completes and is non-blocking.
    """
    try:
        queries_with_intent = analysis.get("queries_with_intent", [])
        visibility_data = analysis.get("multi_llm_visibility_data")
        genius_payload = analysis.get("genius_insights")
        
        if not genius_payload:
            logger.info("Skipping EkkoBrain logging: no genius_payload")
            return
        
        log_audit_to_ekkobrain(
            db=db_session,
            audit=audit,
            business=business,
            queries_with_intent=queries_with_intent,
            visibility_data=visibility_data,
            genius_payload=genius_payload
        )
        logger.info("EkkoBrain artifacts logged for audit_id=%d", audit.id)
        
    except Exception as e:
        logger.warning("EkkoBrain logging failed (non-fatal): %s", e)


def get_audit_analysis_data(audit: Audit) -> Optional[dict]:
    """
    Reconstruct analysis data from stored audit for display.
    Returns data in the format expected by templates.
    Also returns error information for failed audits.
    """
    visibility = audit.get_visibility_summary()
    suggestions = audit.get_suggestions()
    
    if audit.status in ("error", "stopped"):
        return {
            "visibility": {
                "error": visibility.get("error") if visibility else "Unknown error",
                "error_type": visibility.get("error_type") if visibility else None,
                "error_details": visibility.get("error_details") if visibility else None
            },
            "suggestions": None
        }
    
    if audit.status != "done":
        return None
    
    if not visibility:
        return None
    
    analysis = {
        "visibility": {
            "tenant_id": visibility.get("tenant_id"),
            "tenant_name": visibility.get("tenant_name"),
            "run_at": visibility.get("run_at"),
            "total_queries": visibility.get("total_queries", 0),
            "mentioned_count": visibility.get("mentioned_count", 0),
            "primary_count": visibility.get("primary_count", 0),
            "avg_score": visibility.get("avg_score", 0),
            "visibility_summary": visibility.get("visibility_summary", ""),
            "visibility_score": round(visibility.get("avg_score", 0) * 50, 1),
            "results": visibility.get("results", [])
        },
        "suggestions": {}
    }
    
    if suggestions:
        analysis["suggestions"]["suggestions"] = suggestions.get("suggestions", [])
        analysis["suggestions"]["genius_insights"] = suggestions.get("genius_insights")
        analysis["suggestions"]["site_snapshot"] = suggestions.get("site_snapshot")
    
    return analysis
