"""
EkkoScope Dossier Generator v4
Narrative-Driven AI Visibility Report

Structure:
- Section A: "The Forensic Audit" (Crime Scene Analysis)
- Section B: "The Coach's Playbook" (4-Week Sprint Plan)

Transitions from "Forensic Analyst" (The Problem) to "Success Coach" (The Solution).
Integrates with Sherlock/Pinecone for real competitor evidence.
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

BLACK_BG = (10, 10, 15)
CYAN_GLOW = (0, 240, 255)
BLOOD_RED = (255, 0, 0)
EVIDENCE_RED = (200, 50, 50)
WHITE_TEXT = (255, 255, 255)
DARK_GRAY = (40, 40, 50)
MEDIUM_GRAY = (100, 100, 110)
LIGHT_GRAY = (150, 150, 160)
SUCCESS_GREEN = (0, 255, 128)
WARNING_YELLOW = (255, 200, 0)
GOLD = (255, 215, 0)
MANILA_FOLDER = (245, 222, 179)
STAMP_RED = (180, 20, 20)
COACH_BLUE = (50, 130, 200)


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


class DossierPDF(FPDF):
    """PDF class for narrative-driven dossier reports."""
    
    def __init__(self, business_name: str, is_detected: bool = False):
        super().__init__()
        self.business_name = business_name
        self.is_detected = is_detected
        self.current_section = "forensic"
        self.set_margins(left=15, top=18, right=15)
        self.set_auto_page_break(auto=True, margin=25)
        
        font_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'fonts')
        regular_font = os.path.join(font_dir, 'JetBrainsMono-Regular.ttf')
        bold_font = os.path.join(font_dir, 'JetBrainsMono-Bold.ttf')
        
        if os.path.exists(regular_font):
            self.add_font('JetBrains', '', regular_font)
            self.add_font('JetBrains', 'B', bold_font)
            self.default_font = 'JetBrains'
        else:
            self.default_font = 'Helvetica'
    
    def add_page(self, orientation="", format="", same=False, duration=0, transition=None):
        super().add_page(orientation, format, same, duration, transition)
        self.set_fill_color(*BLACK_BG)
        self.rect(0, 0, 210, 297, 'F')
    
    def header(self):
        if self.page_no() > 1:
            if self.current_section == "forensic":
                self._draw_forensic_header()
            else:
                self._draw_coach_header()
    
    def _draw_forensic_header(self):
        """Draw header for Forensic Audit section."""
        self.set_font(self.default_font, "B", 9)
        self.set_text_color(*EVIDENCE_RED)
        self.set_xy(15, 8)
        self.cell(0, 10, "CLASSIFIED // FORENSIC AUDIT", align="L")
        self.set_draw_color(*EVIDENCE_RED)
        self.set_line_width(0.5)
        self.line(10, 18, 200, 18)
    
    def _draw_coach_header(self):
        """Draw header for Coach's Playbook section."""
        self.set_font(self.default_font, "B", 9)
        self.set_text_color(*SUCCESS_GREEN)
        self.set_xy(15, 8)
        self.cell(0, 10, "COACH'S PLAYBOOK // 30-DAY SPRINT", align="L")
        self.set_draw_color(*SUCCESS_GREEN)
        self.set_line_width(0.5)
        self.line(10, 18, 200, 18)
    
    def footer(self):
        self.set_y(-20)
        self.set_font(self.default_font, "", 7)
        self.set_text_color(*MEDIUM_GRAY)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}} | EkkoScope Intelligence Dossier", align="C")


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
    Generate narrative-driven dossier PDF.
    
    Args:
        business_name: The client's business name
        analysis: The visibility analysis results
        sherlock_data: Gap analysis data from Sherlock
        competitor_evidence: Smoking gun evidence from Pinecone
        business_id: Optional business ID for fabricator links
    
    Returns:
        PDF bytes
    """
    try:
        if not analysis:
            analysis = {}
        
        visibility_score = analysis.get("avg_score", 0) or 0
        mentioned_count = analysis.get("mentioned_count", 0) or 0
        total_queries = analysis.get("total_queries", 10) or 10
        
        is_detected = mentioned_count > 0 and visibility_score > 0.5
        
        pdf = DossierPDF(business_name, is_detected)
        pdf.alias_nb_pages()
        
        try:
            _add_dossier_cover(pdf, business_name, analysis, is_detected)
        except Exception as e:
            logger.warning(f"Error adding dossier cover: {e}")
            pdf.add_page()
        
        pdf.current_section = "forensic"
        
        try:
            _add_forensic_verdict(pdf, analysis, is_detected)
        except Exception as e:
            logger.warning(f"Error adding forensic verdict: {e}")
        
        try:
            _add_suspect_lineup(pdf, analysis)
        except Exception as e:
            logger.warning(f"Error adding suspect lineup: {e}")
        
        try:
            _add_smoking_gun(pdf, analysis, sherlock_data, competitor_evidence)
        except Exception as e:
            logger.warning(f"Error adding smoking gun: {e}")
        
        pdf.current_section = "coach"
        
        try:
            _add_playbook_intro(pdf, business_name, analysis)
        except Exception as e:
            logger.warning(f"Error adding playbook intro: {e}")
        
        try:
            _add_week_1_triage(pdf, analysis, sherlock_data, business_id)
        except Exception as e:
            logger.warning(f"Error adding week 1: {e}")
        
        try:
            _add_week_2_content_attack(pdf, analysis, sherlock_data, business_id)
        except Exception as e:
            logger.warning(f"Error adding week 2: {e}")
        
        try:
            _add_week_3_authority(pdf, analysis, business_id)
        except Exception as e:
            logger.warning(f"Error adding week 3: {e}")
        
        try:
            _add_week_4_rescan(pdf, business_name)
        except Exception as e:
            logger.warning(f"Error adding week 4: {e}")
        
        try:
            _add_next_steps(pdf, business_name)
        except Exception as e:
            logger.warning(f"Error adding next steps: {e}")
        
        log_report_generated(business_name, "dossier", pages=pdf.page_no())
        
        return pdf.output()
    
    except Exception as e:
        logger.error(f"Critical error generating dossier PDF: {e}")
        raise


def _add_dossier_cover(pdf: DossierPDF, business_name: str, analysis: Dict[str, Any], is_detected: bool):
    """Add dramatic dossier cover page."""
    pdf.add_page()
    
    pdf.set_fill_color(30, 30, 35)
    pdf.rect(20, 30, 170, 200, 'F')
    
    pdf.set_draw_color(*EVIDENCE_RED)
    pdf.set_line_width(2)
    pdf.rect(20, 30, 170, 200)
    
    pdf.set_font(pdf.default_font, "B", 14)
    pdf.set_text_color(*EVIDENCE_RED)
    pdf.set_xy(25, 35)
    pdf.cell(0, 8, "CLASSIFIED INTELLIGENCE DOSSIER", align="L")
    
    pdf.set_font(pdf.default_font, "", 10)
    pdf.set_text_color(*LIGHT_GRAY)
    pdf.set_xy(25, 45)
    pdf.cell(0, 6, f"Case File: {datetime.utcnow().strftime('%Y-%m-%d')}", align="L")
    
    pdf.ln(30)
    pdf.set_font(pdf.default_font, "B", 28)
    pdf.set_text_color(*CYAN_GLOW)
    pdf.cell(0, 15, "SUBJECT:", align="C")
    pdf.ln(15)
    
    pdf.set_font(pdf.default_font, "B", 22)
    pdf.set_text_color(*WHITE_TEXT)
    pdf.multi_cell(0, 12, sanitize_text(business_name), align="C")
    pdf.ln(10)
    
    pdf.set_font(pdf.default_font, "", 12)
    pdf.set_text_color(*LIGHT_GRAY)
    pdf.cell(0, 8, "AI Visibility Investigation Report", align="C")
    pdf.ln(25)
    
    stamp_x, stamp_y = 120, 160
    pdf.set_draw_color(*STAMP_RED if not is_detected else SUCCESS_GREEN)
    pdf.set_line_width(3)
    pdf.rect(stamp_x, stamp_y, 60, 25)
    pdf.set_font(pdf.default_font, "B", 16)
    
    if is_detected:
        pdf.set_text_color(*SUCCESS_GREEN)
        pdf.set_xy(stamp_x, stamp_y + 5)
        pdf.cell(60, 15, "DETECTED", align="C")
    else:
        pdf.set_text_color(*STAMP_RED)
        pdf.set_xy(stamp_x, stamp_y + 5)
        pdf.cell(60, 15, "INVISIBLE", align="C")
    
    pdf.set_font(pdf.default_font, "", 9)
    pdf.set_text_color(*MEDIUM_GRAY)
    pdf.set_xy(25, 210)
    pdf.multi_cell(160, 5, "This dossier contains sensitive competitive intelligence. "
                   "Handle with appropriate discretion.", align="C")


def _add_forensic_verdict(pdf: DossierPDF, analysis: Dict[str, Any], is_detected: bool):
    """Add the Forensic Verdict section with dramatic presentation."""
    pdf.add_page()
    
    pdf.set_font(pdf.default_font, "B", 24)
    pdf.set_text_color(*EVIDENCE_RED)
    pdf.cell(0, 15, "SECTION A: THE FORENSIC AUDIT", align="L")
    pdf.ln(12)
    
    pdf.set_font(pdf.default_font, "", 11)
    pdf.set_text_color(*LIGHT_GRAY)
    pdf.multi_cell(0, 6, '"We analyzed how AI assistants respond to queries in your market. '
                   'The evidence reveals your current visibility posture."')
    pdf.ln(10)
    
    pdf.set_font(pdf.default_font, "B", 18)
    pdf.set_text_color(*CYAN_GLOW)
    pdf.cell(0, 10, "THE VERDICT", align="L")
    pdf.ln(12)
    
    verdict_y = pdf.get_y()
    pdf.set_fill_color(40, 40, 50)
    pdf.rect(20, verdict_y, 170, 60, 'F')
    
    if is_detected:
        pdf.set_draw_color(*SUCCESS_GREEN)
        pdf.set_text_color(*SUCCESS_GREEN)
        verdict = "DETECTED"
        subtext = "AI assistants ARE recommending your business"
    else:
        pdf.set_draw_color(*BLOOD_RED)
        pdf.set_text_color(*BLOOD_RED)
        verdict = "INVISIBLE"
        subtext = "AI assistants are NOT recommending your business"
    
    pdf.set_line_width(2)
    pdf.rect(20, verdict_y, 170, 60)
    
    pdf.set_font(pdf.default_font, "B", 36)
    pdf.set_xy(20, verdict_y + 10)
    pdf.cell(170, 20, verdict, align="C")
    
    pdf.set_font(pdf.default_font, "", 12)
    pdf.set_text_color(*WHITE_TEXT)
    pdf.set_xy(20, verdict_y + 35)
    pdf.cell(170, 10, subtext, align="C")
    
    pdf.ln(70)
    
    mentioned = analysis.get("mentioned_count", 0)
    total = analysis.get("total_queries", 10)
    primary = analysis.get("primary_count", 0)
    
    pdf.set_font(pdf.default_font, "B", 12)
    pdf.set_text_color(*CYAN_GLOW)
    pdf.cell(0, 8, "EVIDENCE SUMMARY:", align="L")
    pdf.ln(10)
    
    metrics = [
        (f"{mentioned}/{total}", "Queries with brand mention", CYAN_GLOW if mentioned > 0 else BLOOD_RED),
        (f"{primary}", "Times listed as #1 recommendation", SUCCESS_GREEN if primary > 0 else BLOOD_RED),
        (f"{round((mentioned/total)*100 if total > 0 else 0)}%", "AI Visibility Rate", CYAN_GLOW),
    ]
    
    for value, label, color in metrics:
        pdf.set_fill_color(35, 35, 45)
        box_y = pdf.get_y()
        pdf.rect(25, box_y, 160, 15, 'F')
        
        pdf.set_font(pdf.default_font, "B", 14)
        pdf.set_text_color(*color)
        pdf.set_xy(30, box_y + 3)
        pdf.cell(40, 10, str(value), align="L")
        
        pdf.set_font(pdf.default_font, "", 10)
        pdf.set_text_color(*LIGHT_GRAY)
        pdf.set_xy(75, box_y + 3)
        pdf.cell(100, 10, label, align="L")
        
        pdf.ln(18)


def _add_suspect_lineup(pdf: DossierPDF, analysis: Dict[str, Any]):
    """Add the Suspect Lineup - Top 3 Competitors."""
    pdf.add_page()
    
    pdf.set_font(pdf.default_font, "B", 18)
    pdf.set_text_color(*EVIDENCE_RED)
    pdf.cell(0, 12, "THE SUSPECT LINEUP", align="L")
    pdf.ln(10)
    
    pdf.set_font(pdf.default_font, "", 10)
    pdf.set_text_color(*LIGHT_GRAY)
    pdf.multi_cell(0, 5, "These competitors are dominating the AI recommendations in your market. "
                   "They are the ones being suggested when customers ask AI assistants for help.")
    pdf.ln(10)
    
    results = analysis.get("results", [])
    all_competitors = []
    for r in results:
        all_competitors.extend(r.get("competitors", []))
    
    competitor_freq = Counter(all_competitors)
    top_3 = competitor_freq.most_common(3)
    
    if not top_3:
        pdf.set_font(pdf.default_font, "", 12)
        pdf.set_text_color(*WARNING_YELLOW)
        pdf.cell(0, 10, "No competitor data available.", align="L")
        return
    
    for rank, (competitor, frequency) in enumerate(top_3, 1):
        pdf.set_fill_color(35, 35, 45)
        card_y = pdf.get_y()
        pdf.rect(20, card_y, 170, 45, 'F')
        
        pdf.set_draw_color(*CYAN_GLOW)
        pdf.set_line_width(1)
        pdf.rect(20, card_y, 170, 45)
        
        pdf.set_fill_color(*CYAN_GLOW)
        pdf.rect(20, card_y, 30, 45, 'F')
        pdf.set_font(pdf.default_font, "B", 20)
        pdf.set_text_color(*BLACK_BG)
        pdf.set_xy(20, card_y + 12)
        pdf.cell(30, 20, f"#{rank}", align="C")
        
        pdf.set_font(pdf.default_font, "B", 14)
        pdf.set_text_color(*WHITE_TEXT)
        pdf.set_xy(55, card_y + 8)
        pdf.cell(130, 10, sanitize_text(competitor[:40]), align="L")
        
        pdf.set_font(pdf.default_font, "", 10)
        pdf.set_text_color(*CYAN_GLOW)
        pdf.set_xy(55, card_y + 22)
        pdf.cell(130, 8, f"Mentioned {frequency} times across AI queries", align="L")
        
        threat_level = "HIGH" if frequency >= 5 else ("MEDIUM" if frequency >= 2 else "LOW")
        threat_color = BLOOD_RED if threat_level == "HIGH" else (WARNING_YELLOW if threat_level == "MEDIUM" else LIGHT_GRAY)
        
        pdf.set_font(pdf.default_font, "B", 9)
        pdf.set_text_color(*threat_color)
        pdf.set_xy(55, card_y + 32)
        pdf.cell(50, 6, f"THREAT LEVEL: {threat_level}", align="L")
        
        pdf.ln(50)


def _add_smoking_gun(pdf: DossierPDF, analysis: Dict[str, Any], 
                     sherlock_data: Optional[Dict[str, Any]], 
                     competitor_evidence: Optional[List[Dict[str, Any]]]):
    """Add the Smoking Gun evidence from Pinecone analysis."""
    pdf.add_page()
    
    pdf.set_font(pdf.default_font, "B", 18)
    pdf.set_text_color(*EVIDENCE_RED)
    pdf.cell(0, 12, 'THE "SMOKING GUN"', align="L")
    pdf.ln(10)
    
    pdf.set_font(pdf.default_font, "", 10)
    pdf.set_text_color(*LIGHT_GRAY)
    pdf.multi_cell(0, 5, "This is the critical evidence: specific topics and content your competitors "
                   "are using that you're missing. This is WHY they rank and you don't.")
    pdf.ln(10)
    
    gaps = []
    
    if sherlock_data and isinstance(sherlock_data, dict):
        missions = sherlock_data.get("missions", []) or []
        if isinstance(missions, list):
            for mission in missions[:5]:
                if isinstance(mission, dict):
                    gaps.append({
                        "topic": str(mission.get("title", mission.get("topic", "Unknown"))),
                        "competitor_mentions": str(mission.get("competitor_mentions", "Multiple competitors")),
                        "your_mentions": 0,
                        "severity": str(mission.get("severity", "high"))
                    })
    
    if not gaps and competitor_evidence and isinstance(competitor_evidence, list):
        for ev in competitor_evidence[:5]:
            if isinstance(ev, dict):
                gaps.append({
                    "topic": str(ev.get("topic", "Unknown Topic")),
                    "competitor_mentions": str(ev.get("source", "Competitor")),
                    "your_mentions": 0,
                    "severity": "high"
                })
    
    if not gaps:
        results = analysis.get("results", []) or []
        if isinstance(results, list):
            for r in results:
                if isinstance(r, dict) and r.get("score", 0) == 0:
                    query = str(r.get("query", ""))
                    intent = str(r.get("intent_type", "general"))
                    competitors = r.get("competitors", []) or []
                    if competitors and isinstance(competitors, list):
                        gaps.append({
                            "topic": query[:50] if query else "Query Analysis Gap",
                            "competitor_mentions": str(competitors[0]) if competitors else "Competitors",
                            "your_mentions": 0,
                            "severity": "high" if intent in ["emergency", "high_ticket"] else "medium"
                        })
                    if len(gaps) >= 5:
                        break
    
    if not gaps:
        pdf.set_fill_color(40, 40, 50)
        fallback_y = pdf.get_y()
        pdf.rect(20, fallback_y, 170, 60, 'F')
        
        pdf.set_font(pdf.default_font, "B", 12)
        pdf.set_text_color(*WARNING_YELLOW)
        pdf.set_xy(30, fallback_y + 10)
        pdf.cell(150, 8, "INVESTIGATION IN PROGRESS", align="C")
        
        pdf.set_font(pdf.default_font, "", 10)
        pdf.set_text_color(*LIGHT_GRAY)
        pdf.set_xy(30, fallback_y + 25)
        pdf.multi_cell(150, 5, "Run the Sherlock Semantic Scanner to identify specific content gaps. "
                       "This advanced analysis will reveal exactly what topics competitors cover "
                       "that you're missing - the 'smoking gun' evidence for your visibility gaps.", align="C")
        
        pdf.ln(10)
        pdf.set_font(pdf.default_font, "B", 10)
        pdf.set_text_color(*CYAN_GLOW)
        pdf.cell(0, 8, "Recommended: Run Deep Semantic Scan from Mission Control", align="C")
        return
    
    pdf.set_font(pdf.default_font, "B", 12)
    pdf.set_text_color(*CYAN_GLOW)
    pdf.cell(0, 8, "EVIDENCE LOG:", align="L")
    pdf.ln(10)
    
    for i, gap in enumerate(gaps, 1):
        if pdf.get_y() > 240:
            pdf.add_page()
        
        severity = str(gap.get("severity", "medium")).lower()
        if severity == "high":
            pdf.set_fill_color(50, 30, 30)
        else:
            pdf.set_fill_color(40, 40, 30)
        
        evidence_y = pdf.get_y()
        pdf.rect(20, evidence_y, 170, 30, 'F')
        
        pdf.set_font(pdf.default_font, "B", 10)
        pdf.set_text_color(*BLOOD_RED if severity == "high" else WARNING_YELLOW)
        pdf.set_xy(25, evidence_y + 3)
        topic_text = sanitize_text(str(gap.get("topic", "Unknown"))[:60])
        pdf.cell(160, 6, f"EVIDENCE #{i}: {topic_text}", align="L")
        
        pdf.set_font(pdf.default_font, "", 9)
        pdf.set_text_color(*WHITE_TEXT)
        pdf.set_xy(25, evidence_y + 12)
        competitor_text = sanitize_text(str(gap.get("competitor_mentions", "Competitor"))[:30])
        pdf.cell(160, 5, f"Competitor '{competitor_text}' covers this topic", align="L")
        
        pdf.set_text_color(*BLOOD_RED)
        pdf.set_xy(25, evidence_y + 20)
        your_mentions = gap.get("your_mentions", 0) or 0
        pdf.cell(160, 5, f"You mention this topic: {your_mentions} times", align="L")
        
        pdf.ln(35)


def _add_playbook_intro(pdf: DossierPDF, business_name: str, analysis: Dict[str, Any]):
    """Add the transition to Coach's Playbook."""
    pdf.add_page()
    
    pdf.set_font(pdf.default_font, "B", 24)
    pdf.set_text_color(*SUCCESS_GREEN)
    pdf.cell(0, 15, "SECTION B: THE COACH'S PLAYBOOK", align="L")
    pdf.ln(12)
    
    pdf.set_draw_color(*SUCCESS_GREEN)
    pdf.set_line_width(1)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(10)
    
    pdf.set_font(pdf.default_font, "", 11)
    pdf.set_text_color(*LIGHT_GRAY)
    pdf.multi_cell(0, 6, '"Now that we know the problem, it\'s time to fix it. '
                   'This is your 30-Day Sprint to AI visibility. Follow this playbook and '
                   'you WILL start appearing in AI recommendations."')
    pdf.ln(15)
    
    pdf.set_fill_color(30, 50, 40)
    intro_y = pdf.get_y()
    pdf.rect(20, intro_y, 170, 50, 'F')
    
    pdf.set_font(pdf.default_font, "B", 14)
    pdf.set_text_color(*SUCCESS_GREEN)
    pdf.set_xy(30, intro_y + 8)
    pdf.cell(150, 8, "THE 4-WEEK SPRINT:", align="L")
    
    weeks = [
        ("Week 1:", "Triage & Patching", '"Stop the bleeding"'),
        ("Week 2:", "Content Counter-Attack", '"Close the gaps"'),
        ("Week 3:", "Authority & Signals", '"Build reputation"'),
        ("Week 4:", "The Re-Scan", '"Measure results"'),
    ]
    
    pdf.set_font(pdf.default_font, "", 9)
    for i, (week, title, tagline) in enumerate(weeks):
        pdf.set_xy(35, intro_y + 22 + (i * 7))
        pdf.set_text_color(*CYAN_GLOW)
        pdf.cell(20, 6, week, align="L")
        pdf.set_text_color(*WHITE_TEXT)
        pdf.cell(50, 6, title, align="L")
        pdf.set_text_color(*MEDIUM_GRAY)
        pdf.cell(70, 6, tagline, align="L")
    
    pdf.ln(60)


def _add_week_1_triage(pdf: DossierPDF, analysis: Dict[str, Any], sherlock_data: Optional[Dict[str, Any]], business_id: Optional[int] = None):
    """Add Week 1: Triage & Patching section."""
    pdf.add_page()
    
    _add_week_header(pdf, 1, "TRIAGE & PATCHING", '"Stop the Bleeding" Phase', SUCCESS_GREEN)
    
    pdf.set_font(pdf.default_font, "", 10)
    pdf.set_text_color(*LIGHT_GRAY)
    pdf.multi_cell(0, 5, "Before we attack, we must fix the foundation. Your competitors have "
                   "their technical SEO in order. We need to match that by end of week.")
    pdf.ln(8)
    
    tasks = [
        {
            "task": "Implement JSON-LD Schema markup on homepage and service pages",
            "why": "AI assistants prioritize structured data when forming recommendations",
            "tool": "Schema.json",
            "tool_type": "schema",
            "tool_url": get_fabricator_url(business_id, "schema") if business_id else None
        },
        {
            "task": "Verify and optimize sitemap.xml and robots.txt",
            "why": "Ensures AI crawlers can properly index your content",
            "tool": None,
            "tool_type": None,
            "tool_url": None
        },
        {
            "task": "Add FAQ schema to key service pages",
            "why": "FAQ content is heavily weighted in AI training data",
            "tool": "FAQ_Schema.json",
            "tool_type": "faq",
            "tool_url": get_fabricator_url(business_id, "faq") if business_id else None
        },
        {
            "task": "Optimize meta descriptions with location + service keywords",
            "why": "Meta descriptions directly influence how AI summarizes your business",
            "tool": "Meta_Tags.txt",
            "tool_type": "content",
            "tool_url": get_fabricator_url(business_id, "content") if business_id else None
        }
    ]
    
    for task_data in tasks:
        _add_task_card(pdf, task_data)


def _add_week_2_content_attack(pdf: DossierPDF, analysis: Dict[str, Any], sherlock_data: Optional[Dict[str, Any]], business_id: Optional[int] = None):
    """Add Week 2: Content Counter-Attack section."""
    pdf.add_page()
    
    _add_week_header(pdf, 2, "THE CONTENT COUNTER-ATTACK", '"Gap Closure" Phase', CYAN_GLOW)
    
    pdf.set_font(pdf.default_font, "", 10)
    pdf.set_text_color(*LIGHT_GRAY)
    pdf.multi_cell(0, 5, "The Detective found gaps in your content. Your job this week is to "
                   "launch the missing pages using the templates we've generated.")
    pdf.ln(8)
    
    gap_topics = []
    if sherlock_data and isinstance(sherlock_data, dict):
        missions = sherlock_data.get("missions", []) or []
        if isinstance(missions, list):
            for m in missions[:3]:
                if isinstance(m, dict):
                    gap_topics.append(str(m.get("title", m.get("topic", "Service Page"))))
    
    if not gap_topics:
        gap_topics = ["Emergency Services Page", "Service Area Page", "Industry FAQ Page"]
    
    tasks = []
    for i, topic in enumerate(gap_topics):
        tasks.append({
            "task": f"Create landing page: {sanitize_text(topic)}",
            "why": "This is a topic your competitors cover but you don't",
            "tool": "Landing_Page_Template.html",
            "tool_type": "html",
            "tool_url": get_fabricator_url(business_id, "html") if business_id else None
        })
    
    tasks.append({
        "task": "Interlink all new pages to existing service pages",
        "why": "Internal links help AI understand your content hierarchy",
        "tool": None,
        "tool_type": None,
        "tool_url": None
    })
    
    for task_data in tasks:
        _add_task_card(pdf, task_data)


def _add_week_3_authority(pdf: DossierPDF, analysis: Dict[str, Any], business_id: Optional[int] = None):
    """Add Week 3: Authority & Signals section."""
    pdf.add_page()
    
    _add_week_header(pdf, 3, "AUTHORITY & SIGNALS", '"Reputation" Phase', GOLD)
    
    pdf.set_font(pdf.default_font, "", 10)
    pdf.set_text_color(*LIGHT_GRAY)
    pdf.multi_cell(0, 5, "We need to get you cited. AI assistants weight businesses with "
                   "strong external signals. Submit your business to directories where your "
                   "competitors are listed but you are not.")
    pdf.ln(8)
    
    tasks = [
        {
            "task": "Submit to Google Business Profile (if not already)",
            "why": "Google data directly feeds AI training sets",
            "tool": None,
            "tool_type": None,
            "tool_url": None
        },
        {
            "task": "Submit to industry-specific directories",
            "why": "Vertical directories are heavily weighted for local recommendations",
            "tool": "Directory_List.txt",
            "tool_type": "list",
            "tool_url": get_fabricator_url(business_id, "list") if business_id else None
        },
        {
            "task": "Request reviews from recent customers",
            "why": "Review volume and recency influence AI recommendations",
            "tool": "Review_Request_Template.txt",
            "tool_type": "content",
            "tool_url": get_fabricator_url(business_id, "content") if business_id else None
        },
        {
            "task": "Ensure NAP consistency across all listings",
            "why": "Inconsistent data confuses AI and lowers trust scores",
            "tool": None,
            "tool_type": None,
            "tool_url": None
        }
    ]
    
    for task_data in tasks:
        _add_task_card(pdf, task_data)


def _add_week_4_rescan(pdf: DossierPDF, business_name: str):
    """Add Week 4: The Re-Scan section."""
    pdf.add_page()
    
    _add_week_header(pdf, 4, "THE RE-SCAN", '"Weigh-In" Phase', COACH_BLUE)
    
    pdf.set_font(pdf.default_font, "", 10)
    pdf.set_text_color(*LIGHT_GRAY)
    pdf.multi_cell(0, 5, "We will re-run the Private Eye scan on Day 30 to measure your "
                   "visibility lift. This is your moment of truth.")
    pdf.ln(8)
    
    tasks = [
        {
            "task": "Review and optimize based on 3-week performance",
            "why": "Make adjustments before the final scan",
            "tool": None,
            "tool_type": None
        },
        {
            "task": "Schedule follow-up AI visibility audit",
            "why": "Measure improvement and identify next phase priorities",
            "tool": None,
            "tool_type": None
        },
        {
            "task": "Document all changes made during sprint",
            "why": "Correlate changes with visibility improvements",
            "tool": None,
            "tool_type": None
        }
    ]
    
    for task_data in tasks:
        _add_task_card(pdf, task_data)
    
    pdf.ln(10)
    pdf.set_fill_color(30, 50, 60)
    box_y = pdf.get_y()
    pdf.rect(20, box_y, 170, 40, 'F')
    
    pdf.set_font(pdf.default_font, "B", 12)
    pdf.set_text_color(*COACH_BLUE)
    pdf.set_xy(30, box_y + 8)
    pdf.cell(150, 8, "EXPECTED OUTCOME:", align="L")
    
    pdf.set_font(pdf.default_font, "", 10)
    pdf.set_text_color(*WHITE_TEXT)
    pdf.set_xy(30, box_y + 20)
    pdf.multi_cell(150, 5, "If you complete this 30-day sprint, you should see a "
                   "measurable improvement in AI visibility - typically 20-50% increase "
                   "in brand mentions across AI assistants.")


def _add_week_header(pdf: DossierPDF, week_num: int, title: str, subtitle: str, color: tuple):
    """Add a week header with consistent styling."""
    pdf.set_fill_color(*color)
    pdf.rect(15, pdf.get_y(), 180, 20, 'F')
    
    pdf.set_font(pdf.default_font, "B", 16)
    pdf.set_text_color(*BLACK_BG)
    pdf.set_xy(20, pdf.get_y() + 3)
    pdf.cell(50, 15, f"WEEK {week_num}:", align="L")
    
    pdf.set_font(pdf.default_font, "B", 14)
    pdf.cell(100, 15, title, align="L")
    
    pdf.ln(25)
    
    pdf.set_font(pdf.default_font, "", 11)
    pdf.set_text_color(*LIGHT_GRAY)
    pdf.cell(0, 6, subtitle, align="L")
    pdf.ln(10)


def _add_task_card(pdf: DossierPDF, task_data: Dict[str, Any]):
    """Add a task card with optional tool download link."""
    if pdf.get_y() > 240:
        pdf.add_page()
    
    pdf.set_fill_color(35, 35, 45)
    card_y = pdf.get_y()
    has_tool = task_data.get("tool") and task_data.get("tool_url")
    card_height = 32 if has_tool else 22
    pdf.rect(20, card_y, 170, card_height, 'F')
    
    pdf.set_font(pdf.default_font, "", 10)
    pdf.set_text_color(*WHITE_TEXT)
    pdf.set_xy(25, card_y + 3)
    task_text = sanitize_text(str(task_data.get("task", "Task")))
    pdf.multi_cell(140, 5, task_text)
    
    pdf.set_font(pdf.default_font, "", 8)
    pdf.set_text_color(*CYAN_GLOW)
    pdf.set_xy(25, card_y + 12)
    why_text = sanitize_text(str(task_data.get("why", ""))[:80])
    pdf.cell(140, 5, f"Why: {why_text}", align="L")
    
    if has_tool:
        tool_name = sanitize_text(str(task_data.get("tool", "")))
        tool_url = str(task_data.get("tool_url", ""))
        
        pdf.set_fill_color(30, 60, 45)
        pdf.rect(25, card_y + 20, 160, 10, 'F')
        
        pdf.set_font(pdf.default_font, "B", 8)
        pdf.set_text_color(*SUCCESS_GREEN)
        pdf.set_xy(28, card_y + 22)
        pdf.cell(80, 6, f"DOWNLOAD: {tool_name}", align="L")
        
        if tool_url:
            pdf.set_text_color(*LIGHT_GRAY)
            pdf.set_font(pdf.default_font, "", 7)
            pdf.set_xy(110, card_y + 22)
            pdf.cell(70, 6, f"{tool_url}", align="R")
    
    pdf.set_y(card_y + card_height + 5)


def _add_next_steps(pdf: DossierPDF, business_name: str):
    """Add final call to action page."""
    pdf.add_page()
    
    pdf.set_font(pdf.default_font, "B", 22)
    pdf.set_text_color(*SUCCESS_GREEN)
    pdf.cell(0, 15, "YOUR NEXT MOVE", align="C")
    pdf.ln(20)
    
    pdf.set_font(pdf.default_font, "", 11)
    pdf.set_text_color(*WHITE_TEXT)
    pdf.multi_cell(0, 6, "This dossier has revealed the problem and provided the solution. "
                   "The only question now is: will you take action?", align="C")
    pdf.ln(15)
    
    pdf.set_fill_color(40, 60, 50)
    box_y = pdf.get_y()
    pdf.rect(30, box_y, 150, 80, 'F')
    
    pdf.set_draw_color(*SUCCESS_GREEN)
    pdf.set_line_width(2)
    pdf.rect(30, box_y, 150, 80)
    
    pdf.set_font(pdf.default_font, "B", 14)
    pdf.set_text_color(*SUCCESS_GREEN)
    pdf.set_xy(35, box_y + 10)
    pdf.cell(140, 10, "RECOMMENDED NEXT STEPS:", align="C")
    
    steps = [
        "1. Download your fix tools from Mission Control",
        "2. Implement Week 1 tasks immediately",
        "3. Schedule your Day 30 re-scan",
        "4. Consider EkkoBrain monitoring for ongoing visibility"
    ]
    
    pdf.set_font(pdf.default_font, "", 10)
    pdf.set_text_color(*WHITE_TEXT)
    for i, step in enumerate(steps):
        pdf.set_xy(40, box_y + 28 + (i * 12))
        pdf.cell(130, 8, step, align="L")
    
    pdf.ln(100)
    pdf.set_font(pdf.default_font, "", 9)
    pdf.set_text_color(*MEDIUM_GRAY)
    pdf.cell(0, 8, "Generated by EkkoScope GEO Engine | Powered by Sherlock Intelligence", align="C")
