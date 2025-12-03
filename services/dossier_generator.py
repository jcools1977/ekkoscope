"""
EkkoScope Intelligence Report Generator v5
Tier-1 Strategy Consulting Design (McKinsey meets Palantir)

Professional threat assessment format designed for executive consumption.
Clean Swiss-style layout with corporate consulting aesthetics.
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from fpdf import FPDF
from collections import Counter

from services.ekkoscope_sentinel import log_report_generated

logger = logging.getLogger(__name__)

DEEP_NAVY = (15, 23, 42)
SLATE_GREY = (100, 116, 139)
ALERT_RED = (239, 68, 68)
WHITE = (255, 255, 255)
LIGHT_SLATE = (148, 163, 184)
BACKGROUND = (248, 250, 252)
BORDER_LIGHT = (226, 232, 240)
SUCCESS_GREEN = (34, 197, 94)
WARNING_AMBER = (245, 158, 11)
DARK_TEXT = (30, 41, 59)


def sanitize_text(text: str) -> str:
    """Replace unsupported Unicode characters for PDF rendering."""
    if not text:
        return ""
    
    replacements = {
        '"': '"', '"': '"', ''': "'", ''': "'",
        '–': '-', '—': '-', '…': '...', '•': '*', '·': '*',
        '→': '->', '←': '<-', '↔': '<->', '✓': '[OK]', '✗': '[X]',
        '×': 'x', '≤': '<=', '≥': '>=', '≠': '!=', '±': '+/-',
        '°': ' deg', '™': '(TM)', '®': '(R)', '©': '(C)',
        '\u00A0': ' ', '\u2002': ' ', '\u2003': ' ', '\u2009': ' ',
        '\u200b': '', '\u200c': '', '\u200d': '', '\ufeff': '',
    }
    
    for u, a in replacements.items():
        text = text.replace(u, a)
    
    return ''.join(c if ord(c) < 128 else '' for c in text)


class IntelligenceReportPDF(FPDF):
    """Corporate-grade PDF for executive threat assessments."""
    
    def __init__(self, client_name: str):
        super().__init__()
        self.client_name = client_name
        self.report_date = datetime.utcnow().strftime("%B %d, %Y")
        self.set_margins(left=20, top=20, right=20)
        self.set_auto_page_break(auto=True, margin=25)
        
        font_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'fonts')
        inter_regular = os.path.join(font_dir, 'Inter-Regular.ttf')
        inter_bold = os.path.join(font_dir, 'Inter-Bold.ttf')
        
        if os.path.exists(inter_regular):
            self.add_font('Inter', '', inter_regular)
            self.add_font('Inter', 'B', inter_bold)
            self.default_font = 'Inter'
        else:
            self.default_font = 'Helvetica'
    
    def add_page(self, orientation="", format="", same=False, duration=0, transition=None):
        super().add_page(orientation, format, same, duration, transition)
        self.set_fill_color(*WHITE)
        self.rect(0, 0, 210, 297, 'F')
    
    def header(self):
        if self.page_no() > 1:
            self.set_font(self.default_font, "", 8)
            self.set_text_color(*SLATE_GREY)
            self.set_xy(20, 10)
            self.cell(80, 5, f"EkkoScope Intelligence | Client: {self.client_name[:30]}", align="L")
            self.set_xy(110, 10)
            self.cell(80, 5, f"Date: {self.report_date}", align="R")
            
            self.set_draw_color(*BORDER_LIGHT)
            self.set_line_width(0.3)
            self.line(20, 17, 190, 17)
    
    def footer(self):
        self.set_y(-15)
        self.set_font(self.default_font, "", 7)
        self.set_text_color(*SLATE_GREY)
        self.cell(0, 5, "CONFIDENTIAL - FOR INTERNAL USE ONLY", align="C")
        self.set_y(-10)
        self.cell(0, 5, f"Page {self.page_no()}", align="C")


def get_fabricator_url(business_id: int, tool_type: str) -> str:
    """Generate URL to download fabricated assets."""
    tool_endpoints = {
        "schema": f"/api/sherlock/fabricate/schema/{business_id}",
        "html": f"/api/sherlock/fabricate/landing/{business_id}",
        "content": f"/api/sherlock/fabricate/content/{business_id}",
        "faq": f"/api/sherlock/fabricate/faq/{business_id}",
        "list": f"/api/sherlock/fabricate/list/{business_id}",
    }
    return tool_endpoints.get(tool_type, f"/api/sherlock/fabricate/{tool_type}/{business_id}")


def build_dossier_pdf(
    business_name: str,
    analysis: Dict[str, Any],
    sherlock_data: Optional[Dict[str, Any]] = None,
    competitor_evidence: Optional[List[Dict[str, Any]]] = None,
    business_id: Optional[int] = None
) -> bytes:
    """
    Generate executive-grade intelligence report PDF.
    
    Args:
        business_name: The client's business name
        analysis: The visibility analysis results
        sherlock_data: Gap analysis data from Sherlock
        competitor_evidence: Evidence from Pinecone analysis
        business_id: Optional business ID for asset links
    
    Returns:
        PDF bytes
    """
    try:
        if not analysis:
            analysis = {}
        
        visibility_score = analysis.get("avg_score", 0) or 0
        mentioned_count = analysis.get("mentioned_count", 0) or 0
        total_queries = analysis.get("total_queries", 10) or 10
        
        visibility_pct = round((mentioned_count / total_queries) * 100) if total_queries > 0 else 0
        
        pdf = IntelligenceReportPDF(business_name)
        pdf.alias_nb_pages()
        
        try:
            _add_executive_briefing(pdf, business_name, analysis, visibility_pct)
        except Exception as e:
            logger.warning(f"Error adding executive briefing: {e}")
            pdf.add_page()
        
        try:
            _add_threat_landscape(pdf, analysis)
        except Exception as e:
            logger.warning(f"Error adding threat landscape: {e}")
        
        try:
            _add_semantic_gap_analysis(pdf, analysis, sherlock_data, competitor_evidence)
        except Exception as e:
            logger.warning(f"Error adding semantic gap analysis: {e}")
        
        try:
            _add_remediation_roadmap(pdf, business_name, analysis, business_id)
        except Exception as e:
            logger.warning(f"Error adding remediation roadmap: {e}")
        
        log_report_generated(business_name, "intelligence_report", pages=pdf.page_no())
        
        return pdf.output()
    
    except Exception as e:
        logger.error(f"Critical error generating intelligence report: {e}")
        raise


def _add_executive_briefing(pdf: IntelligenceReportPDF, business_name: str, 
                            analysis: Dict[str, Any], visibility_pct: int):
    """Page 1: The Executive Briefing (BLUF - Bottom Line Up Front)."""
    pdf.add_page()
    
    pdf.set_font(pdf.default_font, "", 9)
    pdf.set_text_color(*SLATE_GREY)
    pdf.set_xy(20, 15)
    pdf.cell(80, 5, "EKKOSCOPE INTELLIGENCE", align="L")
    pdf.set_xy(150, 15)
    pdf.cell(40, 5, "CONFIDENTIAL MARKET BRIEF", align="R")
    
    pdf.set_draw_color(*BORDER_LIGHT)
    pdf.set_line_width(0.5)
    pdf.line(20, 22, 190, 22)
    
    pdf.set_font(pdf.default_font, "B", 22)
    pdf.set_text_color(*DEEP_NAVY)
    pdf.set_xy(20, 35)
    pdf.cell(170, 12, "Market Intelligence Report", align="L")
    
    pdf.set_font(pdf.default_font, "", 12)
    pdf.set_text_color(*SLATE_GREY)
    pdf.set_xy(20, 48)
    pdf.cell(170, 8, sanitize_text(business_name), align="L")
    
    pdf.set_xy(20, 58)
    pdf.set_font(pdf.default_font, "", 10)
    pdf.cell(170, 6, f"Assessment Date: {pdf.report_date}", align="L")
    
    pdf.set_xy(20, 80)
    pdf.set_font(pdf.default_font, "B", 11)
    pdf.set_text_color(*DEEP_NAVY)
    pdf.cell(170, 8, "CURRENT MARKET PENETRATION", align="C")
    
    circle_x, circle_y = 105, 120
    circle_r = 35
    
    if visibility_pct == 0:
        pdf.set_fill_color(*ALERT_RED)
    elif visibility_pct < 30:
        pdf.set_fill_color(*WARNING_AMBER)
    else:
        pdf.set_fill_color(*SUCCESS_GREEN)
    
    pdf.ellipse(circle_x - circle_r, circle_y - circle_r, circle_r * 2, circle_r * 2, 'F')
    
    pdf.set_font(pdf.default_font, "B", 48)
    pdf.set_text_color(*WHITE)
    pct_text = f"{visibility_pct}%"
    pdf.set_xy(circle_x - 30, circle_y - 15)
    pdf.cell(60, 30, pct_text, align="C")
    
    pdf.set_font(pdf.default_font, "", 10)
    pdf.set_text_color(*SLATE_GREY)
    pdf.set_xy(20, 165)
    pdf.cell(170, 6, "AI Share of Voice", align="C")
    
    pdf.set_xy(20, 185)
    pdf.set_font(pdf.default_font, "B", 12)
    pdf.set_text_color(*DEEP_NAVY)
    pdf.cell(170, 8, "EXECUTIVE SUMMARY", align="L")
    
    mentioned = analysis.get("mentioned_count", 0) or 0
    total = analysis.get("total_queries", 10) or 10
    results = analysis.get("results", []) or []
    
    all_competitors = []
    for r in results:
        if isinstance(r, dict):
            all_competitors.extend(r.get("competitors", []))
    
    competitor_freq = Counter(all_competitors)
    top_competitor = competitor_freq.most_common(1)
    top_comp_name = top_competitor[0][0] if top_competitor else "Competitors"
    top_comp_share = round((top_competitor[0][1] / total) * 100) if top_competitor and total > 0 else 0
    
    bullet_points = []
    
    if visibility_pct == 0:
        bullet_points.append(f"Critical Risk: {sanitize_text(business_name)} currently holds 0% Share of Voice in AI-mediated search.")
    else:
        bullet_points.append(f"Current Position: {sanitize_text(business_name)} holds {visibility_pct}% Share of Voice in AI-mediated search.")
    
    if top_competitor:
        bullet_points.append(f"Primary Threat: {sanitize_text(top_comp_name)[:40]} commands {top_comp_share}% market share in AI recommendations.")
    
    if visibility_pct < 30:
        bullet_points.append("Strategic Imperative: Immediate deployment of targeted content assets required to intercept competitor traffic.")
    else:
        bullet_points.append("Opportunity: Strengthen current positioning through content optimization and authority building.")
    
    pdf.set_font(pdf.default_font, "", 10)
    pdf.set_text_color(*DARK_TEXT)
    
    y_pos = 198
    for point in bullet_points:
        pdf.set_fill_color(*ALERT_RED if "Critical" in point else (*DEEP_NAVY,))
        pdf.ellipse(25, y_pos + 2, 3, 3, 'F')
        pdf.set_xy(32, y_pos)
        pdf.multi_cell(155, 6, sanitize_text(point), align="L")
        y_pos = pdf.get_y() + 4
    
    pdf.set_draw_color(*BORDER_LIGHT)
    pdf.set_line_width(0.3)
    pdf.line(20, 270, 190, 270)
    
    pdf.set_font(pdf.default_font, "", 8)
    pdf.set_text_color(*SLATE_GREY)
    pdf.set_xy(20, 273)
    pdf.cell(170, 5, f"Analysis based on {total} strategic queries across major AI platforms", align="C")


def _add_threat_landscape(pdf: IntelligenceReportPDF, analysis: Dict[str, Any]):
    """Page 2: Competitive Vector Analysis - The Threat Landscape."""
    pdf.add_page()
    
    pdf.set_font(pdf.default_font, "B", 18)
    pdf.set_text_color(*DEEP_NAVY)
    pdf.set_xy(20, 25)
    pdf.cell(170, 10, "Competitive Vector Analysis", align="L")
    
    pdf.set_font(pdf.default_font, "", 10)
    pdf.set_text_color(*SLATE_GREY)
    pdf.set_xy(20, 38)
    pdf.multi_cell(170, 5, "Market share distribution across AI recommendation channels. "
                   "Analysis of competitive positioning and threat assessment.")
    
    results = analysis.get("results", []) or []
    total_queries = len(results) if results else 10
    
    all_competitors = []
    for r in results:
        if isinstance(r, dict):
            all_competitors.extend(r.get("competitors", []))
    
    competitor_freq = Counter(all_competitors)
    top_5 = competitor_freq.most_common(5)
    
    if not top_5:
        pdf.set_font(pdf.default_font, "", 11)
        pdf.set_text_color(*SLATE_GREY)
        pdf.set_xy(20, 60)
        pdf.cell(170, 10, "Insufficient data for competitive analysis.", align="C")
        return
    
    pdf.set_font(pdf.default_font, "B", 11)
    pdf.set_text_color(*DEEP_NAVY)
    pdf.set_xy(20, 55)
    pdf.cell(170, 8, "MARKET SHARE DISTRIBUTION", align="L")
    
    max_freq = max([freq for _, freq in top_5]) if top_5 else 1
    bar_start_x = 80
    bar_max_width = 100
    
    y_pos = 70
    for rank, (competitor, frequency) in enumerate(top_5, 1):
        share = round((frequency / total_queries) * 100) if total_queries > 0 else 0
        bar_width = (frequency / max_freq) * bar_max_width if max_freq > 0 else 0
        
        pdf.set_font(pdf.default_font, "", 9)
        pdf.set_text_color(*DARK_TEXT)
        pdf.set_xy(20, y_pos)
        pdf.cell(55, 10, sanitize_text(competitor[:25]), align="L")
        
        pdf.set_fill_color(*DEEP_NAVY)
        pdf.rect(bar_start_x, y_pos + 2, bar_width, 6, 'F')
        
        pdf.set_font(pdf.default_font, "B", 9)
        pdf.set_text_color(*DEEP_NAVY)
        pdf.set_xy(bar_start_x + bar_width + 3, y_pos)
        pdf.cell(20, 10, f"{share}%", align="L")
        
        y_pos += 14
    
    pdf.set_font(pdf.default_font, "B", 11)
    pdf.set_text_color(*DEEP_NAVY)
    pdf.set_xy(20, 150)
    pdf.cell(170, 8, "ADVERSARY INTELLIGENCE TABLE", align="L")
    
    table_y = 162
    col_widths = [15, 65, 30, 60]
    headers = ["#", "Adversary", "Dominance", "Key Strength"]
    
    pdf.set_fill_color(*DEEP_NAVY)
    pdf.rect(20, table_y, 170, 10, 'F')
    
    pdf.set_font(pdf.default_font, "B", 9)
    pdf.set_text_color(*WHITE)
    x_pos = 20
    for i, header in enumerate(headers):
        pdf.set_xy(x_pos, table_y + 2)
        pdf.cell(col_widths[i], 6, header, align="L" if i > 0 else "C")
        x_pos += col_widths[i]
    
    table_y += 10
    
    for rank, (competitor, frequency) in enumerate(top_5, 1):
        share = round((frequency / total_queries) * 100) if total_queries > 0 else 0
        
        if rank % 2 == 0:
            pdf.set_fill_color(*BACKGROUND)
            pdf.rect(20, table_y, 170, 12, 'F')
        
        pdf.set_draw_color(*BORDER_LIGHT)
        pdf.set_line_width(0.2)
        pdf.line(20, table_y + 12, 190, table_y + 12)
        
        threat_level = "High" if share >= 20 else ("Medium" if share >= 10 else "Low")
        key_weapon = "Dominant market position" if share >= 20 else "Active AI presence"
        
        pdf.set_font(pdf.default_font, "", 9)
        pdf.set_text_color(*DARK_TEXT)
        
        x_pos = 20
        pdf.set_xy(x_pos, table_y + 3)
        pdf.cell(col_widths[0], 6, str(rank), align="C")
        x_pos += col_widths[0]
        
        pdf.set_xy(x_pos, table_y + 3)
        pdf.cell(col_widths[1], 6, sanitize_text(competitor[:28]), align="L")
        x_pos += col_widths[1]
        
        pdf.set_font(pdf.default_font, "B", 9)
        if threat_level == "High":
            pdf.set_text_color(*ALERT_RED)
        elif threat_level == "Medium":
            pdf.set_text_color(*WARNING_AMBER)
        else:
            pdf.set_text_color(*SLATE_GREY)
        
        pdf.set_xy(x_pos, table_y + 3)
        pdf.cell(col_widths[2], 6, f"{share}%", align="L")
        x_pos += col_widths[2]
        
        pdf.set_font(pdf.default_font, "", 9)
        pdf.set_text_color(*DARK_TEXT)
        pdf.set_xy(x_pos, table_y + 3)
        pdf.cell(col_widths[3], 6, key_weapon, align="L")
        
        table_y += 12


def _add_semantic_gap_analysis(pdf: IntelligenceReportPDF, analysis: Dict[str, Any],
                                sherlock_data: Optional[Dict[str, Any]],
                                competitor_evidence: Optional[List[Dict[str, Any]]]):
    """Page 3: Semantic Gap Intelligence - Content Gap Forensics."""
    pdf.add_page()
    
    pdf.set_font(pdf.default_font, "B", 18)
    pdf.set_text_color(*DEEP_NAVY)
    pdf.set_xy(20, 25)
    pdf.cell(170, 10, "Content Gap Forensics", align="L")
    
    pdf.set_font(pdf.default_font, "", 10)
    pdf.set_text_color(*SLATE_GREY)
    pdf.set_xy(20, 38)
    pdf.multi_cell(170, 5, "Semantic analysis of messaging disparities. Side-by-side comparison of "
                   "competitor signals versus your current content positioning.")
    
    gaps = []
    
    if sherlock_data and isinstance(sherlock_data, dict):
        missions = sherlock_data.get("missions", []) or []
        if isinstance(missions, list):
            for mission in missions[:4]:
                if isinstance(mission, dict):
                    gaps.append({
                        "topic": str(mission.get("title", mission.get("topic", "Content Gap"))),
                        "competitor_signal": str(mission.get("competitor_mentions", "Active messaging detected")),
                        "your_signal": "No matching signal detected",
                        "severity": str(mission.get("severity", "high"))
                    })
    
    if not gaps:
        results = analysis.get("results", []) or []
        if isinstance(results, list):
            for r in results:
                if isinstance(r, dict) and r.get("score", 0) == 0:
                    query = str(r.get("query", ""))
                    competitors = r.get("competitors", []) or []
                    if competitors and isinstance(competitors, list) and query:
                        intent = str(r.get("intent_type", "general"))
                        gaps.append({
                            "topic": query[:45] if query else "Search Query",
                            "competitor_signal": f"{competitors[0][:25]} appears in results" if competitors else "Competitor visibility",
                            "your_signal": "Zero-signal detected",
                            "severity": "high" if intent in ["emergency", "high_ticket"] else "medium"
                        })
                    if len(gaps) >= 4:
                        break
    
    if not gaps:
        pdf.set_fill_color(*BACKGROUND)
        pdf.rect(20, 55, 170, 50, 'F')
        
        pdf.set_font(pdf.default_font, "B", 11)
        pdf.set_text_color(*DEEP_NAVY)
        pdf.set_xy(20, 65)
        pdf.cell(170, 8, "DEEP ANALYSIS PENDING", align="C")
        
        pdf.set_font(pdf.default_font, "", 10)
        pdf.set_text_color(*SLATE_GREY)
        pdf.set_xy(20, 78)
        pdf.multi_cell(170, 5, "Execute the Semantic Intelligence Scanner from Mission Control "
                       "to identify specific content gaps and generate actionable remediation tasks.", align="C")
        return
    
    y_pos = 55
    
    for i, gap in enumerate(gaps, 1):
        if y_pos > 230:
            pdf.add_page()
            y_pos = 30
        
        pdf.set_font(pdf.default_font, "B", 10)
        pdf.set_text_color(*DEEP_NAVY)
        pdf.set_xy(20, y_pos)
        topic_text = sanitize_text(str(gap.get("topic", "Signal Gap"))[:50])
        pdf.cell(170, 8, f"Gap #{i}: {topic_text}", align="L")
        
        y_pos += 12
        
        col_width = 82
        
        pdf.set_fill_color(254, 226, 226)
        pdf.rect(20, y_pos, col_width, 35, 'F')
        
        pdf.set_font(pdf.default_font, "B", 9)
        pdf.set_text_color(*ALERT_RED)
        pdf.set_xy(25, y_pos + 3)
        pdf.cell(col_width - 10, 6, "COMPETITOR SIGNAL", align="L")
        
        pdf.set_font(pdf.default_font, "", 9)
        pdf.set_text_color(*DARK_TEXT)
        pdf.set_xy(25, y_pos + 12)
        competitor_text = sanitize_text(str(gap.get("competitor_signal", "Active messaging"))[:80])
        pdf.multi_cell(col_width - 10, 5, competitor_text, align="L")
        
        pdf.set_fill_color(*BACKGROUND)
        pdf.rect(108, y_pos, col_width, 35, 'F')
        
        pdf.set_font(pdf.default_font, "B", 9)
        pdf.set_text_color(*SLATE_GREY)
        pdf.set_xy(113, y_pos + 3)
        pdf.cell(col_width - 10, 6, "YOUR SIGNAL", align="L")
        
        pdf.set_font(pdf.default_font, "", 9)
        pdf.set_text_color(*DARK_TEXT)
        pdf.set_xy(113, y_pos + 12)
        your_text = sanitize_text(str(gap.get("your_signal", "No signal detected"))[:80])
        pdf.multi_cell(col_width - 10, 5, your_text, align="L")
        
        y_pos += 42
    
    if pdf.get_y() < 220:
        pdf.set_fill_color(*BACKGROUND)
        analyst_y = max(y_pos + 5, 220)
        pdf.rect(20, analyst_y, 170, 35, 'F')
        
        pdf.set_draw_color(*DEEP_NAVY)
        pdf.set_line_width(0.5)
        pdf.line(20, analyst_y, 20, analyst_y + 35)
        
        pdf.set_font(pdf.default_font, "B", 10)
        pdf.set_text_color(*DEEP_NAVY)
        pdf.set_xy(25, analyst_y + 5)
        pdf.cell(160, 6, "ANALYST OBSERVATION", align="L")
        
        pdf.set_font(pdf.default_font, "", 9)
        pdf.set_text_color(*DARK_TEXT)
        pdf.set_xy(25, analyst_y + 14)
        pdf.multi_cell(160, 5, "Competitors demonstrate active signals for urgency, speed, and locality. "
                       "Your current content lacks these semantic markers, causing AI models to deprecate "
                       "your ranking for high-intent queries. Immediate content remediation recommended.", align="L")


def _add_remediation_roadmap(pdf: IntelligenceReportPDF, business_name: str,
                              analysis: Dict[str, Any], business_id: Optional[int] = None):
    """Page 4: 30-Day Tactical Roadmap - The Remediation Protocol."""
    pdf.add_page()
    
    pdf.set_font(pdf.default_font, "B", 18)
    pdf.set_text_color(*DEEP_NAVY)
    pdf.set_xy(20, 25)
    pdf.cell(170, 10, "30-Day Tactical Roadmap", align="L")
    
    pdf.set_font(pdf.default_font, "", 10)
    pdf.set_text_color(*SLATE_GREY)
    pdf.set_xy(20, 38)
    pdf.multi_cell(170, 5, "Phased remediation protocol designed for rapid market penetration improvement. "
                   "Execute sequentially for optimal results.")
    
    phases = [
        {
            "week": "PHASE 1",
            "title": "Infrastructure Hardening",
            "timeline": "Days 1-7",
            "tasks": [
                "Deploy JSON-LD structured data schema",
                "Optimize meta descriptions with target keywords",
                "Implement local business markup",
                "Verify Google Business Profile completeness"
            ],
            "color": DEEP_NAVY
        },
        {
            "week": "PHASE 2", 
            "title": "Asset Deployment",
            "timeline": "Days 8-14",
            "tasks": [
                "Launch emergency service landing page",
                "Create FAQ content addressing gap topics",
                "Deploy location-specific content pages",
                "Implement urgency signals in copy"
            ],
            "color": (59, 130, 246)
        },
        {
            "week": "PHASE 3",
            "title": "Authority Signals",
            "timeline": "Days 15-21", 
            "tasks": [
                "Generate citation requests to directories",
                "Implement customer review solicitation",
                "Create industry authority content",
                "Build local partnership signals"
            ],
            "color": (16, 185, 129)
        },
        {
            "week": "PHASE 4",
            "title": "Re-Assessment",
            "timeline": "Days 22-30",
            "tasks": [
                "Execute follow-up visibility scan",
                "Measure Share of Voice improvement",
                "Identify remaining gap areas",
                "Plan Phase 2 optimization cycle"
            ],
            "color": (139, 92, 246)
        }
    ]
    
    y_pos = 55
    timeline_x = 35
    content_x = 55
    
    pdf.set_draw_color(*BORDER_LIGHT)
    pdf.set_line_width(2)
    pdf.line(timeline_x, y_pos, timeline_x, y_pos + 195)
    
    for phase in phases:
        pdf.set_fill_color(*phase["color"])
        pdf.ellipse(timeline_x - 5, y_pos - 5, 10, 10, 'F')
        
        pdf.set_font(pdf.default_font, "B", 11)
        pdf.set_text_color(*phase["color"])
        pdf.set_xy(content_x, y_pos - 5)
        pdf.cell(60, 8, phase["week"], align="L")
        
        pdf.set_font(pdf.default_font, "", 9)
        pdf.set_text_color(*SLATE_GREY)
        pdf.set_xy(content_x + 60, y_pos - 5)
        pdf.cell(40, 8, phase["timeline"], align="L")
        
        pdf.set_font(pdf.default_font, "B", 10)
        pdf.set_text_color(*DEEP_NAVY)
        pdf.set_xy(content_x, y_pos + 5)
        pdf.cell(130, 6, phase["title"], align="L")
        
        pdf.set_font(pdf.default_font, "", 9)
        pdf.set_text_color(*DARK_TEXT)
        
        task_y = y_pos + 13
        for task in phase["tasks"]:
            pdf.set_xy(content_x + 5, task_y)
            pdf.cell(5, 5, "-", align="L")
            pdf.set_xy(content_x + 10, task_y)
            pdf.cell(120, 5, sanitize_text(task), align="L")
            task_y += 6
        
        y_pos += 50
    
    pdf.set_fill_color(*DEEP_NAVY)
    cta_y = 260
    pdf.rect(20, cta_y, 170, 20, 'F')
    
    pdf.set_font(pdf.default_font, "B", 10)
    pdf.set_text_color(*WHITE)
    pdf.set_xy(20, cta_y + 6)
    pdf.cell(170, 8, "Access Mission Control to Deploy Assets: /dashboard", align="C")
