# EkkoScope - GEO Engine for AI Visibility

## Overview

EkkoScope is a premium SaaS web application designed to analyze and improve "AI visibility" for businesses. It assesses how frequently businesses are recommended by AI assistants like ChatGPT by running comprehensive queries against AI APIs. The system determines prominence compared to competitors and provides actionable content recommendations. The project aims to empower businesses to understand and optimize their presence in AI-driven search and recommendation landscapes. Key capabilities include AI visibility audits, premium PDF report generation, and integrated content recommendations.

## Recent Changes (November 2025)

### Premium PDF Report Enhancement (v1.0)
- **Enhanced Query Generation**: Expanded from 4 generic queries to 20-30 industry-specific queries with intent classification (emergency, high_ticket, replenishment, informational, transactional)
- **Professional PDF Reports**: Complete redesign with:
  - Executive Dashboard with key metrics and score distribution
  - Query Analysis with intent classification
  - Competitor Landscape Matrix with threat levels
  - Multi-Source Visibility comparison (OpenAI vs Perplexity)
  - Detailed Page Blueprints section (3-7 pages with SEO specs)
  - 30-Day Implementation Roadmap (week-by-week action plan)
  - Strategic Recommendations section
- **Industry-Specific Content**: Reports now use business categories and specific products/services rather than generic "industrial supplies" language
- **Branding Fixes**: Consistent EkkoScope naming, proper bullet formatting, no raw markdown characters

### Key Files Updated
- `services/query_generator.py` (NEW) - Comprehensive query generation with intent classification
- `services/reporting.py` - Complete PDF report redesign
- `services/analysis.py` - Added intent metadata to query results
- `services/database.py` - Enhanced tenant config with categories and business_type

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Frontend

EkkoScope utilizes Jinja2 for server-side rendering, delivering a single-page application experience primarily through form submissions. The design incorporates a full dark theme with a sci-fi aesthetic, featuring neon teal and electric blue accents, a custom radar logo, and animated radar buttons for audit actions. PDF reports are print-friendly, using brand colors as accents. The UI is built with pure HTML/CSS, avoiding JavaScript frameworks for simplicity and statelessness.

### Backend

The backend is built with FastAPI and Uvicorn, running on Python 3.11+. It handles AI visibility analysis, premium PDF report generation (`fpdf2`), website content fetching (`site_inspector.py`), and sophisticated insights generation through "Genius Mode." The application orchestrates the audit pipeline, interacting with AI models to score business mentions (0-2 scale) and generate content recommendations. Configuration for businesses and queries is managed through a SQLite database.

### AI Integration

The system integrates with the OpenAI API for core AI visibility analysis and content recommendation generation. It employs prompt engineering for structured, JSON-formatted responses. Genius Mode leverages both OpenAI and optionally Perplexity AI to generate patterns, priority opportunities, and quick wins based on query results and website content analysis. Each query is now classified by intent type for more actionable insights.

### System Design Choices

- **Persistence**: SQLite database for storing business information, audit results, and user data.
- **Query Generation**: Advanced industry-specific query generator with 20-30 queries per audit, classified by intent (emergency, high_ticket, replenishment, informational, transactional).
- **Reporting**: Premium PDF reports (10-15 pages) with executive dashboard, competitor analysis, page blueprints, and 30-day action plans.
- **Genius Mode**: Provides structured, site-aware insights (patterns, opportunities, quick wins) based on AI analysis.
- **Scoring Logic**: Businesses are scored 0-2 based on mention and prominence in AI responses.
- **Intent Classification**: Queries are classified by business intent for prioritized recommendations.
- **Error Handling**: Robust error management, including custom exceptions for API key validation and graceful UI error display.
- **Security**: Utilizes Replit Secrets for API key storage, session-based business ID protection for checkout, and webhook signature verification for payment processing.

## External Dependencies

### Third-Party Services

- **OpenAI API**: Core AI engine for visibility analysis and content recommendations. Requires `OPENAI_API_KEY`.
- **Perplexity API**: (Optional) Provides web-grounded, real-time search capabilities to augment AI visibility analysis. Requires `PERPLEXITY_API_KEY`.
- **Stripe**: Payment gateway for one-time snapshot audits and ongoing subscriptions. Integrates Stripe Checkout for payment processing and webhooks for transaction handling. Requires `STRIPE_PRICE_SNAPSHOT`, `STRIPE_PRICE_ONGOING_SETUP`, `STRIPE_PRICE_ONGOING_MONTHLY`, and `STRIPE_WEBHOOK_SECRET`.

### Python Packages

- **Web Framework**: `fastapi`, `uvicorn[standard]`, `jinja2`
- **AI/API Clients**: `openai`, `httpx` (for Replit connector API)
- **Database**: `SQLAlchemy`
- **PDF Generation**: `fpdf2`
- **Utilities**: `python-dotenv`, `python-multipart`

### Data Storage

- **SQLite Database**: `echoscope.db` for all persistent application data (businesses, audits).
- **File-based**: `data/tenants.json` for initial tenant configurations, `reports/` for generated PDF outputs.
```