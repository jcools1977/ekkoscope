"""
PDF Report Generation for EkkoScope GEO Visibility Analysis v0.3
Uses fpdf2 to create professional, client-ready PDF reports.
Print-friendly design with brand accent colors.
Includes Executive Summary, Impact/Effort scoring, and Next 30 Days Focus.
"""

from datetime import datetime
from typing import Dict, Any, List
from fpdf import FPDF
from collections import Counter
import os
from services.genius import generate_executive_summary

BRAND_TEAL = (46, 230, 168)
BRAND_BLUE = (24, 163, 255)
DARK_TEXT = (30, 41, 59)
MEDIUM_TEXT = (71, 85, 105)
LIGHT_TEXT = (100, 116, 139)
ACCENT_BG = (241, 245, 249)


class EkkoScopePDF(FPDF):
    """Custom PDF class with EkkoScope branding and automatic page numbering."""
    
    def __init__(self, tenant_name: str):
        super().__init__()
        self.tenant_name = tenant_name
        self.set_auto_page_break(auto=True, margin=25)
    
    def header(self):
        if self.page_no() > 1:
            self._draw_header_logo()
            self.set_font("Helvetica", "", 9)
            self.set_text_color(*LIGHT_TEXT)
            self.set_xy(45, 10)
            self.cell(0, 10, f"AI Visibility Report - {self.tenant_name}", align="L")
            
            self.set_draw_color(*BRAND_TEAL)
            self.set_line_width(0.5)
            self.line(10, 22, 200, 22)
            self.ln(20)
    
    def _draw_header_logo(self):
        """Draw a simplified radar logo for PDF header."""
        cx, cy = 25, 15
        
        self.set_draw_color(*BRAND_TEAL)
        self.set_line_width(0.4)
        self.ellipse(cx-10, cy-10, 20, 20)
        self.ellipse(cx-6, cy-6, 12, 12)
        
        self.set_fill_color(*BRAND_TEAL)
        self.ellipse(cx-2, cy-2, 4, 4, style="F")
    
    def footer(self):
        self.set_y(-20)
        
        self.set_draw_color(*BRAND_TEAL)
        self.set_line_width(0.3)
        self.line(10, self.get_y(), 200, self.get_y())
        
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*LIGHT_TEXT)
        self.set_y(-15)
        self.cell(95, 10, "EkkoScope - GEO Engine for AI Visibility", align="L")
        self.cell(95, 10, f"Page {self.page_no()} of {{nb}}", align="R")


def normalize_analysis_data(analysis: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize analysis data to ensure all required fields exist.
    Returns a standardized structure for PDF generation.
    """
    results = analysis.get("results", [])
    total_queries = analysis.get("total_queries", len(results))
    
    score_counts = {0: 0, 1: 0, 2: 0}
    all_competitors = []
    
    for result in results:
        score = result.get("score", 0)
        score_counts[score] = score_counts.get(score, 0) + 1
        all_competitors.extend(result.get("competitors", []))
    
    competitor_freq = Counter(all_competitors)
    top_competitors = [
        {"name": name, "frequency": count}
        for name, count in competitor_freq.most_common(5)
    ]
    
    suggestions = analysis.get("suggestions", [])
    grouped_recommendations = {}
    for suggestion in suggestions:
        rec_type = suggestion.get("type", "other")
        if rec_type not in grouped_recommendations:
            grouped_recommendations[rec_type] = []
        grouped_recommendations[rec_type].append(suggestion)
    
    return {
        "tenant_name": analysis.get("tenant_name", "Unknown"),
        "generated_at": analysis.get("run_at", datetime.utcnow().isoformat() + "Z"),
        "total_queries": total_queries,
        "average_score": analysis.get("avg_score", 0),
        "score_counts": score_counts,
        "queries": results,
        "top_competitors": top_competitors,
        "recommendations": grouped_recommendations,
        "visibility_summary": analysis.get("visibility_summary", ""),
        "genius_insights": analysis.get("genius_insights", None)
    }


def build_ekkoscope_pdf(tenant: Dict[str, Any], analysis: Dict[str, Any]) -> bytes:
    """
    Generate a professional PDF report from tenant config and analysis results.
    
    Args:
        tenant: Tenant configuration dictionary
        analysis: Analysis results from run_analysis()
    
    Returns:
        PDF file as bytes
    """
    data = normalize_analysis_data(analysis)
    tenant_name = data["tenant_name"]
    
    pdf = EkkoScopePDF(tenant_name)
    pdf.alias_nb_pages()
    
    _add_cover_page(pdf, data)
    _add_summary_section(pdf, data)
    _add_executive_summary_section(pdf, data, analysis)
    _add_query_details_section(pdf, data)
    _add_competitor_section(pdf, data)
    _add_genius_insights_section_v2(pdf, data)
    _add_recommendations_section(pdf, data)
    
    return pdf.output()


def _draw_cover_logo(pdf: EkkoScopePDF):
    """Draw a large radar logo for the cover page."""
    cx, cy = 105, 60
    
    pdf.set_draw_color(*BRAND_TEAL)
    pdf.set_line_width(0.8)
    pdf.ellipse(cx-30, cy-30, 60, 60)
    
    pdf.set_line_width(0.5)
    pdf.ellipse(cx-20, cy-20, 40, 40)
    
    pdf.set_line_width(0.3)
    pdf.ellipse(cx-10, cy-10, 20, 20)
    
    pdf.set_line_width(0.2)
    pdf.line(cx-30, cy, cx+30, cy)
    pdf.line(cx, cy-30, cx, cy+30)
    
    pdf.set_fill_color(*BRAND_TEAL)
    pdf.ellipse(cx-3, cy-3, 6, 6, style="F")
    
    pdf.set_draw_color(*BRAND_TEAL)
    pdf.set_line_width(1.2)
    pdf.line(cx+8, cy-4, cx+8, cy+4)
    pdf.set_line_width(0.9)
    pdf.line(cx+14, cy-7, cx+14, cy+7)
    pdf.set_line_width(0.6)
    pdf.line(cx+20, cy-10, cx+20, cy+10)


def _add_cover_page(pdf: EkkoScopePDF, data: Dict[str, Any]):
    """Add cover page with branding and tenant info."""
    pdf.add_page()
    
    _draw_cover_logo(pdf)
    
    pdf.ln(70)
    
    pdf.set_font("Helvetica", "", 36)
    pdf.set_text_color(*DARK_TEXT)
    pdf.cell(0, 15, "Ekko", align="R", new_x="LEFT")
    pdf.set_x(pdf.get_x() + 85)
    pdf.set_font("Helvetica", "B", 36)
    pdf.set_text_color(*BRAND_TEAL)
    pdf.cell(0, 15, "Scope", align="L")
    pdf.ln(20)
    
    pdf.set_font("Helvetica", "", 16)
    pdf.set_text_color(*MEDIUM_TEXT)
    pdf.cell(0, 10, "GEO Engine for AI Visibility", align="C")
    pdf.ln(30)
    
    pdf.set_draw_color(*BRAND_TEAL)
    pdf.set_line_width(1)
    pdf.line(60, pdf.get_y(), 150, pdf.get_y())
    pdf.ln(20)
    
    pdf.set_font("Helvetica", "B", 24)
    pdf.set_text_color(*DARK_TEXT)
    pdf.multi_cell(0, 12, data["tenant_name"], align="C")
    pdf.ln(10)
    
    pdf.set_font("Helvetica", "", 12)
    pdf.set_text_color(*LIGHT_TEXT)
    pdf.cell(0, 8, "AI Visibility Analysis Report", align="C")
    pdf.ln(25)
    
    generated_at = data["generated_at"]
    try:
        dt = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
        formatted_date = dt.strftime("%B %d, %Y at %H:%M UTC")
    except:
        formatted_date = generated_at
    
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(*MEDIUM_TEXT)
    pdf.cell(0, 8, f"Generated: {formatted_date}", align="C")


def _add_summary_section(pdf: EkkoScopePDF, data: Dict[str, Any]):
    """Add AI visibility summary section with modern styling."""
    pdf.add_page()
    
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(*BRAND_TEAL)
    pdf.cell(0, 12, "AI Visibility Summary", align="L")
    pdf.ln(15)
    
    score_counts = data["score_counts"]
    total = data["total_queries"]
    avg = data["average_score"]
    
    card_y = pdf.get_y()
    card_height = 35
    card_width = 58
    gap = 5
    
    metrics = [
        ("Total Queries", str(total), BRAND_BLUE),
        ("Avg Score", f"{avg}/2.0", BRAND_TEAL),
        ("Primary", str(score_counts.get(2, 0)), (34, 197, 94)),
    ]
    
    for i, (label, value, color) in enumerate(metrics):
        x = 10 + (card_width + gap) * i
        
        pdf.set_fill_color(*ACCENT_BG)
        pdf.set_draw_color(*color)
        pdf.set_line_width(0.5)
        pdf.rect(x, card_y, card_width, card_height, style="FD")
        
        pdf.set_xy(x, card_y + 5)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*LIGHT_TEXT)
        pdf.cell(card_width, 6, label, align="C")
        
        pdf.set_xy(x, card_y + 14)
        pdf.set_font("Helvetica", "B", 20)
        pdf.set_text_color(*color)
        pdf.cell(card_width, 12, value, align="C")
    
    pdf.set_y(card_y + card_height + 15)
    
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(*DARK_TEXT)
    pdf.cell(0, 10, "Score Distribution", align="L")
    pdf.ln(10)
    
    bar_y = pdf.get_y()
    bar_height = 12
    max_width = 140
    
    score_labels = [
        ("Score 0 - Not Mentioned", score_counts.get(0, 0), (239, 68, 68)),
        ("Score 1 - Mentioned", score_counts.get(1, 0), (245, 158, 11)),
        ("Score 2 - Primary", score_counts.get(2, 0), BRAND_TEAL),
    ]
    
    for label, count, color in score_labels:
        width = (count / max(total, 1)) * max_width if total > 0 else 0
        
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(*MEDIUM_TEXT)
        pdf.cell(55, bar_height, label, align="L")
        
        if width > 0:
            pdf.set_fill_color(*color)
            pdf.rect(65, bar_y + 2, width, bar_height - 4, style="F")
        
        pdf.set_text_color(*DARK_TEXT)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_xy(65 + max_width + 5, bar_y)
        pdf.cell(20, bar_height, f"{count}", align="L")
        
        bar_y += bar_height + 3
        pdf.set_y(bar_y)
    
    if data.get("visibility_summary"):
        pdf.ln(10)
        
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(*BRAND_BLUE)
        pdf.cell(0, 6, "Summary", align="L")
        pdf.ln(6)
        
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(*MEDIUM_TEXT)
        pdf.set_x(12)
        pdf.multi_cell(178, 5, data["visibility_summary"][:500])


def _add_executive_summary_section(pdf: EkkoScopePDF, data: Dict[str, Any], analysis: Dict[str, Any]):
    """Add Executive Summary section with 3-5 key bullets grounded in data."""
    genius = data.get("genius_insights")
    
    if pdf.get_y() > 220:
        pdf.add_page()
    else:
        pdf.ln(12)
    
    pdf.set_fill_color(241, 245, 249)
    pdf.set_draw_color(*BRAND_TEAL)
    pdf.set_line_width(0.8)
    
    summary_start_y = pdf.get_y()
    
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(*BRAND_TEAL)
    pdf.cell(0, 8, "Executive Summary", align="L")
    pdf.ln(10)
    
    try:
        bullets = generate_executive_summary(genius, analysis)
    except Exception:
        bullets = ["Genius Mode insights unavailable for this run."]
    
    if not bullets:
        bullets = ["Genius Mode insights unavailable for this run."]
    
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*DARK_TEXT)
    
    for bullet in bullets[:5]:
        if pdf.get_y() > 270:
            break
        
        pdf.set_text_color(*BRAND_TEAL)
        pdf.cell(6, 6, ">", align="L")
        pdf.set_text_color(*DARK_TEXT)
        
        bullet_text = str(bullet)[:200]
        pdf.multi_cell(180, 5, bullet_text)
        pdf.ln(2)


def _add_query_details_section(pdf: EkkoScopePDF, data: Dict[str, Any]):
    """Add per-query analysis table with modern styling."""
    pdf.add_page()
    
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(*BRAND_TEAL)
    pdf.cell(0, 12, "Query Analysis Details", align="L")
    pdf.ln(15)
    
    col_widths = [100, 25, 55]
    headers = ["Query", "Score", "Top Competitor"]
    
    pdf.set_fill_color(*BRAND_TEAL)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 10)
    
    for i, header in enumerate(headers):
        pdf.cell(col_widths[i], 10, header, border=0, align="C" if i > 0 else "L", fill=True)
    pdf.ln()
    
    pdf.set_font("Helvetica", "", 9)
    row_fill = False
    
    for query_data in data["queries"]:
        if pdf.get_y() > 260:
            pdf.add_page()
            pdf.set_fill_color(*BRAND_TEAL)
            pdf.set_text_color(255, 255, 255)
            pdf.set_font("Helvetica", "B", 10)
            for i, header in enumerate(headers):
                pdf.cell(col_widths[i], 10, header, border=0, align="C" if i > 0 else "L", fill=True)
            pdf.ln()
            pdf.set_font("Helvetica", "", 9)
            row_fill = False
        
        query = query_data.get("query", "")[:60]
        if len(query_data.get("query", "")) > 60:
            query += "..."
        
        score = query_data.get("score", 0)
        competitors = query_data.get("competitors", [])
        top_comp = competitors[0] if competitors else "-"
        if len(top_comp) > 25:
            top_comp = top_comp[:22] + "..."
        
        if row_fill:
            pdf.set_fill_color(*ACCENT_BG)
        else:
            pdf.set_fill_color(255, 255, 255)
        
        pdf.set_text_color(*DARK_TEXT)
        pdf.cell(col_widths[0], 8, query, border=0, align="L", fill=True)
        
        if score == 2:
            pdf.set_text_color(*BRAND_TEAL)
        elif score == 1:
            pdf.set_text_color(245, 158, 11)
        else:
            pdf.set_text_color(239, 68, 68)
        
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(col_widths[1], 8, str(score), border=0, align="C", fill=True)
        
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*MEDIUM_TEXT)
        pdf.cell(col_widths[2], 8, top_comp, border=0, align="L", fill=True)
        pdf.ln()
        
        row_fill = not row_fill


def _add_competitor_section(pdf: EkkoScopePDF, data: Dict[str, Any]):
    """Add competitor overview section."""
    top_competitors = data.get("top_competitors", [])
    
    if not top_competitors:
        return
    
    if pdf.get_y() > 200:
        pdf.add_page()
    else:
        pdf.ln(15)
    
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(*BRAND_TEAL)
    pdf.cell(0, 12, "Competitor Overview", align="L")
    pdf.ln(12)
    
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*MEDIUM_TEXT)
    pdf.multi_cell(0, 5, "These competitors appeared most frequently in AI recommendations across your queries:")
    pdf.ln(8)
    
    total_queries = data["total_queries"]
    col_widths = [120, 60]
    
    pdf.set_fill_color(*BRAND_BLUE)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(col_widths[0], 10, "Competitor", border=0, align="L", fill=True)
    pdf.cell(col_widths[1], 10, "Frequency", border=0, align="C", fill=True)
    pdf.ln()
    
    pdf.set_font("Helvetica", "", 10)
    row_fill = False
    
    for comp in top_competitors[:5]:
        name = comp.get("name", "")[:50]
        freq = comp.get("frequency", 0)
        
        if row_fill:
            pdf.set_fill_color(*ACCENT_BG)
        else:
            pdf.set_fill_color(255, 255, 255)
        
        pdf.set_text_color(*DARK_TEXT)
        pdf.cell(col_widths[0], 10, name, border=0, align="L", fill=True)
        pdf.cell(col_widths[1], 10, f"{freq} of {total_queries} queries", border=0, align="C", fill=True)
        pdf.ln()
        
        row_fill = not row_fill


def _add_genius_insights_section_v2(pdf: EkkoScopePDF, data: Dict[str, Any]):
    """Add Genius Insights v2 with Impact/Effort scoring and Next 30 Days Focus."""
    genius = data.get("genius_insights")
    
    if not genius or not isinstance(genius, dict):
        return
    
    patterns = genius.get("patterns", []) or []
    opportunities = genius.get("priority_opportunities", []) or []
    quick_wins = genius.get("quick_wins", []) or []
    future_answers = genius.get("future_ai_answers", []) or []
    
    if not isinstance(patterns, list):
        patterns = []
    if not isinstance(opportunities, list):
        opportunities = []
    if not isinstance(quick_wins, list):
        quick_wins = []
    if not isinstance(future_answers, list):
        future_answers = []
    
    if not any([patterns, opportunities, quick_wins, future_answers]):
        return
    
    pdf.add_page()
    
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(*BRAND_TEAL)
    pdf.cell(0, 12, "Genius Insights & Opportunity Map", align="L")
    pdf.ln(5)
    
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*MEDIUM_TEXT)
    site_note = " (with site content analysis)" if genius.get("site_analyzed") else ""
    pdf.multi_cell(0, 5, f"Deep strategic analysis powered by AI{site_note} to uncover hidden patterns and high-value opportunities.")
    pdf.ln(10)
    
    if patterns:
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(*BRAND_BLUE)
        pdf.cell(0, 10, "Patterns in AI Visibility", align="L")
        pdf.ln(8)
        
        for pattern in patterns[:3]:
            if pdf.get_y() > 250:
                pdf.add_page()
            
            if isinstance(pattern, dict):
                summary = pattern.get("summary", "")
                evidence = pattern.get("evidence", [])
                implication = pattern.get("implication", "")
                
                pdf.set_font("Helvetica", "B", 10)
                pdf.set_text_color(*DARK_TEXT)
                pdf.set_x(12)
                pdf.multi_cell(178, 5, summary[:150])
                
                if evidence and isinstance(evidence, list):
                    pdf.set_font("Helvetica", "", 9)
                    pdf.set_text_color(*MEDIUM_TEXT)
                    for ev in evidence[:2]:
                        pdf.set_x(16)
                        pdf.multi_cell(174, 4, f"- {str(ev)[:120]}")
                
                if implication:
                    pdf.set_font("Helvetica", "I", 9)
                    pdf.set_text_color(*LIGHT_TEXT)
                    pdf.set_x(12)
                    pdf.multi_cell(178, 4, f"Implication: {implication[:150]}")
            else:
                pdf.set_font("Helvetica", "", 10)
                pdf.set_text_color(*DARK_TEXT)
                pdf.set_x(12)
                pdf.multi_cell(178, 5, str(pattern)[:200])
            
            pdf.ln(5)
        
        pdf.ln(5)
    
    if opportunities:
        if pdf.get_y() > 180:
            pdf.add_page()
        
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(34, 197, 94)
        pdf.cell(0, 10, "Priority Opportunities (with Impact/Effort)", align="L")
        pdf.ln(10)
        
        for idx, opp in enumerate(opportunities[:3], 1):
            if pdf.get_y() > 200:
                pdf.add_page()
            
            if not isinstance(opp, dict):
                continue
            
            query = opp.get("query", "")
            impact = opp.get("impact_score", opp.get("intent_value", 5))
            effort = opp.get("effort", opp.get("difficulty", "medium"))
            intent_type = opp.get("intent_type", "")
            money_reason = opp.get("money_reason", opp.get("reason", ""))
            recommended_page = opp.get("recommended_page", {})
            note_on_site = ""
            if isinstance(recommended_page, dict):
                note_on_site = recommended_page.get("note_on_current_site", "")
            
            pdf.set_fill_color(236, 253, 245)
            pdf.set_draw_color(34, 197, 94)
            pdf.rect(10, pdf.get_y(), 190, 10, style="FD")
            
            pdf.set_font("Helvetica", "B", 11)
            pdf.set_text_color(34, 197, 94)
            pdf.set_x(12)
            query_display = query[:55] + "..." if len(query) > 55 else query
            pdf.cell(0, 10, f"{idx}. {query_display}", align="L")
            pdf.ln(12)
            
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(*BRAND_BLUE)
            pdf.set_x(15)
            effort_str = str(effort).capitalize() if effort else "Medium"
            intent_str = f" | Intent: {intent_type.replace('_', ' ').title()}" if intent_type else ""
            pdf.cell(0, 5, f"Impact: {impact}/10  |  Effort: {effort_str}{intent_str}", align="L")
            pdf.ln(6)
            
            if money_reason:
                pdf.set_font("Helvetica", "", 9)
                pdf.set_text_color(*MEDIUM_TEXT)
                pdf.set_x(15)
                pdf.multi_cell(175, 4, money_reason[:180])
                pdf.ln(2)
            
            if recommended_page and isinstance(recommended_page, dict):
                pdf.set_font("Helvetica", "B", 9)
                pdf.set_text_color(*BRAND_TEAL)
                pdf.set_x(15)
                pdf.cell(0, 5, "Page Blueprint:", align="L")
                pdf.ln(5)
                
                pdf.set_font("Helvetica", "", 8)
                pdf.set_text_color(*DARK_TEXT)
                
                slug = str(recommended_page.get("slug", "") or "")
                seo_title = str(recommended_page.get("seo_title", "") or "")
                h1 = str(recommended_page.get("h1", "") or "")
                outline = recommended_page.get("outline", [])
                internal_links = recommended_page.get("internal_links", [])
                if not isinstance(outline, list):
                    outline = []
                
                if slug:
                    pdf.set_x(18)
                    pdf.cell(0, 4, f"URL: {slug[:60]}", align="L")
                    pdf.ln(4)
                
                if seo_title:
                    pdf.set_x(18)
                    pdf.cell(0, 4, f"SEO Title: {seo_title[:65]}", align="L")
                    pdf.ln(4)
                
                if h1:
                    pdf.set_x(18)
                    pdf.cell(0, 4, f"H1: {h1[:65]}", align="L")
                    pdf.ln(4)
                
                if outline:
                    pdf.set_x(18)
                    pdf.cell(0, 4, "Outline:", align="L")
                    pdf.ln(4)
                    for item in outline[:5]:
                        pdf.set_x(22)
                        pdf.cell(0, 4, f"- {str(item)[:55]}", align="L")
                        pdf.ln(4)
                
                if note_on_site:
                    pdf.set_font("Helvetica", "I", 8)
                    pdf.set_text_color(245, 158, 11)
                    pdf.set_x(18)
                    pdf.multi_cell(172, 4, f"Site note: {note_on_site[:150]}")
            
            pdf.ln(8)
    
    if quick_wins and len(quick_wins) >= 1:
        if pdf.get_y() > 200:
            pdf.add_page()
        
        pdf.set_fill_color(255, 251, 235)
        pdf.set_draw_color(245, 158, 11)
        pdf.set_line_width(1)
        
        box_y = pdf.get_y()
        pdf.rect(10, box_y, 190, 8, style="FD")
        
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(245, 158, 11)
        pdf.set_xy(15, box_y + 1)
        pdf.cell(0, 6, "Next 30 Days Focus", align="L")
        pdf.ln(12)
        
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(*DARK_TEXT)
        
        for idx, win in enumerate(quick_wins[:3], 1):
            if pdf.get_y() > 270:
                break
            
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(245, 158, 11)
            pdf.cell(10, 6, f"{idx}.", align="L")
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(*DARK_TEXT)
            
            win_text = str(win)[:200]
            pdf.multi_cell(170, 5, win_text)
            pdf.ln(3)
        
        pdf.ln(8)
    
    if quick_wins and len(quick_wins) > 3:
        if pdf.get_y() > 220:
            pdf.add_page()
        
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(245, 158, 11)
        pdf.cell(0, 8, "Additional Quick Wins", align="L")
        pdf.ln(8)
        
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*DARK_TEXT)
        
        for idx, win in enumerate(quick_wins[3:5], 4):
            if pdf.get_y() > 270:
                break
            
            pdf.set_text_color(245, 158, 11)
            pdf.cell(8, 5, f"{idx}.", align="L")
            pdf.set_text_color(*DARK_TEXT)
            pdf.multi_cell(172, 5, str(win)[:180])
            pdf.ln(2)
        
        pdf.ln(5)
    
    if future_answers:
        if pdf.get_y() > 180:
            pdf.add_page()
        
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(*BRAND_BLUE)
        pdf.cell(0, 10, "Future AI Answers (Preview)", align="L")
        pdf.ln(6)
        
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*LIGHT_TEXT)
        pdf.multi_cell(0, 5, "Preview of how AI assistants could respond once your visibility improves:")
        pdf.ln(5)
        
        for answer in future_answers[:2]:
            if pdf.get_y() > 230:
                pdf.add_page()
            
            if not isinstance(answer, dict):
                continue
            
            query = answer.get("query", "")
            example = answer.get("example_answer", "")
            
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(*DARK_TEXT)
            pdf.multi_cell(0, 5, f"Q: {query[:75]}")
            pdf.ln(2)
            
            pdf.set_fill_color(*ACCENT_BG)
            pdf.set_font("Helvetica", "I", 9)
            pdf.set_text_color(*MEDIUM_TEXT)
            
            pdf.set_x(12)
            pdf.multi_cell(178, 5, example[:350], fill=True)
            pdf.ln(8)


def _add_recommendations_section(pdf: EkkoScopePDF, data: Dict[str, Any]):
    """Add grouped recommendations section."""
    recommendations = data.get("recommendations", {})
    
    if not recommendations:
        return
    
    pdf.add_page()
    
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(*BRAND_TEAL)
    pdf.cell(0, 12, "Recommended Actions", align="L")
    pdf.ln(5)
    
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*MEDIUM_TEXT)
    pdf.multi_cell(0, 5, "Strategic recommendations to improve your AI visibility based on the analysis:")
    pdf.ln(10)
    
    type_config = {
        "new_page": ("New Pages to Create", (34, 197, 94)),
        "update_page": ("Pages to Update", BRAND_BLUE),
        "faq": ("FAQ Content", (168, 85, 247)),
        "authority": ("Authority Building", (245, 158, 11)),
        "branding": ("Branding", (244, 114, 182)),
        "other": ("Other Recommendations", LIGHT_TEXT)
    }
    
    for rec_type, suggestions in recommendations.items():
        if not suggestions:
            continue
        
        if pdf.get_y() > 230:
            pdf.add_page()
        
        label, color = type_config.get(rec_type, (rec_type.title(), LIGHT_TEXT))
        
        pdf.set_fill_color(*color)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(60, 8, label, align="C", fill=True)
        pdf.ln(12)
        
        for suggestion in suggestions[:5]:
            if pdf.get_y() > 255:
                pdf.add_page()
            
            title = suggestion.get("title", "")
            details = suggestion.get("details", "")
            
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(*DARK_TEXT)
            if len(title) > 80:
                title = title[:77] + "..."
            pdf.cell(0, 6, title, align="L")
            pdf.ln(5)
            
            if details:
                pdf.set_font("Helvetica", "", 9)
                pdf.set_text_color(*MEDIUM_TEXT)
                pdf.set_x(15)
                if len(details) > 200:
                    details = details[:197] + "..."
                pdf.multi_cell(175, 4, details)
            
            pdf.ln(5)
        
        pdf.ln(8)
