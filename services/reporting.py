"""
PDF Report Generation for EkkoScope GEO Visibility Analysis v1.0
Premium-quality, agency-grade PDF reports with comprehensive GEO analysis.
Features: Multi-source visibility, detailed page blueprints, 30-day action plans.
"""

from datetime import datetime
from typing import Dict, Any, List, Optional
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
WHITE = (255, 255, 255)
SUCCESS_GREEN = (34, 197, 94)
WARNING_YELLOW = (245, 158, 11)
ERROR_RED = (239, 68, 68)
PURPLE = (168, 85, 247)
PINK = (244, 114, 182)


class EkkoScopePDF(FPDF):
    """Custom PDF class with EkkoScope branding and automatic page numbering."""
    
    def __init__(self, tenant_name: str, business_type: str = ""):
        super().__init__()
        self.tenant_name = tenant_name
        self.business_type = business_type
        self.set_margins(left=15, top=18, right=15)
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
    
    def section_header(self, title: str, subtitle: str = ""):
        """Add a consistent section header."""
        self.set_font("Helvetica", "B", 20)
        self.set_text_color(*BRAND_TEAL)
        self.cell(0, 12, title, align="L")
        self.ln(8)
        
        if subtitle:
            self.set_font("Helvetica", "", 10)
            self.set_text_color(*MEDIUM_TEXT)
            self.multi_cell(0, 5, subtitle)
            self.ln(5)
    
    def subsection_header(self, title: str, color: tuple = BRAND_BLUE):
        """Add a subsection header."""
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(*color)
        self.cell(0, 10, title, align="L")
        self.ln(8)
    
    def bullet_point(self, text: str, indent: int = 12):
        """Add a properly formatted bullet point."""
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*BRAND_TEAL)
        self.set_x(indent)
        self.cell(5, 5, ">", align="L")
        self.set_text_color(*DARK_TEXT)
        self.multi_cell(175, 5, text)
        self.ln(2)
    
    def numbered_item(self, number: int, text: str, indent: int = 12):
        """Add a properly formatted numbered item."""
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(*BRAND_TEAL)
        self.set_x(indent)
        self.cell(8, 5, f"{number}.", align="L")
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*DARK_TEXT)
        self.multi_cell(170, 5, text)
        self.ln(2)


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
        "site_snapshot": analysis.get("site_snapshot", None)
    }


def build_ekkoscope_pdf(tenant: Dict[str, Any], analysis: Dict[str, Any]) -> bytes:
    """Generate a premium PDF report from tenant config and analysis results."""
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
    
    return pdf.output()


def _draw_cover_logo(pdf: EkkoScopePDF):
    """Draw a compact, professional radar logo matching website style."""
    cx, cy = 105, 40
    
    pdf.set_draw_color(*BRAND_TEAL)
    pdf.set_line_width(0.6)
    pdf.ellipse(cx-12, cy-12, 24, 24)
    
    pdf.set_line_width(0.4)
    pdf.ellipse(cx-8, cy-8, 16, 16)
    
    pdf.set_line_width(0.3)
    pdf.ellipse(cx-4, cy-4, 8, 8)
    
    pdf.set_fill_color(*BRAND_TEAL)
    pdf.ellipse(cx-1.5, cy-1.5, 3, 3, style="F")
    
    pdf.set_draw_color(*BRAND_TEAL)
    pdf.set_line_width(0.8)
    pdf.line(cx+6, cy-3, cx+6, cy+3)
    pdf.set_line_width(0.6)
    pdf.line(cx+10, cy-5, cx+10, cy+5)
    pdf.set_line_width(0.4)
    pdf.line(cx+14, cy-7, cx+14, cy+7)


def _add_cover_page(pdf: EkkoScopePDF, data: Dict[str, Any], tenant: Dict[str, Any]):
    """Add professional cover page with branding."""
    pdf.add_page()
    
    _draw_cover_logo(pdf)
    
    pdf.ln(35)
    
    pdf.set_font("Helvetica", "B", 32)
    pdf.set_text_color(*BRAND_TEAL)
    pdf.cell(0, 15, "EkkoScope", align="C")
    pdf.ln(12)
    
    pdf.set_font("Helvetica", "", 14)
    pdf.set_text_color(*MEDIUM_TEXT)
    pdf.cell(0, 8, "GEO Engine for AI Visibility", align="C")
    pdf.ln(25)
    
    pdf.set_draw_color(*BRAND_TEAL)
    pdf.set_line_width(1.5)
    pdf.line(50, pdf.get_y(), 160, pdf.get_y())
    pdf.ln(20)
    
    pdf.set_font("Helvetica", "B", 28)
    pdf.set_text_color(*DARK_TEXT)
    pdf.multi_cell(0, 12, data["tenant_name"], align="C")
    pdf.ln(8)
    
    pdf.set_font("Helvetica", "", 14)
    pdf.set_text_color(*LIGHT_TEXT)
    pdf.cell(0, 8, "AI Visibility Analysis Report", align="C")
    pdf.ln(8)
    
    pdf.set_font("Helvetica", "I", 11)
    pdf.set_text_color(*MEDIUM_TEXT)
    pdf.cell(0, 6, "Comprehensive GEO analysis of how AI assistants recommend your business", align="C")
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
    pdf.ln(5)
    
    geo_focus = tenant.get("geo_focus", [])
    if geo_focus:
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(*LIGHT_TEXT)
        pdf.cell(0, 6, f"Market Focus: {', '.join(geo_focus[:3])}", align="C")


def _add_executive_dashboard(pdf: EkkoScopePDF, data: Dict[str, Any], analysis: Dict[str, Any]):
    """Add executive dashboard with key metrics and summary."""
    pdf.add_page()
    
    pdf.section_header("Executive Dashboard", "Key metrics and insights from your AI visibility analysis")
    pdf.ln(5)
    
    score_counts = data["score_counts"]
    total = data["total_queries"]
    avg = data["average_score"]
    mentioned = data.get("mentioned_count", 0)
    primary = data.get("primary_count", 0)
    
    card_y = pdf.get_y()
    card_height = 38
    card_width = 44
    gap = 4
    
    metrics = [
        ("Queries", str(total), BRAND_BLUE, "Analyzed"),
        ("Visibility", f"{(mentioned/max(total,1)*100):.0f}%", BRAND_TEAL, "Mentioned"),
        ("Primary", str(primary), SUCCESS_GREEN, "Top Pick"),
        ("Avg Score", f"{avg:.1f}/2", WARNING_YELLOW if avg < 1 else BRAND_TEAL, "Score"),
    ]
    
    for i, (label, value, color, sublabel) in enumerate(metrics):
        x = 10 + (card_width + gap) * i
        
        pdf.set_fill_color(*ACCENT_BG)
        pdf.set_draw_color(*color)
        pdf.set_line_width(0.8)
        pdf.rect(x, card_y, card_width, card_height, style="FD")
        
        pdf.set_xy(x, card_y + 4)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*LIGHT_TEXT)
        pdf.cell(card_width, 5, label, align="C")
        
        pdf.set_xy(x, card_y + 12)
        pdf.set_font("Helvetica", "B", 22)
        pdf.set_text_color(*color)
        pdf.cell(card_width, 12, value, align="C")
        
        pdf.set_xy(x, card_y + 28)
        pdf.set_font("Helvetica", "", 7)
        pdf.set_text_color(*LIGHT_TEXT)
        pdf.cell(card_width, 5, sublabel, align="C")
    
    pdf.set_y(card_y + card_height + 15)
    
    pdf.subsection_header("Score Distribution by Intent")
    
    bar_y = pdf.get_y()
    bar_height = 10
    max_width = 100
    
    score_labels = [
        ("Score 0 - Not Mentioned", score_counts.get(0, 0), ERROR_RED),
        ("Score 1 - Mentioned", score_counts.get(1, 0), WARNING_YELLOW),
        ("Score 2 - Primary Recommendation", score_counts.get(2, 0), SUCCESS_GREEN),
    ]
    
    for label, count, color in score_labels:
        width = (count / max(total, 1)) * max_width if total > 0 else 0
        
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*MEDIUM_TEXT)
        pdf.cell(70, bar_height, label, align="L")
        
        if width > 0:
            pdf.set_fill_color(*color)
            pdf.rect(80, bar_y + 2, width, bar_height - 4, style="F")
        
        pdf.set_text_color(*DARK_TEXT)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_xy(185, bar_y)
        pdf.cell(15, bar_height, f"{count}", align="R")
        
        bar_y += bar_height + 2
        pdf.set_y(bar_y)
    
    pdf.ln(10)
    
    pdf.subsection_header("Executive Summary")
    
    genius = data.get("genius_insights")
    try:
        bullets = generate_executive_summary(genius, analysis)
    except Exception:
        bullets = ["Genius Mode insights unavailable for this run."]
    
    if not bullets:
        bullets = ["Genius Mode insights unavailable for this run."]
    
    for bullet in bullets[:6]:
        if pdf.get_y() > 250:
            pdf.add_page()
        pdf.bullet_point(str(bullet))
    
    if data.get("visibility_summary"):
        if pdf.get_y() > 240:
            pdf.add_page()
        pdf.ln(5)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*BRAND_BLUE)
        pdf.cell(0, 6, "Analysis Summary", align="L")
        pdf.ln(6)
        
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*MEDIUM_TEXT)
        pdf.multi_cell(0, 4, data["visibility_summary"])


def _add_query_analysis_section(pdf: EkkoScopePDF, data: Dict[str, Any], tenant: Dict[str, Any]):
    """Add detailed query analysis with intent classification - full text, no truncation."""
    pdf.add_page()
    
    pdf.section_header(
        "Query Analysis Details",
        "Comprehensive breakdown of AI visibility across all tested queries"
    )
    pdf.ln(5)
    
    for query_data in data["queries"]:
        if pdf.get_y() > 240:
            pdf.add_page()
        
        query = query_data.get("query", "")
        score = query_data.get("score", 0)
        intent = query_data.get("intent_type", "informational")
        competitors = query_data.get("competitors", [])
        ai_response = query_data.get("response", "")
        
        if score == 2:
            score_color = SUCCESS_GREEN
            score_label = "PRIMARY"
            border_color = SUCCESS_GREEN
        elif score == 1:
            score_color = WARNING_YELLOW
            score_label = "MENTIONED"
            border_color = WARNING_YELLOW
        else:
            score_color = ERROR_RED
            score_label = "NOT FOUND"
            border_color = ERROR_RED
        
        pdf.set_draw_color(*border_color)
        pdf.set_line_width(0.8)
        start_y = pdf.get_y()
        pdf.line(10, start_y, 10, start_y + 4)
        
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*DARK_TEXT)
        pdf.set_x(14)
        pdf.multi_cell(155, 5, query)
        
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*score_color)
        pdf.set_x(175)
        pdf.set_y(start_y)
        pdf.cell(25, 5, score_label, align="R")
        pdf.ln(6)
        
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*PURPLE)
        pdf.set_x(14)
        pdf.cell(0, 4, f"Intent: {intent.replace('_', ' ').title()}", align="L")
        pdf.ln(4)
        
        if competitors:
            pdf.set_text_color(*MEDIUM_TEXT)
            pdf.set_x(14)
            comp_str = "Competitors: " + ", ".join(competitors)
            pdf.multi_cell(0, 4, comp_str)
        pdf.ln(3)
        
        if ai_response:
            pdf.set_fill_color(*ACCENT_BG)
            response_y = pdf.get_y()
            
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(*MEDIUM_TEXT)
            pdf.set_x(14)
            
            pdf.set_fill_color(*ACCENT_BG)
            pdf.rect(14, response_y, 182, 2, style="F")
            pdf.multi_cell(182, 4, ai_response)
            end_y = pdf.get_y()
            pdf.rect(14, response_y, 182, end_y - response_y, style="F")
            pdf.set_xy(14, response_y)
            pdf.multi_cell(182, 4, ai_response)
        
        pdf.ln(8)
    
    pdf.ln(5)
    total = data["total_queries"]
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(*LIGHT_TEXT)
    pdf.cell(0, 5, f"Total: {total} queries analyzed across multiple intent categories", align="L")


def _add_competitor_matrix(pdf: EkkoScopePDF, data: Dict[str, Any]):
    """Add competitor analysis with full name display - no truncation."""
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
        
        name = comp.get("name", "")
        freq = comp.get("frequency", 0)
        share = (freq / max(total_queries, 1)) * 100
        
        if share > 75:
            threat = "Critical"
            threat_color = ERROR_RED
        elif share > 50:
            threat = "High"
            threat_color = WARNING_YELLOW
        elif share > 25:
            threat = "Medium"
            threat_color = BRAND_BLUE
        else:
            threat = "Low"
            threat_color = SUCCESS_GREEN
        
        pdf.set_fill_color(*threat_color)
        pdf.set_text_color(*WHITE)
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(8, 7, f"{idx + 1}", border=0, align="C", fill=True)
        pdf.cell(2, 7, "", border=0)
        
        pdf.set_text_color(*DARK_TEXT)
        if idx == 0:
            pdf.set_font("Helvetica", "B", 10)
        else:
            pdf.set_font("Helvetica", "B", 9)
        pdf.multi_cell(0, 5, name)
        
        pdf.set_x(15)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*MEDIUM_TEXT)
        pdf.cell(45, 5, f"Appearances: {freq} of {total_queries}", align="L")
        pdf.cell(40, 5, f"Share of Voice: {share:.1f}%", align="L")
        
        pdf.set_text_color(*threat_color)
        pdf.set_font("Helvetica", "B", 8)
        pdf.cell(40, 5, f"Threat: {threat}", align="L")
        pdf.ln(8)
    
    pdf.ln(5)
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(*LIGHT_TEXT)
    pdf.multi_cell(0, 4, "Threat Level indicates how often a competitor appears in AI recommendations relative to total queries. Critical = appears in 75%+ of queries.")


def _add_multi_source_visibility(pdf: EkkoScopePDF, data: Dict[str, Any]):
    """Add multi-source visibility comparison (OpenAI, Perplexity, Gemini)."""
    pdf.add_page()
    
    multi_llm = data.get("multi_llm_visibility")
    providers_used = multi_llm.get("providers_used", []) if multi_llm else []
    
    perplexity_data = data.get("perplexity_visibility")
    perplexity_enabled = perplexity_data and perplexity_data.get("enabled", False)
    
    pdf.section_header(
        "Multi-Source AI Visibility Matrix",
        "Cross-platform comparison of your visibility across multiple AI assistants"
    )
    pdf.ln(5)
    
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*BRAND_BLUE)
    pdf.cell(0, 8, "AI Providers Analyzed", align="L")
    pdf.ln(8)
    
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*DARK_TEXT)
    
    provider_descriptions = {
        "openai_sim": "OpenAI (ChatGPT) - Simulated assistant recommendations",
        "perplexity_web": "Perplexity - Web-grounded real-time search visibility",
        "gemini_sim": "Google Gemini - Simulated AI assistant recommendations"
    }
    
    if providers_used:
        for provider in providers_used:
            desc = provider_descriptions.get(provider, provider)
            pdf.bullet_point(desc)
    else:
        pdf.bullet_point("OpenAI GPT-4o-mini - Simulated AI recommendations")
        if perplexity_enabled:
            pdf.bullet_point("Perplexity Sonar - Web-grounded real-time visibility")
    
    site_snapshot = data.get("site_snapshot")
    if site_snapshot and site_snapshot.get("pages"):
        pdf.bullet_point("Site Content Analysis - Current website content review")
    
    pdf.ln(8)
    
    multi_llm_queries = multi_llm.get("queries", []) if multi_llm else []
    
    provider_labels = {
        "openai_sim": "OpenAI",
        "perplexity_web": "Perplexity",
        "gemini_sim": "Gemini"
    }
    
    if multi_llm_queries and len(providers_used) > 1:
        pdf.subsection_header("AI Provider Visibility Analysis")
        
        for idx, q_agg in enumerate(multi_llm_queries):
            if pdf.get_y() > 220:
                pdf.add_page()
            
            query = q_agg.get("query", "")
            intent = q_agg.get("intent", "")
            
            pdf.set_fill_color(*BRAND_TEAL)
            pdf.set_text_color(*WHITE)
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(10, 7, f"{idx + 1}.", border=0, align="R", fill=True)
            pdf.cell(0, 7, "", border=0, fill=True)
            pdf.ln()
            
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(*DARK_TEXT)
            pdf.multi_cell(0, 5, query)
            
            if intent:
                pdf.set_font("Helvetica", "I", 8)
                pdf.set_text_color(*LIGHT_TEXT)
                pdf.cell(0, 4, f"Intent: {intent}", align="L")
                pdf.ln(5)
            else:
                pdf.ln(2)
            
            providers_data = q_agg.get("providers", [])
            providers_by_name = {p.get("provider"): p for p in providers_data}
            
            all_competitors = []
            
            status_x = 15
            for provider in ["openai_sim", "perplexity_web", "gemini_sim"]:
                if provider in providers_used:
                    pv = providers_by_name.get(provider, {})
                    target_found = pv.get("target_found", False)
                    label = provider_labels.get(provider, provider)
                    
                    pdf.set_font("Helvetica", "", 8)
                    pdf.set_text_color(*MEDIUM_TEXT)
                    pdf.set_x(status_x)
                    pdf.cell(25, 5, f"{label}:", align="L")
                    
                    if target_found:
                        pdf.set_text_color(*SUCCESS_GREEN)
                        pdf.set_font("Helvetica", "B", 8)
                        pdf.cell(20, 5, "FOUND", align="L")
                    else:
                        pdf.set_text_color(*ERROR_RED)
                        pdf.set_font("Helvetica", "B", 8)
                        pdf.cell(20, 5, "Missing", align="L")
                    
                    status_x += 48
                    
                    for brand in pv.get("recommended_brands", [])[:3]:
                        name = brand.get("name", "") if isinstance(brand, dict) else str(brand)
                        if name and name not in all_competitors:
                            all_competitors.append(name)
            
            pdf.ln()
            
            if all_competitors:
                pdf.set_font("Helvetica", "", 8)
                pdf.set_text_color(*MEDIUM_TEXT)
                pdf.set_x(15)
                comp_str = "Competitors mentioned: " + ", ".join(all_competitors)
                pdf.multi_cell(0, 4, comp_str)
            
            pdf.ln(6)
        
        pdf.ln(3)
        
        summary = multi_llm.get("summary", {}) if multi_llm else {}
        provider_stats = summary.get("provider_stats", {})
        
        if provider_stats:
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(*BRAND_BLUE)
            pdf.cell(0, 8, "Visibility by Provider", align="L")
            pdf.ln(6)
            
            pdf.set_font("Helvetica", "", 9)
            for provider, stats in provider_stats.items():
                if stats.get("total_probes", 0) > 0:
                    label = provider_labels.get(provider, provider)
                    found = stats.get("target_found", 0)
                    total = stats.get("successful_probes", 0)
                    pct = stats.get("target_percent", 0)
                    
                    pdf.set_text_color(*DARK_TEXT)
                    pdf.cell(40, 5, f"{label}:", align="L")
                    
                    if pct >= 50:
                        pdf.set_text_color(*SUCCESS_GREEN)
                    elif pct >= 25:
                        pdf.set_text_color(*WARNING_YELLOW)
                    else:
                        pdf.set_text_color(*ERROR_RED)
                    
                    pdf.cell(0, 5, f"Found in {found}/{total} queries ({pct:.1f}%)", align="L")
                    pdf.ln()
    
    elif perplexity_enabled:
        perplexity_queries_list = perplexity_data.get("queries", []) if perplexity_data else []
        
        if perplexity_queries_list:
            pdf.subsection_header("OpenAI vs Perplexity Visibility Analysis")
            
            perplexity_queries = {q.get("query", ""): q for q in perplexity_queries_list}
            
            for idx, query_data in enumerate(data["queries"]):
                if pdf.get_y() > 220:
                    pdf.add_page()
                
                query = query_data.get("query", "")
                openai_score = query_data.get("score", 0)
                
                perp_data = perplexity_queries.get(query, {})
                perp_parsed = perp_data.get("data", {})
                perp_mentioned = perp_parsed.get("target_business_found", False) if perp_parsed else False
                
                competitors = query_data.get("competitors", [])
                
                pdf.set_fill_color(*BRAND_TEAL)
                pdf.set_text_color(*WHITE)
                pdf.set_font("Helvetica", "B", 9)
                pdf.cell(10, 7, f"{idx + 1}.", border=0, align="R", fill=True)
                pdf.cell(0, 7, "", border=0, fill=True)
                pdf.ln()
                
                pdf.set_font("Helvetica", "B", 9)
                pdf.set_text_color(*DARK_TEXT)
                pdf.multi_cell(0, 5, query)
                pdf.ln(2)
                
                pdf.set_font("Helvetica", "", 8)
                pdf.set_text_color(*MEDIUM_TEXT)
                pdf.set_x(15)
                pdf.cell(25, 5, "OpenAI:", align="L")
                if openai_score == 2:
                    pdf.set_text_color(*SUCCESS_GREEN)
                    pdf.set_font("Helvetica", "B", 8)
                    pdf.cell(30, 5, "Primary", align="L")
                elif openai_score == 1:
                    pdf.set_text_color(*WARNING_YELLOW)
                    pdf.set_font("Helvetica", "B", 8)
                    pdf.cell(30, 5, "Mentioned", align="L")
                else:
                    pdf.set_text_color(*ERROR_RED)
                    pdf.set_font("Helvetica", "B", 8)
                    pdf.cell(30, 5, "Not Found", align="L")
                
                pdf.set_font("Helvetica", "", 8)
                pdf.set_text_color(*MEDIUM_TEXT)
                pdf.cell(25, 5, "Perplexity:", align="L")
                if perp_mentioned:
                    pdf.set_text_color(*SUCCESS_GREEN)
                    pdf.set_font("Helvetica", "B", 8)
                    pdf.cell(20, 5, "FOUND", align="L")
                else:
                    pdf.set_text_color(*ERROR_RED)
                    pdf.set_font("Helvetica", "B", 8)
                    pdf.cell(20, 5, "Missing", align="L")
                pdf.ln()
                
                if competitors:
                    pdf.set_font("Helvetica", "", 8)
                    pdf.set_text_color(*MEDIUM_TEXT)
                    pdf.set_x(15)
                    comp_str = "Competitors mentioned: " + ", ".join(competitors)
                    pdf.multi_cell(0, 4, comp_str)
                
                pdf.ln(6)
    else:
        pdf.set_fill_color(*ACCENT_BG)
        pdf.set_draw_color(*BRAND_BLUE)
        pdf.rect(10, pdf.get_y(), 190, 30, style="FD")
        
        pdf.set_xy(15, pdf.get_y() + 5)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*BRAND_BLUE)
        pdf.cell(0, 6, "Multi-LLM Visibility Analysis", align="L")
        
        pdf.set_xy(15, pdf.get_y() + 10)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*MEDIUM_TEXT)
        pdf.multi_cell(180, 4, "Multi-provider visibility analysis was not available for this audit. Enable Perplexity and/or Gemini API keys to see cross-platform visibility data from multiple AI assistants.")
        
        pdf.ln(20)
    
    pdf.ln(10)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*DARK_TEXT)
    pdf.cell(0, 8, "Understanding Your Visibility Gap", align="L")
    pdf.ln(8)
    
    total = data["total_queries"]
    mentioned = data.get("mentioned_count", 0)
    primary = data.get("primary_count", 0)
    
    gap_pct = ((total - mentioned) / max(total, 1)) * 100
    
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*MEDIUM_TEXT)
    pdf.multi_cell(0, 5, f"Your business is missing from {gap_pct:.0f}% of relevant AI-generated recommendations. This represents significant lost visibility and potential customers being directed to competitors instead.")


def _add_genius_insights_section(pdf: EkkoScopePDF, data: Dict[str, Any]):
    """Add Genius Insights with patterns and opportunities."""
    genius = data.get("genius_insights")
    
    if not genius or not isinstance(genius, dict):
        return
    
    patterns = genius.get("patterns", []) or []
    opportunities = genius.get("priority_opportunities", []) or []
    quick_wins = genius.get("quick_wins", []) or []
    future_answers = genius.get("future_ai_answers", []) or []
    
    if not any([patterns, opportunities, quick_wins, future_answers]):
        return
    
    pdf.add_page()
    
    pdf.section_header(
        "Genius Insights & Opportunity Map",
        "Deep strategic analysis powered by AI to uncover hidden patterns and high-value opportunities"
    )
    
    site_note = " with site content analysis" if genius.get("site_analyzed") else ""
    perp_note = " and Perplexity web visibility" if genius.get("perplexity_used") else ""
    if site_note or perp_note:
        pdf.set_font("Helvetica", "I", 9)
        pdf.set_text_color(*LIGHT_TEXT)
        pdf.cell(0, 5, f"Analysis includes:{site_note}{perp_note}", align="L")
        pdf.ln(8)
    
    if patterns:
        pdf.subsection_header("Patterns in AI Visibility", BRAND_BLUE)
        
        for idx, pattern in enumerate(patterns, 1):
            if pdf.get_y() > 220:
                pdf.add_page()
            
            if isinstance(pattern, dict):
                summary = pattern.get("summary", "")
                evidence = pattern.get("evidence", [])
                implication = pattern.get("implication", "")
                
                pdf.set_font("Helvetica", "B", 10)
                pdf.set_text_color(*DARK_TEXT)
                pdf.multi_cell(0, 5, f"{idx}. {summary}")
                pdf.ln(2)
                
                if evidence and isinstance(evidence, list):
                    pdf.set_font("Helvetica", "", 9)
                    pdf.set_text_color(*MEDIUM_TEXT)
                    for ev in evidence:
                        if pdf.get_y() > 260:
                            pdf.add_page()
                        pdf.set_x(15)
                        pdf.multi_cell(175, 4, f"  > {str(ev)}")
                
                if implication:
                    if pdf.get_y() > 260:
                        pdf.add_page()
                    pdf.set_font("Helvetica", "I", 9)
                    pdf.set_text_color(*PURPLE)
                    pdf.set_x(15)
                    pdf.multi_cell(175, 4, f"Impact: {implication}")
            else:
                pdf.set_font("Helvetica", "", 10)
                pdf.set_text_color(*DARK_TEXT)
                pdf.multi_cell(0, 5, f"{idx}. {str(pattern)}")
            
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
            
            query = opp.get("query", "")
            impact = opp.get("impact_score", opp.get("intent_value", 5))
            effort = opp.get("effort", "medium")
            intent_type = opp.get("intent_type", "")
            money_reason = opp.get("money_reason", opp.get("reason", ""))
            
            pdf.set_fill_color(236, 253, 245)
            pdf.set_draw_color(*SUCCESS_GREEN)
            pdf.set_line_width(0.5)
            
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(*SUCCESS_GREEN)
            pdf.set_x(12)
            pdf.multi_cell(0, 5, f"{idx}. {query}")
            pdf.ln(2)
            
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(*BRAND_BLUE)
            pdf.set_x(15)
            effort_str = str(effort).capitalize() if effort else "Medium"
            intent_str = f" | Intent: {intent_type.replace('_', ' ').title()}" if intent_type else ""
            pdf.cell(0, 5, f"Impact: {impact}/10  |  Effort: {effort_str}{intent_str}", align="L")
            pdf.ln(6)
            
            if money_reason:
                if pdf.get_y() > 260:
                    pdf.add_page()
                pdf.set_font("Helvetica", "", 9)
                pdf.set_text_color(*MEDIUM_TEXT)
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
            
            win_text = str(win) if isinstance(win, str) else str(win)
            pdf.numbered_item(idx, win_text)
    
    if future_answers:
        if pdf.get_y() > 200:
            pdf.add_page()
        else:
            pdf.ln(10)
        
        pdf.subsection_header("Future AI Answers (Preview)", PURPLE)
        
        pdf.set_font("Helvetica", "I", 9)
        pdf.set_text_color(*MEDIUM_TEXT)
        pdf.multi_cell(0, 4, "Preview of how AI assistants could respond once your visibility improves:")
        pdf.ln(5)
        
        for fa in future_answers:
            if pdf.get_y() > 220:
                pdf.add_page()
            
            if not isinstance(fa, dict):
                continue
            
            query = fa.get("query", "")
            answer = fa.get("example_answer", "")
            
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(*DARK_TEXT)
            pdf.multi_cell(0, 5, f"Q: {query}")
            pdf.ln(3)
            
            pdf.set_fill_color(*ACCENT_BG)
            start_y = pdf.get_y()
            
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(*MEDIUM_TEXT)
            pdf.set_x(15)
            pdf.multi_cell(180, 4, answer)
            
            end_y = pdf.get_y()
            pdf.rect(12, start_y - 2, 186, end_y - start_y + 4, style="F")
            pdf.set_xy(15, start_y)
            pdf.multi_cell(180, 4, answer)
            
            pdf.ln(8)


def _add_page_blueprints_section(pdf: EkkoScopePDF, data: Dict[str, Any], tenant: Dict[str, Any]):
    """Add detailed page blueprints for high-priority opportunities - full content, no truncation."""
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
        
        query = opp.get("query", "Untitled Page")
        impact = opp.get("impact_score", 5)
        effort = opp.get("effort", "medium")
        
        pdf.set_fill_color(*BRAND_TEAL)
        pdf.set_text_color(*WHITE)
        pdf.set_font("Helvetica", "B", 11)
        pdf.multi_cell(0, 8, f"Blueprint {idx}: {query}", fill=True)
        pdf.ln(3)
        
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*LIGHT_TEXT)
        pdf.cell(0, 5, f"Impact: {impact}/10  |  Effort: {str(effort).capitalize()}  |  Target: {region_str}", align="L")
        pdf.ln(8)
        
        slug = str(recommended_page.get("slug", "") or "")
        seo_title = str(recommended_page.get("seo_title", "") or "")
        h1 = str(recommended_page.get("h1", "") or "")
        outline = recommended_page.get("outline", [])
        internal_links = recommended_page.get("internal_links", [])
        note_on_site = recommended_page.get("note_on_current_site", "")
        
        if slug:
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(*DARK_TEXT)
            pdf.cell(25, 5, "URL:", align="L")
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(*BRAND_BLUE)
            pdf.multi_cell(0, 5, slug)
        
        if seo_title:
            if pdf.get_y() > 260:
                pdf.add_page()
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(*DARK_TEXT)
            pdf.cell(25, 5, "SEO Title:", align="L")
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(*MEDIUM_TEXT)
            pdf.multi_cell(0, 5, seo_title)
        
        if h1:
            if pdf.get_y() > 260:
                pdf.add_page()
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(*DARK_TEXT)
            pdf.cell(25, 5, "H1:", align="L")
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(*MEDIUM_TEXT)
            pdf.multi_cell(0, 5, h1)
        
        if outline and isinstance(outline, list):
            if pdf.get_y() > 240:
                pdf.add_page()
            pdf.ln(3)
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(*DARK_TEXT)
            pdf.cell(0, 5, "Content Outline:", align="L")
            pdf.ln(5)
            
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(*MEDIUM_TEXT)
            for item in outline:
                if pdf.get_y() > 265:
                    pdf.add_page()
                pdf.set_x(20)
                pdf.multi_cell(170, 4, f"> {str(item)}")
                pdf.ln(1)
        
        if internal_links and isinstance(internal_links, list):
            if pdf.get_y() > 250:
                pdf.add_page()
            pdf.ln(2)
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(*DARK_TEXT)
            pdf.cell(0, 5, "Internal Links:", align="L")
            pdf.ln(5)
            
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(*BRAND_BLUE)
            for link in internal_links:
                if pdf.get_y() > 265:
                    pdf.add_page()
                pdf.set_x(20)
                pdf.multi_cell(170, 4, f"> {str(link)}")
                pdf.ln(1)
        
        if note_on_site:
            if pdf.get_y() > 240:
                pdf.add_page()
            pdf.ln(3)
            pdf.set_fill_color(255, 251, 235)
            start_y = pdf.get_y()
            pdf.set_font("Helvetica", "I", 8)
            pdf.set_text_color(*WARNING_YELLOW)
            pdf.set_x(18)
            pdf.multi_cell(174, 4, f"Site Note: {note_on_site}")
            end_y = pdf.get_y()
            pdf.rect(15, start_y - 2, 180, end_y - start_y + 4, style="F")
            pdf.set_xy(18, start_y)
            pdf.multi_cell(174, 4, f"Site Note: {note_on_site}")
        
        pdf.ln(10)


def _add_30_day_action_plan(pdf: EkkoScopePDF, data: Dict[str, Any], tenant: Dict[str, Any]):
    """Add 30-day implementation roadmap - full task descriptions with wrapping."""
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
        
        pdf.set_fill_color(*BRAND_TEAL)
        pdf.set_text_color(*WHITE)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 8, week["title"], align="L", fill=True)
        pdf.ln(9)
        
        pdf.set_font("Helvetica", "I", 9)
        pdf.set_text_color(*MEDIUM_TEXT)
        pdf.cell(0, 5, f"Focus: {week['focus']}", align="L")
        pdf.ln(7)
        
        for task in week["tasks"]:
            if pdf.get_y() > 250:
                pdf.add_page()
            
            pdf.set_fill_color(*ACCENT_BG)
            start_y = pdf.get_y()
            
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(*DARK_TEXT)
            pdf.set_x(12)
            pdf.multi_cell(110, 5, task["task"])
            
            task_end_y = pdf.get_y()
            row_height = max(task_end_y - start_y, 5)
            
            pdf.set_xy(125, start_y)
            impact = task["impact"]
            if impact == "High":
                pdf.set_text_color(*SUCCESS_GREEN)
            elif impact == "Medium":
                pdf.set_text_color(*WARNING_YELLOW)
            else:
                pdf.set_text_color(*LIGHT_TEXT)
            pdf.set_font("Helvetica", "B", 8)
            pdf.cell(18, row_height, impact, align="C")
            
            pdf.set_xy(145, start_y)
            pdf.set_text_color(*BRAND_BLUE)
            pdf.cell(12, row_height, task["effort"], align="C")
            
            pdf.set_xy(160, start_y)
            pdf.set_text_color(*MEDIUM_TEXT)
            pdf.set_font("Helvetica", "", 8)
            pdf.cell(30, row_height, task["owner"], align="L")
            
            pdf.set_y(task_end_y + 2)
        
        pdf.ln(8)
    
    pdf.ln(5)
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(*LIGHT_TEXT)
    pdf.multi_cell(0, 4, "Effort: S = Small (1-2 hours), M = Medium (half day), L = Large (1+ days)")


def _add_recommendations_section(pdf: EkkoScopePDF, data: Dict[str, Any]):
    """Add grouped recommendations section - full content, no truncation."""
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
        "update_page": ("Pages to Update", BRAND_BLUE),
        "faq": ("FAQ Content", PURPLE),
        "authority": ("Authority Building", WARNING_YELLOW),
        "branding": ("Branding", PINK),
        "other": ("Other Recommendations", LIGHT_TEXT)
    }
    
    for rec_type, suggestions in recommendations.items():
        if not suggestions:
            continue
        
        if pdf.get_y() > 200:
            pdf.add_page()
        
        label, color = type_config.get(rec_type, (rec_type.replace("_", " ").title(), LIGHT_TEXT))
        
        pdf.set_fill_color(*color)
        pdf.set_text_color(*WHITE)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(55, 7, label, align="C", fill=True)
        pdf.ln(10)
        
        for suggestion in suggestions:
            if pdf.get_y() > 230:
                pdf.add_page()
            
            title = suggestion.get("title", "")
            details = suggestion.get("details", "")
            
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(*DARK_TEXT)
            pdf.multi_cell(0, 5, title)
            pdf.ln(2)
            
            if details:
                if pdf.get_y() > 260:
                    pdf.add_page()
                pdf.set_font("Helvetica", "", 9)
                pdf.set_text_color(*MEDIUM_TEXT)
                pdf.set_x(15)
                pdf.multi_cell(175, 4, details)
            
            pdf.ln(5)
        
        pdf.ln(5)
