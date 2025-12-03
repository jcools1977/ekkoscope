"""
EkkoScope - GEO Engine for AI Visibility
FastAPI application with admin panel and persistence (Sprint 1)
"""

import json
import os
import secrets
from datetime import datetime
from io import BytesIO
from typing import Optional

from fastapi import FastAPI, Request, Form, Depends, HTTPException, Cookie, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse, FileResponse, Response, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from services.analysis import run_analysis, MissingAPIKeyError
from services.reporting import build_ekkoscope_pdf
from services.dossier_generator import build_dossier_pdf
from services.database import init_db, get_db_session, Business, Audit, User, Purchase
from services.audit_runner import run_audit_for_business, get_audit_analysis_data
from services.stripe_client import load_stripe_config, create_checkout_session, create_subscription_checkout_session, create_ekkobrain_addon_checkout_session, verify_webhook_signature, get_stripe_client
from services.auth import get_current_user, login_user, logout_user, create_user, authenticate_user
from services.email_service import send_welcome_email, send_followup_email, send_audit_complete_email

app = FastAPI()

SESSION_SECRET = os.getenv("SESSION_SECRET", secrets.token_hex(32))
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

TENANTS = {}

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "ekkoscope2024")
ADMIN_EMAILS = [e.strip().lower() for e in os.getenv("ADMIN_EMAILS", "").split(",") if e.strip()]

if ADMIN_PASSWORD == "ekkoscope2024":
    import warnings
    warnings.warn(
        "SECURITY WARNING: Using default admin password. "
        "Set ADMIN_PASSWORD environment variable for production use.",
        UserWarning
    )


@app.on_event("startup")
async def startup():
    global TENANTS
    with open("data/tenants.json") as f:
        TENANTS = json.load(f)
    init_db()
    
    from services.config import OPENAI_ENABLED, PERPLEXITY_ENABLED, GEMINI_ENABLED, get_enabled_providers
    print(f"[STARTUP] OpenAI enabled: {OPENAI_ENABLED}")
    print(f"[STARTUP] Perplexity enabled: {PERPLEXITY_ENABLED}")
    print(f"[STARTUP] Gemini enabled: {GEMINI_ENABLED}")
    print(f"[STARTUP] All enabled providers: {get_enabled_providers()}")
    
    try:
        from services.ekkobrain_pinecone import init_ekkobrain_index
        init_ekkobrain_index()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("EkkoBrain init failed (non-fatal): %s", e)
    
    from datetime import datetime, timedelta
    from services.audit_scheduler import scheduler_loop, get_next_audit_date
    
    db = get_db_session()
    try:
        active_subs_without_schedule = db.query(Business).filter(
            Business.subscription_active == True,
            Business.next_audit_at == None
        ).all()
        
        if active_subs_without_schedule:
            print(f"[STARTUP] Backfilling next_audit_at for {len(active_subs_without_schedule)} active subscribers")
            for business in active_subs_without_schedule:
                business.next_audit_at = get_next_audit_date()
                if not business.subscription_start_at:
                    business.subscription_start_at = datetime.utcnow()
            db.commit()
            print(f"[STARTUP] Backfill complete")
    except Exception as e:
        print(f"[STARTUP] Backfill error (non-fatal): {e}")
    finally:
        db.close()
    
    import asyncio
    asyncio.create_task(scheduler_loop(interval_minutes=60))
    print("[STARTUP] Audit scheduler started (checks hourly for due audits)")


def get_tenant_list():
    return [
        {"id": tenant_id, "name": config["display_name"]}
        for tenant_id, config in TENANTS.items()
    ]


def is_authenticated(request: Request) -> bool:
    """Check if user is authenticated for admin access.
    Returns True if:
    - User logged in via admin password, OR
    - User is logged in as a regular user with is_admin=True
    """
    if request.session.get("authenticated", False):
        return True
    
    user = get_current_user(request)
    if user and user.is_admin:
        return True
    
    return False


def require_auth(request: Request):
    """Dependency to require authentication."""
    if not is_authenticated(request):
        raise HTTPException(status_code=302, headers={"Location": "/admin/login"})
    return True


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    user = get_current_user(request)
    if user:
        return RedirectResponse(url="/dashboard", status_code=302)
    # Redirect to signup - marketing landing page is on ekkoscope.com
    return RedirectResponse(url="/auth/signup", status_code=302)


@app.get("/auth/login", response_class=HTMLResponse)
async def auth_login_page(request: Request, next: Optional[str] = None):
    user = get_current_user(request)
    if user:
        return RedirectResponse(url=next or "/dashboard", status_code=302)
    return templates.TemplateResponse(
        "auth/login.html",
        {"request": request, "error": None, "success": None, "email": None, "next": next}
    )


@app.post("/auth/login", response_class=HTMLResponse)
async def auth_login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    next: Optional[str] = Form(None)
):
    db = get_db_session()
    try:
        user = authenticate_user(db, email, password)
        if not user:
            return templates.TemplateResponse(
                "auth/login.html",
                {"request": request, "error": "Invalid email or password", "success": None, "email": email, "next": next}
            )
        
        login_user(request, user)
        return RedirectResponse(url=next or "/dashboard", status_code=302)
    finally:
        db.close()


@app.get("/auth/signup", response_class=HTMLResponse)
async def auth_signup_page(request: Request, next: Optional[str] = None):
    user = get_current_user(request)
    if user:
        return RedirectResponse(url=next or "/dashboard", status_code=302)
    return templates.TemplateResponse(
        "auth/signup.html",
        {"request": request, "error": None, "email": None, "first_name": None, "last_name": None, "next": next}
    )


@app.post("/auth/signup", response_class=HTMLResponse)
async def auth_signup(
    request: Request,
    background_tasks: BackgroundTasks,
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    first_name: Optional[str] = Form(None),
    last_name: Optional[str] = Form(None),
    next: Optional[str] = Form(None)
):
    if password != confirm_password:
        return templates.TemplateResponse(
            "auth/signup.html",
            {"request": request, "error": "Passwords do not match", "email": email, "first_name": first_name, "last_name": last_name, "next": next}
        )
    
    if len(password) < 8:
        return templates.TemplateResponse(
            "auth/signup.html",
            {"request": request, "error": "Password must be at least 8 characters", "email": email, "first_name": first_name, "last_name": last_name, "next": next}
        )
    
    db = get_db_session()
    try:
        user = create_user(db, email, password, first_name, last_name)
        
        if email.lower().strip() in ADMIN_EMAILS:
            user.is_admin = True
            db.commit()
        
        login_user(request, user)
        
        background_tasks.add_task(send_welcome_email, email, first_name or "there")
        
        redirect_url = "/admin" if user.is_admin else (next or "/dashboard")
        return RedirectResponse(url=redirect_url, status_code=302)
    except ValueError as e:
        return templates.TemplateResponse(
            "auth/signup.html",
            {"request": request, "error": str(e), "email": email, "first_name": first_name, "last_name": last_name, "next": next}
        )
    except Exception as e:
        error_msg = "An error occurred creating your account. Please try again."
        return templates.TemplateResponse(
            "auth/signup.html",
            {"request": request, "error": error_msg, "email": email, "first_name": first_name, "last_name": last_name, "next": next}
        )
    finally:
        db.close()


@app.get("/auth/logout")
async def auth_logout(request: Request):
    logout_user(request)
    return RedirectResponse(url="/", status_code=302)


@app.get("/dashboard", response_class=HTMLResponse)
async def user_dashboard(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/auth/login?next=/dashboard", status_code=302)
    
    db = get_db_session()
    try:
        businesses = db.query(Business).filter(Business.owner_user_id == user.id).all()
        
        return templates.TemplateResponse(
            "dashboard/index.html",
            {"request": request, "user": user, "businesses": businesses}
        )
    finally:
        db.close()


@app.get("/dashboard/business/new", response_class=HTMLResponse)
async def dashboard_business_new_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/auth/login?next=/dashboard/business/new", status_code=302)
    
    return templates.TemplateResponse(
        "dashboard/business_new.html",
        {"request": request, "user": user, "error": None, "form_data": None}
    )


@app.post("/dashboard/business/new", response_class=HTMLResponse)
async def dashboard_business_new(
    request: Request,
    name: str = Form(...),
    primary_domain: str = Form(...),
    business_type: str = Form("local_service"),
    contact_name: Optional[str] = Form(None),
    contact_email: Optional[str] = Form(None),
    categories: Optional[str] = Form(None),
    regions: Optional[str] = Form(None)
):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    form_data = {
        "name": name,
        "primary_domain": primary_domain,
        "business_type": business_type,
        "contact_name": contact_name,
        "contact_email": contact_email,
        "categories": categories,
        "regions": regions
    }
    
    primary_domain = primary_domain.lower().strip()
    primary_domain = primary_domain.replace("http://", "").replace("https://", "").split("/")[0]
    
    db = get_db_session()
    try:
        business = Business(
            owner_user_id=user.id,
            name=name.strip(),
            primary_domain=primary_domain,
            business_type=business_type,
            contact_name=contact_name,
            contact_email=contact_email or user.email,
            source="dashboard"
        )
        
        if categories:
            cats = [c.strip() for c in categories.split(",") if c.strip()]
            business.set_categories(cats)
        
        if regions:
            regs = [r.strip() for r in regions.split(",") if r.strip()]
            business.set_regions(regs)
        
        db.add(business)
        db.commit()
        db.refresh(business)
        
        if user.is_admin:
            return RedirectResponse(url=f"/dashboard/business/{business.id}", status_code=302)
        return RedirectResponse(url=f"/dashboard/business/{business.id}/upgrade", status_code=302)
    except Exception as e:
        return templates.TemplateResponse(
            "dashboard/business_new.html",
            {"request": request, "user": user, "error": str(e), "form_data": form_data}
        )
    finally:
        db.close()


@app.get("/dashboard/business/{business_id}", response_class=HTMLResponse)
async def dashboard_business_detail(request: Request, business_id: int):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    db = get_db_session()
    try:
        if user.is_admin:
            business = db.query(Business).filter(Business.id == business_id).first()
        else:
            business = db.query(Business).filter(
                Business.id == business_id,
                Business.owner_user_id == user.id
            ).first()
        
        if not business:
            return RedirectResponse(url="/dashboard", status_code=302)
        
        audits = db.query(Audit).filter(Audit.business_id == business.id).order_by(Audit.created_at.desc()).all()
        
        return templates.TemplateResponse(
            "dashboard/business_detail.html",
            {"request": request, "user": user, "business": business, "audits": audits}
        )
    finally:
        db.close()


@app.post("/dashboard/business/{business_id}/run-audit")
async def dashboard_run_audit(request: Request, business_id: int, background_tasks: BackgroundTasks):
    """Admin-only: Run an audit without payment (runs in background)."""
    user = get_current_user(request)
    if not user or not user.is_admin:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    db = get_db_session()
    try:
        business = db.query(Business).filter(Business.id == business_id).first()
        if not business:
            return RedirectResponse(url="/dashboard", status_code=302)
        
        audit = Audit(
            business_id=business.id,
            channel="admin_run",
            status="pending"
        )
        db.add(audit)
        db.commit()
        db.refresh(audit)
        
        background_tasks.add_task(run_audit_background, business.id, audit.id)
        
        return RedirectResponse(url=f"/dashboard/business/{business.id}", status_code=302)
    finally:
        db.close()


@app.post("/dashboard/business/{business_id}/run-free-audit")
async def dashboard_run_free_audit(request: Request, business_id: int, background_tasks: BackgroundTasks):
    """Run a free first audit for the user (one-time only)."""
    session_user = get_current_user(request)
    if not session_user:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    db = get_db_session()
    try:
        db_user = db.query(User).filter(User.id == session_user.id).first()
        if not db_user:
            return RedirectResponse(url="/auth/login", status_code=302)
        
        if db_user.free_audit_used:
            return RedirectResponse(url=f"/dashboard/business/{business_id}/upgrade", status_code=302)
        
        business = db.query(Business).filter(
            Business.id == business_id,
            Business.owner_user_id == db_user.id
        ).first()
        if not business:
            return RedirectResponse(url="/dashboard", status_code=302)
        
        db_user.free_audit_used = True
        db.commit()
        
        audit = Audit(
            business_id=business.id,
            channel="free_report",
            status="pending"
        )
        db.add(audit)
        db.commit()
        db.refresh(audit)
        
        background_tasks.add_task(run_audit_background, business.id, audit.id)
        
        return RedirectResponse(url=f"/dashboard/business/{business.id}", status_code=302)
    finally:
        db.close()


@app.get("/dashboard/business/{business_id}/audit/{audit_id}", response_class=HTMLResponse)
async def dashboard_audit_detail(request: Request, business_id: int, audit_id: int):
    """View audit results."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    db = get_db_session()
    try:
        if user.is_admin:
            business = db.query(Business).filter(Business.id == business_id).first()
        else:
            business = db.query(Business).filter(
                Business.id == business_id,
                Business.owner_user_id == user.id
            ).first()
        
        if not business:
            return RedirectResponse(url="/dashboard", status_code=302)
        
        audit = db.query(Audit).filter(Audit.id == audit_id, Audit.business_id == business_id).first()
        if not audit:
            return RedirectResponse(url=f"/dashboard/business/{business_id}", status_code=302)
        
        analysis_data = get_audit_analysis_data(audit)
        
        return templates.TemplateResponse(
            "dashboard/audit_detail.html",
            {"request": request, "user": user, "business": business, "audit": audit, "analysis": analysis_data}
        )
    finally:
        db.close()


@app.get("/dashboard/business/{business_id}/audit/{audit_id}/analytics", response_class=HTMLResponse)
async def dashboard_audit_analytics(request: Request, business_id: int, audit_id: int):
    """View detailed analytics dashboard for an audit."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    db = get_db_session()
    try:
        if user.is_admin:
            business = db.query(Business).filter(Business.id == business_id).first()
        else:
            business = db.query(Business).filter(
                Business.id == business_id,
                Business.owner_user_id == user.id
            ).first()
        
        if not business:
            return RedirectResponse(url="/dashboard", status_code=302)
        
        audit = db.query(Audit).filter(Audit.id == audit_id, Audit.business_id == business_id).first()
        if not audit:
            return RedirectResponse(url=f"/dashboard/business/{business_id}", status_code=302)
        
        if audit.status not in ("completed", "done"):
            return RedirectResponse(url=f"/dashboard/business/{business_id}/audit/{audit_id}", status_code=302)
        
        visibility_summary = audit.get_visibility_summary() or {}
        
        summary = {
            "total_queries": visibility_summary.get("total_queries", 0),
            "overall_target_found": visibility_summary.get("overall_target_found", 0),
            "overall_target_percent": visibility_summary.get("overall_target_percent", 0),
            "provider_stats": visibility_summary.get("provider_stats", {}),
            "top_competitors": visibility_summary.get("top_competitors", []),
            "intent_breakdown": visibility_summary.get("intent_breakdown", {})
        }
        
        queries = []
        for aq in audit.audit_queries:
            providers_list = []
            for vr in aq.visibility_results:
                target_found = bool(vr.brand_name and business.name.lower() in vr.brand_name.lower())
                providers_list.append({
                    "provider": vr.provider,
                    "target_found": target_found,
                    "brand_name": vr.brand_name,
                    "rank": vr.rank
                })
            target_found_count = sum(1 for p in providers_list if p.get("target_found"))
            query_obj = type('Query', (), {
                "query": aq.query_text,
                "intent": aq.intent,
                "providers": providers_list,
                "target_found_count": target_found_count
            })()
            queries.append(query_obj)
        
        return templates.TemplateResponse(
            "dashboard/report_analytics.html",
            {
                "request": request,
                "user": user,
                "business": business,
                "audit": audit,
                "summary": summary,
                "queries": queries
            }
        )
    finally:
        db.close()


@app.get("/dashboard/business/{business_id}/audit/{audit_id}/mission", response_class=HTMLResponse)
async def dashboard_mission_control(request: Request, business_id: int, audit_id: int):
    """Mission Control - Living dashboard for AI visibility operations."""
    from sqlalchemy.orm import joinedload
    
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    db = get_db_session()
    try:
        if user.is_admin:
            business = db.query(Business).filter(Business.id == business_id).first()
        else:
            business = db.query(Business).filter(
                Business.id == business_id,
                Business.owner_user_id == user.id
            ).first()
        
        if not business:
            return RedirectResponse(url="/dashboard", status_code=302)
        
        audit = db.query(Audit).options(
            joinedload(Audit.audit_queries).joinedload(AuditQuery.visibility_results)
        ).filter(Audit.id == audit_id, Audit.business_id == business_id).first()
        if not audit:
            return RedirectResponse(url=f"/dashboard/business/{business_id}", status_code=302)
        
        if audit.status not in ("completed", "done"):
            return RedirectResponse(url=f"/dashboard/business/{business_id}/audit/{audit_id}", status_code=302)
        
        visibility_summary = audit.get_visibility_summary() or {}
        
        total_queries = visibility_summary.get("total_queries", 0)
        queries_found = visibility_summary.get("overall_target_found", 0)
        visibility_score = visibility_summary.get("overall_target_percent", 0)
        
        provider_stats = visibility_summary.get("provider_stats", {})
        
        raw_competitors = visibility_summary.get("top_competitors", []) or []
        logger.info("[MISSION] Initial raw_competitors from summary: %s", len(raw_competitors))
        
        if not raw_competitors:
            from collections import Counter
            competitor_counter = Counter()
            business_aliases = [business.name.lower()]
            brand_aliases = getattr(business, 'brand_aliases', None)
            if brand_aliases:
                business_aliases.extend([a.strip().lower() for a in brand_aliases.split(',') if a.strip()])
            
            logger.info("[MISSION] Building competitors from audit queries. Aliases: %s", business_aliases)
            
            for aq in audit.audit_queries:
                for vr in aq.visibility_results:
                    if vr.brand_name:
                        brand_lower = vr.brand_name.lower()
                        is_our_brand = any(alias in brand_lower or brand_lower in alias for alias in business_aliases)
                        if not is_our_brand and len(vr.brand_name) > 2:
                            competitor_counter[vr.brand_name] += 1
            
            raw_competitors = [{"name": name, "count": count} for name, count in competitor_counter.most_common(15)]
            logger.info("[MISSION] Built %d competitors from queries: %s", len(raw_competitors), [c['name'] for c in raw_competitors[:5]])
        
        competitors = []
        total_competitor_mentions = sum(c.get("count", 0) for c in raw_competitors) if raw_competitors else 0
        for comp in raw_competitors[:10]:
            if total_competitor_mentions > 0:
                dominance = int((comp.get("count", 0) / total_competitor_mentions) * 100)
                dominance = min(max(dominance, 5), 95)
            else:
                dominance = 0
            competitors.append({
                "name": comp.get("name", "Unknown Competitor"),
                "mentions": comp.get("count", 0),
                "dominance": dominance
            })
        
        if competitors:
            top_threat_dominance = competitors[0]["dominance"]
            market_leader_score = max(visibility_score + 15, min(65, top_threat_dominance + 20))
        else:
            top_threat_dominance = 0
            market_leader_score = max(35, visibility_score + 20)
        
        intent_breakdown = visibility_summary.get("intent_breakdown", {}) or {}
        formatted_intent = {}
        for intent_type, data in intent_breakdown.items():
            if not intent_type or intent_type.strip() == "":
                continue
            if isinstance(data, dict):
                formatted_intent[intent_type] = {
                    "total": data.get("total", 0),
                    "found": data.get("found", 0)
                }
            else:
                formatted_intent[intent_type] = {"total": int(data) if data else 0, "found": 0}
        
        if not formatted_intent:
            formatted_intent = {"general": {"total": total_queries, "found": queries_found}}
        
        missing_queries = []
        for aq in audit.audit_queries:
            found_in_any = False
            for vr in aq.visibility_results:
                if vr.brand_name and business.name.lower() in vr.brand_name.lower():
                    found_in_any = True
                    break
            if not found_in_any:
                missing_queries.append({
                    "text": aq.query_text,
                    "intent": aq.intent or "general"
                })
        
        recommendations = []
        try:
            analysis_data = get_audit_analysis_data(audit)
            if analysis_data and isinstance(analysis_data, dict):
                suggestions = analysis_data.get("suggestions")
                if suggestions:
                    sug_list = []
                    if hasattr(suggestions, "suggestions"):
                        sug_list = suggestions.suggestions or []
                    elif isinstance(suggestions, list):
                        sug_list = suggestions
                    
                    for i, sug in enumerate(sug_list[:6]):
                        priority = "Critical" if i < 2 else ("High" if i < 4 else "Normal")
                        title = getattr(sug, "title", None) or (sug.get("title") if isinstance(sug, dict) else str(sug))
                        description = getattr(sug, "details", None) or (sug.get("details", "") if isinstance(sug, dict) else "")
                        recommendations.append({
                            "title": title,
                            "description": description,
                            "priority": priority,
                            "effort": "Medium",
                            "impact": "High" if i < 3 else "Medium"
                        })
        except Exception:
            pass
        
        top_competitor = competitors[0] if competitors else None
        
        industry = (business.industry or "").lower()
        business_type = (business.business_type or "").lower()
        
        industry_avg_job_values = {
            "plumbing": 450,
            "hvac": 800,
            "roofing": 12000,
            "electrical": 350,
            "landscaping": 200,
            "pest control": 150,
            "moving": 1200,
            "cleaning": 180,
            "auto repair": 550,
            "dental": 400,
            "legal": 2500,
            "real estate": 8000,
            "insurance": 1500,
            "financial": 3000,
            "restaurant": 35,
            "retail": 75,
            "ecommerce": 350,
            "saas": 500,
            "packaging": 280,
            "shipping": 320,
            "supplies": 250,
            "manufacturing": 1500,
            "wholesale": 800,
            "b2b": 650,
        }
        
        avg_job_value = 500
        search_terms = f"{industry} {business_type}".lower()
        for ind_key, value in industry_avg_job_values.items():
            if ind_key in search_terms:
                avg_job_value = value
                break
        
        if visibility_score <= 5:
            visibility_gap = 100
        elif visibility_score <= 20:
            visibility_gap = 100 - visibility_score
        else:
            visibility_gap = max(50, 100 - visibility_score)
        
        if top_threat_dominance > 0:
            visibility_gap = max(visibility_gap, top_threat_dominance)
        
        base_monthly_inquiries = 60 if avg_job_value < 200 else (30 if avg_job_value < 1000 else 15)
        
        lost_leads_per_month = int((visibility_gap / 100) * base_monthly_inquiries)
        monthly_revenue_leak = lost_leads_per_month * avg_job_value
        hourly_revenue_leak = round(monthly_revenue_leak / 720, 2)
        
        logger.info("[REVENUE CALC] Business: %s, Industry: '%s', Type: '%s'", business.name, industry, business_type)
        logger.info("[REVENUE CALC] avg_job_value: %s, visibility_gap: %s, base_inquiries: %s", avg_job_value, visibility_gap, base_monthly_inquiries)
        logger.info("[REVENUE CALC] lost_leads: %s, monthly_leak: %s, hourly_leak: %s", lost_leads_per_month, monthly_revenue_leak, hourly_revenue_leak)
        
        return templates.TemplateResponse(
            "dashboard/mission_control.html",
            {
                "request": request,
                "user": user,
                "business": business,
                "audit": audit,
                "visibility_score": int(visibility_score),
                "total_queries": total_queries,
                "queries_found": queries_found,
                "provider_stats": provider_stats,
                "competitors": competitors,
                "top_competitor": top_competitor,
                "top_threat_dominance": top_threat_dominance,
                "market_leader_score": market_leader_score,
                "intent_breakdown": formatted_intent,
                "missing_queries": missing_queries,
                "recommendations": recommendations,
                "hourly_revenue_leak": hourly_revenue_leak,
                "monthly_revenue_leak": monthly_revenue_leak,
                "avg_job_value": avg_job_value,
                "visibility_gap": visibility_gap
            }
        )
    finally:
        db.close()


@app.get("/dashboard/business/{business_id}/edit", response_class=HTMLResponse)
async def dashboard_business_edit_page(request: Request, business_id: int):
    """Show edit form for a business."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    db = get_db_session()
    try:
        if user.is_admin:
            business = db.query(Business).filter(Business.id == business_id).first()
        else:
            business = db.query(Business).filter(
                Business.id == business_id,
                Business.owner_user_id == user.id
            ).first()
        
        if not business:
            return RedirectResponse(url="/dashboard", status_code=302)
        
        return templates.TemplateResponse(
            "dashboard/business_edit.html",
            {"request": request, "user": user, "business": business, "error": None}
        )
    finally:
        db.close()


@app.post("/dashboard/business/{business_id}/edit")
async def dashboard_business_edit(
    request: Request,
    business_id: int,
    name: str = Form(...),
    primary_domain: str = Form(...),
    business_type: str = Form("local_service"),
    categories: Optional[str] = Form(None),
    regions: Optional[str] = Form(None),
    contact_name: Optional[str] = Form(None),
    contact_email: Optional[str] = Form(None)
):
    """Update business details."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    db = get_db_session()
    try:
        if user.is_admin:
            business = db.query(Business).filter(Business.id == business_id).first()
        else:
            business = db.query(Business).filter(
                Business.id == business_id,
                Business.owner_user_id == user.id
            ).first()
        
        if not business:
            return RedirectResponse(url="/dashboard", status_code=302)
        
        business.name = name.strip()
        business.primary_domain = primary_domain.lower().strip().replace("http://", "").replace("https://", "").split("/")[0]
        business.business_type = business_type
        business.contact_name = contact_name
        business.contact_email = contact_email
        
        if categories:
            cats = [c.strip() for c in categories.split(",") if c.strip()]
            business.set_categories(cats)
        else:
            business.set_categories([])
        
        if regions:
            regs = [r.strip() for r in regions.split(",") if r.strip()]
            business.set_regions(regs)
        else:
            business.set_regions([])
        
        db.commit()
        return RedirectResponse(url=f"/dashboard/business/{business.id}", status_code=302)
    except Exception as e:
        return templates.TemplateResponse(
            "dashboard/business_edit.html",
            {"request": request, "user": user, "business": business, "error": str(e)}
        )
    finally:
        db.close()


@app.post("/dashboard/business/{business_id}/audit/{audit_id}/delete")
async def dashboard_delete_audit(request: Request, business_id: int, audit_id: int):
    """Delete an audit."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    db = get_db_session()
    try:
        if user.is_admin:
            business = db.query(Business).filter(Business.id == business_id).first()
        else:
            business = db.query(Business).filter(
                Business.id == business_id,
                Business.owner_user_id == user.id
            ).first()
        
        if not business:
            return RedirectResponse(url="/dashboard", status_code=302)
        
        audit = db.query(Audit).filter(Audit.id == audit_id, Audit.business_id == business_id).first()
        if audit:
            if audit.pdf_path:
                import os as osmod
                if osmod.path.exists(audit.pdf_path):
                    osmod.remove(audit.pdf_path)
            db.delete(audit)
            db.commit()
        
        return RedirectResponse(url=f"/dashboard/business/{business_id}", status_code=302)
    finally:
        db.close()


@app.post("/dashboard/business/{business_id}/audit/{audit_id}/stop")
async def dashboard_stop_audit(request: Request, business_id: int, audit_id: int):
    """Stop a running audit by setting its status to error."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    db = get_db_session()
    try:
        if user.is_admin:
            business = db.query(Business).filter(Business.id == business_id).first()
        else:
            business = db.query(Business).filter(
                Business.id == business_id,
                Business.owner_user_id == user.id
            ).first()
        
        if not business:
            return RedirectResponse(url="/dashboard", status_code=302)
        
        audit = db.query(Audit).filter(Audit.id == audit_id, Audit.business_id == business_id).first()
        if audit and audit.status in ('running', 'pending'):
            audit.status = 'stopped'
            audit.set_visibility_summary({"error": "Audit was manually stopped by user"})
            db.commit()
        
        return RedirectResponse(url=f"/dashboard/business/{business_id}", status_code=302)
    finally:
        db.close()


@app.get("/dashboard/business/{business_id}/upgrade", response_class=HTMLResponse)
async def dashboard_business_upgrade(request: Request, business_id: int):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    db = get_db_session()
    try:
        business = db.query(Business).filter(
            Business.id == business_id,
            Business.owner_user_id == user.id
        ).first()
        
        if not business:
            return RedirectResponse(url="/dashboard", status_code=302)
        
        return templates.TemplateResponse(
            "dashboard/upgrade.html",
            {"request": request, "user": user, "business": business}
        )
    finally:
        db.close()


@app.post("/dashboard/business/{business_id}/checkout/report")
async def dashboard_checkout_report(request: Request, business_id: int):
    """Checkout for $490 Full GEO Report - one-time payment."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    db = get_db_session()
    try:
        business = db.query(Business).filter(
            Business.id == business_id,
            Business.owner_user_id == user.id
        ).first()
        
        if not business:
            return RedirectResponse(url="/dashboard", status_code=302)
        
        await load_stripe_config()
        stripe_client = get_stripe_client()
        
        report_price_id = os.getenv("STRIPE_PRICE_REPORT_490")
        if not report_price_id:
            return RedirectResponse(url=f"/dashboard/business/{business.id}/upgrade?error=not_configured", status_code=302)
        
        domain = os.getenv("REPLIT_DEV_DOMAIN") or os.getenv("REPLIT_DOMAINS", "").split(",")[0]
        if not domain:
            domain = "localhost:5000"
        
        protocol = "https" if "replit" in domain else "http"
        base_url = f"{protocol}://{domain}"
        
        success_url = f"{base_url}/dashboard/success?session_id={{CHECKOUT_SESSION_ID}}&product=report&business_id={business.id}"
        cancel_url = f"{base_url}/dashboard/business/{business.id}/upgrade"
        
        session = stripe_client.checkout.Session.create(
            mode="payment",
            line_items=[{"price": report_price_id, "quantity": 1}],
            success_url=success_url,
            cancel_url=cancel_url,
            customer_email=user.email,
            metadata={
                "user_id": str(user.id),
                "business_id": str(business.id),
                "product": "geo_report_490"
            }
        )
        return RedirectResponse(url=session.url, status_code=303)
    except Exception as e:
        print(f"Report checkout error: {e}")
        return RedirectResponse(url=f"/dashboard/business/{business_id}/upgrade", status_code=302)
    finally:
        db.close()


@app.post("/dashboard/business/{business_id}/checkout/continuous")
async def dashboard_checkout_continuous(request: Request, business_id: int):
    """Checkout for $290/month Continuous Monitoring - recurring."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    db = get_db_session()
    try:
        business = db.query(Business).filter(
            Business.id == business_id,
            Business.owner_user_id == user.id
        ).first()
        
        if not business:
            return RedirectResponse(url="/dashboard", status_code=302)
        
        await load_stripe_config()
        stripe_client = get_stripe_client()
        
        continuous_price_id = os.getenv("STRIPE_PRICE_CONTINUOUS_290")
        if not continuous_price_id:
            return RedirectResponse(url=f"/dashboard/business/{business.id}/upgrade?error=not_configured", status_code=302)
        
        domain = os.getenv("REPLIT_DEV_DOMAIN") or os.getenv("REPLIT_DOMAINS", "").split(",")[0]
        if not domain:
            domain = "localhost:5000"
        
        protocol = "https" if "replit" in domain else "http"
        base_url = f"{protocol}://{domain}"
        
        success_url = f"{base_url}/dashboard/success?session_id={{CHECKOUT_SESSION_ID}}&product=continuous&business_id={business.id}"
        cancel_url = f"{base_url}/dashboard/business/{business.id}/upgrade"
        
        session = stripe_client.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": continuous_price_id, "quantity": 1}],
            success_url=success_url,
            cancel_url=cancel_url,
            customer_email=user.email,
            metadata={
                "user_id": str(user.id),
                "business_id": str(business.id),
                "product": "continuous_290"
            }
        )
        return RedirectResponse(url=session.url, status_code=302)
    except Exception as e:
        print(f"Continuous checkout error: {e}")
        return RedirectResponse(url=f"/dashboard/business/{business_id}/upgrade", status_code=302)
    finally:
        db.close()


@app.post("/dashboard/business/{business_id}/checkout/ekkobrain-addon")
async def dashboard_checkout_ekkobrain_addon(request: Request, business_id: int):
    """Checkout for EkkoBrain add-on only - $149/month for existing subscribers."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    db = get_db_session()
    try:
        business = db.query(Business).filter(
            Business.id == business_id,
            Business.owner_user_id == user.id
        ).first()
        
        if not business:
            return RedirectResponse(url="/dashboard", status_code=302)
        
        if not business.subscription_active:
            return RedirectResponse(url=f"/dashboard/business/{business.id}/upgrade", status_code=302)
        
        request.session["ekkobrain_addon_business_id"] = business.id
        
        domain = os.getenv("REPLIT_DEV_DOMAIN") or os.getenv("REPLIT_DOMAINS", "").split(",")[0]
        if not domain:
            domain = "localhost:5000"
        
        protocol = "https" if "replit" in domain else "http"
        base_url = f"{protocol}://{domain}"
        
        success_url = f"{base_url}/dashboard/success?session_id={{CHECKOUT_SESSION_ID}}"
        cancel_url = f"{base_url}/dashboard/business/{business.id}"
        
        session = await create_ekkobrain_addon_checkout_session(
            business_id=business.id,
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={"user_id": str(user.id), "plan": "ekkobrain_addon"}
        )
        return RedirectResponse(url=session.url, status_code=302)
    except Exception as e:
        return RedirectResponse(url=f"/dashboard/business/{business.id}", status_code=302)
    finally:
        db.close()


@app.get("/dashboard/success", response_class=HTMLResponse)
async def dashboard_payment_success(request: Request, session_id: Optional[str] = None):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    return templates.TemplateResponse(
        "dashboard/success.html",
        {"request": request, "user": user, "session_id": session_id}
    )


@app.get("/checkout/report")
async def checkout_report(request: Request):
    """Checkout for $490 Full GEO Report - one-time."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/auth/login?next=/checkout/report", status_code=302)
    
    try:
        await load_stripe_config()
        stripe_client = get_stripe_client()
        
        report_price_id = os.getenv("STRIPE_PRICE_REPORT_490")
        if not report_price_id:
            print("Report checkout error: STRIPE_PRICE_REPORT_490 not configured")
            return RedirectResponse(url="/dashboard?error=report_not_configured", status_code=302)
        
        domain = os.getenv("REPLIT_DEV_DOMAIN") or os.getenv("REPLIT_DOMAINS", "").split(",")[0]
        if not domain:
            domain = "localhost:5000"
        
        protocol = "https" if "replit" in domain else "http"
        base_url = f"{protocol}://{domain}"
        
        success_url = f"{base_url}/dashboard/success?session_id={{CHECKOUT_SESSION_ID}}&product=report"
        cancel_url = f"{base_url}/dashboard"
        
        session = stripe_client.checkout.Session.create(
            mode="payment",
            line_items=[{"price": report_price_id, "quantity": 1}],
            success_url=success_url,
            cancel_url=cancel_url,
            customer_email=user.email,
            metadata={
                "user_id": str(user.id),
                "product": "geo_report_490"
            }
        )
        return RedirectResponse(url=session.url, status_code=302)
    except Exception as e:
        print(f"Report checkout error: {e}")
        return RedirectResponse(url="/dashboard?error=checkout_failed", status_code=302)


@app.get("/checkout/continuous")
async def checkout_continuous(request: Request):
    """Checkout for $290/month Continuous Monitoring - recurring."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/auth/login?next=/checkout/continuous", status_code=302)
    
    try:
        await load_stripe_config()
        stripe_client = get_stripe_client()
        
        continuous_price_id = os.getenv("STRIPE_PRICE_CONTINUOUS_290")
        if not continuous_price_id:
            print("Continuous checkout error: STRIPE_PRICE_CONTINUOUS_290 not configured")
            return RedirectResponse(url="/dashboard?error=continuous_not_configured", status_code=302)
        
        domain = os.getenv("REPLIT_DEV_DOMAIN") or os.getenv("REPLIT_DOMAINS", "").split(",")[0]
        if not domain:
            domain = "localhost:5000"
        
        protocol = "https" if "replit" in domain else "http"
        base_url = f"{protocol}://{domain}"
        
        success_url = f"{base_url}/dashboard/success?session_id={{CHECKOUT_SESSION_ID}}&product=continuous"
        cancel_url = f"{base_url}/dashboard"
        
        session = stripe_client.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": continuous_price_id, "quantity": 1}],
            success_url=success_url,
            cancel_url=cancel_url,
            customer_email=user.email,
            metadata={
                "user_id": str(user.id),
                "product": "continuous_290"
            }
        )
        return RedirectResponse(url=session.url, status_code=302)
    except Exception as e:
        print(f"Continuous checkout error: {e}")
        return RedirectResponse(url="/dashboard?error=checkout_failed", status_code=302)


@app.get("/dashboard/business/{business_id}/audit/{audit_id}/remediate", response_class=HTMLResponse)
async def dashboard_remediate_audit(request: Request, business_id: int, audit_id: int):
    """View remediation options for a completed audit."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    db = get_db_session()
    try:
        business = db.query(Business).filter(
            Business.id == business_id,
            Business.owner_user_id == user.id
        ).first()
        
        if not business:
            return RedirectResponse(url="/dashboard", status_code=302)
        
        audit = db.query(Audit).filter(
            Audit.id == audit_id,
            Audit.business_id == business.id
        ).first()
        
        if not audit or audit.status not in ("completed", "done"):
            return RedirectResponse(url=f"/dashboard/business/{business_id}", status_code=302)
        
        return templates.TemplateResponse(
            "dashboard/remediate.html",
            {"request": request, "user": user, "business": business, "audit": audit}
        )
    finally:
        db.close()


@app.post("/dashboard/business/{business_id}/audit/{audit_id}/run-remediation")
async def run_remediation(request: Request, business_id: int, audit_id: int, background_tasks: BackgroundTasks):
    """Run full auto-remediation on an audit."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    db = get_db_session()
    try:
        business = db.query(Business).filter(
            Business.id == business_id,
            Business.owner_user_id == user.id
        ).first()
        
        if not business:
            return RedirectResponse(url="/dashboard", status_code=302)
        
        audit = db.query(Audit).filter(
            Audit.id == audit_id,
            Audit.business_id == business.id,
            Audit.status.in_(["completed", "done"])
        ).first()
        
        if not audit:
            return RedirectResponse(url=f"/dashboard/business/{business_id}", status_code=302)
        
        from services.pdf_parser import parse_geo_report
        from services.fix_planner import generate_fix_plan
        from services.remediation_agents import RemediationOrchestrator
        from services.fixed_report import save_fixed_report
        
        report_path = audit.report_path
        if not report_path or not os.path.exists(report_path):
            return RedirectResponse(url=f"/dashboard/business/{business_id}/audit/{audit_id}?error=no_report", status_code=302)
        
        try:
            parsed_report = parse_geo_report(report_path)
            
            business_context = {
                "business_type": business.business_type or "",
                "domain": business.domain or "",
                "categories": business.categories or []
            }
            
            fix_plan = generate_fix_plan(parsed_report, business_context)
            
            orchestrator = RemediationOrchestrator(parsed_report, business_context)
            remediation_result = orchestrator.run_full_remediation(fix_plan)
            
            fixed_report_path = save_fixed_report(
                business.business_name,
                remediation_result
            )
            
            audit.remediation_result = json.dumps(remediation_result)
            audit.fixed_report_path = fixed_report_path
            db.commit()
            
            return RedirectResponse(
                url=f"/dashboard/business/{business_id}/audit/{audit_id}/fixed-report",
                status_code=302
            )
            
        except Exception as e:
            print(f"Remediation error: {e}")
            return RedirectResponse(
                url=f"/dashboard/business/{business_id}/audit/{audit_id}?error=remediation_failed",
                status_code=302
            )
    finally:
        db.close()


@app.get("/dashboard/business/{business_id}/audit/{audit_id}/fixed-report")
async def get_fixed_report(request: Request, business_id: int, audit_id: int):
    """Download the fixed report PDF."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    db = get_db_session()
    try:
        business = db.query(Business).filter(
            Business.id == business_id,
            Business.owner_user_id == user.id
        ).first()
        
        if not business:
            return RedirectResponse(url="/dashboard", status_code=302)
        
        audit = db.query(Audit).filter(
            Audit.id == audit_id,
            Audit.business_id == business.id
        ).first()
        
        if not audit or not audit.fixed_report_path:
            return RedirectResponse(url=f"/dashboard/business/{business_id}/audit/{audit_id}", status_code=302)
        
        if not os.path.exists(audit.fixed_report_path):
            return RedirectResponse(url=f"/dashboard/business/{business_id}/audit/{audit_id}", status_code=302)
        
        return FileResponse(
            audit.fixed_report_path,
            media_type="application/pdf",
            filename=os.path.basename(audit.fixed_report_path)
        )
    finally:
        db.close()


@app.get("/checkout/autofix")
async def checkout_autofix(request: Request):
    """Checkout for $1188/month Auto-Fix subscription (reports + agents). Admin only during beta."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/auth/login?next=/checkout/autofix", status_code=302)
    
    if not user.is_admin:
        return RedirectResponse(url="/pricing?error=beta_admin_only", status_code=302)
    
    try:
        await load_stripe_config()
        stripe_client = get_stripe_client()
        
        domain = os.getenv("REPLIT_DEV_DOMAIN") or os.getenv("REPLIT_DOMAINS", "").split(",")[0]
        if not domain:
            domain = "localhost:5000"
        
        protocol = "https" if "replit" in domain else "http"
        base_url = f"{protocol}://{domain}"
        
        success_url = f"{base_url}/dashboard/success?session_id={{CHECKOUT_SESSION_ID}}&product=autofix"
        cancel_url = f"{base_url}/pricing"
        
        session = stripe_client.checkout.Session.create(
            mode="subscription",
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "unit_amount": 118800,
                    "recurring": {"interval": "month"},
                    "product_data": {
                        "name": "EkkoScope Auto-Fix",
                        "description": "Bi-weekly reports + 4 AI agents auto-generate fixes"
                    }
                },
                "quantity": 1
            }],
            success_url=success_url,
            cancel_url=cancel_url,
            customer_email=user.email,
            metadata={
                "user_id": str(user.id),
                "product": "autofix_1188"
            }
        )
        return RedirectResponse(url=session.url, status_code=302)
    except Exception as e:
        print(f"Auto-fix checkout error: {e}")
        return RedirectResponse(url="/dashboard?error=checkout_failed", status_code=302)


@app.post("/dashboard/business/{business_id}/checkout/autofix")
async def dashboard_checkout_autofix(request: Request, business_id: int):
    """Checkout for $1188/month Auto-Fix subscription for a specific business. Admin only during beta."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    if not user.is_admin:
        return RedirectResponse(url="/dashboard?error=beta_admin_only", status_code=302)
    
    db = get_db_session()
    try:
        business = db.query(Business).filter(
            Business.id == business_id,
            Business.owner_user_id == user.id
        ).first()
        
        if not business:
            return RedirectResponse(url="/dashboard", status_code=302)
        
        await load_stripe_config()
        stripe_client = get_stripe_client()
        
        domain = os.getenv("REPLIT_DEV_DOMAIN") or os.getenv("REPLIT_DOMAINS", "").split(",")[0]
        if not domain:
            domain = "localhost:5000"
        
        protocol = "https" if "replit" in domain else "http"
        base_url = f"{protocol}://{domain}"
        
        success_url = f"{base_url}/dashboard/success?session_id={{CHECKOUT_SESSION_ID}}&product=autofix&business_id={business.id}"
        cancel_url = f"{base_url}/dashboard/business/{business.id}"
        
        session = stripe_client.checkout.Session.create(
            mode="subscription",
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "unit_amount": 118800,
                    "recurring": {"interval": "month"},
                    "product_data": {
                        "name": "EkkoScope Auto-Fix",
                        "description": f"Bi-weekly reports + 4 AI agents for {business.name}"
                    }
                },
                "quantity": 1
            }],
            success_url=success_url,
            cancel_url=cancel_url,
            customer_email=user.email,
            metadata={
                "user_id": str(user.id),
                "business_id": str(business.id),
                "product": "autofix_1188"
            }
        )
        return RedirectResponse(url=session.url, status_code=302)
    except Exception as e:
        print(f"Auto-fix checkout error: {e}")
        return RedirectResponse(url=f"/dashboard/business/{business_id}?error=checkout_failed", status_code=302)
    finally:
        db.close()


@app.get("/dashboard/business/{business_id}/audits", response_class=HTMLResponse)
async def dashboard_business_audits(request: Request, business_id: int):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    db = get_db_session()
    try:
        business = db.query(Business).filter(
            Business.id == business_id,
            Business.owner_user_id == user.id
        ).first()
        
        if not business:
            return RedirectResponse(url="/dashboard", status_code=302)
        
        audits = db.query(Audit).filter(Audit.business_id == business.id).order_by(Audit.created_at.desc()).all()
        
        return templates.TemplateResponse(
            "dashboard/audits.html",
            {"request": request, "user": user, "business": business, "audits": audits}
        )
    finally:
        db.close()


@app.post("/analyze", response_class=HTMLResponse)
async def analyze(request: Request, tenant_id: str = Form(...)):
    try:
        if tenant_id not in TENANTS:
            return templates.TemplateResponse(
                "index.html",
                {
                    "request": request,
                    "tenants": get_tenant_list(),
                    "analysis": None,
                    "selected_tenant_id": tenant_id,
                    "error": f"Invalid tenant: {tenant_id}"
                }
            )
        
        tenant_config = TENANTS[tenant_id]
        analysis = run_analysis(tenant_config)
        
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "tenants": get_tenant_list(),
                "analysis": analysis,
                "selected_tenant_id": tenant_id,
                "error": None
            }
        )
    
    except MissingAPIKeyError as e:
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "tenants": get_tenant_list(),
                "analysis": None,
                "selected_tenant_id": tenant_id,
                "error": str(e)
            }
        )
    
    except Exception as e:
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "tenants": get_tenant_list(),
                "analysis": None,
                "selected_tenant_id": tenant_id,
                "error": f"Error running analysis: {str(e)}"
            }
        )


@app.get("/report/{tenant_id}")
async def download_report(request: Request, tenant_id: str):
    """Generate and download an EkkoScope PDF report for the given tenant."""
    try:
        if tenant_id not in TENANTS:
            return templates.TemplateResponse(
                "index.html",
                {
                    "request": request,
                    "tenants": get_tenant_list(),
                    "analysis": None,
                    "selected_tenant_id": None,
                    "error": f"Invalid tenant ID: {tenant_id}"
                }
            )
        
        tenant_config = TENANTS[tenant_id]
        analysis = run_analysis(tenant_config)
        pdf_bytes = build_ekkoscope_pdf(tenant_config, analysis)
        
        return StreamingResponse(
            BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="ekkoscope_report_{tenant_id}.pdf"'
            }
        )
    
    except MissingAPIKeyError as e:
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "tenants": get_tenant_list(),
                "analysis": None,
                "selected_tenant_id": tenant_id,
                "error": str(e)
            }
        )
    
    except Exception as e:
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "tenants": get_tenant_list(),
                "analysis": None,
                "selected_tenant_id": tenant_id,
                "error": f"Error generating report: {str(e)}"
            }
        )


@app.get("/dossier/{business_id}")
async def download_dossier(request: Request, business_id: int):
    """Generate and download an EkkoScope Intelligence Dossier PDF."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    
    db = get_db_session()
    try:
        business = db.query(Business).filter(Business.id == business_id).first()
        if not business:
            raise HTTPException(status_code=404, detail="Business not found")
        
        is_admin = user.email.lower() in [e.lower() for e in ADMIN_EMAILS] if ADMIN_EMAILS else False
        if business.owner_user_id != user.id and not is_admin:
            raise HTTPException(status_code=403, detail="Not authorized")
        
        latest_audit = db.query(Audit).filter(
            Audit.business_id == business_id,
            Audit.status.in_(["done", "completed"])
        ).order_by(Audit.created_at.desc()).first()
        
        if not latest_audit:
            raise HTTPException(status_code=400, detail="No completed audit available. Run an audit first.")
        
        analysis = latest_audit.get_visibility_summary()
        if not analysis:
            raise HTTPException(status_code=400, detail="No audit results available. Run an audit first.")
        
        sherlock_data = None
        try:
            from services.sherlock_engine import get_missions_for_business, is_sherlock_enabled
            if is_sherlock_enabled():
                missions = get_missions_for_business(business_id)
                if missions:
                    sherlock_data = {"missions": missions}
        except Exception:
            pass
        
        pdf_bytes = build_dossier_pdf(
            business_name=business.name,
            analysis=analysis,
            sherlock_data=sherlock_data,
            competitor_evidence=None,
            business_id=business_id
        )
        
        safe_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in business.name)
        filename = f"ekkoscope_dossier_{safe_name}.pdf"
        
        return StreamingResponse(
            BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
    
    finally:
        db.close()


@app.get("/admin/login", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    """Show admin login page."""
    if is_authenticated(request):
        return RedirectResponse(url="/admin", status_code=302)
    
    user = get_current_user(request)
    
    return templates.TemplateResponse(
        "admin/login.html",
        {"request": request, "error": None, "user": user}
    )


@app.post("/admin/login")
async def admin_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...)
):
    """Process admin login."""
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        request.session["authenticated"] = True
        request.session["username"] = username
        return RedirectResponse(url="/admin", status_code=302)
    
    return templates.TemplateResponse(
        "admin/login.html",
        {"request": request, "error": "Invalid username or password"}
    )


@app.get("/admin/logout")
async def admin_logout(request: Request):
    """Log out admin user."""
    request.session.clear()
    return RedirectResponse(url="/admin/login", status_code=302)


@app.get("/admin/followups", response_class=HTMLResponse)
async def admin_followups(request: Request):
    """View users who need follow-up emails."""
    if not is_authenticated(request):
        return RedirectResponse(url="/admin/login", status_code=302)
    
    from datetime import timedelta
    db = get_db_session()
    try:
        cutoff_24h = datetime.utcnow() - timedelta(hours=24)
        cutoff_72h = datetime.utcnow() - timedelta(hours=72)
        
        users_needing_followup = db.query(User).filter(
            User.created_at < cutoff_24h,
            User.created_at > cutoff_72h,
            User.follow_up_sent_at == None
        ).all()
        
        non_purchasers = []
        for user in users_needing_followup:
            if len(user.purchases) == 0:
                hours_since = int((datetime.utcnow() - user.created_at).total_seconds() / 3600)
                non_purchasers.append({
                    "user": user,
                    "hours_since_signup": hours_since
                })
        
        return templates.TemplateResponse(
            "admin/followups.html",
            {"request": request, "non_purchasers": non_purchasers}
        )
    finally:
        db.close()


@app.post("/admin/followups/send")
async def admin_send_followups(request: Request, background_tasks: BackgroundTasks):
    """Send follow-up emails to non-purchasers."""
    if not is_authenticated(request):
        return RedirectResponse(url="/admin/login", status_code=302)
    
    from datetime import timedelta
    db = get_db_session()
    try:
        cutoff_24h = datetime.utcnow() - timedelta(hours=24)
        cutoff_72h = datetime.utcnow() - timedelta(hours=72)
        
        users_needing_followup = db.query(User).filter(
            User.created_at < cutoff_24h,
            User.created_at > cutoff_72h,
            User.follow_up_sent_at == None
        ).all()
        
        sent_count = 0
        for user in users_needing_followup:
            if len(user.purchases) == 0:
                hours_since = int((datetime.utcnow() - user.created_at).total_seconds() / 3600)
                background_tasks.add_task(send_followup_email, user.email, user.first_name or "there", hours_since)
                user.follow_up_sent_at = datetime.utcnow()
                sent_count += 1
        
        db.commit()
        return RedirectResponse(url=f"/admin/followups?sent={sent_count}", status_code=302)
    finally:
        db.close()


@app.get("/admin/activation-codes", response_class=HTMLResponse)
async def admin_activation_codes(request: Request):
    """List and manage activation codes."""
    if not is_authenticated(request):
        return RedirectResponse(url="/admin/login", status_code=302)
    
    from services.database import ActivationCode
    
    db = get_db_session()
    try:
        codes = (
            db.query(ActivationCode)
            .order_by(ActivationCode.created_at.desc())
            .all()
        )
        
        code_data = []
        for code in codes:
            code_data.append({
                "id": code.id,
                "code": code.code,
                "label": code.label,
                "status": code.status,
                "uses_remaining": code.uses_remaining,
                "max_uses": code.max_uses,
                "expires_at": code.expires_at,
                "redeemed_by": code.redeemed_by.email if code.redeemed_by else None,
                "redeemed_business": code.redeemed_business.name if code.redeemed_business else None,
                "redeemed_at": code.redeemed_at,
                "created_at": code.created_at
            })
        
        success = request.query_params.get("success")
        generated_codes = request.query_params.get("codes", "").split(",") if request.query_params.get("codes") else []
        
        return templates.TemplateResponse(
            "admin/activation_codes.html",
            {
                "request": request,
                "codes": code_data,
                "success": success,
                "generated_codes": [c for c in generated_codes if c],
                "username": request.session.get("username", "Admin")
            }
        )
    finally:
        db.close()


@app.post("/admin/activation-codes/generate")
async def admin_generate_codes(
    request: Request,
    count: int = Form(1),
    label: str = Form("")
):
    """Generate new activation codes."""
    if not is_authenticated(request):
        return RedirectResponse(url="/admin/login", status_code=302)
    
    from services.database import ActivationCode, generate_activation_code
    
    if count < 1:
        count = 1
    if count > 100:
        count = 100
    
    db = get_db_session()
    try:
        user = get_current_user(request)
        admin_id = user.id if user else None
        
        generated = []
        for _ in range(count):
            code_str = generate_activation_code(8)
            while db.query(ActivationCode).filter(ActivationCode.code == code_str).first():
                code_str = generate_activation_code(8)
            
            code = ActivationCode(
                code=code_str,
                label=label.strip() or f"LinkedIn Campaign",
                max_uses=1,
                uses_remaining=1,
                created_by_admin_id=admin_id
            )
            db.add(code)
            generated.append(code_str)
        
        db.commit()
        
        codes_param = ",".join(generated)
        return RedirectResponse(
            url=f"/admin/activation-codes?success=Generated {count} codes&codes={codes_param}",
            status_code=302
        )
    finally:
        db.close()


@app.post("/admin/activation-codes/{code_id}/delete")
async def admin_delete_code(request: Request, code_id: int):
    """Delete an activation code."""
    if not is_authenticated(request):
        return RedirectResponse(url="/admin/login", status_code=302)
    
    from services.database import ActivationCode
    
    db = get_db_session()
    try:
        code = db.query(ActivationCode).filter(ActivationCode.id == code_id).first()
        if code:
            db.delete(code)
            db.commit()
        return RedirectResponse(url="/admin/activation-codes?success=Code deleted", status_code=302)
    finally:
        db.close()


@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    """Admin dashboard with stats and recent audits."""
    if not is_authenticated(request):
        return RedirectResponse(url="/admin/login", status_code=302)
    
    db = get_db_session()
    try:
        business_count = db.query(Business).count()
        audit_count = db.query(Audit).count()
        
        recent_audits = (
            db.query(Audit)
            .order_by(Audit.created_at.desc())
            .limit(10)
            .all()
        )
        
        audit_data = []
        for audit in recent_audits:
            audit_data.append({
                "id": audit.id,
                "business_name": audit.business.name if audit.business else "Unknown",
                "business_id": audit.business_id,
                "channel": audit.channel,
                "status": audit.status,
                "created_at": audit.created_at,
                "completed_at": audit.completed_at
            })
        
        return templates.TemplateResponse(
            "admin/dashboard.html",
            {
                "request": request,
                "business_count": business_count,
                "audit_count": audit_count,
                "recent_audits": audit_data,
                "username": request.session.get("username", "Admin")
            }
        )
    finally:
        db.close()


@app.get("/admin/demo-pdf")
async def admin_demo_pdf(request: Request):
    """Generate a demo PDF report for prospect presentations."""
    if not is_authenticated(request):
        return RedirectResponse(url="/admin/login", status_code=302)
    
    from services.reporting_demo import generate_demo_pdf
    from fastapi.responses import Response
    
    pdf_output = generate_demo_pdf()
    pdf_bytes = bytes(pdf_output) if isinstance(pdf_output, bytearray) else pdf_output
    
    filename = f"EkkoScope_Demo_Report_{datetime.now().strftime('%Y%m%d')}.pdf"
    
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )


@app.get("/admin/businesses", response_class=HTMLResponse)
async def admin_businesses(request: Request):
    """List all businesses with visibility monitoring."""
    if not is_authenticated(request):
        return RedirectResponse(url="/admin/login", status_code=302)
    
    db = get_db_session()
    try:
        businesses = (
            db.query(Business)
            .order_by(Business.created_at.desc())
            .all()
        )
        
        business_data = []
        for biz in businesses:
            latest_audit = None
            visibility_score = None
            last_scan = None
            
            completed_audits = [a for a in biz.audits if a.status == 'done']
            if completed_audits:
                latest_audit = max(completed_audits, key=lambda a: a.completed_at or a.created_at)
                last_scan = latest_audit.completed_at or latest_audit.created_at
                
                try:
                    summary = latest_audit.get_visibility_summary()
                    if summary:
                        visibility_score = summary.get('visibility_score', summary.get('overall_visibility'))
                except:
                    pass
            
            business_data.append({
                "id": biz.id,
                "name": biz.name,
                "primary_domain": biz.primary_domain,
                "business_type": biz.business_type,
                "source": biz.source,
                "subscription_active": biz.subscription_active,
                "plan": biz.plan or "snapshot",
                "created_at": biz.created_at,
                "audit_count": len(biz.audits),
                "visibility_score": visibility_score,
                "last_scan": last_scan,
                "autofix_enabled": biz.autofix_enabled if hasattr(biz, 'autofix_enabled') else False
            })
        
        return templates.TemplateResponse(
            "admin/businesses.html",
            {
                "request": request,
                "businesses": business_data
            }
        )
    finally:
        db.close()


@app.get("/admin/business/new", response_class=HTMLResponse)
async def admin_business_form(request: Request):
    """Show admin business creation form."""
    if not is_authenticated(request):
        return RedirectResponse(url="/admin/login", status_code=302)
    
    return templates.TemplateResponse(
        "admin/business_new.html",
        {"request": request, "error": None}
    )


@app.post("/admin/business/new")
async def admin_business_create(
    request: Request,
    name: str = Form(...),
    primary_domain: str = Form(...),
    extra_domains: str = Form(""),
    business_type: str = Form("local_service"),
    regions: str = Form(""),
    categories: str = Form(""),
    contact_name: str = Form(""),
    contact_email: str = Form("")
):
    """Create a new business from admin panel."""
    if not is_authenticated(request):
        return RedirectResponse(url="/admin/login", status_code=302)
    
    db = get_db_session()
    try:
        extra_domains_list = [d.strip() for d in extra_domains.split(",") if d.strip()]
        regions_list = [r.strip() for r in regions.split(",") if r.strip()]
        categories_list = [c.strip() for c in categories.split(",") if c.strip()]
        
        business = Business(
            name=name,
            primary_domain=primary_domain,
            business_type=business_type,
            contact_name=contact_name or None,
            contact_email=contact_email or None,
            source="admin"
        )
        business.set_extra_domains(extra_domains_list)
        business.set_regions(regions_list)
        business.set_categories(categories_list)
        
        db.add(business)
        db.commit()
        db.refresh(business)
        
        return RedirectResponse(url=f"/admin/business/{business.id}", status_code=302)
    except Exception as e:
        return templates.TemplateResponse(
            "admin/business_new.html",
            {"request": request, "error": f"Error creating business: {str(e)}"}
        )
    finally:
        db.close()


@app.get("/admin/business/{business_id}", response_class=HTMLResponse)
async def admin_business_detail(request: Request, business_id: int):
    """Show business detail with audits."""
    if not is_authenticated(request):
        return RedirectResponse(url="/admin/login", status_code=302)
    
    db = get_db_session()
    try:
        business = db.query(Business).filter(Business.id == business_id).first()
        if not business:
            return templates.TemplateResponse(
                "admin/error.html",
                {"request": request, "error": "Business not found"}
            )
        
        audits = (
            db.query(Audit)
            .filter(Audit.business_id == business_id)
            .order_by(Audit.created_at.desc())
            .all()
        )
        
        audit_data = []
        for audit in audits:
            audit_data.append({
                "id": audit.id,
                "channel": audit.channel,
                "status": audit.status,
                "site_inspector_used": audit.site_inspector_used,
                "created_at": audit.created_at,
                "completed_at": audit.completed_at,
                "has_pdf": bool(audit.pdf_path)
            })
        
        return templates.TemplateResponse(
            "admin/business_detail.html",
            {
                "request": request,
                "business": {
                    "id": business.id,
                    "name": business.name,
                    "primary_domain": business.primary_domain,
                    "extra_domains": business.get_extra_domains(),
                    "business_type": business.business_type,
                    "regions": business.get_regions(),
                    "categories": business.get_categories(),
                    "contact_name": business.contact_name,
                    "contact_email": business.contact_email,
                    "source": business.source,
                    "subscription_active": business.subscription_active,
                    "plan": business.plan or "snapshot",
                    "stripe_subscription_id": business.stripe_subscription_id,
                    "created_at": business.created_at
                },
                "audits": audit_data
            }
        )
    finally:
        db.close()


@app.get("/admin/business/{business_id}/mission", response_class=HTMLResponse)
async def admin_business_mission_control(request: Request, business_id: int):
    """Redirect admin to the latest Mission Control for a business."""
    if not is_authenticated(request):
        return RedirectResponse(url="/admin/login", status_code=302)
    
    db = get_db_session()
    try:
        business = db.query(Business).filter(Business.id == business_id).first()
        if not business:
            return RedirectResponse(url="/admin/businesses", status_code=302)
        
        completed_audits = [a for a in business.audits if a.status in ('done', 'completed')]
        if not completed_audits:
            return RedirectResponse(url=f"/admin/business/{business_id}", status_code=302)
        
        latest_audit = max(completed_audits, key=lambda a: a.completed_at or a.created_at)
        return RedirectResponse(
            url=f"/dashboard/business/{business_id}/audit/{latest_audit.id}/mission",
            status_code=302
        )
    finally:
        db.close()


@app.post("/admin/business/{business_id}/run")
async def admin_run_audit(request: Request, business_id: int, background_tasks: BackgroundTasks):
    """Run an EkkoScope audit for a business (runs in background)."""
    if not is_authenticated(request):
        return RedirectResponse(url="/admin/login", status_code=302)
    
    db = get_db_session()
    try:
        business = db.query(Business).filter(Business.id == business_id).first()
        if not business:
            return RedirectResponse(url="/admin/businesses", status_code=302)
        
        audit = Audit(
            business_id=business.id,
            channel="admin_run",
            status="pending"
        )
        db.add(audit)
        db.commit()
        db.refresh(audit)
        
        background_tasks.add_task(run_audit_background, business.id, audit.id)
        
        return RedirectResponse(url=f"/admin/business/{business_id}", status_code=302)
    finally:
        db.close()


@app.post("/admin/business/{business_id}/refresh")
async def admin_refresh_audit(request: Request, business_id: int, background_tasks: BackgroundTasks):
    """Run a monthly refresh audit for an ongoing subscription business (runs in background)."""
    if not is_authenticated(request):
        return RedirectResponse(url="/admin/login", status_code=302)
    
    db = get_db_session()
    try:
        business = db.query(Business).filter(Business.id == business_id).first()
        if not business:
            return RedirectResponse(url="/admin/businesses", status_code=302)
        
        if not business.subscription_active or business.plan != "ongoing":
            return RedirectResponse(url=f"/admin/business/{business_id}", status_code=302)
        
        audit = Audit(
            business_id=business.id,
            channel="admin_run",
            status="pending"
        )
        db.add(audit)
        db.commit()
        db.refresh(audit)
        
        background_tasks.add_task(run_audit_background, business.id, audit.id)
        
        return RedirectResponse(url=f"/admin/business/{business_id}", status_code=302)
    finally:
        db.close()


@app.get("/admin/business/{business_id}/edit", response_class=HTMLResponse)
async def admin_business_edit_page(request: Request, business_id: int):
    """Show edit form for a business."""
    if not is_authenticated(request):
        return RedirectResponse(url="/admin/login", status_code=302)
    
    db = get_db_session()
    try:
        business = db.query(Business).filter(Business.id == business_id).first()
        if not business:
            return RedirectResponse(url="/admin/businesses", status_code=302)
        
        return templates.TemplateResponse(
            "admin/business_edit.html",
            {
                "request": request,
                "business": {
                    "id": business.id,
                    "name": business.name,
                    "primary_domain": business.primary_domain,
                    "extra_domains": business.get_extra_domains(),
                    "business_type": business.business_type,
                    "regions": business.get_regions(),
                    "categories": business.get_categories(),
                    "contact_name": business.contact_name,
                    "contact_email": business.contact_email
                },
                "error": None
            }
        )
    finally:
        db.close()


@app.post("/admin/business/{business_id}/edit")
async def admin_business_edit(
    request: Request,
    business_id: int,
    name: str = Form(...),
    primary_domain: str = Form(...),
    extra_domains: Optional[str] = Form(None),
    business_type: str = Form("local_service"),
    categories: Optional[str] = Form(None),
    regions: Optional[str] = Form(None),
    contact_name: Optional[str] = Form(None),
    contact_email: Optional[str] = Form(None)
):
    """Update business details (Admin)."""
    if not is_authenticated(request):
        return RedirectResponse(url="/admin/login", status_code=302)
    
    db = get_db_session()
    try:
        business = db.query(Business).filter(Business.id == business_id).first()
        if not business:
            return RedirectResponse(url="/admin/businesses", status_code=302)
        
        business.name = name.strip()
        business.primary_domain = primary_domain.lower().strip().replace("http://", "").replace("https://", "").split("/")[0]
        business.business_type = business_type
        business.contact_name = contact_name
        business.contact_email = contact_email
        
        if extra_domains:
            eds = [d.strip().lower().replace("http://", "").replace("https://", "").split("/")[0] for d in extra_domains.split(",") if d.strip()]
            business.set_extra_domains(eds)
        else:
            business.set_extra_domains([])
        
        if categories:
            cats = [c.strip() for c in categories.split(",") if c.strip()]
            business.set_categories(cats)
        else:
            business.set_categories([])
        
        if regions:
            regs = [r.strip() for r in regions.split(",") if r.strip()]
            business.set_regions(regs)
        else:
            business.set_regions([])
        
        db.commit()
        return RedirectResponse(url=f"/admin/business/{business.id}", status_code=302)
    except Exception as e:
        return templates.TemplateResponse(
            "admin/business_edit.html",
            {"request": request, "business": {"id": business_id}, "error": str(e)}
        )
    finally:
        db.close()


# =============================================================================
# CLIENT HANDOFF MODULE
# =============================================================================

@app.post("/admin/business/{business_id}/generate-claim")
async def admin_generate_claim_link(request: Request, business_id: int):
    """Generate a magic claim link for client handoff."""
    if not is_authenticated(request):
        return JSONResponse({"error": "Admin access required"}, status_code=403)
    
    from services.database import ClaimToken
    from datetime import timedelta
    
    db = get_db_session()
    try:
        business = db.query(Business).filter(Business.id == business_id).first()
        if not business:
            return JSONResponse({"error": "Business not found"}, status_code=404)
        
        user = get_current_user(request)
        if not user:
            return JSONResponse({"error": "User not found"}, status_code=403)
        
        claim = ClaimToken(
            business_id=business.id,
            created_by_user_id=user.id,
            token=ClaimToken.generate_token(),
            expires_at=datetime.utcnow() + timedelta(days=7)
        )
        
        db.add(claim)
        db.commit()
        db.refresh(claim)
        
        domain = os.getenv("REPLIT_DEV_DOMAIN", request.base_url.hostname)
        claim_url = f"https://{domain}/claim?token={claim.token}"
        
        return JSONResponse({
            "success": True,
            "claim_url": claim_url,
            "token": claim.token,
            "expires_at": claim.expires_at.isoformat(),
            "business_name": business.name
        })
        
    finally:
        db.close()


@app.get("/admin/business/{business_id}/email-script")
async def admin_get_email_script(request: Request, business_id: int):
    """Generate personalized sales email script for client handoff."""
    if not is_authenticated(request):
        return JSONResponse({"error": "Admin access required"}, status_code=403)
    
    from services.database import SherlockMission, SherlockCompetitor
    
    db = get_db_session()
    try:
        business = db.query(Business).filter(Business.id == business_id).first()
        if not business:
            return JSONResponse({"error": "Business not found"}, status_code=404)
        
        latest_audit = (
            db.query(Audit)
            .filter(Audit.business_id == business_id, Audit.status.in_(["done", "completed"]))
            .order_by(Audit.completed_at.desc())
            .first()
        )
        
        visibility_score = 0
        if latest_audit:
            summary = latest_audit.get_visibility_summary()
            if summary:
                visibility_score = summary.get("overall_score", 0)
        
        competitors = db.query(SherlockCompetitor).filter(
            SherlockCompetitor.business_id == business_id
        ).limit(3).all()
        
        competitor_names = [c.name for c in competitors] if competitors else ["[Competitor 1]", "[Competitor 2]"]
        
        missions = db.query(SherlockMission).filter(
            SherlockMission.business_id == business_id,
            SherlockMission.status == "pending"
        ).limit(3).all()
        
        gap_topic = missions[0].missing_topic if missions else "key service areas"
        
        email_script = f"""Hey [Client Name],

I ran that scan on {business.name}.

STATUS: Your AI visibility is at {visibility_score}%. Your competitor {competitor_names[0]} has significantly more coverage.

I found a semantic gap in your "{gap_topic}" content.

The good news: I've already identified {len(missions) if missions else 3} specific fixes that could dramatically improve your visibility.

View the full evidence here: [INSERT CLAIM LINK]

Want me to walk you through the findings? I can show you exactly what your competitors are doing that you're not.

Best,
[Your Name]

---
P.S. The link expires in 7 days. The longer you wait, the more leads go to {competitor_names[0]}."""

        return JSONResponse({
            "success": True,
            "email_script": email_script,
            "business_name": business.name,
            "visibility_score": visibility_score,
            "competitors": competitor_names,
            "gap_topic": gap_topic
        })
        
    finally:
        db.close()


@app.get("/claim", response_class=HTMLResponse)
async def claim_page(request: Request, token: str = None):
    """Public claim page - client sets password to access their dashboard."""
    if not token:
        return templates.TemplateResponse(
            "public/claim_error.html",
            {"request": request, "error": "No claim token provided"}
        )
    
    from services.database import ClaimToken
    
    db = get_db_session()
    try:
        claim = db.query(ClaimToken).filter(ClaimToken.token == token).first()
        
        if not claim:
            return templates.TemplateResponse(
                "public/claim_error.html",
                {"request": request, "error": "Invalid claim link"}
            )
        
        if not claim.is_valid():
            if claim.redeemed_at:
                return templates.TemplateResponse(
                    "public/claim_error.html",
                    {"request": request, "error": "This link has already been used. Please login to access your dashboard."}
                )
            else:
                return templates.TemplateResponse(
                    "public/claim_error.html",
                    {"request": request, "error": "This link has expired. Please contact us for a new link."}
                )
        
        business = db.query(Business).filter(Business.id == claim.business_id).first()
        if not business:
            return templates.TemplateResponse(
                "public/claim_error.html",
                {"request": request, "error": "Business not found"}
            )
        
        return templates.TemplateResponse(
            "public/claim.html",
            {
                "request": request,
                "token": token,
                "business_name": business.name,
                "business_domain": business.primary_domain
            }
        )
        
    finally:
        db.close()


@app.post("/claim")
async def claim_submit(
    request: Request,
    token: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    first_name: str = Form(""),
    last_name: str = Form("")
):
    """Handle claim form submission - create user account and link to business."""
    from services.database import ClaimToken
    
    db = get_db_session()
    try:
        claim = db.query(ClaimToken).filter(ClaimToken.token == token).first()
        
        if not claim or not claim.is_valid():
            return templates.TemplateResponse(
                "public/claim_error.html",
                {"request": request, "error": "Invalid or expired claim link"}
            )
        
        business = db.query(Business).filter(Business.id == claim.business_id).first()
        if not business:
            return templates.TemplateResponse(
                "public/claim_error.html",
                {"request": request, "error": "Business not found"}
            )
        
        if business.owner_user_id:
            existing_owner = db.query(User).filter(User.id == business.owner_user_id).first()
            if existing_owner and existing_owner.email.lower() != email.lower().strip():
                return templates.TemplateResponse(
                    "public/claim_error.html",
                    {
                        "request": request,
                        "error": "This business already has an owner. Please contact support if you believe this is an error."
                    }
                )
        
        existing_user = db.query(User).filter(User.email == email.lower().strip()).first()
        
        if existing_user:
            if not existing_user.verify_password(password):
                return templates.TemplateResponse(
                    "public/claim.html",
                    {
                        "request": request,
                        "token": token,
                        "business_name": business.name,
                        "business_domain": business.primary_domain,
                        "error": "An account with this email exists. Please enter the correct password or use a different email."
                    }
                )
            user = existing_user
        else:
            user = User(
                email=email.lower().strip(),
                first_name=first_name.strip() if first_name else None,
                last_name=last_name.strip() if last_name else None
            )
            user.set_password(password)
            db.add(user)
            db.commit()
            db.refresh(user)
        
        if not business.owner_user_id:
            business.owner_user_id = user.id
        
        other_tokens = db.query(ClaimToken).filter(
            ClaimToken.business_id == business.id,
            ClaimToken.id != claim.id,
            ClaimToken.status == "active"
        ).all()
        for other_token in other_tokens:
            other_token.status = "revoked"
        
        claim.redeemed_at = datetime.utcnow()
        claim.redeemed_by_user_id = user.id
        claim.client_email = email
        claim.client_name = f"{first_name} {last_name}".strip() if first_name or last_name else None
        claim.status = "redeemed"
        
        db.commit()
        
        login_user(request, user)
        
        completed_audits = [a for a in business.audits if a.status in ('done', 'completed')]
        if completed_audits:
            latest_audit = max(completed_audits, key=lambda a: a.completed_at or a.created_at)
            return RedirectResponse(
                url=f"/dashboard/business/{business.id}/audit/{latest_audit.id}/mission?welcome=true",
                status_code=302
            )
        
        return RedirectResponse(
            url=f"/dashboard/business/{business.id}?welcome=true",
            status_code=302
        )
        
    except Exception as e:
        return templates.TemplateResponse(
            "public/claim_error.html",
            {"request": request, "error": f"An error occurred: {str(e)}"}
        )
    finally:
        db.close()


@app.post("/admin/audit/{audit_id}/delete")
async def admin_delete_audit(request: Request, audit_id: int):
    """Delete an audit (Admin)."""
    if not is_authenticated(request):
        return RedirectResponse(url="/admin/login", status_code=302)
    
    db = get_db_session()
    try:
        audit = db.query(Audit).filter(Audit.id == audit_id).first()
        if audit:
            business_id = audit.business_id
            if audit.pdf_path:
                import os as osmod
                if osmod.path.exists(audit.pdf_path):
                    osmod.remove(audit.pdf_path)
            db.delete(audit)
            db.commit()
            return RedirectResponse(url=f"/admin/business/{business_id}", status_code=302)
        return RedirectResponse(url="/admin/businesses", status_code=302)
    finally:
        db.close()


@app.get("/admin/audit/{audit_id}", response_class=HTMLResponse)
async def admin_audit_detail(request: Request, audit_id: int):
    """Show audit detail page."""
    if not is_authenticated(request):
        return RedirectResponse(url="/admin/login", status_code=302)
    
    db = get_db_session()
    try:
        audit = db.query(Audit).filter(Audit.id == audit_id).first()
        if not audit:
            return templates.TemplateResponse(
                "admin/error.html",
                {"request": request, "error": "Audit not found"}
            )
        
        business = audit.business
        visibility = audit.get_visibility_summary() or {}
        suggestions = audit.get_suggestions() or {}
        
        return templates.TemplateResponse(
            "admin/audit_detail.html",
            {
                "request": request,
                "audit": {
                    "id": audit.id,
                    "channel": audit.channel,
                    "status": audit.status,
                    "site_inspector_used": audit.site_inspector_used,
                    "created_at": audit.created_at,
                    "completed_at": audit.completed_at,
                    "has_pdf": bool(audit.pdf_path),
                    "pdf_path": audit.pdf_path
                },
                "business": {
                    "id": business.id,
                    "name": business.name
                } if business else None,
                "visibility": visibility,
                "suggestions": suggestions
            }
        )
    finally:
        db.close()


@app.get("/admin/audit/{audit_id}/download")
async def admin_download_audit_pdf(request: Request, audit_id: int):
    """Download the PDF report for an audit."""
    if not is_authenticated(request):
        return RedirectResponse(url="/admin/login", status_code=302)
    
    db = get_db_session()
    try:
        audit = db.query(Audit).filter(Audit.id == audit_id).first()
        if not audit or not audit.pdf_path:
            return RedirectResponse(url=f"/admin/audit/{audit_id}", status_code=302)
        
        if not os.path.exists(audit.pdf_path):
            return RedirectResponse(url=f"/admin/audit/{audit_id}", status_code=302)
        
        filename = os.path.basename(audit.pdf_path)
        return FileResponse(
            audit.pdf_path,
            media_type="application/pdf",
            filename=filename
        )
    finally:
        db.close()


@app.get("/business/new", response_class=HTMLResponse)
async def public_business_form(request: Request):
    """Show public business creation form."""
    return templates.TemplateResponse(
        "public/business_new.html",
        {"request": request, "error": None, "success": False}
    )


@app.post("/business/new")
async def public_business_create(
    request: Request,
    name: str = Form(...),
    primary_domain: str = Form(...),
    extra_domains: str = Form(""),
    business_type: str = Form("local_service"),
    regions: str = Form(""),
    categories: str = Form(""),
    contact_name: str = Form(""),
    contact_email: str = Form("")
):
    """Create a new business from public form."""
    db = get_db_session()
    try:
        extra_domains_list = [d.strip() for d in extra_domains.split(",") if d.strip()]
        regions_list = [r.strip() for r in regions.split(",") if r.strip()]
        categories_list = [c.strip() for c in categories.split(",") if c.strip()]
        
        business = Business(
            name=name,
            primary_domain=primary_domain,
            business_type=business_type,
            contact_name=contact_name or None,
            contact_email=contact_email or None,
            source="public"
        )
        business.set_extra_domains(extra_domains_list)
        business.set_regions(regions_list)
        business.set_categories(categories_list)
        
        db.add(business)
        db.commit()
        
        return templates.TemplateResponse(
            "public/business_new.html",
            {"request": request, "error": None, "success": True}
        )
    except Exception as e:
        return templates.TemplateResponse(
            "public/business_new.html",
            {"request": request, "error": f"Error creating business: {str(e)}", "success": False}
        )
    finally:
        db.close()


# =============================================================================
# SNAPSHOT PUBLIC PAID FLOW (SPRINT 2)
# =============================================================================

@app.get("/snapshot", response_class=HTMLResponse)
async def snapshot_landing(request: Request):
    """Show Snapshot marketing/landing page."""
    return templates.TemplateResponse(
        "public/snapshot/landing.html",
        {"request": request}
    )


@app.get("/snapshot/business", response_class=HTMLResponse)
async def snapshot_business_form(request: Request):
    """Show business info form for Snapshot purchase."""
    return templates.TemplateResponse(
        "public/snapshot/business_form.html",
        {"request": request, "error": None, "form_data": None}
    )


@app.post("/snapshot/business")
async def snapshot_business_submit(
    request: Request,
    name: str = Form(...),
    primary_domain: str = Form(...),
    extra_domains: str = Form(""),
    business_type: str = Form(...),
    regions: str = Form(""),
    categories: str = Form(""),
    contact_name: str = Form(...),
    contact_email: str = Form(...)
):
    """Create business and redirect to Stripe Checkout."""
    db = get_db_session()
    try:
        extra_domains_list = [d.strip() for d in extra_domains.split("\n") if d.strip()]
        regions_list = [r.strip() for r in regions.split(",") if r.strip()]
        categories_list = [c.strip() for c in categories.split(",") if c.strip()]
        
        business = Business(
            name=name,
            primary_domain=primary_domain,
            business_type=business_type,
            contact_name=contact_name,
            contact_email=contact_email,
            source="public",
            subscription_active=False
        )
        business.set_extra_domains(extra_domains_list)
        business.set_regions(regions_list)
        business.set_categories(categories_list)
        
        db.add(business)
        db.commit()
        db.refresh(business)
        
        request.session["snapshot_business_id"] = business.id
        
        return RedirectResponse(url=f"/snapshot/checkout?business_id={business.id}", status_code=302)
    except Exception as e:
        form_data = {
            "name": name,
            "primary_domain": primary_domain,
            "extra_domains": extra_domains,
            "business_type": business_type,
            "regions": regions,
            "categories": categories,
            "contact_name": contact_name,
            "contact_email": contact_email
        }
        return templates.TemplateResponse(
            "public/snapshot/business_form.html",
            {"request": request, "error": f"Error: {str(e)}", "form_data": form_data}
        )
    finally:
        db.close()


@app.get("/snapshot/checkout")
async def snapshot_checkout(request: Request, business_id: int):
    """Create Stripe Checkout session and redirect."""
    session_business_id = request.session.get("snapshot_business_id")
    if session_business_id != business_id:
        return RedirectResponse(url="/snapshot/business", status_code=302)
    
    db = get_db_session()
    try:
        business = db.query(Business).filter(Business.id == business_id).first()
        if not business:
            return RedirectResponse(url="/snapshot/business", status_code=302)
        
        domain = os.getenv("REPLIT_DEV_DOMAIN") or os.getenv("REPLIT_DOMAINS", "").split(",")[0]
        if not domain:
            domain = "localhost:5000"
        
        protocol = "https" if "replit" in domain else "http"
        base_url = f"{protocol}://{domain}"
        
        success_url = f"{base_url}/snapshot/success?session_id={{CHECKOUT_SESSION_ID}}"
        cancel_url = f"{base_url}/snapshot/cancel"
        
        try:
            session = await create_checkout_session(
                business_id=business.id,
                success_url=success_url,
                cancel_url=cancel_url
            )
            return RedirectResponse(url=session.url, status_code=303)
        except ValueError as e:
            return templates.TemplateResponse(
                "public/snapshot/business_form.html",
                {"request": request, "error": f"Stripe configuration error: {str(e)}", "form_data": None}
            )
        except Exception as e:
            return templates.TemplateResponse(
                "public/snapshot/business_form.html",
                {"request": request, "error": f"Payment error: {str(e)}", "form_data": None}
            )
    finally:
        db.close()


@app.get("/snapshot/success", response_class=HTMLResponse)
async def snapshot_success(request: Request, session_id: Optional[str] = None):
    """Show success page after payment."""
    db = get_db_session()
    try:
        business = None
        audit = None
        
        if session_id:
            try:
                await load_stripe_config()
                stripe = get_stripe_client()
                session = stripe.checkout.Session.retrieve(session_id)
                
                business_id = session.metadata.get("business_id")
                if business_id:
                    business = db.query(Business).filter(Business.id == int(business_id)).first()
                    if business:
                        audit = (
                            db.query(Audit)
                            .filter(Audit.business_id == business.id)
                            .filter(Audit.channel == "self_serve")
                            .order_by(Audit.created_at.desc())
                            .first()
                        )
            except Exception as e:
                print(f"Error retrieving Stripe session: {e}")
        
        return templates.TemplateResponse(
            "public/snapshot/success.html",
            {"request": request, "business": business, "audit": audit}
        )
    finally:
        db.close()


@app.get("/snapshot/cancel", response_class=HTMLResponse)
async def snapshot_cancel(request: Request):
    """Show cancel page."""
    return templates.TemplateResponse(
        "public/snapshot/cancel.html",
        {"request": request}
    )


@app.get("/snapshot/audit/{audit_id}", response_class=HTMLResponse)
async def snapshot_audit_view(request: Request, audit_id: int):
    """Public view of a self-serve audit."""
    db = get_db_session()
    try:
        audit = db.query(Audit).filter(Audit.id == audit_id).first()
        
        if not audit or audit.channel != "self_serve":
            return templates.TemplateResponse(
                "admin/error.html",
                {"request": request, "error": "Audit not found"}
            )
        
        business = audit.business
        visibility = audit.get_visibility_summary() or {}
        suggestions = audit.get_suggestions() or {}
        
        return templates.TemplateResponse(
            "public/snapshot/audit_view.html",
            {
                "request": request,
                "audit": {
                    "id": audit.id,
                    "status": audit.status,
                    "completed_at": audit.completed_at,
                    "has_pdf": bool(audit.pdf_path)
                },
                "business": {
                    "id": business.id,
                    "name": business.name
                } if business else None,
                "visibility": visibility,
                "suggestions": suggestions
            }
        )
    finally:
        db.close()


@app.get("/snapshot/audit/{audit_id}/download")
async def snapshot_audit_download(request: Request, audit_id: int):
    """Download PDF for a self-serve audit."""
    db = get_db_session()
    try:
        audit = db.query(Audit).filter(Audit.id == audit_id).first()
        
        if not audit or audit.channel != "self_serve":
            return RedirectResponse(url="/snapshot", status_code=302)
        
        if not audit.pdf_path or not os.path.exists(audit.pdf_path):
            return RedirectResponse(url=f"/snapshot/audit/{audit_id}", status_code=302)
        
        filename = os.path.basename(audit.pdf_path)
        return FileResponse(
            audit.pdf_path,
            media_type="application/pdf",
            filename=filename
        )
    finally:
        db.close()


# =============================================================================
# PRICING PAGE
# =============================================================================

@app.get("/pricing", response_class=HTMLResponse)
async def pricing_page(request: Request):
    """Show pricing page with both Snapshot and Ongoing plans."""
    user = get_current_user(request)
    error = request.query_params.get("error")
    return templates.TemplateResponse(
        "public/pricing.html",
        {
            "request": request,
            "user": user,
            "is_admin": user.is_admin if user else False,
            "error": error
        }
    )


# =============================================================================
# ACTIVATION CODE REDEMPTION (LINKEDIN CAMPAIGN)
# =============================================================================

@app.get("/activate", response_class=HTMLResponse)
async def activate_landing(request: Request):
    """Landing page for activation code redemption."""
    user = get_current_user(request)
    code = request.query_params.get("code", "")
    error = request.query_params.get("error")
    
    return templates.TemplateResponse(
        "public/activate.html",
        {
            "request": request,
            "user": user,
            "prefilled_code": code,
            "error": error
        }
    )


@app.post("/activate")
async def activate_submit(
    request: Request,
    background_tasks: BackgroundTasks,
    code: str = Form(...),
    name: str = Form(""),
    primary_domain: str = Form(""),
    business_type: str = Form("local_service"),
    regions: str = Form(""),
    categories: str = Form("")
):
    """Validate activation code and create business + trigger audit."""
    from services.database import ActivationCode
    
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url=f"/auth/login?next=/activate?code={code}", status_code=302)
    
    db = get_db_session()
    try:
        activation = db.query(ActivationCode).filter(
            ActivationCode.code == code.strip().upper()
        ).first()
        
        if not activation:
            return RedirectResponse(url="/activate?error=Invalid activation code", status_code=302)
        
        if not activation.is_valid:
            return RedirectResponse(url=f"/activate?error=This code has already been used or expired", status_code=302)
        
        if not name or not primary_domain:
            return templates.TemplateResponse(
                "public/activate.html",
                {
                    "request": request,
                    "user": user,
                    "prefilled_code": code,
                    "error": "Please fill in your business name and website",
                    "show_business_form": True
                }
            )
        
        regions_list = [r.strip() for r in regions.split(",") if r.strip()]
        categories_list = [c.strip() for c in categories.split(",") if c.strip()]
        
        business = Business(
            owner_user_id=user.id,
            name=name,
            primary_domain=primary_domain,
            business_type=business_type,
            contact_name=user.full_name,
            contact_email=user.email,
            source="activation_code",
            plan="activation"
        )
        business.set_regions(regions_list)
        business.set_categories(categories_list)
        
        db.add(business)
        db.commit()
        db.refresh(business)
        
        activation.uses_remaining -= 1
        activation.redeemed_by_user_id = user.id
        activation.redeemed_business_id = business.id
        activation.redeemed_at = datetime.utcnow()
        db.commit()
        
        audit = Audit(
            business_id=business.id,
            channel="activation_code",
            status="pending"
        )
        db.add(audit)
        db.commit()
        db.refresh(audit)
        
        background_tasks.add_task(run_audit_background, business.id, audit.id)
        
        return RedirectResponse(
            url=f"/dashboard/business/{business.id}?activated=true",
            status_code=302
        )
    finally:
        db.close()


# =============================================================================
# AUTO-DISCOVERY INTELLIGENCE API
# =============================================================================

@app.post("/api/intel/auto-discover")
async def intel_auto_discover(request: Request):
    """
    Auto-Discovery endpoint - The "Magic Wand" for sales demos.
    Takes a URL and returns complete business intelligence:
    - Tech stack detection
    - Business name and location extraction
    - Industry classification
    - Top 3 competitor discovery via Google Search
    """
    from services.auto_discovery import auto_discover
    
    user = get_current_user(request)
    if not user or not user.is_admin:
        return JSONResponse({"error": "Admin access required"}, status_code=403)
    
    try:
        body = await request.json()
        url = body.get("url", "").strip()
    except:
        return JSONResponse({"error": "Invalid request body"}, status_code=400)
    
    if not url:
        return JSONResponse({"error": "URL is required"}, status_code=400)
    
    result = await auto_discover(url)
    return JSONResponse(result)


@app.get("/admin/onboarding")
async def admin_onboarding_page(request: Request):
    """
    Admin page for onboarding new businesses with Auto-Discovery.
    """
    user = get_current_user(request)
    if not user or not user.is_admin:
        return RedirectResponse(url="/login", status_code=302)
    
    return templates.TemplateResponse(
        "admin/onboarding.html",
        {"request": request, "user": user}
    )


@app.post("/admin/onboarding/create")
async def admin_onboarding_create(
    request: Request,
    background_tasks: BackgroundTasks,
    business_name: str = Form(...),
    website_url: str = Form(...),
    location: str = Form(""),
    industry: str = Form(""),
    business_type: str = Form("local_service"),
    tech_stack: str = Form(""),
    competitors: str = Form(""),
    keywords: str = Form(""),
    contact_email: str = Form(""),
    contact_phone: str = Form(""),
    run_initial_scan: bool = Form(False),
    update_if_exists: bool = Form(False)
):
    """
    Create a new business from the onboarding form and optionally run initial intelligence scan.
    """
    from services.sherlock_engine import is_sherlock_enabled
    
    user = get_current_user(request)
    if not user or not user.is_admin:
        return JSONResponse({"error": "Admin access required"}, status_code=403)
    
    db = get_db_session()
    try:
        normalized_url = website_url.strip()
        if not normalized_url.startswith(("http://", "https://")):
            normalized_url = f"https://{normalized_url}"
        
        clean_domain = normalized_url.replace("https://", "").replace("http://", "").replace("www.", "").rstrip("/")
        
        existing = db.query(Business).filter(
            Business.primary_domain.contains(clean_domain)
        ).first()
        
        if existing and not update_if_exists:
            return JSONResponse({
                "success": False,
                "error": f"Business already exists: {existing.name}",
                "business_id": existing.id,
                "can_update": True
            }, status_code=400)
        
        if existing and update_if_exists:
            existing.name = business_name
            existing.industry = industry
            existing.business_type = business_type
            existing.competitors = competitors
            existing.contact_email = contact_email or existing.contact_email
            existing.contact_phone = contact_phone or existing.contact_phone
            if location:
                existing.set_regions([location])
            if keywords:
                existing.set_categories([k.strip() for k in keywords.split(",") if k.strip()])
            db.commit()
            db.refresh(existing)
            business = existing
            is_update = True
        else:
            business = Business(
                name=business_name,
                primary_domain=clean_domain,
                owner_user_id=user.id,
                industry=industry,
                business_type=business_type,
                competitors=competitors,
                contact_email=contact_email,
                contact_phone=contact_phone
            )
            if location:
                business.set_regions([location])
            if keywords:
                business.set_categories([k.strip() for k in keywords.split(",") if k.strip()])
            is_update = False
            db.add(business)
        
        db.commit()
        db.refresh(business)
        
        action_word = "updated" if is_update else "created"
        result = {
            "success": True,
            "business_id": business.id,
            "business_name": business.name,
            "is_update": is_update,
            "message": f"Business '{business_name}' {action_word} successfully"
        }
        
        if run_initial_scan and is_sherlock_enabled():
            async def run_initial_intelligence():
                from services.sherlock_engine import ingest_knowledge
                try:
                    ingest_knowledge(normalized_url, "client_site", business.id, user.id)
                    
                    if competitors:
                        comp_list = [c.strip() for c in competitors.split("\n") if c.strip()]
                        for comp_url in comp_list[:3]:
                            if not comp_url.startswith(("http://", "https://")):
                                comp_url = f"https://{comp_url}"
                            ingest_knowledge(comp_url, "competitor_site", business.id, user.id)
                except Exception as e:
                    print(f"Initial intelligence scan error: {e}")
            
            background_tasks.add_task(run_initial_intelligence)
            result["message"] += " - Intelligence scan started in background."
        
        return JSONResponse(result)
        
    except Exception as e:
        db.rollback()
        return JSONResponse({"error": str(e)}, status_code=500)
    finally:
        db.close()


# =============================================================================
# SHERLOCK SEMANTIC INTELLIGENCE API
# =============================================================================

@app.post("/api/sherlock/ingest")
async def sherlock_ingest(
    request: Request,
    background_tasks: BackgroundTasks,
    url: str = Form(...),
    content_type: str = Form("client_site"),
    business_id: int = Form(...)
):
    """
    Ingest content from a URL into Sherlock's semantic memory.
    Content types: client_site, competitor_site, market_review
    """
    from services.sherlock_engine import ingest_knowledge, is_sherlock_enabled
    
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "Authentication required"}, status_code=401)
    
    if not is_sherlock_enabled():
        return JSONResponse({"error": "Sherlock is not enabled. Check Pinecone API key."}, status_code=503)
    
    db = get_db_session()
    try:
        business = db.query(Business).filter(Business.id == business_id).first()
        if not business:
            return JSONResponse({"error": "Business not found"}, status_code=404)
        
        if business.owner_user_id != user.id and not user.is_admin:
            return JSONResponse({"error": "Not authorized"}, status_code=403)
        
        result = ingest_knowledge(url, content_type, business_id, user.id)
        return JSONResponse(result)
        
    finally:
        db.close()


@app.post("/api/sherlock/analyze-gap")
async def sherlock_analyze_gap(
    request: Request,
    business_id: int = Form(...),
    competitor_id: int = Form(None)
):
    """
    Run semantic gap analysis between client and competitor content.
    This is the killer feature - identifies missing TOPICS, not keywords.
    """
    from services.sherlock_engine import analyze_semantic_gap, is_sherlock_enabled
    
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "Authentication required"}, status_code=401)
    
    if not is_sherlock_enabled():
        return JSONResponse({"error": "Sherlock is not enabled"}, status_code=503)
    
    db = get_db_session()
    try:
        business = db.query(Business).filter(Business.id == business_id).first()
        if not business:
            return JSONResponse({"error": "Business not found"}, status_code=404)
        
        if business.owner_user_id != user.id and not user.is_admin:
            return JSONResponse({"error": "Not authorized"}, status_code=403)
        
        result = analyze_semantic_gap(business_id, competitor_id)
        return JSONResponse(result)
        
    finally:
        db.close()


@app.post("/api/sherlock/generate-missions")
async def sherlock_generate_missions(
    request: Request,
    business_id: int = Form(...)
):
    """
    Generate actionable missions from gap analysis.
    Each mission tells the user exactly what content to create.
    """
    from services.sherlock_engine import generate_missions, is_sherlock_enabled
    
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "Authentication required"}, status_code=401)
    
    if not is_sherlock_enabled():
        return JSONResponse({"error": "Sherlock is not enabled"}, status_code=503)
    
    db = get_db_session()
    try:
        business = db.query(Business).filter(Business.id == business_id).first()
        if not business:
            return JSONResponse({"error": "Business not found"}, status_code=404)
        
        if business.owner_user_id != user.id and not user.is_admin:
            return JSONResponse({"error": "Not authorized"}, status_code=403)
        
        missions = generate_missions(business_id)
        return JSONResponse({"success": True, "missions": missions})
        
    finally:
        db.close()


@app.get("/api/sherlock/missions/{business_id}")
async def sherlock_get_missions(
    request: Request,
    business_id: int,
    status: str = None
):
    """Get all missions for a business."""
    from services.sherlock_engine import get_missions_for_business
    
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "Authentication required"}, status_code=401)
    
    db = get_db_session()
    try:
        business = db.query(Business).filter(Business.id == business_id).first()
        if not business:
            return JSONResponse({"error": "Business not found"}, status_code=404)
        
        if business.owner_user_id != user.id and not user.is_admin:
            return JSONResponse({"error": "Not authorized"}, status_code=403)
        
        missions = get_missions_for_business(business_id, status)
        return JSONResponse({"success": True, "missions": missions})
        
    finally:
        db.close()


@app.post("/api/sherlock/missions/{mission_id}/complete")
async def sherlock_complete_mission(
    request: Request,
    mission_id: int
):
    """Mark a mission as completed."""
    from services.sherlock_engine import complete_mission
    from services.database import SherlockMission
    
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "Authentication required"}, status_code=401)
    
    db = get_db_session()
    try:
        mission = db.query(SherlockMission).filter(SherlockMission.id == mission_id).first()
        if not mission:
            return JSONResponse({"error": "Mission not found"}, status_code=404)
        
        business = db.query(Business).filter(Business.id == mission.business_id).first()
        if business.owner_user_id != user.id and not user.is_admin:
            return JSONResponse({"error": "Not authorized"}, status_code=403)
        
        success = complete_mission(mission_id)
        return JSONResponse({"success": success})
        
    finally:
        db.close()


@app.post("/api/sherlock/add-competitor")
async def sherlock_add_competitor(
    request: Request,
    business_id: int = Form(...),
    name: str = Form(...),
    url: str = Form(...),
    is_primary: bool = Form(False)
):
    """Add a competitor for tracking and semantic comparison."""
    from services.sherlock_engine import add_competitor
    
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "Authentication required"}, status_code=401)
    
    db = get_db_session()
    try:
        business = db.query(Business).filter(Business.id == business_id).first()
        if not business:
            return JSONResponse({"error": "Business not found"}, status_code=404)
        
        if business.owner_user_id != user.id and not user.is_admin:
            return JSONResponse({"error": "Not authorized"}, status_code=403)
        
        competitor_id = add_competitor(business_id, name, url, is_primary, "api")
        if competitor_id:
            return JSONResponse({"success": True, "competitor_id": competitor_id})
        return JSONResponse({"error": "Failed to add competitor"}, status_code=500)
        
    finally:
        db.close()


@app.post("/api/sherlock/full-analysis")
async def sherlock_full_analysis(
    request: Request,
    background_tasks: BackgroundTasks,
    business_id: int = Form(...),
    client_url: str = Form(...),
    competitor_urls: str = Form("")
):
    """
    Run complete Sherlock analysis pipeline:
    1. Ingest client site
    2. Ingest competitor sites  
    3. Run semantic gap analysis
    4. Generate missions
    """
    from services.sherlock_engine import run_full_analysis, is_sherlock_enabled
    
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "Authentication required"}, status_code=401)
    
    if not is_sherlock_enabled():
        return JSONResponse({"error": "Sherlock is not enabled"}, status_code=503)
    
    db = get_db_session()
    try:
        business = db.query(Business).filter(Business.id == business_id).first()
        if not business:
            return JSONResponse({"error": "Business not found"}, status_code=404)
        
        if business.owner_user_id != user.id and not user.is_admin:
            return JSONResponse({"error": "Not authorized"}, status_code=403)
        
        competitor_list = [u.strip() for u in competitor_urls.split("\n") if u.strip()]
        
        result = run_full_analysis(business_id, client_url, competitor_list)
        return JSONResponse(result)
        
    finally:
        db.close()


@app.post("/api/sherlock/rescan")
async def sherlock_rescan(
    request: Request,
    business_id: int = Form(...),
    competitor_urls: str = Form("")
):
    """
    Force Intelligence Rescan - clears existing data and re-runs full analysis.
    Use this to fix legacy data issues or refresh stale intelligence.
    """
    from services.sherlock_engine import rescan_intelligence, is_sherlock_enabled
    
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "Authentication required"}, status_code=401)
    
    if not is_sherlock_enabled():
        return JSONResponse({"error": "Sherlock is not enabled"}, status_code=503)
    
    db = get_db_session()
    try:
        business = db.query(Business).filter(Business.id == business_id).first()
        if not business:
            return JSONResponse({"error": "Business not found"}, status_code=404)
        
        if business.owner_user_id != user.id and not user.is_admin:
            return JSONResponse({"error": "Not authorized"}, status_code=403)
        
        client_url = f"https://{business.primary_domain}"
        
        competitor_list = [u.strip() for u in competitor_urls.split("\n") if u.strip()] if competitor_urls else None
        
        result = rescan_intelligence(business_id, client_url, competitor_list)
        return JSONResponse(result)
        
    except Exception as e:
        return JSONResponse({"error": f"Rescan failed: {str(e)}"}, status_code=500)
    finally:
        db.close()


@app.get("/api/sherlock/status")
async def sherlock_status(request: Request):
    """Check if Sherlock semantic analysis is enabled."""
    from services.sherlock_engine import is_sherlock_enabled
    
    return JSONResponse({
        "enabled": is_sherlock_enabled(),
        "service": "Sherlock Semantic Intelligence",
        "capabilities": [
            "URL content ingestion",
            "Semantic topic extraction",
            "Vector embedding storage",
            "Competitor gap analysis",
            "Mission generation",
            "Strategic consultation (RAG)",
            "Fix fabrication",
            "Force Intelligence Rescan"
        ]
    })


@app.post("/api/sherlock/consult")
async def sherlock_consult(request: Request):
    """
    The 'Interrogation Room' - RAG-powered strategic consultation.
    
    User asks: "Why is Coastal Roofing beating me?"
    System: Retrieves relevant vectors, synthesizes with LLM.
    """
    from services.sherlock_engine import consult_strategist, is_sherlock_enabled
    
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "Authentication required"}, status_code=401)
    
    if not is_sherlock_enabled():
        return JSONResponse({"error": "Sherlock is not enabled"}, status_code=503)
    
    try:
        data = await request.json()
    except:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)
    
    query = data.get("query", "").strip()
    business_id = data.get("business_id")
    
    if not query:
        return JSONResponse({"error": "Query is required"}, status_code=400)
    
    if not business_id:
        return JSONResponse({"error": "business_id is required"}, status_code=400)
    
    db = get_db_session()
    try:
        business = db.query(Business).filter(Business.id == business_id).first()
        if not business:
            return JSONResponse({"error": "Business not found"}, status_code=404)
        
        if business.owner_user_id != user.id and not user.is_admin:
            return JSONResponse({"error": "Not authorized"}, status_code=403)
        
        result = consult_strategist(query, business_id)
        return JSONResponse(result)
        
    except Exception as e:
        logger.error("Consultation error: %s", e)
        return JSONResponse({"error": str(e)[:100]}, status_code=500)
    finally:
        db.close()


@app.post("/api/sherlock/fabricate/{mission_id}")
async def sherlock_fabricate(request: Request, mission_id: int):
    """
    The 'Fabricator' - Generate actual files to solve a mission.
    
    Takes a mission and generates the schema, HTML, or content files needed.
    Returns JSON with files array that frontend uses to create ZIP download.
    """
    from services.sherlock_engine import fabricate_fix, get_mission_by_id, is_sherlock_enabled
    
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "Authentication required"}, status_code=401)
    
    if not is_sherlock_enabled():
        return JSONResponse({"error": "Sherlock not enabled. Configure OpenAI API key."}, status_code=503)
    
    mission = get_mission_by_id(mission_id)
    if not mission:
        return JSONResponse({"error": "Mission not found"}, status_code=404)
    
    db = get_db_session()
    try:
        business = db.query(Business).filter(Business.id == mission["business_id"]).first()
        if not business:
            return JSONResponse({"error": "Business not found"}, status_code=404)
        
        if business.owner_user_id != user.id and not user.is_admin:
            return JSONResponse({"error": "Not authorized"}, status_code=403)
        
        result = fabricate_fix(mission_id)
        return JSONResponse(result)
        
    except Exception as e:
        logger.error("Fabrication error: %s", e)
        return JSONResponse({"error": str(e)[:100]}, status_code=500)
    finally:
        db.close()


@app.get("/api/sherlock/mission/{mission_id}")
async def sherlock_get_mission(request: Request, mission_id: int):
    """Get a single mission by ID."""
    from services.sherlock_engine import get_mission_by_id
    
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "Authentication required"}, status_code=401)
    
    mission = get_mission_by_id(mission_id)
    if not mission:
        return JSONResponse({"error": "Mission not found"}, status_code=404)
    
    db = get_db_session()
    try:
        business = db.query(Business).filter(Business.id == mission["business_id"]).first()
        if business and (business.owner_user_id == user.id or user.is_admin):
            return JSONResponse(mission)
        return JSONResponse({"error": "Not authorized"}, status_code=403)
    finally:
        db.close()


# =============================================================================
# ONGOING PUBLIC PAID FLOW (SPRINT 3)
# =============================================================================

@app.get("/ongoing", response_class=HTMLResponse)
async def ongoing_landing(request: Request):
    """Show Ongoing subscription landing page."""
    return templates.TemplateResponse(
        "public/ongoing/landing.html",
        {"request": request}
    )


@app.get("/ongoing/business", response_class=HTMLResponse)
async def ongoing_business_form(request: Request):
    """Show business info form for Ongoing subscription."""
    return templates.TemplateResponse(
        "public/ongoing/business_form.html",
        {"request": request, "error": None, "form_data": None}
    )


@app.post("/ongoing/business")
async def ongoing_business_submit(
    request: Request,
    name: str = Form(...),
    primary_domain: str = Form(...),
    extra_domains: str = Form(""),
    business_type: str = Form(...),
    regions: str = Form(""),
    categories: str = Form(""),
    contact_name: str = Form(...),
    contact_email: str = Form(...)
):
    """Create business for ongoing plan and redirect to Stripe Checkout."""
    db = get_db_session()
    try:
        extra_domains_list = [d.strip() for d in extra_domains.split("\n") if d.strip()]
        regions_list = [r.strip() for r in regions.split(",") if r.strip()]
        categories_list = [c.strip() for c in categories.split(",") if c.strip()]
        
        business = Business(
            name=name,
            primary_domain=primary_domain,
            business_type=business_type,
            contact_name=contact_name,
            contact_email=contact_email,
            source="public",
            plan="ongoing",
            subscription_active=False
        )
        business.set_extra_domains(extra_domains_list)
        business.set_regions(regions_list)
        business.set_categories(categories_list)
        
        db.add(business)
        db.commit()
        db.refresh(business)
        
        request.session["ongoing_business_id"] = business.id
        
        return RedirectResponse(url=f"/ongoing/checkout?business_id={business.id}", status_code=302)
    except Exception as e:
        form_data = {
            "name": name,
            "primary_domain": primary_domain,
            "extra_domains": extra_domains,
            "business_type": business_type,
            "regions": regions,
            "categories": categories,
            "contact_name": contact_name,
            "contact_email": contact_email
        }
        return templates.TemplateResponse(
            "public/ongoing/business_form.html",
            {"request": request, "error": f"Error: {str(e)}", "form_data": form_data}
        )
    finally:
        db.close()


@app.get("/ongoing/checkout")
async def ongoing_checkout(request: Request, business_id: int):
    """Create Stripe Checkout session for subscription and redirect."""
    session_business_id = request.session.get("ongoing_business_id")
    if session_business_id != business_id:
        return RedirectResponse(url="/ongoing/business", status_code=302)
    
    db = get_db_session()
    try:
        business = db.query(Business).filter(Business.id == business_id).first()
        if not business:
            return RedirectResponse(url="/ongoing/business", status_code=302)
        
        domain = os.getenv("REPLIT_DEV_DOMAIN") or os.getenv("REPLIT_DOMAINS", "").split(",")[0]
        if not domain:
            domain = "localhost:5000"
        
        protocol = "https" if "replit" in domain else "http"
        base_url = f"{protocol}://{domain}"
        
        success_url = f"{base_url}/ongoing/success?session_id={{CHECKOUT_SESSION_ID}}"
        cancel_url = f"{base_url}/ongoing/cancel"
        
        try:
            session = await create_subscription_checkout_session(
                business_id=business.id,
                success_url=success_url,
                cancel_url=cancel_url
            )
            return RedirectResponse(url=session.url, status_code=302)
        except Exception as e:
            return templates.TemplateResponse(
                "public/ongoing/business_form.html",
                {"request": request, "error": f"Error creating checkout: {str(e)}", "form_data": None}
            )
    finally:
        db.close()


@app.get("/ongoing/success", response_class=HTMLResponse)
async def ongoing_success(request: Request, session_id: Optional[str] = None):
    """Show success page after subscription payment. Bi-weekly subscribers go straight to Command Control."""
    db = get_db_session()
    try:
        business = None
        audit = None
        
        if session_id:
            try:
                await load_stripe_config()
                stripe = get_stripe_client()
                session = stripe.checkout.Session.retrieve(session_id)
                
                business_id = session.metadata.get("business_id")
                if business_id:
                    business = db.query(Business).filter(Business.id == int(business_id)).first()
                    if business:
                        if business.subscription_tier == "biweekly":
                            latest_audit = (
                                db.query(Audit)
                                .filter(Audit.business_id == business.id)
                                .order_by(Audit.created_at.desc())
                                .first()
                            )
                            if latest_audit and latest_audit.status == "completed":
                                return RedirectResponse(
                                    url=f"/dashboard/business/{business.id}/audit/{latest_audit.id}/mission",
                                    status_code=302
                                )
                            return templates.TemplateResponse(
                                "dashboard/biweekly_welcome.html",
                                {"request": request, "business": business}
                            )
                        
                        audit = (
                            db.query(Audit)
                            .filter(Audit.business_id == business.id)
                            .filter(Audit.channel == "self_serve")
                            .order_by(Audit.created_at.desc())
                            .first()
                        )
            except Exception as e:
                print(f"Error retrieving Stripe session: {e}")
        
        return templates.TemplateResponse(
            "public/ongoing/success.html",
            {"request": request, "business": business, "audit": audit}
        )
    finally:
        db.close()


@app.get("/ongoing/cancel", response_class=HTMLResponse)
async def ongoing_cancel(request: Request):
    """Show cancel page for subscription."""
    return templates.TemplateResponse(
        "public/ongoing/cancel.html",
        {"request": request}
    )


@app.get("/ongoing/audit/{audit_id}", response_class=HTMLResponse)
async def ongoing_audit_view(request: Request, audit_id: int):
    """Public view of an ongoing subscription audit."""
    db = get_db_session()
    try:
        audit = db.query(Audit).filter(Audit.id == audit_id).first()
        
        if not audit or audit.channel != "self_serve":
            return templates.TemplateResponse(
                "admin/error.html",
                {"request": request, "error": "Audit not found"}
            )
        
        business = audit.business
        if not business or business.plan != "ongoing":
            return templates.TemplateResponse(
                "admin/error.html",
                {"request": request, "error": "Audit not found"}
            )
        
        visibility = audit.get_visibility_summary() or {}
        suggestions = audit.get_suggestions() or {}
        
        return templates.TemplateResponse(
            "public/snapshot/audit_view.html",
            {
                "request": request,
                "audit": {
                    "id": audit.id,
                    "status": audit.status,
                    "completed_at": audit.completed_at,
                    "has_pdf": bool(audit.pdf_path)
                },
                "business": {
                    "id": business.id,
                    "name": business.name
                } if business else None,
                "visibility": visibility,
                "suggestions": suggestions
            }
        )
    finally:
        db.close()


@app.get("/ongoing/audit/{audit_id}/download")
async def ongoing_audit_download(request: Request, audit_id: int):
    """Download PDF for an ongoing subscription audit."""
    db = get_db_session()
    try:
        audit = db.query(Audit).filter(Audit.id == audit_id).first()
        
        if not audit or audit.channel != "self_serve":
            return RedirectResponse(url="/ongoing", status_code=302)
        
        business = audit.business
        if not business or business.plan != "ongoing":
            return RedirectResponse(url="/ongoing", status_code=302)
        
        if not audit.pdf_path or not os.path.exists(audit.pdf_path):
            return RedirectResponse(url=f"/ongoing/audit/{audit_id}", status_code=302)
        
        filename = os.path.basename(audit.pdf_path)
        return FileResponse(
            audit.pdf_path,
            media_type="application/pdf",
            filename=filename
        )
    finally:
        db.close()


def run_audit_background(business_id: int, audit_id: int):
    """Background task to run an audit."""
    print(f"[AUDIT DEBUG] Starting background task for audit {audit_id}, business {business_id}")
    import sys
    sys.stdout.flush()
    
    db = get_db_session()
    try:
        print(f"[AUDIT DEBUG] Got DB session for audit {audit_id}")
        sys.stdout.flush()
        
        business = db.query(Business).filter(Business.id == business_id).first()
        audit = db.query(Audit).filter(Audit.id == audit_id).first()
        
        print(f"[AUDIT DEBUG] Found business={business is not None}, audit={audit is not None}")
        sys.stdout.flush()
        
        if business and audit:
            try:
                print(f"[AUDIT DEBUG] Calling run_audit_for_business for audit {audit_id}")
                sys.stdout.flush()
                run_audit_for_business(business, audit, db)
                print(f"[AUDIT DEBUG] Audit {audit_id} completed successfully")
                sys.stdout.flush()
            except Exception as e:
                import traceback
                print(f"[AUDIT DEBUG] Audit {audit_id} EXCEPTION: {e}")
                print(f"[AUDIT DEBUG] Traceback: {traceback.format_exc()}")
                sys.stdout.flush()
                audit.status = "error"
                audit.set_visibility_summary({
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "error_details": traceback.format_exc()
                })
                db.commit()
                print(f"Audit {audit_id} failed: {e}")
        else:
            print(f"[AUDIT DEBUG] Missing business or audit for {audit_id}")
            sys.stdout.flush()
    except Exception as outer_e:
        print(f"[AUDIT DEBUG] OUTER EXCEPTION in audit {audit_id}: {outer_e}")
        import traceback
        print(f"[AUDIT DEBUG] Outer traceback: {traceback.format_exc()}")
        sys.stdout.flush()
    finally:
        db.close()
        print(f"[AUDIT DEBUG] Background task finished for audit {audit_id}")
        sys.stdout.flush()


@app.get("/api/audit/{audit_id}/status")
async def api_audit_status(request: Request, audit_id: int):
    """Get audit status for polling (authenticated)."""
    user = get_current_user(request)
    if not user:
        return {"status": "unauthorized"}
    
    db = get_db_session()
    try:
        audit = db.query(Audit).filter(Audit.id == audit_id).first()
        if not audit:
            return {"status": "not_found"}
        
        if not user.is_admin:
            business = db.query(Business).filter(
                Business.id == audit.business_id,
                Business.owner_user_id == user.id
            ).first()
            if not business:
                return {"status": "unauthorized"}
        
        return {"status": audit.status, "audit_id": audit.id}
    finally:
        db.close()


@app.get("/api/business/{business_id}/latest-audit")
async def api_latest_audit(request: Request, business_id: int):
    """Get the latest audit for a business (authenticated)."""
    user = get_current_user(request)
    if not user:
        return {"audit_id": None, "status": "unauthorized"}
    
    db = get_db_session()
    try:
        if user.is_admin:
            business = db.query(Business).filter(Business.id == business_id).first()
        else:
            business = db.query(Business).filter(
                Business.id == business_id,
                Business.owner_user_id == user.id
            ).first()
        
        if not business:
            return {"audit_id": None, "status": "unauthorized"}
        
        audit = (
            db.query(Audit)
            .filter(Audit.business_id == business_id)
            .order_by(Audit.created_at.desc())
            .first()
        )
        if not audit:
            return {"audit_id": None, "status": None}
        return {"audit_id": audit.id, "status": audit.status}
    finally:
        db.close()


@app.post("/webhooks/stripe")
async def stripe_webhook(request: Request, background_tasks: BackgroundTasks):
    """Handle Stripe webhook events."""
    try:
        payload = await request.body()
        sig_header = request.headers.get("stripe-signature")
        
        if not sig_header:
            return Response(content="Missing signature", status_code=400)
        
        config = await load_stripe_config()
        
        if not config.webhook_secret:
            print("ERROR: STRIPE_WEBHOOK_SECRET not configured - rejecting webhook for security")
            return Response(content="Webhook secret not configured", status_code=500)
        
        try:
            event = verify_webhook_signature(payload, sig_header, config.webhook_secret)
            event_type = event.type
            data_object = event.data.object
        except Exception as e:
            print(f"Webhook signature verification failed: {e}")
            return Response(content="Invalid signature", status_code=400)
        
        if event_type == "checkout.session.completed":
            business_id = data_object.get("metadata", {}).get("business_id")
            product_type = data_object.get("metadata", {}).get("product")
            plan = data_object.get("metadata", {}).get("plan")
            ekkobrain = data_object.get("metadata", {}).get("ekkobrain")
            subscription_id = data_object.get("subscription")
            
            if product_type == "autofix_1188" and business_id:
                db = get_db_session()
                try:
                    from services.audit_scheduler import schedule_first_audit
                    
                    business = db.query(Business).filter(Business.id == int(business_id)).first()
                    if business:
                        business.subscription_active = True
                        business.autofix_enabled = True
                        business.plan = "autofix"
                        business.subscription_tier = "autofix"  # Premium tier with auto-remediation
                        if subscription_id:
                            business.stripe_autofix_subscription_id = subscription_id
                        db.commit()
                        
                        schedule_first_audit(business.id)
                        print(f"Activated Auto-Fix subscription for business {business.id}")
                        
                        existing_audit = (
                            db.query(Audit)
                            .filter(Audit.business_id == business.id)
                            .filter(Audit.channel.in_(["self_serve", "scheduled"]))
                            .filter(Audit.status.in_(["pending", "running"]))
                            .first()
                        )
                        
                        if not existing_audit:
                            audit = Audit(
                                business_id=business.id,
                                channel="self_serve",
                                status="pending"
                            )
                            db.add(audit)
                            db.commit()
                            db.refresh(audit)
                            
                            background_tasks.add_task(run_audit_background, business.id, audit.id)
                            print(f"Created initial audit {audit.id} for Auto-Fix subscriber {business.id}")
                finally:
                    db.close()
            
            if product_type == "geo_report_490" and business_id:
                db = get_db_session()
                try:
                    business = db.query(Business).filter(Business.id == int(business_id)).first()
                    if business:
                        business.subscription_tier = "one_time"  # One-time report purchase
                        business.plan = "report"
                        db.commit()
                        print(f"Set one-time report tier for business {business.id}")
                finally:
                    db.close()
            
            valid_products = (
                "echoscope_snapshot", "echoscope_ongoing", "ekkoscope_snapshot", "ekkoscope_ongoing",
                "ekkoscope_standard", "ekkoscope_ekkobrain_addon", "continuous_290"
            )
            valid_plans = ("ongoing", "standard", "standard_ekkobrain", "ekkobrain_addon")
            
            if business_id and (product_type in valid_products or plan in valid_plans):
                db = get_db_session()
                try:
                    from services.audit_scheduler import schedule_first_audit
                    
                    business = db.query(Business).filter(Business.id == int(business_id)).first()
                    
                    if business:
                        if plan in ("standard", "standard_ekkobrain", "ongoing") or product_type == "continuous_290":
                            business.subscription_active = True
                            business.plan = "standard"
                            business.subscription_tier = "biweekly"  # Bi-weekly monitoring tier
                            if subscription_id:
                                business.stripe_subscription_id = subscription_id
                            
                            if plan == "standard_ekkobrain" or ekkobrain == "true":
                                business.ekkobrain_access = True
                            
                            db.commit()
                            
                            schedule_first_audit(business.id)
                            print(f"Activated bi-weekly subscription for business {business.id} (EkkoBrain: {business.ekkobrain_access})")
                        
                        elif plan == "ekkobrain_addon":
                            business.ekkobrain_access = True
                            if subscription_id:
                                business.stripe_ekkobrain_subscription_id = subscription_id
                            db.commit()
                            print(f"Activated EkkoBrain add-on for business {business.id}")
                        
                        if plan in ("standard", "standard_ekkobrain") or product_type == "continuous_290":
                            existing_audit = (
                                db.query(Audit)
                                .filter(Audit.business_id == business.id)
                                .filter(Audit.channel.in_(["self_serve", "scheduled"]))
                                .filter(Audit.status.in_(["pending", "running"]))
                                .first()
                            )
                            
                            if not existing_audit:
                                audit = Audit(
                                    business_id=business.id,
                                    channel="self_serve",
                                    status="pending"
                                )
                                db.add(audit)
                                db.commit()
                                db.refresh(audit)
                                
                                background_tasks.add_task(run_audit_background, business.id, audit.id)
                                print(f"Created initial audit {audit.id} for new subscriber {business.id}")
                finally:
                    db.close()
        
        return Response(content="OK", status_code=200)
    except Exception as e:
        print(f"Webhook error: {e}")
        return Response(content="Webhook error", status_code=500)
