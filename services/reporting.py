"""
PDF Report Generation for EchoScope GEO Visibility Analysis
Uses fpdf2 to create professional, client-ready PDF reports.
"""

from datetime import datetime
from typing import Dict, Any, List
from fpdf import FPDF
from collections import Counter


class EchoScopePDF(FPDF):
    """Custom PDF class with EchoScope branding and automatic page numbering."""
    
    def __init__(self, tenant_name: str):
        super().__init__()
        self.tenant_name = tenant_name
        self.set_auto_page_break(auto=True, margin=25)
    
    def header(self):
        if self.page_no() > 1:
            self.set_font("Helvetica", "I", 9)
            self.set_text_color(100, 100, 100)
            self.cell(0, 10, f"EchoScope Report - {self.tenant_name}", align="L")
            self.ln(15)
    
    def footer(self):
        self.set_y(-20)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(100, 100, 100)
        self.cell(0, 10, "EchoScope - AI GEO Visibility Scanner", align="L")
        self.cell(0, 10, f"Page {self.page_no()} of {{nb}}", align="R")


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
        "visibility_summary": analysis.get("visibility_summary", "")
    }


def build_echoscope_pdf(tenant: Dict[str, Any], analysis: Dict[str, Any]) -> bytes:
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
    
    pdf = EchoScopePDF(tenant_name)
    pdf.alias_nb_pages()
    
    _add_cover_page(pdf, data)
    _add_summary_section(pdf, data)
    _add_query_details_section(pdf, data)
    _add_competitor_section(pdf, data)
    _add_recommendations_section(pdf, data)
    
    return pdf.output()


def _add_cover_page(pdf: EchoScopePDF, data: Dict[str, Any]):
    """Add cover page with branding and tenant info."""
    pdf.add_page()
    
    pdf.set_font("Helvetica", "B", 32)
    pdf.set_text_color(56, 102, 220)
    pdf.ln(50)
    pdf.cell(0, 20, "EchoScope", align="C")
    pdf.ln(25)
    
    pdf.set_font("Helvetica", "", 18)
    pdf.set_text_color(60, 60, 60)
    pdf.cell(0, 10, "AI GEO Visibility Report", align="C")
    pdf.ln(40)
    
    pdf.set_font("Helvetica", "B", 24)
    pdf.set_text_color(40, 40, 40)
    pdf.multi_cell(0, 12, data["tenant_name"], align="C")
    pdf.ln(20)
    
    pdf.set_font("Helvetica", "", 12)
    pdf.set_text_color(100, 100, 100)
    
    generated_at = data["generated_at"]
    try:
        dt = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
        formatted_date = dt.strftime("%B %d, %Y at %H:%M UTC")
    except:
        formatted_date = generated_at
    
    pdf.cell(0, 8, f"Generated: {formatted_date}", align="C")
    pdf.ln(60)
    
    pdf.set_font("Helvetica", "I", 10)
    pdf.set_text_color(140, 140, 140)
    pdf.cell(0, 8, "Powered by EchoScope", align="C")


def _add_summary_section(pdf: EchoScopePDF, data: Dict[str, Any]):
    """Add AI visibility summary section."""
    pdf.add_page()
    
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(56, 102, 220)
    pdf.cell(0, 12, "AI Visibility Summary", align="L")
    pdf.ln(15)
    
    pdf.set_draw_color(56, 102, 220)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(10)
    
    total = data["total_queries"]
    avg_score = data["average_score"]
    counts = data["score_counts"]
    
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(40, 40, 40)
    pdf.cell(90, 10, "Queries Analyzed:", align="L")
    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 10, str(total), align="L")
    pdf.ln(8)
    
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(90, 10, "Average Visibility Score:", align="L")
    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 10, f"{avg_score:.2f} / 2.00", align="L")
    pdf.ln(15)
    
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, "Score Distribution", align="L")
    pdf.ln(10)
    
    score_labels = {
        2: ("Top Recommendation", 46, 160, 67),
        1: ("Mentioned (Not Top)", 255, 193, 7),
        0: ("Not Recommended", 220, 53, 69)
    }
    
    for score in [2, 1, 0]:
        label, r, g, b = score_labels[score]
        count = counts.get(score, 0)
        percentage = (count / total * 100) if total > 0 else 0
        
        pdf.set_fill_color(r, g, b)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(30, 8, f"Score {score}", align="C", fill=True)
        
        pdf.set_text_color(40, 40, 40)
        pdf.set_font("Helvetica", "", 11)
        pdf.cell(60, 8, f"  {label}", align="L")
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 8, f"{count} queries ({percentage:.0f}%)", align="L")
        pdf.ln(10)
    
    pdf.ln(10)
    
    if data.get("visibility_summary"):
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(40, 40, 40)
        pdf.cell(0, 10, "Key Insights", align="L")
        pdf.ln(8)
        
        pdf.set_font("Helvetica", "", 11)
        pdf.set_text_color(60, 60, 60)
        pdf.multi_cell(0, 6, data["visibility_summary"])


def _add_query_details_section(pdf: EchoScopePDF, data: Dict[str, Any]):
    """Add per-query details table."""
    pdf.add_page()
    
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(56, 102, 220)
    pdf.cell(0, 12, "Per-Query Analysis", align="L")
    pdf.ln(15)
    
    pdf.set_draw_color(56, 102, 220)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(10)
    
    col_widths = [100, 25, 65]
    headers = ["Query", "Score", "Status"]
    
    pdf.set_fill_color(56, 102, 220)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 10)
    
    for i, header in enumerate(headers):
        pdf.cell(col_widths[i], 10, header, border=1, align="C", fill=True)
    pdf.ln()
    
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(40, 40, 40)
    
    for query_result in data["queries"]:
        query_text = query_result.get("query", "")
        score = query_result.get("score", 0)
        
        if score == 2:
            status = "Top Recommendation"
            pdf.set_fill_color(230, 255, 230)
        elif score == 1:
            status = "Mentioned"
            pdf.set_fill_color(255, 250, 230)
        else:
            status = "Not Mentioned"
            pdf.set_fill_color(255, 235, 235)
        
        if len(query_text) > 55:
            query_text = query_text[:52] + "..."
        
        if pdf.get_y() > 260:
            pdf.add_page()
            pdf.set_fill_color(56, 102, 220)
            pdf.set_text_color(255, 255, 255)
            pdf.set_font("Helvetica", "B", 10)
            for i, header in enumerate(headers):
                pdf.cell(col_widths[i], 10, header, border=1, align="C", fill=True)
            pdf.ln()
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(40, 40, 40)
            
            if score == 2:
                pdf.set_fill_color(230, 255, 230)
            elif score == 1:
                pdf.set_fill_color(255, 250, 230)
            else:
                pdf.set_fill_color(255, 235, 235)
        
        pdf.cell(col_widths[0], 10, query_text, border=1, align="L", fill=True)
        pdf.cell(col_widths[1], 10, str(score), border=1, align="C", fill=True)
        pdf.cell(col_widths[2], 10, status, border=1, align="C", fill=True)
        pdf.ln()


def _add_competitor_section(pdf: EchoScopePDF, data: Dict[str, Any]):
    """Add competitor overview section."""
    competitors = data.get("top_competitors", [])
    
    if not competitors:
        return
    
    pdf.add_page()
    
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(56, 102, 220)
    pdf.cell(0, 12, "Competitor Overview", align="L")
    pdf.ln(15)
    
    pdf.set_draw_color(56, 102, 220)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(10)
    
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(60, 60, 60)
    pdf.multi_cell(0, 6, "These businesses were mentioned in AI responses across your analyzed queries. Understanding your competition helps identify opportunities for improvement.")
    pdf.ln(10)
    
    total_queries = data["total_queries"]
    
    col_widths = [120, 70]
    headers = ["Competitor", "Appearances"]
    
    pdf.set_fill_color(56, 102, 220)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 10)
    
    for i, header in enumerate(headers):
        pdf.cell(col_widths[i], 10, header, border=1, align="C", fill=True)
    pdf.ln()
    
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(40, 40, 40)
    pdf.set_fill_color(248, 249, 250)
    
    for idx, competitor in enumerate(competitors):
        name = competitor.get("name", "Unknown")
        freq = competitor.get("frequency", 0)
        
        if len(name) > 60:
            name = name[:57] + "..."
        
        fill = idx % 2 == 0
        pdf.cell(col_widths[0], 10, name, border=1, align="L", fill=fill)
        pdf.cell(col_widths[1], 10, f"{freq} of {total_queries} queries", border=1, align="C", fill=fill)
        pdf.ln()


def _add_recommendations_section(pdf: EchoScopePDF, data: Dict[str, Any]):
    """Add grouped recommendations section."""
    recommendations = data.get("recommendations", {})
    
    if not recommendations:
        return
    
    pdf.add_page()
    
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(56, 102, 220)
    pdf.cell(0, 12, "Recommended Actions", align="L")
    pdf.ln(15)
    
    pdf.set_draw_color(56, 102, 220)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(10)
    
    type_labels = {
        "new_page": "New Pages",
        "update_page": "Page Updates",
        "faq": "FAQ Content",
        "authority": "Authority Building",
        "branding": "Branding",
        "other": "Other Recommendations"
    }
    
    type_colors = {
        "new_page": (40, 167, 69),
        "update_page": (0, 123, 255),
        "faq": (255, 193, 7),
        "authority": (111, 66, 193),
        "branding": (253, 126, 20),
        "other": (108, 117, 125)
    }
    
    for rec_type, suggestions in recommendations.items():
        if not suggestions:
            continue
        
        if pdf.get_y() > 240:
            pdf.add_page()
        
        label = type_labels.get(rec_type, rec_type.title())
        r, g, b = type_colors.get(rec_type, (108, 117, 125))
        
        pdf.set_fill_color(r, g, b)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(60, 8, label, align="C", fill=True)
        pdf.ln(12)
        
        for suggestion in suggestions[:5]:
            if pdf.get_y() > 260:
                pdf.add_page()
            
            title = suggestion.get("title", "")
            details = suggestion.get("details", "")
            
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(40, 40, 40)
            pdf.cell(5, 6, chr(149), align="L")
            pdf.cell(0, 6, title, align="L")
            pdf.ln(6)
            
            if details:
                pdf.set_font("Helvetica", "", 9)
                pdf.set_text_color(80, 80, 80)
                pdf.set_x(15)
                pdf.multi_cell(180, 5, details)
                pdf.ln(4)
        
        pdf.ln(8)
