# EkkoScope - GEO Engine for AI Visibility

## Overview

EkkoScope is a web application designed to analyze and improve "AI visibility" for businesses. It assesses how frequently businesses are recommended by AI assistants like ChatGPT by running predefined queries against AI APIs. The system determines prominence compared to competitors and provides actionable content recommendations. The project aims to empower businesses to understand and optimize their presence in AI-driven search and recommendation landscapes. Key capabilities include AI visibility audits, PDF report generation, and integrated content recommendations.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Frontend

EkkoScope utilizes Jinja2 for server-side rendering, delivering a single-page application experience primarily through form submissions. The design incorporates a full dark theme with a sci-fi aesthetic, featuring neon teal and electric blue accents, a custom radar logo, and subtle animations. PDF reports are print-friendly, using brand colors as accents. The UI is built with pure HTML/CSS, avoiding JavaScript frameworks for simplicity and statelessness.

### Backend

The backend is built with FastAPI and Uvicorn, running on Python 3.11+. It handles AI visibility analysis, PDF report generation (`fpdf2`), website content fetching (`site_inspector.py`), and sophisticated insights generation through "Genius Mode." The application orchestrates the audit pipeline, interacting with AI models to score business mentions (0-2 scale) and generate content recommendations. Configuration for businesses and queries is managed through a SQLite database and `data/tenants.json`.

### AI Integration

The system integrates with the OpenAI API for core AI visibility analysis and content recommendation generation. It employs prompt engineering for structured, JSON-formatted responses. Genius Mode leverages both OpenAI and optionally Perplexity AI to generate patterns, priority opportunities, and quick wins based on query results and website content analysis.

### System Design Choices

- **Persistence**: SQLite database for storing business information, audit results, and user data.
- **Configuration**: JSON files (`data/tenants.json`) for initial tenant and query configurations.
- **Reporting**: Generates professional, branded PDF reports summarizing AI visibility.
- **Genius Mode**: Provides structured, site-aware insights (patterns, opportunities, quick wins) based on AI analysis.
- **Scoring Logic**: Businesses are scored 0-2 based on mention and prominence in AI responses.
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