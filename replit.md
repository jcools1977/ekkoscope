# EkkoScope - GEO Engine for AI Visibility

## Overview

EkkoScope is a premium SaaS web application designed to analyze and improve "AI visibility" for businesses. It assesses how frequently businesses are recommended by AI assistants like ChatGPT by running comprehensive queries against AI APIs, determining prominence compared to competitors, and providing actionable content recommendations. The project aims to empower businesses to understand and optimize their presence in AI-driven search and recommendation landscapes, offering features like AI visibility audits, premium PDF report generation, integrated content recommendations, and autonomous auto-remediation via specialized AI agents. The business vision is to provide a critical tool for businesses navigating the evolving AI-driven search and recommendation landscape, offering a competitive edge and significant market potential.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### UI/UX Decisions

EkkoScope utilizes Jinja2 for server-side rendering, delivering a single-page application experience. The design features a full dark theme with a sci-fi aesthetic, neon teal and electric blue accents, a custom radar logo, and animated radar buttons. PDF reports are print-friendly, using brand colors as accents. The UI is built with pure HTML/CSS, avoiding JavaScript frameworks for simplicity. A new client presentation mode allows for agency white-labeling, hiding paywalls, and full content access. The unified Black-Ops design system employs a color scheme of pure black (`#0a0a0f`), cyan accents (`#00f0ff`), and blood-red alerts (`#ff0000`), with JetBrains Mono typography throughout.

### Technical Implementations

The backend is built with FastAPI and Uvicorn on Python 3.11+. It handles AI visibility analysis, premium PDF report generation (`fpdf2`), website content fetching (`site_inspector.py`), and sophisticated insights generation through "Genius Mode." The application orchestrates the audit pipeline, interacting with AI models to score business mentions (0-2 scale) and generate content recommendations. Configuration for businesses and queries is managed through a SQLite database.

### Feature Specifications

- **AI Visibility Audits**: Comprehensive reports on how businesses are recommended by AI assistants.
- **Premium PDF Report Generation**: Detailed, multi-page reports with executive dashboards, competitor analysis, page blueprints, and 30-day action plans. Reports feature full content display with no truncation, list-based layouts, and industry-specific content.
- **Dossier Report Format**: Narrative-driven "Intelligence Dossier" PDF that transforms data into a compelling forensic-to-coaching story:
    - **Section A: "The Forensic Audit"**: CLASSIFIED cover page with INVISIBLE/DETECTED verdict stamp, Suspect Lineup (top 3 competitors), and "Smoking Gun" evidence from gap analysis.
    - **Section B: "The Coach's Playbook"**: 4-week implementation sprint with Week 1 (Triage & Patching), Week 2 (Content Counter-Attack), Week 3 (Authority & Signals), Week 4 (Re-Scan).
    - **Fabricator Integration**: Each week's tasks include downloadable tools (Schema.json, Landing_Page_Template.html, etc.) with URLs to the Fabricator API.
    - **Endpoint**: `GET /dossier/{business_id}` generates the narrative PDF on-demand.
- **Content Recommendations**: Actionable suggestions for improving AI visibility.
- **Autonomous Auto-Remediation (EkkoScope v4)**: A system called FixEngine Core that parses GEO reports and generates fixes automatically using a PDF Parser, AI Fix Planner (GPT-4o), and 4 specialized AI agents:
    - **Content Agent**: Generates optimized meta descriptions, FAQs, and page content.
    - **SEO Agent**: Creates JSON-LD schema markup.
    - **Deploy Agent**: Generates WordPress PHP, raw HTML, and API payloads.
    - **Verification Agent**: Calculates before/after metrics.
- **Multi-LLM Visibility System**: Analysis runs across OpenAI, Perplexity, and Google Gemini, providing a unified visibility matrix in reports.
- **EkkoBrain Memory System**: A two-layer architecture (DB + Pinecone vector search) for persistent pattern learning from completed audits, enhancing future recommendations while ensuring privacy.
- **Sherlock Semantic Intelligence Engine**: Advanced gap analysis system using Pinecone vector embeddings to identify semantic differences between client and competitor content. Unlike keyword-based tools, Sherlock identifies missing TOPICS - understanding meaning and context. Key features:
    - **Content Ingestion**: Scrapes and embeds website content into vector space.
    - **Topic Extraction**: Uses GPT to identify semantic themes (not just keywords).
    - **Gap Analysis**: Compares client vs competitor vector spaces to find missing topics.
    - **Mission Generation**: Creates actionable tasks like "Create a page about Storm Damage Insurance."
    - **Strategic Consultant (RAG Chat)**: "Interrogation Room" feature - users ask questions like "Why is Coastal Roofing beating me?" and receive evidence-based strategic advice with Pinecone-retrieved sources.
    - **Fabricator (Asset Generation)**: Turns missions into downloadable files - generates JSON-LD schema, HTML landing pages, FAQ content based on business details and missing topics.
    - **Evidence Display**: Shows "Show Evidence" toggle in chat responses linking to Pinecone source documents.
    - **API Endpoints**: Full REST API at `/api/sherlock/*` including `/consult` (RAG) and `/fabricate/{mission_id}` (file generation).
- **Activation Code System**: Supports one-time-use activation codes for prospects.
- **Free First Report Feature**: New users receive one free AI visibility report upon signup.
- **Sentinel OS Integration**: Real-time logging of AI queries and report generation events to the Sentinel OS dashboard.

### System Design Choices

- **Persistence**: SQLite database for storing business information, audit results, user data, and remediation results.
- **Query Generation**: Advanced industry-specific query generator classifying intent (emergency, high_ticket, replenishment, informational, transactional).
- **Genius Mode**: Provides structured, site-aware insights based on AI analysis.
- **Scoring Logic**: Businesses are scored 0-2 based on mention and prominence in AI responses.
- **Error Handling**: Robust error management with graceful degradation for unavailable AI providers.
- **Security**: Utilizes Replit Secrets for API keys, session-based business ID protection, and webhook signature verification.

## External Dependencies

### Third-Party Services

-   **OpenAI API**: Core AI engine for visibility analysis, simulated ChatGPT recommendations, and Genius Mode insights.
-   **Perplexity API**: (Optional) Provides web-grounded, real-time search capabilities.
-   **Google Gemini API**: (Optional) Additional AI assistant simulation for cross-platform visibility comparison.
-   **Stripe**: Payment gateway for one-time audits and subscriptions, handling checkout and webhooks.
-   **Pinecone**: Vector database using `ekkobrain` index with `text-embedding-3-large` (3072 dimensions). Organized into namespaces:
    - `business-content`: Client website data
    - `competitor-content`: Competitor website data
    - `audit-patterns`: EkkoBrain learning patterns
    - `gap-missions`: Sherlock gap analysis missions
    - `strategic-insights`: Strategic recommendations

### Python Packages

-   **Web Framework**: `fastapi`, `uvicorn[standard]`, `jinja2`
-   **AI/API Clients**: `openai`, `httpx`, `pinecone`
-   **Database**: `SQLAlchemy`
-   **PDF Generation**: `fpdf2`, `PyPDF2`
-   **Utilities**: `python-dotenv`, `python-multipart`

### Data Storage

-   **SQLite Database**: `echoscope.db` for all persistent application data.
-   **File-based**: `data/tenants.json` for initial tenant configurations, `reports/` for generated PDF outputs.