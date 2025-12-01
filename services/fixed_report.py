"""
Fixed Report PDF Generator for EkkoScope v4
Generates before/after comparison reports showing remediation results.
"""

import os
from datetime import datetime
from typing import Dict, Any, List
from fpdf import FPDF
from services.ekkoscope_sentinel import log_report_generated


BLACK_BG = (10, 10, 15)
CYAN_GLOW = (0, 240, 255)
NEON_GREEN = (0, 255, 128)
BLOOD_RED = (255, 0, 0)
WHITE_TEXT = (255, 255, 255)
DARK_GRAY = (40, 40, 50)
MEDIUM_GRAY = (100, 100, 110)
LIGHT_GRAY = (150, 150, 160)
PURPLE = (180, 100, 255)


def sanitize_text(text: str) -> str:
    """Replace unsupported Unicode characters."""
    if not text:
        return ""
    
    replacements = {
        '"': '"', '"': '"', ''': "'", ''': "'",
        '–': '-', '—': '-', '…': '...', '•': '*',
        '→': '->', '←': '<-', '✓': '[OK]', '✗': '[X]',
        '\u00A0': ' ', '\u2002': ' ', '\u2003': ' ',
    }
    
    for u, a in replacements.items():
        text = text.replace(u, a)
    
    return ''.join(c if ord(c) < 128 else '?' for c in text)


class FixedReportPDF(FPDF):
    """PDF class for Fixed Report with before/after comparison."""
    
    def __init__(self, business_name: str):
        super().__init__()
        self.business_name = business_name
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
            self._draw_mini_logo()
            self.set_font(self.default_font, "", 8)
            self.set_text_color(*LIGHT_GRAY)
            self.set_xy(30, 8)
            self.cell(0, 10, f"FIXED REPORT - {self.business_name}", align="L")
    
    def _draw_mini_logo(self):
        """Draw small radar logo in header."""
        cx, cy = 15, 12
        self.set_draw_color(*NEON_GREEN)
        self.set_line_width(0.4)
        self.ellipse(cx-5, cy-5, 10, 10)
        self.set_fill_color(*NEON_GREEN)
        self.ellipse(cx-1, cy-1, 2, 2, style="F")
    
    def footer(self):
        self.set_y(-20)
        self.set_font(self.default_font, "", 7)
        self.set_text_color(*MEDIUM_GRAY)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}} | Powered by EkkoScope FixEngine", align="C")


def build_fixed_report_pdf(
    business_name: str,
    remediation_result: Dict[str, Any],
    original_analysis: Dict[str, Any] = None
) -> bytes:
    """Generate a Fixed Report PDF with before/after comparison."""
    
    pdf = FixedReportPDF(business_name)
    pdf.alias_nb_pages()
    
    _add_cover_page(pdf, business_name, remediation_result)
    _add_improvement_dashboard(pdf, remediation_result)
    _add_agent_results(pdf, remediation_result)
    _add_content_fixes_section(pdf, remediation_result)
    _add_seo_fixes_section(pdf, remediation_result)
    _add_deployment_section(pdf, remediation_result)
    _add_next_steps_section(pdf, remediation_result)
    _add_bundle_upsell_page(pdf, business_name)
    
    log_report_generated(business_name, "fixed_report", pages=pdf.page_no())
    
    return pdf.output()


def _add_cover_page(pdf: FixedReportPDF, business_name: str, result: Dict[str, Any]):
    """Add cover page with dramatic before/after visualization."""
    pdf.add_page()
    
    cx, cy = 105, 50
    pdf.set_draw_color(*NEON_GREEN)
    pdf.set_line_width(1.5)
    pdf.ellipse(cx-20, cy-20, 40, 40)
    pdf.set_line_width(1.0)
    pdf.ellipse(cx-14, cy-14, 28, 28)
    pdf.set_line_width(0.6)
    pdf.ellipse(cx-8, cy-8, 16, 16)
    pdf.set_fill_color(*NEON_GREEN)
    pdf.ellipse(cx-3, cy-3, 6, 6, style="F")
    
    pdf.set_draw_color(*NEON_GREEN)
    pdf.set_line_width(1.5)
    pdf.line(cx+10, cy-8, cx+10, cy+8)
    pdf.line(cx+16, cy-12, cx+16, cy+12)
    pdf.line(cx+22, cy-6, cx+22, cy+6)
    
    pdf.ln(55)
    pdf.set_font(pdf.default_font, "B", 28)
    pdf.set_text_color(*NEON_GREEN)
    pdf.cell(0, 12, "FIXED REPORT", align="C", ln=True)
    
    pdf.set_font(pdf.default_font, "", 10)
    pdf.set_text_color(*CYAN_GLOW)
    pdf.cell(0, 8, "AI VISIBILITY REMEDIATION COMPLETE", align="C", ln=True)
    
    pdf.ln(10)
    pdf.set_font(pdf.default_font, "B", 18)
    pdf.set_text_color(*WHITE_TEXT)
    pdf.cell(0, 10, sanitize_text(business_name), align="C", ln=True)
    
    summary = result.get("summary", {})
    original = summary.get("original_visibility", "0%")
    projected = summary.get("projected_visibility", "0%")
    
    pdf.ln(20)
    
    pdf.set_fill_color(*DARK_GRAY)
    pdf.rect(25, pdf.get_y(), 70, 50, 'F')
    pdf.rect(115, pdf.get_y(), 70, 50, 'F')
    
    box_y = pdf.get_y()
    
    pdf.set_xy(25, box_y + 5)
    pdf.set_font(pdf.default_font, "", 10)
    pdf.set_text_color(*BLOOD_RED)
    pdf.cell(70, 8, "BEFORE", align="C", ln=True)
    
    pdf.set_xy(25, box_y + 18)
    pdf.set_font(pdf.default_font, "B", 28)
    pdf.cell(70, 15, original, align="C", ln=True)
    
    pdf.set_xy(25, box_y + 38)
    pdf.set_font(pdf.default_font, "", 8)
    pdf.set_text_color(*LIGHT_GRAY)
    pdf.cell(70, 6, "AI Visibility", align="C")
    
    pdf.set_xy(115, box_y + 5)
    pdf.set_font(pdf.default_font, "", 10)
    pdf.set_text_color(*NEON_GREEN)
    pdf.cell(70, 8, "AFTER", align="C", ln=True)
    
    pdf.set_xy(115, box_y + 18)
    pdf.set_font(pdf.default_font, "B", 28)
    pdf.cell(70, 15, projected, align="C", ln=True)
    
    pdf.set_xy(115, box_y + 38)
    pdf.set_font(pdf.default_font, "", 8)
    pdf.set_text_color(*LIGHT_GRAY)
    pdf.cell(70, 6, "AI Visibility", align="C")
    
    pdf.set_xy(88, box_y + 18)
    pdf.set_font(pdf.default_font, "B", 20)
    pdf.set_text_color(*CYAN_GLOW)
    pdf.cell(24, 15, "->", align="C")
    
    pdf.set_y(box_y + 60)
    pdf.ln(10)
    
    pdf.set_font(pdf.default_font, "", 9)
    pdf.set_text_color(*LIGHT_GRAY)
    pdf.cell(0, 6, f"Generated: {datetime.utcnow().strftime('%B %d, %Y at %H:%M UTC')}", align="C", ln=True)
    pdf.cell(0, 6, f"Fixes Applied: {summary.get('total_fixes', 0)}", align="C", ln=True)


def _add_improvement_dashboard(pdf: FixedReportPDF, result: Dict[str, Any]):
    """Add improvement metrics dashboard."""
    pdf.add_page()
    
    pdf.set_font(pdf.default_font, "B", 16)
    pdf.set_text_color(*NEON_GREEN)
    pdf.cell(0, 10, "IMPROVEMENT DASHBOARD", align="L", ln=True)
    
    pdf.set_draw_color(*DARK_GRAY)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(8)
    
    summary = result.get("summary", {})
    verification = result.get("agents", {}).get("verification", {}).get("output", {})
    
    metrics = [
        ("Original Visibility", summary.get("original_visibility", "0%"), BLOOD_RED),
        ("Projected Visibility", summary.get("projected_visibility", "0%"), NEON_GREEN),
        ("Improvement Delta", f"+{verification.get('improvement_delta', 0)}%", CYAN_GLOW),
        ("Total Fixes Applied", str(summary.get("total_fixes", 0)), WHITE_TEXT),
        ("Confidence Level", verification.get("confidence", "high").upper(), PURPLE),
    ]
    
    for label, value, color in metrics:
        pdf.set_fill_color(*DARK_GRAY)
        pdf.rect(15, pdf.get_y(), 180, 12, 'F')
        
        pdf.set_font(pdf.default_font, "", 10)
        pdf.set_text_color(*LIGHT_GRAY)
        pdf.set_x(20)
        pdf.cell(100, 12, label)
        
        pdf.set_font(pdf.default_font, "B", 11)
        pdf.set_text_color(*color)
        pdf.cell(75, 12, value, align="R")
        pdf.ln(15)
    
    breakdown = verification.get("breakdown", [])
    if breakdown:
        pdf.ln(10)
        pdf.set_font(pdf.default_font, "B", 12)
        pdf.set_text_color(*CYAN_GLOW)
        pdf.cell(0, 8, "IMPACT BREAKDOWN", align="L", ln=True)
        pdf.ln(3)
        
        for item in breakdown[:10]:
            pdf.set_font(pdf.default_font, "", 9)
            pdf.set_text_color(*WHITE_TEXT)
            fix_name = item.get("fix", "Unknown fix")
            impact = item.get("impact", "+0%")
            pdf.cell(0, 6, f"  [*] {sanitize_text(fix_name)}: {impact}", ln=True)


def _add_agent_results(pdf: FixedReportPDF, result: Dict[str, Any]):
    """Add section showing each agent's execution results."""
    pdf.add_page()
    
    pdf.set_font(pdf.default_font, "B", 16)
    pdf.set_text_color(*NEON_GREEN)
    pdf.cell(0, 10, "AGENT EXECUTION SUMMARY", align="L", ln=True)
    
    pdf.set_draw_color(*DARK_GRAY)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(8)
    
    agents = result.get("agents", {})
    
    agent_info = [
        ("content", "CONTENT AGENT", "Optimized content, meta descriptions, FAQ sections"),
        ("seo", "SEO AGENT", "Schema markup, structured data, local SEO"),
        ("deploy", "DEPLOY AGENT", "WordPress code, HTML snippets, API payloads"),
        ("verification", "VERIFICATION AGENT", "Before/after analysis, impact calculation"),
    ]
    
    for agent_key, agent_name, description in agent_info:
        agent_data = agents.get(agent_key, {})
        status = agent_data.get("status", "unknown")
        fixes = agent_data.get("fixes_generated", 0)
        
        status_color = NEON_GREEN if status == "completed" else BLOOD_RED
        
        pdf.set_fill_color(*DARK_GRAY)
        pdf.rect(15, pdf.get_y(), 180, 25, 'F')
        
        pdf.set_font(pdf.default_font, "B", 11)
        pdf.set_text_color(*CYAN_GLOW)
        pdf.set_xy(20, pdf.get_y() + 3)
        pdf.cell(100, 8, agent_name)
        
        pdf.set_font(pdf.default_font, "B", 10)
        pdf.set_text_color(*status_color)
        pdf.cell(75, 8, status.upper(), align="R")
        
        pdf.set_xy(20, pdf.get_y() + 10)
        pdf.set_font(pdf.default_font, "", 8)
        pdf.set_text_color(*LIGHT_GRAY)
        pdf.cell(140, 6, description)
        
        pdf.set_text_color(*WHITE_TEXT)
        pdf.cell(35, 6, f"{fixes} fixes", align="R")
        
        pdf.set_y(pdf.get_y() + 18)
        pdf.ln(5)


def _add_content_fixes_section(pdf: FixedReportPDF, result: Dict[str, Any]):
    """Add detailed content fixes section."""
    pdf.add_page()
    
    pdf.set_font(pdf.default_font, "B", 16)
    pdf.set_text_color(*CYAN_GLOW)
    pdf.cell(0, 10, "CONTENT OPTIMIZATIONS", align="L", ln=True)
    
    pdf.set_draw_color(*DARK_GRAY)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(8)
    
    content_output = result.get("agents", {}).get("content", {}).get("output", {})
    
    meta_descriptions = content_output.get("meta_descriptions", [])
    if meta_descriptions:
        pdf.set_font(pdf.default_font, "B", 11)
        pdf.set_text_color(*NEON_GREEN)
        pdf.cell(0, 8, "Meta Descriptions", ln=True)
        pdf.ln(2)
        
        for meta in meta_descriptions:
            content = meta.get("content") or meta.get("meta_description", "")
            if content:
                pdf.set_fill_color(20, 20, 30)
                pdf.rect(15, pdf.get_y(), 180, 20, 'F')
                
                pdf.set_font(pdf.default_font, "", 8)
                pdf.set_text_color(*WHITE_TEXT)
                pdf.set_xy(18, pdf.get_y() + 3)
                pdf.multi_cell(174, 4, sanitize_text(content[:300]))
                pdf.ln(5)
    
    faq_sections = content_output.get("faq_sections", [])
    if faq_sections:
        pdf.ln(5)
        pdf.set_font(pdf.default_font, "B", 11)
        pdf.set_text_color(*NEON_GREEN)
        pdf.cell(0, 8, "FAQ Section", ln=True)
        pdf.ln(2)
        
        for faq_section in faq_sections:
            faq_items = faq_section.get("faq_items", [])
            for i, faq in enumerate(faq_items[:5], 1):
                question = faq.get("question", "")
                answer = faq.get("answer", "")
                
                pdf.set_font(pdf.default_font, "B", 9)
                pdf.set_text_color(*CYAN_GLOW)
                pdf.cell(0, 6, f"Q{i}: {sanitize_text(question[:100])}", ln=True)
                
                pdf.set_font(pdf.default_font, "", 8)
                pdf.set_text_color(*LIGHT_GRAY)
                pdf.multi_cell(0, 4, f"A: {sanitize_text(answer[:200])}")
                pdf.ln(3)


def _add_seo_fixes_section(pdf: FixedReportPDF, result: Dict[str, Any]):
    """Add SEO fixes section with schema markup."""
    pdf.add_page()
    
    pdf.set_font(pdf.default_font, "B", 16)
    pdf.set_text_color(*CYAN_GLOW)
    pdf.cell(0, 10, "SEO & SCHEMA MARKUP", align="L", ln=True)
    
    pdf.set_draw_color(*DARK_GRAY)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(8)
    
    seo_output = result.get("agents", {}).get("seo", {}).get("output", {})
    
    schemas = seo_output.get("schema_markup", [])
    for schema in schemas:
        schema_type = schema.get("schema_type", "Unknown")
        
        pdf.set_font(pdf.default_font, "B", 11)
        pdf.set_text_color(*NEON_GREEN)
        pdf.cell(0, 8, f"Schema: {schema_type}", ln=True)
        
        pdf.set_fill_color(20, 20, 30)
        pdf.rect(15, pdf.get_y(), 180, 25, 'F')
        
        pdf.set_font(pdf.default_font, "", 7)
        pdf.set_text_color(*MEDIUM_GRAY)
        pdf.set_xy(18, pdf.get_y() + 2)
        
        jsonld = schema.get("jsonld", {})
        if jsonld:
            import json
            preview = json.dumps(jsonld, indent=2)[:400]
            pdf.multi_cell(174, 3, sanitize_text(preview))
        
        pdf.ln(8)
    
    local_fixes = seo_output.get("local_seo_fixes", [])
    if local_fixes:
        pdf.ln(5)
        pdf.set_font(pdf.default_font, "B", 11)
        pdf.set_text_color(*CYAN_GLOW)
        pdf.cell(0, 8, "Local SEO Checklist", ln=True)
        pdf.ln(2)
        
        for fix in local_fixes:
            task = fix.get("task", "")
            priority = fix.get("priority", "medium")
            
            color = BLOOD_RED if priority == "high" else CYAN_GLOW
            
            pdf.set_font(pdf.default_font, "", 8)
            pdf.set_text_color(*color)
            pdf.cell(5, 5, "[*]")
            pdf.set_text_color(*WHITE_TEXT)
            pdf.cell(0, 5, f" {sanitize_text(task)}", ln=True)


def _add_deployment_section(pdf: FixedReportPDF, result: Dict[str, Any]):
    """Add deployment code section."""
    pdf.add_page()
    
    pdf.set_font(pdf.default_font, "B", 16)
    pdf.set_text_color(*CYAN_GLOW)
    pdf.cell(0, 10, "DEPLOYMENT CODE", align="L", ln=True)
    
    pdf.set_draw_color(*DARK_GRAY)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(8)
    
    deploy_output = result.get("agents", {}).get("deploy", {}).get("output", {})
    
    instructions = deploy_output.get("deployment_instructions", [])
    if instructions:
        pdf.set_font(pdf.default_font, "B", 11)
        pdf.set_text_color(*NEON_GREEN)
        pdf.cell(0, 8, "Implementation Steps", ln=True)
        pdf.ln(2)
        
        for instr in instructions:
            step = instr.get("step", "")
            action = instr.get("action", "")
            
            pdf.set_font(pdf.default_font, "B", 9)
            pdf.set_text_color(*CYAN_GLOW)
            pdf.cell(10, 6, f"{step}.")
            pdf.set_font(pdf.default_font, "", 9)
            pdf.set_text_color(*WHITE_TEXT)
            pdf.cell(0, 6, sanitize_text(action), ln=True)
    
    pdf.ln(10)
    
    wp_code = deploy_output.get("wordpress_code", {})
    if wp_code.get("code"):
        pdf.set_font(pdf.default_font, "B", 11)
        pdf.set_text_color(*PURPLE)
        pdf.cell(0, 8, "WordPress Code (functions.php)", ln=True)
        
        pdf.set_fill_color(20, 20, 30)
        pdf.rect(15, pdf.get_y(), 180, 40, 'F')
        
        pdf.set_font(pdf.default_font, "", 6)
        pdf.set_text_color(*NEON_GREEN)
        pdf.set_xy(18, pdf.get_y() + 2)
        pdf.multi_cell(174, 3, sanitize_text(wp_code["code"][:600]))
        pdf.ln(5)


def _add_next_steps_section(pdf: FixedReportPDF, result: Dict[str, Any]):
    """Add next steps and recommendations."""
    pdf.add_page()
    
    pdf.set_font(pdf.default_font, "B", 16)
    pdf.set_text_color(*NEON_GREEN)
    pdf.cell(0, 10, "NEXT STEPS", align="L", ln=True)
    
    pdf.set_draw_color(*DARK_GRAY)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(8)
    
    verification = result.get("agents", {}).get("verification", {}).get("output", {})
    next_steps = verification.get("next_steps", [])
    
    for i, step in enumerate(next_steps, 1):
        pdf.set_fill_color(*DARK_GRAY)
        pdf.rect(15, pdf.get_y(), 180, 12, 'F')
        
        pdf.set_font(pdf.default_font, "B", 10)
        pdf.set_text_color(*CYAN_GLOW)
        pdf.set_xy(20, pdf.get_y() + 3)
        pdf.cell(10, 6, f"{i}.")
        
        pdf.set_font(pdf.default_font, "", 9)
        pdf.set_text_color(*WHITE_TEXT)
        pdf.cell(0, 6, sanitize_text(step))
        
        pdf.ln(15)
    
    pdf.ln(10)
    pdf.set_font(pdf.default_font, "B", 12)
    pdf.set_text_color(*CYAN_GLOW)
    pdf.cell(0, 8, "MONITORING RECOMMENDATION", align="C", ln=True)
    
    pdf.ln(5)
    pdf.set_font(pdf.default_font, "", 9)
    pdf.set_text_color(*LIGHT_GRAY)
    pdf.multi_cell(0, 5, "For ongoing visibility optimization, consider EkkoScope Continuous Monitoring at $290/month. Get a fresh report every 14 days with visibility delta tracking and priority email summaries.", align="C")


def _add_bundle_upsell_page(pdf: FixedReportPDF, business_name: str):
    """Add $1188 bundle upsell page."""
    pdf.add_page()
    
    pdf.set_fill_color(15, 15, 25)
    pdf.rect(0, 0, 210, 297, 'F')
    
    pdf.ln(30)
    
    pdf.set_font(pdf.default_font, "B", 24)
    pdf.set_text_color(*NEON_GREEN)
    pdf.cell(0, 12, "UNLOCK FULL POWER", align="C", ln=True)
    
    pdf.set_font(pdf.default_font, "", 12)
    pdf.set_text_color(*CYAN_GLOW)
    pdf.cell(0, 8, "SENTINEL OS + EKKOSCOPE FIX BUNDLE", align="C", ln=True)
    
    pdf.ln(15)
    
    pdf.set_fill_color(*DARK_GRAY)
    pdf.rect(30, pdf.get_y(), 150, 100, 'F')
    
    box_y = pdf.get_y()
    
    pdf.set_xy(30, box_y + 10)
    pdf.set_font(pdf.default_font, "B", 36)
    pdf.set_text_color(*NEON_GREEN)
    pdf.cell(150, 20, "$1,188", align="C", ln=True)
    
    pdf.set_font(pdf.default_font, "", 10)
    pdf.set_text_color(*LIGHT_GRAY)
    pdf.set_xy(30, box_y + 35)
    pdf.cell(150, 6, "One-Time Payment", align="C", ln=True)
    
    pdf.set_xy(30, box_y + 50)
    pdf.set_font(pdf.default_font, "", 9)
    pdf.set_text_color(*WHITE_TEXT)
    
    features = [
        "Sentinel OS Real-Time Monitoring Dashboard",
        "EkkoScope Full GEO Report ($490 value)",
        "Auto-Fix Agent Suite ($498 value)",
        "Before/After Verification Report",
        "Priority Support Channel",
        "12-Month Visibility Tracking"
    ]
    
    for feature in features:
        pdf.set_x(45)
        pdf.set_text_color(*NEON_GREEN)
        pdf.cell(10, 6, "[+]")
        pdf.set_text_color(*WHITE_TEXT)
        pdf.cell(0, 6, feature, ln=True)
    
    pdf.set_y(box_y + 110)
    pdf.ln(15)
    
    pdf.set_font(pdf.default_font, "B", 11)
    pdf.set_text_color(*CYAN_GLOW)
    pdf.cell(0, 8, "Ready to dominate AI visibility?", align="C", ln=True)
    
    pdf.ln(5)
    pdf.set_font(pdf.default_font, "", 9)
    pdf.set_text_color(*LIGHT_GRAY)
    pdf.cell(0, 6, "Contact us at fix@ekkoscope.com or reply to your report email", align="C", ln=True)
    
    pdf.ln(20)
    
    pdf.set_draw_color(*NEON_GREEN)
    pdf.set_line_width(1)
    pdf.rect(50, pdf.get_y(), 110, 20, 'D')
    
    pdf.set_font(pdf.default_font, "B", 12)
    pdf.set_text_color(*NEON_GREEN)
    pdf.set_xy(50, pdf.get_y() + 5)
    pdf.cell(110, 10, "GET THE BUNDLE", align="C")


def save_fixed_report(
    business_name: str,
    remediation_result: Dict[str, Any],
    output_dir: str = "reports"
) -> str:
    """Generate and save fixed report PDF, return file path."""
    
    os.makedirs(output_dir, exist_ok=True)
    
    safe_name = "".join(c if c.isalnum() or c in " _-" else "_" for c in business_name)
    safe_name = safe_name.replace(" ", "_")
    
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"fixed_{safe_name}_{timestamp}.pdf"
    filepath = os.path.join(output_dir, filename)
    
    pdf_bytes = build_fixed_report_pdf(business_name, remediation_result)
    
    with open(filepath, "wb") as f:
        f.write(pdf_bytes)
    
    return filepath
