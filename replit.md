# EchoScope - GEO Engine for AI Visibility

## Overview

EchoScope is a web application that analyzes "AI visibility" for businesses by testing how frequently they are recommended by AI assistants like ChatGPT. The system runs predefined queries against the OpenAI API to determine if a business is mentioned, how prominently it's featured compared to competitors, and provides actionable content recommendations to improve visibility.

The application is designed for V1 simplicity: no authentication, no database persistence, and no scheduled jobs. It focuses on immediate analysis and reporting for configured business tenants.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Frontend Architecture

**Technology Stack:**
- Jinja2 templating engine for server-side rendering
- Single-page application pattern with form submission
- Static CSS file for styling (no frameworks)

**Design Pattern:**
- Traditional server-rendered HTML approach
- Form POST submission triggers analysis
- Results rendered on the same page after processing
- No JavaScript framework - pure HTML/CSS with backend rendering

**Rationale:**
Simple, stateless UI that doesn't require complex client-side state management. This reduces complexity and maintenance overhead for V1.

### Backend Architecture

**Framework:**
- FastAPI as the web framework
- Uvicorn as the ASGI server
- Python 3.11+ runtime environment

**Application Structure:**
```
main.py              # FastAPI application and route handlers
services/
  analysis.py        # Core business logic for AI visibility analysis
  reporting.py       # PDF report generation using fpdf2
data/
  tenants.json       # Tenant configuration (queries, brand aliases, geo focus)
templates/           # Jinja2 HTML templates
static/              # CSS styling
```

**Request Flow:**
1. User selects tenant from dropdown and submits form
2. Backend loads tenant configuration from JSON
3. For each query, calls OpenAI API to get business recommendations
4. Scores results (0-2 scale) based on brand mention and ranking
5. Generates content recommendations via additional OpenAI call
6. Renders complete analysis results back to template
7. User can download a professional PDF report via "Download Report (PDF)" button

**PDF Report Generation:**
The `/report/{tenant_id}` endpoint generates a client-ready PDF containing:
- Cover page with EchoScope branding and tenant name
- AI visibility summary with score distribution
- Per-query details table showing each query and its score
- Competitor overview showing top 5 competitors by frequency
- Grouped recommendations (new pages, updates, FAQs, authority, branding)
- Professional footer with page numbering

**Scoring Logic:**
- **Score 0**: Business not mentioned in AI response
- **Score 1**: Business mentioned but not as primary recommendation
- **Score 2**: Business is the first/primary recommendation

**Error Handling:**
- Custom `MissingAPIKeyError` for OpenAI API key validation
- Graceful error rendering in UI without crashes
- Template-level error display to user

### Configuration Management

**Tenant Configuration (data/tenants.json):**
Each tenant includes:
- `id`: Unique identifier
- `display_name`: Human-readable name
- `domains`: Website URLs
- `brand_aliases`: Variations of business name for matching
- `geo_focus`: Geographic areas of operation
- `priority_queries`: Predefined search queries to test

**Rationale:**
JSON-based configuration allows easy addition of new tenants without code changes. No database needed for V1 since tenant data is static and minimal.

### AI Integration Architecture

**OpenAI API Integration:**
- Official `openai` Python client library
- API key stored in environment variables (Replit Secrets)
- Two-phase AI interaction:
  1. Query phase: Get business recommendations for each query
  2. Recommendation phase: Generate content improvement suggestions

**Prompt Engineering:**
- Structured prompts request JSON-formatted responses
- Brand alias matching with normalization (lowercase, whitespace handling)
- Competitor identification through exclusion logic

**Rationale:**
Using OpenAI's structured outputs ensures consistent, parseable responses. The two-phase approach separates data gathering from insight generation, making the system more maintainable.

## External Dependencies

### Third-Party Services

**OpenAI API:**
- **Purpose**: Generate AI-powered business recommendations and content suggestions
- **Configuration**: Requires `OPENAI_API_KEY` environment variable
- **Usage**: 
  - Query execution to simulate AI assistant searches
  - Content recommendation generation
- **Error Handling**: Custom exception raised if API key missing

### Python Packages

**Core Framework:**
- `fastapi`: Web framework for API and rendering
- `uvicorn[standard]`: ASGI server for development and production
- `jinja2`: Template engine for HTML rendering

**API Clients:**
- `openai`: Official OpenAI Python client

**PDF Generation:**
- `fpdf2`: Pure-Python PDF generation library for professional reports

**Utilities:**
- `python-dotenv`: Environment variable management (optional)
- `python-multipart`: Form data parsing for FastAPI

**Deployment:**
- Designed for Replit deployment
- Uses Replit Secrets manager for API key storage
- No external database or caching layer required

### Data Storage

**File-based Configuration:**
- `data/tenants.json`: Static tenant configuration
- No persistent database in V1
- All analysis results are ephemeral (displayed once, not stored)

**Rationale:**
File-based approach eliminates database setup complexity. For V1 scope with 2 tenants and limited queries, JSON configuration is sufficient and easier to modify.