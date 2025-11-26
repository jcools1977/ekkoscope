"""
Audit Runner Service for EkkoScope Sprint 1.
Orchestrates the full audit pipeline using existing v0.3 logic.
"""

import os
import json
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session

from services.database import Business, Audit
from services.analysis import run_analysis, MissingAPIKeyError
from services.reporting import build_ekkoscope_pdf


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
    
    Args:
        business: The Business model instance
        audit: The Audit model instance (must be created with status='pending')
        db_session: SQLAlchemy database session
    
    Returns:
        Updated Audit instance
    """
    try:
        audit.status = "running"
        db_session.commit()
        
        tenant_config = business.to_tenant_config()
        
        analysis = run_analysis(tenant_config)
        
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


def get_audit_analysis_data(audit: Audit) -> Optional[dict]:
    """
    Reconstruct analysis data from stored audit for display.
    Returns data in the format expected by templates.
    """
    if audit.status != "done":
        return None
    
    visibility = audit.get_visibility_summary()
    suggestions = audit.get_suggestions()
    
    if not visibility:
        return None
    
    analysis = {
        "tenant_id": visibility.get("tenant_id"),
        "tenant_name": visibility.get("tenant_name"),
        "run_at": visibility.get("run_at"),
        "total_queries": visibility.get("total_queries", 0),
        "mentioned_count": visibility.get("mentioned_count", 0),
        "primary_count": visibility.get("primary_count", 0),
        "avg_score": visibility.get("avg_score", 0),
        "visibility_summary": visibility.get("visibility_summary", ""),
        "results": visibility.get("results", [])
    }
    
    if suggestions:
        analysis["suggestions"] = suggestions.get("suggestions", [])
        analysis["genius_insights"] = suggestions.get("genius_insights")
        analysis["site_snapshot"] = suggestions.get("site_snapshot")
    
    return analysis
