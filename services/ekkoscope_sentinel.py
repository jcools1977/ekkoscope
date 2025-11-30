"""
EkkoScope -> Sentinel_OS Integration
Logs AI queries and report generation events to Sentinel_OS monitoring dashboard.
"""

import os
import httpx
from datetime import datetime
from typing import Optional

SENTINEL_API_KEY = os.environ.get("SENTINEL_API_KEY")
SENTINEL_BASE_URL = "https://sentinel-os.replit.app/api"

def _send_event(event_type: str, data: dict) -> bool:
    """Send an event to Sentinel_OS."""
    if not SENTINEL_API_KEY:
        return False
    
    try:
        headers = {
            "Authorization": f"Bearer {SENTINEL_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "event_type": event_type,
            "source": "ekkoscope",
            "timestamp": datetime.utcnow().isoformat(),
            "data": data
        }
        
        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                f"{SENTINEL_BASE_URL}/events",
                json=payload,
                headers=headers
            )
            return response.status_code == 200
    except Exception as e:
        print(f"[Sentinel] Failed to send event: {e}")
        return False


def log_ai_query(model: str, prompt: str, business_name: Optional[str] = None, 
                 response_preview: Optional[str] = None, tokens_used: Optional[int] = None) -> bool:
    """
    Log an AI query to Sentinel_OS.
    
    Args:
        model: The AI model used (e.g., "chatgpt", "gemini", "perplexity")
        prompt: The prompt sent to the AI
        business_name: Optional name of the business being analyzed
        response_preview: Optional preview of the AI response (first 200 chars)
        tokens_used: Optional number of tokens used
    """
    data = {
        "model": model,
        "prompt_preview": prompt[:500] if prompt else "",
        "prompt_length": len(prompt) if prompt else 0,
    }
    
    if business_name:
        data["business_name"] = business_name
    if response_preview:
        data["response_preview"] = response_preview[:200]
    if tokens_used:
        data["tokens_used"] = tokens_used
        
    return _send_event("ai_query", data)


def log_report_generated(business_name: str, report_type: str = "geo_report", 
                         pages: Optional[int] = None, queries_analyzed: Optional[int] = None) -> bool:
    """
    Log a report generation event to Sentinel_OS.
    
    Args:
        business_name: Name of the business the report was generated for
        report_type: Type of report (e.g., "geo_report", "visibility_audit")
        pages: Optional number of pages in the report
        queries_analyzed: Optional number of queries analyzed
    """
    data = {
        "business_name": business_name,
        "report_type": report_type,
    }
    
    if pages:
        data["pages"] = pages
    if queries_analyzed:
        data["queries_analyzed"] = queries_analyzed
        
    return _send_event("report_generated", data)


def log_audit_started(business_name: str, business_type: Optional[str] = None) -> bool:
    """Log when an audit is started."""
    data = {
        "business_name": business_name,
    }
    if business_type:
        data["business_type"] = business_type
        
    return _send_event("audit_started", data)


def log_audit_completed(business_name: str, visibility_score: Optional[float] = None,
                        competitors_found: Optional[int] = None) -> bool:
    """Log when an audit is completed."""
    data = {
        "business_name": business_name,
    }
    if visibility_score is not None:
        data["visibility_score"] = visibility_score
    if competitors_found is not None:
        data["competitors_found"] = competitors_found
        
    return _send_event("audit_completed", data)
