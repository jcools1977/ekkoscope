# EchoScope - GEO Engine for AI Visibility

## Overview

EchoScope is a web application that analyzes "AI visibility" for businesses by testing how frequently they are recommended by AI assistants like ChatGPT. The system runs predefined queries against the OpenAI API to determine if a business is mentioned, how prominently it's featured compared to competitors, and provides actionable content recommendations to improve visibility.

**Sprint 1 Update:** The application now includes a persistence layer with SQLite, admin panel with authentication, and public business submission form. Businesses and audit results are stored in the database, allowing for historical tracking and management.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Frontend Architecture

**Technology Stack:**
- Jinja2 templating engine for server-side rendering
- Single-page application pattern with form submission
- Static CSS file for styling (no frameworks)

**Branding & Visual Design:**
- Sci-fi radar logo concept representing "GEO radar for AI echoes"
- Full dark theme matching the logo aesthetic
- Color palette (CSS variables defined in :root):
  - Primary: #2EE6A8 (neon teal) and #18A3FF (electric blue)
  - Background: #050B11 (near-black, blue-tinted) with gradient to #0a1628
  - Cards: #0d1b2a with subtle borders (#1e3a5f)
  - Text: #F5F7FA (primary), #94a3b8 (secondary), #64748b (muted)
  - Score colors: Red (#ef4444), Amber (#f59e0b), Teal (#2EE6A8)
- Logo files in `static/img/`:
  - `echoscope-logo.svg`: Full logo with animated radar and wordmark
  - `echoscope-icon.svg`: Icon-only version
  - `favicon.svg`: Browser tab icon
- "Echo" in regular weight, "Scope" in semi-bold teal accent
- Gradient accents, glow effects, and smooth hover transitions throughout
- Custom scrollbar and text selection styling
- Animated radar button for "Run GEO Analysis" with:
  - SVG radar icon matching the logo
  - Spinning sweep animation on hover
  - Loading state with "Scanning AI..." text when analyzing

**PDF Report Styling:**
- Print-friendly design (white background to save ink)
- Brand colors as accents (teal headings, blue highlights)
- Radar logo on cover page and headers
- Score distribution bar charts
- Professional tables with alternating row colors

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
  genius.py          # Genius Mode insights generation (patterns, opportunities, quick wins)
  reporting.py       # PDF report generation using fpdf2
  site_inspector.py  # Website content fetching and analysis
  database.py        # SQLAlchemy models (Business, Audit) and SQLite config
  audit_runner.py    # Orchestrates audit pipeline using existing v0.3 logic
data/
  tenants.json       # Legacy tenant configuration (queries, brand aliases, geo focus)
templates/
  index.html         # Main public GEO analysis page
  admin/             # Admin panel templates
    base.html        # Admin layout with sidebar
    login.html       # Admin login page
    dashboard.html   # Admin dashboard with stats
    businesses.html  # Business listing
    business_detail.html  # Business profile and audit history
    business_new.html     # Admin business creation form
    audit_detail.html     # Audit results display
    error.html       # Error page
  public/
    business_new.html  # Public business submission form
static/              # CSS styling
reports/             # Generated PDF reports storage
echoscope.db         # SQLite database file
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
- Genius Insights & Opportunity Map (see below)
- Grouped recommendations (new pages, updates, FAQs, authority, branding)
- Professional footer with page numbering

**Site Inspector (v0.3):**
The `services/site_inspector.py` module fetches and analyzes actual tenant website content:
- Retrieves homepage and configured important paths
- Extracts titles, meta descriptions, headings, and text content
- Provides site snapshot to Genius Mode for content gap analysis
- Graceful error handling if site fetch fails

**Genius Mode v2 Insights (v0.3):**
The `generate_genius_insights()` function in `services/genius.py` produces site-aware, structured insights:
- **Patterns**: Visibility patterns with summary, evidence array, and implications
- **Priority Opportunities**: Enhanced with impact_score (1-10), effort (low/medium/high), intent_type, money_reason, and note_on_current_site for gap analysis
- **Quick Wins**: 3-5 concrete 30-day actions referencing specific pages or assets
- **Future AI Answers**: Preview of ideal AI recommendations

All insights are grounded in actual queries, competitors, geo, and site content analysis.

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
- `stripe`: Stripe payment processing SDK

**PDF Generation:**
- `fpdf2`: Pure-Python PDF generation library for professional reports

**Utilities:**
- `python-dotenv`: Environment variable management (optional)
- `python-multipart`: Form data parsing for FastAPI
- `httpx`: Async HTTP client for Replit connector API

**Deployment:**
- Designed for Replit deployment
- Uses Replit Secrets manager for API key storage
- No external database or caching layer required

### Data Storage

**SQLite Database (Sprint 1):**
- `echoscope.db`: SQLite database file
- SQLAlchemy ORM with Business and Audit models
- JSON-encoded text fields for arrays (extra_domains, regions, categories, visibility_summary, suggestions)

**File-based Configuration:**
- `data/tenants.json`: Legacy tenant configuration for original analysis feature
- `reports/`: Generated PDF reports storage

### Stripe Integration (Sprint 2)

**Stripe Checkout Flow:**
- One-time payment for EchoScope Snapshot Audit ($49)
- Stripe credentials fetched from Replit connector API
- Environment variable `STRIPE_PRICE_SNAPSHOT` stores the price ID

**Public Snapshot Flow:**
1. `/snapshot` - Landing page with pricing info
2. `/snapshot/business` - Business info form
3. `/snapshot/checkout` - Creates Stripe Checkout session
4. Stripe Hosted Checkout - User pays
5. `/webhooks/stripe` - Webhook creates audit on successful payment
6. `/snapshot/success` - Shows payment confirmation and audit status
7. `/snapshot/audit/{id}` - Public view of completed audit with PDF download

**Webhook Handler:**
- Listens for `checkout.session.completed` events
- Extracts `business_id` from session metadata
- Creates Audit with `channel="self_serve"` and `status="pending"`
- Runs audit in FastAPI BackgroundTasks to avoid blocking

**Security:**
- Business ID stored in session to prevent checkout hijacking
- Webhook signature verification (when STRIPE_WEBHOOK_SECRET is set)
- Audits only accessible via `self_serve` channel check

### Stripe Integration (Sprint 3 - Ongoing Subscriptions)

**EchoScope Ongoing Plan:**
- Monthly subscription ($29/month) with optional setup fee ($49)
- Environment variables: `STRIPE_PRICE_ONGOING_SETUP`, `STRIPE_PRICE_ONGOING_MONTHLY`
- Subscription mode Stripe Checkout with recurring billing

**Public Ongoing Flow:**
1. `/pricing` - Comparison page showing both Snapshot and Ongoing plans
2. `/ongoing` - Landing page with subscription details
3. `/ongoing/business` - Business info form (creates Business with plan="ongoing")
4. `/ongoing/checkout` - Creates subscription Stripe Checkout session
5. Stripe Hosted Checkout - User subscribes
6. `/webhooks/stripe` - Webhook sets `subscription_active=True`, stores `stripe_subscription_id`
7. `/ongoing/success` - Shows subscription confirmation and audit status
8. `/ongoing/audit/{id}` - Public view of ongoing audits

**Business Model Updates (Sprint 3):**
- `plan` field: "snapshot" or "ongoing" (default: "snapshot")
- `subscription_active` field: Boolean for active subscription status
- `stripe_subscription_id` field: Stores Stripe subscription ID for management

**Admin Panel Updates:**
- Business listing shows Plan and Subscription status columns
- Filter options: Subscribers Only, Ongoing Plan, Public Only
- Business detail shows plan type with colored badges
- "Run Monthly Refresh Audit" button for ongoing subscription businesses

**Webhook Handling:**
- Handles both `echoscope_snapshot` and `echoscope_ongoing` products
- For ongoing: sets `subscription_active=True`, stores subscription ID
- Creates initial self_serve audit for both plan types
- Runs audit in background task

**Admin Capabilities:**
- Admin can always create businesses manually (source="admin")
- Admin can run unlimited audits with channel="admin_run"
- Refresh button creates new admin_run audits for ongoing businesses
- All businesses and audits visible regardless of source/channel