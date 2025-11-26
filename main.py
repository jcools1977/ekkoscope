"""
EchoScope - GEO Engine for AI Visibility
FastAPI application with admin panel and persistence (Sprint 1)
"""

import json
import os
import secrets
from datetime import datetime
from io import BytesIO
from typing import Optional

from fastapi import FastAPI, Request, Form, Depends, HTTPException, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from services.analysis import run_analysis, MissingAPIKeyError
from services.reporting import build_echoscope_pdf
from services.database import init_db, get_db_session, Business, Audit
from services.audit_runner import run_audit_for_business, get_audit_analysis_data

app = FastAPI()

SESSION_SECRET = os.getenv("SESSION_SECRET", secrets.token_hex(32))
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

TENANTS = {}

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "echoscope2024")

if ADMIN_PASSWORD == "echoscope2024":
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


def get_tenant_list():
    return [
        {"id": tenant_id, "name": config["display_name"]}
        for tenant_id, config in TENANTS.items()
    ]


def is_authenticated(request: Request) -> bool:
    """Check if user is authenticated via session."""
    return request.session.get("authenticated", False)


def require_auth(request: Request):
    """Dependency to require authentication."""
    if not is_authenticated(request):
        raise HTTPException(status_code=302, headers={"Location": "/admin/login"})
    return True


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "tenants": get_tenant_list(),
            "analysis": None,
            "selected_tenant_id": None,
            "error": None
        }
    )


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
    """Generate and download an EchoScope PDF report for the given tenant."""
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
        pdf_bytes = build_echoscope_pdf(tenant_config, analysis)
        
        return StreamingResponse(
            BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="echoscope_report_{tenant_id}.pdf"'
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
    
    return templates.TemplateResponse(
        "admin/login.html",
        {"request": request, "error": None}
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
                    "created_at": business.created_at
                },
                "audits": audit_data
            }
        )
    finally:
        db.close()


@app.post("/admin/business/{business_id}/run")
async def admin_run_audit(request: Request, business_id: int):
    """Run an EchoScope audit for a business."""
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
        
        try:
            run_audit_for_business(business, audit, db)
            return RedirectResponse(url=f"/admin/audit/{audit.id}", status_code=302)
        except Exception as e:
            audit.status = "error"
            audit.set_visibility_summary({"error": str(e)})
            db.commit()
            return RedirectResponse(url=f"/admin/audit/{audit.id}", status_code=302)
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
