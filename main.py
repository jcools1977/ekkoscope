import json
import os
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from services.analysis import run_analysis, MissingAPIKeyError

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

TENANTS = {}

@app.on_event("startup")
async def load_tenants():
    global TENANTS
    with open("data/tenants.json") as f:
        TENANTS = json.load(f)


def get_tenant_list():
    return [
        {"id": tenant_id, "name": config["display_name"]}
        for tenant_id, config in TENANTS.items()
    ]


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
