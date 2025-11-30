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
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from services.analysis import run_analysis, MissingAPIKeyError
from services.reporting import build_ekkoscope_pdf
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
    return templates.TemplateResponse(
        "public/landing.html",
        {"request": request}
    )


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


@app.get("/admin/businesses", response_class=HTMLResponse)
async def admin_businesses(request: Request):
    """List all businesses."""
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
            business_data.append({
                "id": biz.id,
                "name": biz.name,
                "primary_domain": biz.primary_domain,
                "business_type": biz.business_type,
                "source": biz.source,
                "subscription_active": biz.subscription_active,
                "plan": biz.plan or "snapshot",
                "created_at": biz.created_at,
                "audit_count": len(biz.audits)
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
    return templates.TemplateResponse(
        "public/pricing.html",
        {"request": request}
    )


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
    """Show success page after subscription payment."""
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
            
            valid_products = (
                "echoscope_snapshot", "echoscope_ongoing", "ekkoscope_snapshot", "ekkoscope_ongoing",
                "ekkoscope_standard", "ekkoscope_ekkobrain_addon"
            )
            valid_plans = ("ongoing", "standard", "standard_ekkobrain", "ekkobrain_addon")
            
            if business_id and (product_type in valid_products or plan in valid_plans):
                db = get_db_session()
                try:
                    from services.audit_scheduler import schedule_first_audit
                    
                    business = db.query(Business).filter(Business.id == int(business_id)).first()
                    
                    if business:
                        if plan in ("standard", "standard_ekkobrain", "ongoing"):
                            business.subscription_active = True
                            business.plan = "standard"
                            if subscription_id:
                                business.stripe_subscription_id = subscription_id
                            
                            if plan == "standard_ekkobrain" or ekkobrain == "true":
                                business.ekkobrain_access = True
                            
                            db.commit()
                            
                            schedule_first_audit(business.id)
                            print(f"Activated standard subscription for business {business.id} (EkkoBrain: {business.ekkobrain_access})")
                        
                        elif plan == "ekkobrain_addon":
                            business.ekkobrain_access = True
                            if subscription_id:
                                business.stripe_ekkobrain_subscription_id = subscription_id
                            db.commit()
                            print(f"Activated EkkoBrain add-on for business {business.id}")
                        
                        if plan in ("standard", "standard_ekkobrain"):
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
