"""
PDF Parser for EkkoScope GEO Reports
Extracts visibility issues, scores, competitors, and recommendations from generated reports.
"""

import os
import re
from typing import Dict, Any, List, Optional
from datetime import datetime
from PyPDF2 import PdfReader


class GEOReportParser:
    """Parse EkkoScope GEO PDF reports to extract actionable issues."""
    
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.raw_text = ""
        self.pages = []
        self._load_pdf()
    
    def _load_pdf(self):
        """Load and extract text from PDF."""
        if not os.path.exists(self.pdf_path):
            raise FileNotFoundError(f"Report not found: {self.pdf_path}")
        
        reader = PdfReader(self.pdf_path)
        self.pages = []
        for page in reader.pages:
            text = page.extract_text() or ""
            self.pages.append(text)
        self.raw_text = "\n\n".join(self.pages)
    
    def extract_business_info(self) -> Dict[str, str]:
        """Extract business name, type, and domain."""
        info = {
            "business_name": "",
            "business_type": "",
            "domain": "",
            "report_date": ""
        }
        
        lines = self.raw_text.split('\n')
        for i, line in enumerate(lines):
            if "AI Visibility Report" in line or "GEO Report" in line:
                if i > 0:
                    info["business_name"] = lines[i-1].strip()
            if "Generated:" in line:
                info["report_date"] = line.replace("Generated:", "").strip()
            if re.match(r'https?://|www\.', line.strip()):
                info["domain"] = line.strip()
        
        name_match = re.search(r'Report\s*[-–]\s*(.+?)(?:\n|AI Visibility)', self.raw_text)
        if name_match:
            info["business_name"] = name_match.group(1).strip()
        
        return info
    
    def extract_visibility_score(self) -> Dict[str, Any]:
        """Extract overall visibility score and breakdown."""
        scores = {
            "overall_score": 0.0,
            "visibility_percentage": 0,
            "mentioned_count": 0,
            "primary_count": 0,
            "total_queries": 0,
            "score_distribution": {}
        }
        
        score_match = re.search(r'(?:Overall|Average|Visibility)\s*(?:Score)?[:\s]*(\d+(?:\.\d+)?)\s*(?:/\s*2|%)?', self.raw_text, re.IGNORECASE)
        if score_match:
            score = float(score_match.group(1))
            if score > 2:
                scores["visibility_percentage"] = int(score)
                scores["overall_score"] = score / 100 * 2
            else:
                scores["overall_score"] = score
                scores["visibility_percentage"] = int(score / 2 * 100)
        
        mentioned_match = re.search(r'Mentioned[:\s]*(\d+)', self.raw_text, re.IGNORECASE)
        if mentioned_match:
            scores["mentioned_count"] = int(mentioned_match.group(1))
        
        primary_match = re.search(r'Primary[:\s]*(\d+)', self.raw_text, re.IGNORECASE)
        if primary_match:
            scores["primary_count"] = int(primary_match.group(1))
        
        queries_match = re.search(r'(?:Total\s*)?Queries[:\s]*(\d+)', self.raw_text, re.IGNORECASE)
        if queries_match:
            scores["total_queries"] = int(queries_match.group(1))
        
        for score_val in [0, 1, 2]:
            score_count = re.search(rf'Score\s*{score_val}[:\s]*(\d+)', self.raw_text, re.IGNORECASE)
            if score_count:
                scores["score_distribution"][score_val] = int(score_count.group(1))
        
        return scores
    
    def extract_visibility_issues(self) -> List[Dict[str, Any]]:
        """Extract specific visibility issues from the report."""
        issues = []
        
        zero_score_pattern = r'(?:Score:\s*0|visibility.*?0%|not\s*mentioned|zero\s*visibility)'
        zero_matches = re.findall(zero_score_pattern, self.raw_text, re.IGNORECASE)
        if zero_matches:
            issues.append({
                "type": "zero_visibility",
                "severity": "critical",
                "description": "Business has 0% visibility in AI responses",
                "count": len(zero_matches),
                "fix_type": "content_optimization"
            })
        
        missing_patterns = [
            (r'missing\s*(?:meta|description)', "missing_meta", "SEO meta descriptions not optimized for AI"),
            (r'no\s*(?:schema|structured\s*data)', "missing_schema", "No schema markup for AI understanding"),
            (r'missing\s*(?:local|geo)\s*(?:seo|signals)', "missing_local_seo", "Missing local SEO signals"),
            (r'(?:no|missing)\s*faq', "missing_faq", "No FAQ section for AI to reference"),
            (r'(?:thin|weak|poor)\s*content', "thin_content", "Content too thin for AI visibility"),
            (r'(?:no|missing)\s*(?:keyword|keywords)', "missing_keywords", "Missing target keywords"),
        ]
        
        for pattern, issue_type, description in missing_patterns:
            if re.search(pattern, self.raw_text, re.IGNORECASE):
                issues.append({
                    "type": issue_type,
                    "severity": "high",
                    "description": description,
                    "fix_type": "seo_optimization" if "schema" in issue_type or "meta" in issue_type else "content_optimization"
                })
        
        if not issues:
            scores = self.extract_visibility_score()
            if scores["overall_score"] < 0.5:
                issues.append({
                    "type": "low_visibility",
                    "severity": "critical",
                    "description": f"Overall visibility score is {scores['overall_score']:.2f}/2 - needs comprehensive optimization",
                    "fix_type": "comprehensive"
                })
            if scores["visibility_percentage"] < 30:
                issues.append({
                    "type": "poor_ai_presence",
                    "severity": "high",
                    "description": f"Only {scores['visibility_percentage']}% visibility across AI platforms",
                    "fix_type": "content_optimization"
                })
        
        return issues
    
    def extract_competitors(self) -> List[Dict[str, Any]]:
        """Extract competitor information from the report."""
        competitors = []
        
        competitor_section = re.search(r'Competitor(?:s|.*?Analysis|.*?Landscape)(.*?)(?:Recommendations|Page\s*Blueprints|Genius)', self.raw_text, re.IGNORECASE | re.DOTALL)
        if competitor_section:
            section_text = competitor_section.group(1)
            comp_lines = [line.strip() for line in section_text.split('\n') if line.strip() and len(line.strip()) > 3]
            
            for line in comp_lines[:10]:
                if re.match(r'^\d+[\.\)]\s*', line):
                    name = re.sub(r'^\d+[\.\)]\s*', '', line)
                    if len(name) < 100 and not any(x in name.lower() for x in ['score', 'visibility', 'mentioned']):
                        competitors.append({
                            "name": name,
                            "mentions": 0,
                            "threat_level": "unknown"
                        })
        
        mentions_pattern = r'(\w+(?:\s+\w+){0,4})\s*[-–:]\s*(\d+)\s*mention'
        for match in re.finditer(mentions_pattern, self.raw_text, re.IGNORECASE):
            competitors.append({
                "name": match.group(1).strip(),
                "mentions": int(match.group(2)),
                "threat_level": "high" if int(match.group(2)) > 5 else "medium"
            })
        
        return competitors[:15]
    
    def extract_queries(self) -> List[Dict[str, Any]]:
        """Extract query analysis from the report."""
        queries = []
        
        query_patterns = [
            r'"([^"]+)"\s*[-–:]\s*Score[:\s]*(\d)',
            r'Query[:\s]*([^\n]+?)\s*Score[:\s]*(\d)',
            r'"([^"]+)"[^\n]*?(?:visibility|score)[:\s]*(\d)',
        ]
        
        for pattern in query_patterns:
            for match in re.finditer(pattern, self.raw_text, re.IGNORECASE):
                query_text = match.group(1).strip()
                score = int(match.group(2))
                if len(query_text) > 10 and len(query_text) < 200:
                    queries.append({
                        "query": query_text,
                        "score": score,
                        "needs_fix": score == 0
                    })
        
        return queries[:30]
    
    def extract_recommendations(self) -> List[Dict[str, Any]]:
        """Extract existing recommendations from the report."""
        recommendations = []
        
        rec_section = re.search(r'Recommendations?(.*?)(?:Action\s*Plan|Next\s*Steps|Appendix|$)', self.raw_text, re.IGNORECASE | re.DOTALL)
        if rec_section:
            section_text = rec_section.group(1)
            rec_lines = [line.strip() for line in section_text.split('\n') if line.strip()]
            
            for line in rec_lines:
                if re.match(r'^[\d\-\*\•]\s*', line) or len(line) > 20:
                    clean_line = re.sub(r'^[\d\-\*\•\.\)]\s*', '', line)
                    if len(clean_line) > 15 and len(clean_line) < 300:
                        recommendations.append({
                            "text": clean_line,
                            "priority": "high" if any(x in clean_line.lower() for x in ['urgent', 'critical', 'immediate']) else "medium"
                        })
        
        return recommendations[:20]
    
    def extract_page_blueprints(self) -> List[Dict[str, Any]]:
        """Extract page blueprint suggestions from the report."""
        blueprints = []
        
        blueprint_section = re.search(r'Page\s*Blueprint(?:s)?(.*?)(?:Roadmap|Action\s*Plan|Recommendations|$)', self.raw_text, re.IGNORECASE | re.DOTALL)
        if blueprint_section:
            section_text = blueprint_section.group(1)
            
            page_matches = re.findall(r'(?:Page|Create)[:\s]*([^\n]+)', section_text, re.IGNORECASE)
            for page in page_matches[:7]:
                if len(page) > 10:
                    blueprints.append({
                        "page_title": page.strip(),
                        "status": "not_created",
                        "priority": "high"
                    })
        
        return blueprints
    
    def get_full_analysis(self) -> Dict[str, Any]:
        """Get complete analysis of the PDF report."""
        return {
            "parsed_at": datetime.utcnow().isoformat() + "Z",
            "pdf_path": self.pdf_path,
            "page_count": len(self.pages),
            "business_info": self.extract_business_info(),
            "visibility_score": self.extract_visibility_score(),
            "issues": self.extract_visibility_issues(),
            "competitors": self.extract_competitors(),
            "queries": self.extract_queries(),
            "recommendations": self.extract_recommendations(),
            "page_blueprints": self.extract_page_blueprints()
        }


def parse_geo_report(pdf_path: str) -> Dict[str, Any]:
    """Convenience function to parse a GEO report."""
    parser = GEOReportParser(pdf_path)
    return parser.get_full_analysis()
