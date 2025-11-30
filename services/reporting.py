"""
PDF Report Generation for EkkoScope GEO Visibility Analysis v2.0
Black-Ops Edition - Premium AI Visibility Intelligence Reports
Features: Pure black design, cyan accents, blood-red alerts, JetBrains Mono typography
"""

from datetime import datetime
from typing import Dict, Any, List, Optional
from fpdf import FPDF
from collections import Counter
import os
from services.genius import generate_executive_summary

BLACK_BG = (10, 10, 15)
CYAN_GLOW = (0, 240, 255)
BLOOD_RED = (255, 0, 0)
WHITE_TEXT = (255, 255, 255)
DARK_GRAY = (40, 40, 50)
MEDIUM_GRAY = (100, 100, 110)
LIGHT_GRAY = (150, 150, 160)
SUCCESS_GREEN = (0, 255, 128)
WARNING_YELLOW = (255, 200, 0)
PURPLE = (180, 100, 255)

BRAND_TEAL = CYAN_GLOW
BRAND_BLUE = CYAN_GLOW
DARK_TEXT = WHITE_TEXT
MEDIUM_TEXT = LIGHT_GRAY
LIGHT_TEXT = MEDIUM_GRAY
ACCENT_BG = (20, 20, 30)
WHITE = WHITE_TEXT
ERROR_RED = BLOOD_RED
PINK = (255, 100, 180)
SLATE_GRAY = (80, 80, 90)


def sanitize_text(text: str) -> str:
    """
    Replace Unicode characters not supported by fonts with ASCII equivalents.
    This prevents PDF generation errors for special characters.
    """
    if not text:
        return ""
    
    replacements = {
        '"': '"',
        '"': '"',
        ''': "'",
        ''': "'",
        '–': '-',
        '—': '-',
        '…': '...',
        '•': '*',
        '·': '*',
        '×': 'x',
        '→': '->',
        '←': '<-',
        '↔': '<->',
        '≤': '<=',
        '≥': '>=',
        '≠': '!=',
        '±': '+/-',
        '°': ' deg',
        '™': '(TM)',
        '®': '(R)',
        '©': '(C)',
        '\u00A0': ' ',
        '\u2002': ' ',
        '\u2003': ' ',
        '\u2009': ' ',
        '\u200b': '',
        '\u200c': '',
        '\u200d': '',
        '\ufeff': '',
    }
    
    for unicode_char, ascii_char in replacements.items():
        text = text.replace(unicode_char, ascii_char)
    
    result = []
    for char in text:
        if ord(char) < 128:
            result.append(char)
        else:
            result.append('?')
    
    return ''.join(result)


class EkkoScopePDF(FPDF):
    """Custom PDF class with EkkoScope black-ops branding."""
    
    def __init__(self, tenant_name: str, business_type: str = ""):
        super().__init__()
        self.tenant_name = tenant_name
        self.business_type = business_type
        self.set_margins(left=15, top=18, right=15)
        self.set_auto_page_break(auto=True, margin=25)
        self.is_upsell_page = False
        
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
        if self.page_no() > 1 and not self.is_upsell_page:
            self._draw_header_logo()
            self.set_font(self.default_font, "", 9)
            self.set_text_color(*LIGHT_GRAY)
            self.set_xy(45, 10)
            self.cell(0, 10, f"AI Visibility Report - {self.tenant_name}", align="L")
            
            self.set_draw_color(*CYAN_GLOW)
            self.set_line_width(0.5)
            self.line(10, 22, 200, 22)
            self.ln(20)
    
    def _draw_header_logo(self):
        """Draw cyan radar logo for PDF header."""
        cx, cy = 25, 15
        
        self.set_draw_color(*CYAN_GLOW)
        self.set_line_width(0.4)
        self.ellipse(cx-10, cy-10, 20, 20)
        self.ellipse(cx-6, cy-6, 12, 12)
        
        self.set_fill_color(*CYAN_GLOW)
        self.ellipse(cx-2, cy-2, 4, 4, style="F")
    
    def footer(self):
        if self.is_upsell_page:
            return
            
        self.set_y(-20)
        
        self.set_draw_color(*CYAN_GLOW)
        self.set_line_width(0.3)
        self.line(10, self.get_y(), 200, self.get_y())
        
        self.set_font(self.default_font, "", 8)
        self.set_text_color(*MEDIUM_GRAY)
        self.set_y(-15)
        self.cell(95, 10, "Powered by EkkoScope GEO Engine | AI Visibility Intelligence", align="L")
        self.cell(95, 10, f"Page {self.page_no()} of {{nb}}", align="R")
    
    def section_header(self, title: str, subtitle: str = ""):
        """Add a consistent section header with cyan glow."""
        self.set_font(self.default_font, "B", 20)
        self.set_text_color(*CYAN_GLOW)
        self.cell(0, 12, title, align="L")
        self.ln(8)
        
        if subtitle:
            self.set_font(self.default_font, "", 10)
            self.set_text_color(*LIGHT_GRAY)
            self.multi_cell(0, 5, subtitle)
            self.ln(5)
    
    def subsection_header(self, title: str, color: Optional[tuple] = None):
        """Add a subsection header."""
        if color is None:
            color = CYAN_GLOW
        self.set_font(self.default_font, "B", 14)
        self.set_text_color(*color)
        self.cell(0, 10, title, align="L")
        self.ln(8)
    
    def bullet_point(self, text: str, indent: int = 12):
        """Add a properly formatted bullet point."""
        self.set_font(self.default_font, "", 10)
        self.set_text_color(*CYAN_GLOW)
        self.set_x(indent)
        self.cell(5, 5, ">", align="L")
        self.set_text_color(*WHITE_TEXT)
        self.multi_cell(175, 5, text)
        self.ln(2)
    
    def numbered_item(self, number: int, text: str, indent: int = 12):
        """Add a properly formatted numbered item."""
        self.set_font(self.default_font, "B", 10)
        self.set_text_color(*CYAN_GLOW)
        self.set_x(indent)
        self.cell(8, 5, f"{number}.", align="L")
        self.set_font(self.default_font, "", 10)
        self.set_text_color(*WHITE_TEXT)
        self.multi_cell(170, 5, text)
        self.ln(2)


def _serialize_multi_llm_visibility(multi_llm: Any) -> Optional[Dict[str, Any]]:
    """
    Convert multi-LLM visibility data to a plain dict, handling Pydantic models.
    Uses JSON-compatible mode to ensure all Enums/complex types are serialized as primitives.
    Returns None if data is missing or invalid.
    """
    if multi_llm is None:
        return None
    
    def to_json_dict(obj):
        """Convert object to JSON-serializable dict with Enums as strings."""
        if obj is None:
            return None
        if hasattr(obj, "model_dump"):
            try:
                return obj.model_dump(mode="json")
            except TypeError:
                return obj.model_dump()
        if hasattr(obj, "dict"):
            d = obj.dict()
            return _convert_enums(d)
        if isinstance(obj, dict):
            return _convert_enums(dict(obj))
        return obj
    
    def _convert_enums(d):
        """Recursively convert Enum values to their string representations."""
        if isinstance(d, dict):
            return {k: _convert_enums(v) for k, v in d.items()}
        if isinstance(d, list):
            return [_convert_enums(item) for item in d]
        if hasattr(d, "value"):
            return d.value
        if hasattr(d, "name") and not callable(d.name):
            return str(d.name)
        return d
    
    try:
        result = to_json_dict(multi_llm)
        if result and isinstance(result, dict):
            if "queries" in result and result["queries"]:
                result["queries"] = [
                    to_json_dict(q) if not isinstance(q, dict) else _convert_enums(q)
                    for q in result["queries"] if q is not None
                ]
            return result
    except Exception:
        pass
    
    return None


def normalize_analysis_data(analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize analysis data to ensure all required fields exist."""
    results = analysis.get("results", [])
    total_queries = analysis.get("total_queries", len(results))
    
    score_counts = {0: 0, 1: 0, 2: 0}
    intent_counts = {"emergency": 0, "high_ticket": 0, "replenishment": 0, "informational": 0, "transactional": 0}
    all_competitors = []
    
    for result in results:
        score = result.get("score", 0)
        score_counts[score] = score_counts.get(score, 0) + 1
        all_competitors.extend(result.get("competitors", []))
        
        intent = result.get("intent_type", "informational")
        if intent in intent_counts:
            intent_counts[intent] += 1
    
    competitor_freq = Counter(all_competitors)
    top_competitors = [
        {"name": name, "frequency": count}
        for name, count in competitor_freq.most_common(10)
    ]
    
    suggestions = analysis.get("suggestions", [])
    grouped_recommendations = {}
    for suggestion in suggestions:
        rec_type = suggestion.get("type", "other")
        if rec_type not in grouped_recommendations:
            grouped_recommendations[rec_type] = []
        grouped_recommendations[rec_type].append(suggestion)
    
    multi_llm_normalized = _serialize_multi_llm_visibility(analysis.get("multi_llm_visibility"))
    
    return {
        "tenant_name": analysis.get("tenant_name", "Unknown"),
        "generated_at": analysis.get("run_at", datetime.utcnow().isoformat() + "Z"),
        "total_queries": total_queries,
        "average_score": analysis.get("avg_score", 0),
        "score_counts": score_counts,
        "intent_counts": intent_counts,
        "mentioned_count": analysis.get("mentioned_count", 0),
        "primary_count": analysis.get("primary_count", 0),
        "queries": results,
        "top_competitors": top_competitors,
        "recommendations": grouped_recommendations,
        "visibility_summary": analysis.get("visibility_summary", ""),
        "genius_insights": analysis.get("genius_insights", None),
        "perplexity_visibility": analysis.get("perplexity_visibility", None),
        "multi_llm_visibility": multi_llm_normalized,
        "site_snapshot": analysis.get("site_snapshot", None)
    }


def build_ekkoscope_pdf(tenant: Dict[str, Any], analysis: Dict[str, Any]) -> bytes:
    """Generate a premium black-ops PDF report from tenant config and analysis results."""
    data = normalize_analysis_data(analysis)
    tenant_name = data["tenant_name"]
    business_type = tenant.get("business_type", "")
    
    pdf = EkkoScopePDF(tenant_name, business_type)
    pdf.alias_nb_pages()
    
    _add_cover_page(pdf, data, tenant)
    _add_executive_dashboard(pdf, data, analysis)
    _add_query_analysis_section(pdf, data, tenant)
    _add_competitor_matrix(pdf, data)
    _add_multi_source_visibility(pdf, data)
    _add_genius_insights_section(pdf, data)
    _add_page_blueprints_section(pdf, data, tenant)
    _add_30_day_action_plan(pdf, data, tenant)
    _add_recommendations_section(pdf, data)
    _add_upsell_page(pdf, data)
    
    return pdf.output()


def _draw_cover_logo(pdf: EkkoScopePDF):
    """Draw a compact, professional cyan radar logo."""
    cx, cy = 105, 40
    
    pdf.set_draw_color(*CYAN_GLOW)
    pdf.set_line_width(0.8)
    pdf.ellipse(cx-12, cy-12, 24, 24)
    
    pdf.set_line_width(0.5)
    pdf.ellipse(cx-8, cy-8, 16, 16)
    
    pdf.set_line_width(0.3)
    pdf.ellipse(cx-4, cy-4, 8, 8)
    
    pdf.set_fill_color(*CYAN_GLOW)
    pdf.ellipse(cx-1.5, cy-1.5, 3, 3, style="F")
    
    pdf.set_draw_color(*CYAN_GLOW)
    pdf.set_line_width(1.0)
    pdf.line(cx+6, cy-3, cx+6, cy+3)
    pdf.set_line_width(0.7)
    pdf.line(cx+10, cy-5, cx+10, cy+5)
    pdf.set_line_width(0.5)
    pdf.line(cx+14, cy-7, cx+14, cy+7)


def _add_cover_page(pdf: EkkoScopePDF, data: Dict[str, Any], tenant: Dict[str, Any]):
    """Add professional cover page with black-ops branding."""
    pdf.add_page()
    
    _draw_cover_logo(pdf)
    
    pdf.ln(35)
    
    pdf.set_font(pdf.default_font, "B", 32)
    pdf.set_text_color(*CYAN_GLOW)
    pdf.cell(0, 15, "EkkoScope", align="C")
    pdf.ln(12)
    
    pdf.set_font(pdf.default_font, "", 14)
    pdf.set_text_color(*LIGHT_GRAY)
    pdf.cell(0, 8, "GEO Engine for AI Visibility", align="C")
    pdf.ln(25)
    
    pdf.set_draw_color(*CYAN_GLOW)
    pdf.set_line_width(1.5)
    pdf.line(50, pdf.get_y(), 160, pdf.get_y())
    pdf.ln(20)
    
    pdf.set_font(pdf.default_font, "B", 26)
    pdf.set_text_color(*WHITE_TEXT)
    pdf.multi_cell(0, 11, data["tenant_name"], align="C")
    pdf.ln(10)
    
    pdf.set_font(pdf.default_font, "", 16)
    pdf.set_text_color(*CYAN_GLOW)
    pdf.cell(0, 8, "AI Visibility Analysis Report", align="C")
    pdf.ln(10)
    
    pdf.set_font(pdf.default_font, "", 11)
    pdf.set_text_color(*LIGHT_GRAY)
    pdf.cell(0, 6, "Comprehensive GEO analysis of how AI assistants recommend your business", align="C")
    pdf.ln(30)
    
    generated_at = data["generated_at"]
    try:
        dt = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
        formatted_date = dt.strftime("%B %d, %Y")
    except:
        formatted_date = generated_at
    
    pdf.set_font(pdf.default_font, "", 11)
    pdf.set_text_color(*LIGHT_GRAY)
    pdf.cell(0, 8, f"Report Date: {formatted_date}", align="C")
    pdf.ln(6)
    
    geo_focus = tenant.get("geo_focus", [])
    if geo_focus:
        pdf.set_font(pdf.default_font, "", 10)
        pdf.set_text_color(*MEDIUM_GRAY)
        pdf.cell(0, 6, f"Market Focus: {', '.join(geo_focus[:3])}", align="C")
    
    pdf.set_y(260)
    pdf.set_draw_color(*MEDIUM_GRAY)
    pdf.set_line_width(0.3)
    pdf.line(40, 260, 170, 260)
    pdf.ln(5)
    pdf.set_font(pdf.default_font, "", 8)
    pdf.set_text_color(*MEDIUM_GRAY)
    pdf.cell(0, 5, "Powered by EkkoScope GEO Engine | AI Visibility Intelligence", align="C")


def _add_executive_dashboard(pdf: EkkoScopePDF, data: Dict[str, Any], analysis: Dict[str, Any]):
    """Add executive dashboard with key metrics - blood red for 0% visibility."""
    pdf.add_page()
    
    pdf.section_header("Executive Dashboard", "Key metrics and insights from your AI visibility analysis")
    pdf.ln(5)
    
    score_counts = data["score_counts"]
    total = data["total_queries"]
    avg = data["average_score"]
    mentioned = data.get("mentioned_count", 0)
    primary = data.get("primary_count", 0)
    
    visibility_pct = (mentioned/max(total,1)*100) if total > 0 else 0
    
    card_y = pdf.get_y()
    card_height = 38
    card_width = 44
    gap = 4
    
    if visibility_pct == 0:
        vis_color = BLOOD_RED
    elif visibility_pct < 30:
        vis_color = WARNING_YELLOW
    else:
        vis_color = SUCCESS_GREEN
    
    if avg == 0:
        avg_color = BLOOD_RED
    elif avg < 1:
        avg_color = WARNING_YELLOW
    else:
        avg_color = CYAN_GLOW
    
    metrics = [
        ("Queries", str(total), CYAN_GLOW, "Analyzed"),
        ("Visibility", f"{visibility_pct:.0f}%", vis_color, "Mentioned"),
        ("Primary", str(primary), SUCCESS_GREEN if primary > 0 else BLOOD_RED, "Top Pick"),
        ("Avg Score", f"{avg:.1f}/2", avg_color, "Score"),
    ]
    
    for i, (label, value, color, sublabel) in enumerate(metrics):
        x = 10 + (card_width + gap) * i
        
        pdf.set_fill_color(*DARK_GRAY)
        pdf.set_draw_color(*color)
        pdf.set_line_width(1.2)
        pdf.rect(x, card_y, card_width, card_height, style="FD")
        
        pdf.set_xy(x, card_y + 4)
        pdf.set_font(pdf.default_font, "", 8)
        pdf.set_text_color(*LIGHT_GRAY)
        pdf.cell(card_width, 5, label, align="C")
        
        pdf.set_xy(x, card_y + 12)
        pdf.set_font(pdf.default_font, "B", 22)
        pdf.set_text_color(*color)
        pdf.cell(card_width, 12, value, align="C")
        
        pdf.set_xy(x, card_y + 28)
        pdf.set_font(pdf.default_font, "", 7)
        pdf.set_text_color(*LIGHT_GRAY)
        pdf.cell(card_width, 5, sublabel, align="C")
    
    pdf.set_y(card_y + card_height + 15)
    
    pdf.subsection_header("AI Visibility Distribution")
    
    bar_y = pdf.get_y()
    bar_height = 18
    full_width = 180
    
    not_found_pct = (score_counts.get(0, 0) / max(total, 1)) * 100 if total > 0 else 100
    mentioned_pct = (score_counts.get(1, 0) / max(total, 1)) * 100 if total > 0 else 0
    primary_pct = (score_counts.get(2, 0) / max(total, 1)) * 100 if total > 0 else 0
    
    pdf.set_font(pdf.default_font, "B", 10)
    pdf.set_text_color(*BLOOD_RED)
    pdf.cell(0, 6, f"NOT FOUND: {not_found_pct:.0f}% of queries", align="L")
    pdf.ln(8)
    
    pdf.set_fill_color(*BLOOD_RED)
    bar_width = (not_found_pct / 100) * full_width
    if bar_width < 2:
        bar_width = 2
    pdf.rect(15, pdf.get_y(), bar_width, bar_height, style="F")
    
    pdf.set_fill_color(*DARK_GRAY)
    pdf.rect(15 + bar_width, pdf.get_y(), full_width - bar_width, bar_height, style="F")
    
    pdf.set_xy(15, pdf.get_y() + 3)
    pdf.set_font(pdf.default_font, "B", 14)
    pdf.set_text_color(*WHITE_TEXT)
    if not_found_pct >= 50:
        pdf.cell(bar_width, bar_height - 6, f"{not_found_pct:.0f}%", align="C")
    
    pdf.ln(bar_height + 10)
    
    score_labels = [
        ("Mentioned (Score 1)", score_counts.get(1, 0), mentioned_pct, WARNING_YELLOW),
        ("Primary Recommendation (Score 2)", score_counts.get(2, 0), primary_pct, SUCCESS_GREEN),
    ]
    
    for label, count, pct, color in score_labels:
        pdf.set_font(pdf.default_font, "", 9)
        pdf.set_text_color(*LIGHT_GRAY)
        pdf.cell(100, 6, label, align="L")
        pdf.set_text_color(*color)
        pdf.set_font(pdf.default_font, "B", 9)
        pdf.cell(30, 6, f"{count} ({pct:.0f}%)", align="R")
        pdf.ln(8)
    
    pdf.ln(10)
    
    pdf.subsection_header("Executive Summary")
    
    genius = data.get("genius_insights")
    try:
        bullets = generate_executive_summary(genius, analysis)
    except Exception:
        bullets = ["AI visibility analysis indicates significant optimization opportunities."]
    
    if not bullets:
        bullets = ["AI visibility analysis indicates significant optimization opportunities."]
    
    for bullet in bullets[:6]:
        if pdf.get_y() > 250:
            pdf.add_page()
        pdf.bullet_point(str(bullet))
    
    if data.get("visibility_summary"):
        if pdf.get_y() > 240:
            pdf.add_page()
        pdf.ln(5)
        pdf.set_font(pdf.default_font, "B", 10)
        pdf.set_text_color(*CYAN_GLOW)
        pdf.cell(0, 6, "Analysis Summary", align="L")
        pdf.ln(6)
        
        pdf.set_font(pdf.default_font, "", 9)
        pdf.set_text_color(*LIGHT_GRAY)
        pdf.set_x(10)
        pdf.multi_cell(190, 4, data["visibility_summary"])


def _add_query_analysis_section(pdf: EkkoScopePDF, data: Dict[str, Any], tenant: Dict[str, Any]):
    """Add detailed query analysis with blood-red NOT FOUND indicators."""
    pdf.add_page()
    
    pdf.section_header(
        "Query Analysis Details",
        "Comprehensive breakdown of AI visibility across all tested queries"
    )
    pdf.ln(5)
    
    multi_llm = data.get("multi_llm_visibility")
    multi_llm_queries = {}
    
    if multi_llm and isinstance(multi_llm, dict):
        for q in multi_llm.get("queries", []) or []:
            if q and isinstance(q, dict) and q.get("query"):
                multi_llm_queries[q["query"]] = q
    
    for query_data in data["queries"]:
        if pdf.get_y() > 240:
            pdf.add_page()
        
        query = sanitize_text(query_data.get("query", ""))
        score = query_data.get("score", 0)
        intent = query_data.get("intent_type", "informational")
        competitors = [sanitize_text(c) for c in query_data.get("competitors", [])]
        ai_response = sanitize_text(query_data.get("response", ""))
        
        llm_query = multi_llm_queries.get(query_data.get("query", ""), {})
        providers_data = llm_query.get("providers", [])
        found_by_any = any(p.get("target_found", False) for p in providers_data) if providers_data else False
        found_as_primary = any(p.get("is_primary", False) for p in providers_data) if providers_data else False
        
        if found_as_primary or score == 2:
            score_color = SUCCESS_GREEN
            score_label = "PRIMARY"
            border_color = SUCCESS_GREEN
        elif found_by_any:
            score_color = WARNING_YELLOW
            score_label = "FOUND"
            border_color = WARNING_YELLOW
        elif score == 1:
            score_color = WARNING_YELLOW
            score_label = "MENTIONED"
            border_color = WARNING_YELLOW
        else:
            score_color = BLOOD_RED
            score_label = "NOT FOUND"
            border_color = BLOOD_RED
        
        start_y = pdf.get_y()
        
        pdf.set_draw_color(*border_color)
        pdf.set_line_width(2.0)
        pdf.line(12, start_y, 12, start_y + 5)
        
        pdf.set_font(pdf.default_font, "B", 9)
        pdf.set_text_color(*score_color)
        pdf.set_xy(160, start_y)
        pdf.cell(40, 5, score_label, align="R")
        
        pdf.set_xy(18, start_y)
        pdf.set_font(pdf.default_font, "B", 10)
        pdf.set_text_color(*WHITE_TEXT)
        pdf.multi_cell(138, 5, query)
        
        end_y = pdf.get_y()
        
        if end_y > start_y + 6:
            pdf.set_draw_color(*border_color)
            pdf.set_line_width(2.0)
            pdf.line(12, start_y, 12, end_y - 2)
        
        pdf.set_font(pdf.default_font, "", 8)
        pdf.set_text_color(*PURPLE)
        pdf.set_x(18)
        pdf.cell(0, 4, f"Intent: {intent.replace('_', ' ').title()}", align="L")
        pdf.ln(4)
        
        if competitors:
            pdf.set_text_color(*LIGHT_GRAY)
            pdf.set_x(18)
            comp_str = "Competitors: " + ", ".join(competitors)
            pdf.multi_cell(177, 4, comp_str)
        pdf.ln(3)
        
        if ai_response:
            pdf.set_font(pdf.default_font, "", 8)
            pdf.set_text_color(*MEDIUM_GRAY)
            pdf.set_fill_color(*DARK_GRAY)
            pdf.set_x(18)
            pdf.multi_cell(178, 4, ai_response, fill=True)
        
        pdf.ln(8)
    
    pdf.ln(5)
    total = data["total_queries"]
    pdf.set_font(pdf.default_font, "", 9)
    pdf.set_text_color(*MEDIUM_GRAY)
    pdf.cell(0, 5, f"Total: {total} queries analyzed across multiple intent categories", align="L")


def _add_competitor_matrix(pdf: EkkoScopePDF, data: Dict[str, Any]):
    """Add competitor analysis with stark white names."""
    top_competitors = data.get("top_competitors", [])
    
    if not top_competitors:
        return
    
    if pdf.get_y() > 180:
        pdf.add_page()
    else:
        pdf.ln(15)
    
    pdf.section_header(
        "Competitor Landscape",
        "Analysis of competitors appearing in AI recommendations across your queries"
    )
    pdf.ln(5)
    
    total_queries = data["total_queries"]
    
    for idx, comp in enumerate(top_competitors[:10]):
        if pdf.get_y() > 240:
            pdf.add_page()
        
        name = sanitize_text(comp.get("name", ""))
        freq = comp.get("frequency", 0)
        share = (freq / max(total_queries, 1)) * 100
        
        if share > 75:
            threat = "Critical"
            threat_color = BLOOD_RED
        elif share > 50:
            threat = "High"
            threat_color = WARNING_YELLOW
        elif share > 25:
            threat = "Medium"
            threat_color = CYAN_GLOW
        else:
            threat = "Low"
            threat_color = SUCCESS_GREEN
        
        pdf.set_fill_color(*threat_color)
        pdf.set_text_color(*BLACK_BG)
        pdf.set_font(pdf.default_font, "B", 9)
        pdf.cell(8, 7, f"{idx + 1}", border=0, align="C", fill=True)
        pdf.cell(2, 7, "", border=0)
        
        pdf.set_text_color(*WHITE_TEXT)
        if idx == 0:
            pdf.set_font(pdf.default_font, "B", 11)
        else:
            pdf.set_font(pdf.default_font, "B", 10)
        pdf.multi_cell(0, 5, name)
        
        pdf.set_x(15)
        pdf.set_font(pdf.default_font, "", 8)
        pdf.set_text_color(*LIGHT_GRAY)
        pdf.cell(45, 5, f"Appearances: {freq} of {total_queries}", align="L")
        pdf.cell(40, 5, f"Share of Voice: {share:.1f}%", align="L")
        
        pdf.set_text_color(*threat_color)
        pdf.set_font(pdf.default_font, "B", 8)
        pdf.cell(40, 5, f"Threat: {threat}", align="L")
        pdf.ln(8)


def _add_multi_source_visibility(pdf: EkkoScopePDF, data: Dict[str, Any]):
    """Add multi-source visibility comparison section."""
    multi_llm = data.get("multi_llm_visibility")
    if not multi_llm or not isinstance(multi_llm, dict):
        return
    
    pdf.add_page()
    
    pdf.section_header(
        "Multi-AI Visibility Analysis",
        "Visibility comparison across major AI assistants: ChatGPT, Gemini, and Perplexity"
    )
    pdf.ln(5)
    
    summary = multi_llm.get("summary", {})
    if summary:
        overall_found = summary.get("overall_found_rate", 0)
        overall_primary = summary.get("overall_primary_rate", 0)
        
        pdf.set_font(pdf.default_font, "B", 12)
        pdf.set_text_color(*CYAN_GLOW)
        pdf.cell(0, 8, "Cross-Platform Summary", align="L")
        pdf.ln(8)
        
        pdf.set_font(pdf.default_font, "", 10)
        found_color = BLOOD_RED if overall_found == 0 else (WARNING_YELLOW if overall_found < 30 else SUCCESS_GREEN)
        pdf.set_text_color(*found_color)
        pdf.cell(0, 6, f"Overall Found Rate: {overall_found:.1f}%", align="L")
        pdf.ln(6)
        
        primary_color = BLOOD_RED if overall_primary == 0 else (WARNING_YELLOW if overall_primary < 20 else SUCCESS_GREEN)
        pdf.set_text_color(*primary_color)
        pdf.cell(0, 6, f"Overall Primary Rate: {overall_primary:.1f}%", align="L")
        pdf.ln(10)
        
        by_provider = summary.get("by_provider", {})
        if by_provider:
            pdf.set_font(pdf.default_font, "B", 11)
            pdf.set_text_color(*CYAN_GLOW)
            pdf.cell(0, 8, "Visibility by AI Provider", align="L")
            pdf.ln(8)
            
            for provider_name, provider_data in by_provider.items():
                if not isinstance(provider_data, dict):
                    continue
                
                found_rate = provider_data.get("found_rate", 0)
                primary_rate = provider_data.get("primary_rate", 0)
                
                display_name = provider_name.replace("_", " ").title()
                if "openai" in provider_name.lower():
                    display_name = "ChatGPT (OpenAI)"
                elif "gemini" in provider_name.lower():
                    display_name = "Gemini (Google)"
                elif "perplexity" in provider_name.lower():
                    display_name = "Perplexity"
                
                pdf.set_font(pdf.default_font, "B", 10)
                pdf.set_text_color(*WHITE_TEXT)
                pdf.cell(60, 6, display_name, align="L")
                
                found_col = BLOOD_RED if found_rate == 0 else (WARNING_YELLOW if found_rate < 30 else SUCCESS_GREEN)
                pdf.set_text_color(*found_col)
                pdf.cell(40, 6, f"Found: {found_rate:.0f}%", align="L")
                
                primary_col = BLOOD_RED if primary_rate == 0 else (WARNING_YELLOW if primary_rate < 20 else SUCCESS_GREEN)
                pdf.set_text_color(*primary_col)
                pdf.cell(40, 6, f"Primary: {primary_rate:.0f}%", align="L")
                pdf.ln(8)
    
    queries = multi_llm.get("queries", [])
    if queries:
        pdf.ln(5)
        pdf.set_font(pdf.default_font, "B", 11)
        pdf.set_text_color(*CYAN_GLOW)
        pdf.cell(0, 8, "Query-Level Breakdown", align="L")
        pdf.ln(8)
        
        for q in queries[:10]:
            if not isinstance(q, dict):
                continue
            
            if pdf.get_y() > 240:
                pdf.add_page()
            
            query_text = sanitize_text(q.get("query", ""))
            providers = q.get("providers", [])
            
            any_found = any(p.get("target_found", False) for p in providers if isinstance(p, dict))
            any_primary = any(p.get("is_primary", False) for p in providers if isinstance(p, dict))
            
            if any_primary:
                status_color = SUCCESS_GREEN
                status = "PRIMARY"
            elif any_found:
                status_color = WARNING_YELLOW
                status = "FOUND"
            else:
                status_color = BLOOD_RED
                status = "NOT FOUND"
            
            pdf.set_font(pdf.default_font, "B", 9)
            pdf.set_text_color(*status_color)
            pdf.cell(25, 5, status, align="L")
            
            pdf.set_text_color(*WHITE_TEXT)
            pdf.set_font(pdf.default_font, "", 9)
            pdf.multi_cell(165, 5, query_text)
            pdf.ln(3)


def _add_genius_insights_section(pdf: EkkoScopePDF, data: Dict[str, Any]):
    """Add Genius Mode insights with enhanced styling."""
    genius = data.get("genius_insights")
    if not genius:
        return
    
    patterns = genius.get("patterns", []) or []
    opportunities = genius.get("priority_opportunities", []) or []
    quick_wins = genius.get("quick_wins", []) or []
    future_answers = genius.get("future_answers", []) or []
    
    if not any([patterns, opportunities, quick_wins, future_answers]):
        return
    
    pdf.add_page()
    
    pdf.section_header(
        "Genius Mode Insights",
        "AI-powered analysis of your visibility patterns and strategic opportunities"
    )
    pdf.ln(5)
    
    analysis_notes = []
    if genius.get("site_aware"):
        analysis_notes.append("site-aware analysis")
    if genius.get("multi_llm_used"):
        analysis_notes.append("multi-LLM visibility comparison")
    
    if analysis_notes:
        pdf.set_font(pdf.default_font, "", 9)
        pdf.set_text_color(*MEDIUM_GRAY)
        notes_text = ", ".join(analysis_notes)
        pdf.cell(0, 5, f"Analysis includes: {notes_text}", align="L")
        pdf.ln(8)
    
    if patterns:
        pdf.subsection_header("Patterns in AI Visibility", CYAN_GLOW)
        
        for idx, pattern in enumerate(patterns, 1):
            if pdf.get_y() > 220:
                pdf.add_page()
            
            if isinstance(pattern, dict):
                summary = sanitize_text(pattern.get("summary", ""))
                evidence = pattern.get("evidence", [])
                implication = sanitize_text(pattern.get("implication", ""))
                
                pdf.set_font(pdf.default_font, "B", 10)
                pdf.set_text_color(*WHITE_TEXT)
                pdf.set_x(10)
                pdf.multi_cell(190, 5, f"{idx}. {summary}")
                pdf.ln(2)
                
                if evidence and isinstance(evidence, list):
                    pdf.set_font(pdf.default_font, "", 9)
                    pdf.set_text_color(*LIGHT_GRAY)
                    for ev in evidence:
                        if pdf.get_y() > 260:
                            pdf.add_page()
                        pdf.set_x(15)
                        pdf.multi_cell(175, 4, f"  > {sanitize_text(str(ev))}")
                
                if implication:
                    if pdf.get_y() > 260:
                        pdf.add_page()
                    pdf.set_font(pdf.default_font, "", 9)
                    pdf.set_text_color(*PURPLE)
                    pdf.set_x(15)
                    pdf.multi_cell(175, 4, f"Impact: {implication}")
            else:
                pdf.set_font(pdf.default_font, "", 10)
                pdf.set_text_color(*WHITE_TEXT)
                pdf.set_x(10)
                pdf.multi_cell(190, 5, f"{idx}. {sanitize_text(str(pattern))}")
            
            pdf.ln(5)
    
    if opportunities:
        if pdf.get_y() > 180:
            pdf.add_page()
        
        pdf.subsection_header("Priority Opportunities", SUCCESS_GREEN)
        
        for idx, opp in enumerate(opportunities, 1):
            if pdf.get_y() > 200:
                pdf.add_page()
            
            if not isinstance(opp, dict):
                continue
            
            query = sanitize_text(opp.get("query", ""))
            impact = opp.get("impact_score", opp.get("intent_value", 5))
            effort = opp.get("effort", "medium")
            intent_type = opp.get("intent_type", "")
            money_reason = sanitize_text(opp.get("money_reason", opp.get("reason", "")))
            
            pdf.set_font(pdf.default_font, "B", 10)
            pdf.set_text_color(*SUCCESS_GREEN)
            pdf.set_x(12)
            pdf.multi_cell(185, 5, f"{idx}. {query}")
            pdf.ln(2)
            
            pdf.set_font(pdf.default_font, "B", 9)
            pdf.set_text_color(*CYAN_GLOW)
            pdf.set_x(15)
            effort_str = str(effort).capitalize() if effort else "Medium"
            intent_str = f" | Intent: {intent_type.replace('_', ' ').title()}" if intent_type else ""
            pdf.cell(0, 5, f"Impact: {impact}/10  |  Effort: {effort_str}{intent_str}", align="L")
            pdf.ln(6)
            
            if money_reason:
                if pdf.get_y() > 260:
                    pdf.add_page()
                pdf.set_font(pdf.default_font, "", 9)
                pdf.set_text_color(*LIGHT_GRAY)
                pdf.set_x(15)
                pdf.multi_cell(175, 4, money_reason)
            
            pdf.ln(5)
    
    if quick_wins:
        if pdf.get_y() > 200:
            pdf.add_page()
        
        pdf.subsection_header("Next 30 Days Focus", WARNING_YELLOW)
        
        for idx, win in enumerate(quick_wins, 1):
            if pdf.get_y() > 250:
                pdf.add_page()
            
            win_text = sanitize_text(str(win) if isinstance(win, str) else str(win))
            pdf.numbered_item(idx, win_text)
    
    if future_answers:
        if pdf.get_y() > 200:
            pdf.add_page()
        else:
            pdf.ln(10)
        
        pdf.subsection_header("Future AI Answers (Preview)", PURPLE)
        
        pdf.set_font(pdf.default_font, "", 9)
        pdf.set_text_color(*LIGHT_GRAY)
        pdf.set_x(10)
        pdf.multi_cell(190, 4, "Preview of how AI assistants could respond once your visibility improves:")
        pdf.ln(5)
        
        for fa in future_answers:
            if pdf.get_y() > 220:
                pdf.add_page()
            
            if not isinstance(fa, dict):
                continue
            
            query = sanitize_text(fa.get("query", ""))
            answer = sanitize_text(fa.get("example_answer", ""))
            
            pdf.set_font(pdf.default_font, "B", 9)
            pdf.set_text_color(*WHITE_TEXT)
            pdf.set_x(10)
            pdf.multi_cell(190, 5, f"Q: {query}")
            pdf.ln(3)
            
            pdf.set_font(pdf.default_font, "", 9)
            pdf.set_text_color(*LIGHT_GRAY)
            pdf.set_fill_color(*DARK_GRAY)
            pdf.set_x(15)
            pdf.multi_cell(180, 4, answer, fill=True)
            
            pdf.ln(8)


def _add_page_blueprints_section(pdf: EkkoScopePDF, data: Dict[str, Any], tenant: Dict[str, Any]):
    """Add detailed page blueprints for high-priority opportunities."""
    genius = data.get("genius_insights")
    if not genius:
        return
    
    opportunities = genius.get("priority_opportunities", [])
    if not opportunities:
        return
    
    pdf.add_page()
    
    pdf.section_header(
        "Page Blueprints",
        "Detailed content specifications for high-priority pages to improve AI visibility"
    )
    pdf.ln(5)
    
    geo_focus = tenant.get("geo_focus", [])
    region_str = geo_focus[0] if geo_focus else "your market"
    
    for idx, opp in enumerate(opportunities, 1):
        if not isinstance(opp, dict):
            continue
        
        recommended_page = opp.get("recommended_page", {})
        if not recommended_page or not isinstance(recommended_page, dict):
            continue
        
        if pdf.get_y() > 160:
            pdf.add_page()
        
        query = sanitize_text(opp.get("query", "Untitled Page"))
        impact = opp.get("impact_score", 5)
        effort = opp.get("effort", "medium")
        
        pdf.set_fill_color(*CYAN_GLOW)
        pdf.set_text_color(*BLACK_BG)
        pdf.set_font(pdf.default_font, "B", 11)
        pdf.set_x(10)
        pdf.multi_cell(190, 8, f"Blueprint {idx}: {query}", fill=True)
        pdf.ln(3)
        
        pdf.set_font(pdf.default_font, "", 9)
        pdf.set_text_color(*LIGHT_GRAY)
        pdf.cell(0, 5, f"Impact: {impact}/10  |  Effort: {str(effort).capitalize()}  |  Target: {region_str}", align="L")
        pdf.ln(8)
        
        slug = sanitize_text(str(recommended_page.get("slug", "") or ""))
        seo_title = sanitize_text(str(recommended_page.get("seo_title", "") or ""))
        h1 = sanitize_text(str(recommended_page.get("h1", "") or ""))
        outline = recommended_page.get("outline", [])
        internal_links = recommended_page.get("internal_links", [])
        note_on_site = sanitize_text(recommended_page.get("note_on_current_site", ""))
        
        if slug:
            pdf.set_font(pdf.default_font, "B", 9)
            pdf.set_text_color(*WHITE_TEXT)
            pdf.cell(0, 5, "URL:", align="L")
            pdf.ln(5)
            pdf.set_font(pdf.default_font, "", 9)
            pdf.set_text_color(*CYAN_GLOW)
            pdf.set_x(10)
            pdf.multi_cell(190, 5, slug)
        
        if seo_title:
            if pdf.get_y() > 260:
                pdf.add_page()
            pdf.set_font(pdf.default_font, "B", 9)
            pdf.set_text_color(*WHITE_TEXT)
            pdf.cell(0, 5, "SEO Title:", align="L")
            pdf.ln(5)
            pdf.set_font(pdf.default_font, "", 9)
            pdf.set_text_color(*LIGHT_GRAY)
            pdf.set_x(10)
            pdf.multi_cell(190, 5, seo_title)
        
        if h1:
            if pdf.get_y() > 260:
                pdf.add_page()
            pdf.set_font(pdf.default_font, "B", 9)
            pdf.set_text_color(*WHITE_TEXT)
            pdf.cell(0, 5, "H1:", align="L")
            pdf.ln(5)
            pdf.set_font(pdf.default_font, "", 9)
            pdf.set_text_color(*LIGHT_GRAY)
            pdf.set_x(10)
            pdf.multi_cell(190, 5, h1)
        
        if outline and isinstance(outline, list):
            if pdf.get_y() > 240:
                pdf.add_page()
            pdf.ln(3)
            pdf.set_font(pdf.default_font, "B", 9)
            pdf.set_text_color(*WHITE_TEXT)
            pdf.cell(0, 5, "Content Outline:", align="L")
            pdf.ln(5)
            
            pdf.set_font(pdf.default_font, "", 9)
            pdf.set_text_color(*LIGHT_GRAY)
            for item in outline:
                if pdf.get_y() > 265:
                    pdf.add_page()
                pdf.set_x(20)
                pdf.multi_cell(170, 4, f"> {sanitize_text(str(item))}")
                pdf.ln(1)
        
        if internal_links and isinstance(internal_links, list):
            if pdf.get_y() > 250:
                pdf.add_page()
            pdf.ln(2)
            pdf.set_font(pdf.default_font, "B", 9)
            pdf.set_text_color(*WHITE_TEXT)
            pdf.cell(0, 5, "Internal Links:", align="L")
            pdf.ln(5)
            
            pdf.set_font(pdf.default_font, "", 9)
            pdf.set_text_color(*CYAN_GLOW)
            for link in internal_links:
                if pdf.get_y() > 265:
                    pdf.add_page()
                pdf.set_x(20)
                pdf.multi_cell(170, 4, f"> {sanitize_text(str(link))}")
                pdf.ln(1)
        
        if note_on_site:
            if pdf.get_y() > 240:
                pdf.add_page()
            pdf.ln(3)
            pdf.set_font(pdf.default_font, "", 8)
            pdf.set_text_color(*WARNING_YELLOW)
            pdf.set_fill_color(40, 35, 20)
            pdf.set_x(15)
            pdf.multi_cell(180, 4, f"Site Note: {note_on_site}", fill=True)
        
        pdf.ln(10)


def _add_30_day_action_plan(pdf: EkkoScopePDF, data: Dict[str, Any], tenant: Dict[str, Any]):
    """Add 30-day implementation roadmap."""
    pdf.add_page()
    
    pdf.section_header(
        "30-Day Implementation Roadmap",
        "Week-by-week action plan to improve your AI visibility"
    )
    pdf.ln(5)
    
    genius = data.get("genius_insights", {}) or {}
    quick_wins = genius.get("quick_wins", []) or []
    opportunities = genius.get("priority_opportunities", []) or []
    
    weeks = [
        {
            "title": "Week 1: Foundation",
            "focus": "Quick wins and immediate optimizations",
            "tasks": [
                {"task": "Audit existing homepage and service pages for AI-friendly content", "impact": "High", "effort": "S", "owner": "Content Writer"},
                {"task": "Optimize meta descriptions with location and service keywords", "impact": "High", "effort": "S", "owner": "Developer"},
                {"task": "Register or update Google My Business profile with complete information", "impact": "High", "effort": "S", "owner": "Owner"},
            ]
        },
        {
            "title": "Week 2: Content Development",
            "focus": "Create new pages targeting high-value queries",
            "tasks": [
                {"task": "Create first priority landing page from blueprint", "impact": "High", "effort": "M", "owner": "Content Writer"},
                {"task": "Add FAQ section addressing top customer questions", "impact": "Medium", "effort": "S", "owner": "Content Writer"},
                {"task": "Implement schema markup on key pages", "impact": "Medium", "effort": "M", "owner": "Developer"},
            ]
        },
        {
            "title": "Week 3: Authority Building",
            "focus": "Establish expertise and build trust signals",
            "tasks": [
                {"task": "Publish industry insight blog post or guide", "impact": "Medium", "effort": "M", "owner": "Content Writer"},
                {"task": "Add customer testimonials and case studies", "impact": "High", "effort": "M", "owner": "Owner"},
                {"task": "Create second priority landing page from blueprint", "impact": "High", "effort": "M", "owner": "Content Writer"},
            ]
        },
        {
            "title": "Week 4: Optimization & Review",
            "focus": "Refine and measure results",
            "tasks": [
                {"task": "Review and optimize internal linking structure", "impact": "Medium", "effort": "S", "owner": "Developer"},
                {"task": "Ensure brand consistency across all domains", "impact": "Medium", "effort": "S", "owner": "Owner"},
                {"task": "Schedule next AI visibility audit to measure progress", "impact": "High", "effort": "S", "owner": "Owner"},
            ]
        }
    ]
    
    if quick_wins:
        weeks[0]["tasks"][0] = {
            "task": str(quick_wins[0]) if quick_wins[0] else weeks[0]["tasks"][0]["task"],
            "impact": "High", "effort": "S", "owner": "Content Writer"
        }
        if len(quick_wins) > 1:
            weeks[0]["tasks"][1] = {
                "task": str(quick_wins[1]) if quick_wins[1] else weeks[0]["tasks"][1]["task"],
                "impact": "High", "effort": "S", "owner": "Developer"
            }
    
    for week in weeks:
        if pdf.get_y() > 180:
            pdf.add_page()
        
        pdf.set_fill_color(*CYAN_GLOW)
        pdf.set_text_color(*BLACK_BG)
        pdf.set_font(pdf.default_font, "B", 11)
        pdf.cell(0, 8, week["title"], align="L", fill=True)
        pdf.ln(9)
        
        pdf.set_font(pdf.default_font, "", 9)
        pdf.set_text_color(*LIGHT_GRAY)
        pdf.cell(0, 5, f"Focus: {week['focus']}", align="L")
        pdf.ln(7)
        
        for task in week["tasks"]:
            if pdf.get_y() > 250:
                pdf.add_page()
            
            pdf.set_fill_color(*DARK_GRAY)
            start_y = pdf.get_y()
            
            pdf.set_font(pdf.default_font, "", 9)
            pdf.set_text_color(*WHITE_TEXT)
            pdf.set_x(12)
            pdf.multi_cell(110, 5, sanitize_text(task["task"]))
            
            task_end_y = pdf.get_y()
            row_height = max(task_end_y - start_y, 5)
            
            pdf.set_xy(125, start_y)
            impact = task["impact"]
            if impact == "High":
                pdf.set_text_color(*SUCCESS_GREEN)
            elif impact == "Medium":
                pdf.set_text_color(*WARNING_YELLOW)
            else:
                pdf.set_text_color(*LIGHT_GRAY)
            pdf.set_font(pdf.default_font, "B", 8)
            pdf.cell(18, row_height, impact, align="C")
            
            pdf.set_xy(145, start_y)
            pdf.set_text_color(*CYAN_GLOW)
            pdf.cell(12, row_height, task["effort"], align="C")
            
            pdf.set_xy(160, start_y)
            pdf.set_text_color(*LIGHT_GRAY)
            pdf.set_font(pdf.default_font, "", 8)
            pdf.cell(30, row_height, task["owner"], align="L")
            
            pdf.set_y(task_end_y + 2)
        
        pdf.ln(8)
    
    pdf.ln(5)
    pdf.set_font(pdf.default_font, "", 9)
    pdf.set_text_color(*MEDIUM_GRAY)
    pdf.multi_cell(0, 4, "Effort: S = Small (1-2 hours), M = Medium (half day), L = Large (1+ days)")


def _add_recommendations_section(pdf: EkkoScopePDF, data: Dict[str, Any]):
    """Add grouped recommendations section."""
    recommendations = data.get("recommendations", {})
    
    if not recommendations:
        return
    
    pdf.add_page()
    
    pdf.section_header(
        "Strategic Recommendations",
        "Comprehensive recommendations to improve your AI visibility based on the analysis"
    )
    pdf.ln(5)
    
    type_config = {
        "new_page": ("New Pages to Create", SUCCESS_GREEN),
        "update_page": ("Pages to Update", CYAN_GLOW),
        "faq": ("FAQ Content", PURPLE),
        "authority": ("Authority Building", WARNING_YELLOW),
        "branding": ("Branding", PINK),
        "other": ("Other Recommendations", LIGHT_GRAY)
    }
    
    for rec_type, suggestions in recommendations.items():
        if not suggestions:
            continue
        
        if pdf.get_y() > 200:
            pdf.add_page()
        
        label, color = type_config.get(rec_type, (rec_type.replace("_", " ").title(), LIGHT_GRAY))
        
        pdf.set_fill_color(*color)
        pdf.set_text_color(*BLACK_BG)
        pdf.set_font(pdf.default_font, "B", 10)
        pdf.cell(55, 7, label, align="C", fill=True)
        pdf.ln(10)
        
        for suggestion in suggestions:
            if pdf.get_y() > 230:
                pdf.add_page()
            
            title = sanitize_text(suggestion.get("title", ""))
            details = sanitize_text(suggestion.get("details", ""))
            
            pdf.set_font(pdf.default_font, "B", 10)
            pdf.set_text_color(*WHITE_TEXT)
            pdf.multi_cell(0, 5, title)
            pdf.ln(2)
            
            if details:
                if pdf.get_y() > 260:
                    pdf.add_page()
                pdf.set_font(pdf.default_font, "", 9)
                pdf.set_text_color(*LIGHT_GRAY)
                pdf.set_x(15)
                pdf.multi_cell(175, 4, details)
            
            pdf.ln(5)
        
        pdf.ln(5)


def _add_upsell_page(pdf: EkkoScopePDF, data: Dict[str, Any]):
    """Add final upsell page with pricing options."""
    pdf.is_upsell_page = True
    pdf.add_page()
    
    pdf.ln(30)
    
    pdf.set_font(pdf.default_font, "B", 14)
    pdf.set_text_color(*CYAN_GLOW)
    pdf.cell(0, 8, "$490", align="L")
    pdf.set_text_color(*WHITE_TEXT)
    pdf.set_font(pdf.default_font, "", 11)
    pdf.cell(0, 8, "  You just paid for the truth", align="L", new_x="LMARGIN", new_y="NEXT")
    
    pdf.ln(12)
    
    pdf.set_font(pdf.default_font, "B", 14)
    pdf.set_text_color(*CYAN_GLOW)
    pdf.cell(0, 8, "$290 / month", align="L")
    pdf.set_text_color(*WHITE_TEXT)
    pdf.set_font(pdf.default_font, "", 11)
    pdf.cell(0, 8, "  Keep watching the truth change (or not)", align="L", new_x="LMARGIN", new_y="NEXT")
    
    pdf.ln(12)
    
    pdf.set_font(pdf.default_font, "B", 14)
    pdf.set_text_color(*CYAN_GLOW)
    pdf.cell(0, 8, 'Reply "FIX"', align="L")
    pdf.set_text_color(*WHITE_TEXT)
    pdf.set_font(pdf.default_font, "", 11)
    pdf.cell(0, 8, "  We make the red bar disappear (first 5 only)", align="L", new_x="LMARGIN", new_y="NEXT")
    
    pdf.ln(30)
    
    box_x = 15
    box_y = pdf.get_y()
    box_width = 180
    box_height = 22
    
    pdf.set_draw_color(*BLOOD_RED)
    pdf.set_line_width(2)
    pdf.rect(box_x, box_y, box_width, box_height)
    
    pdf.set_xy(box_x, box_y + 7)
    pdf.set_font(pdf.default_font, "B", 12)
    pdf.set_text_color(*BLOOD_RED)
    pdf.cell(box_width, 8, "YOUR VISIBILITY: 0%", align="C")
    
    pdf.set_y(270)
    pdf.set_font(pdf.default_font, "", 8)
    pdf.set_text_color(*MEDIUM_GRAY)
    pdf.cell(0, 5, "Powered by EkkoScope | AN2B", align="C")
    
    pdf.is_upsell_page = False
