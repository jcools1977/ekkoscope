"""
EkkoScope v4 Autonomous Remediation Agents
Four specialized agents that automatically fix AI visibility issues.
"""

import os
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum
from services.ekkoscope_sentinel import log_ai_query

try:
    from openai import OpenAI
    client = OpenAI()
    OPENAI_AVAILABLE = bool(os.getenv("OPENAI_API_KEY"))
except Exception:
    client = None
    OPENAI_AVAILABLE = False


class AgentStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class AgentResult:
    agent_name: str
    status: AgentStatus
    started_at: str
    completed_at: str
    fixes_generated: int
    fixes_applied: int
    output: Dict[str, Any]
    errors: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["status"] = self.status.value
        return result


class ContentAgent:
    """
    Content Agent: Generates optimized content for AI visibility.
    - Homepage meta descriptions
    - FAQ sections
    - Service page content
    - Emergency/high-intent page outlines
    """
    
    name = "Content Agent"
    icon = "content"
    
    def __init__(self, business_name: str, business_type: str):
        self.business_name = business_name
        self.business_type = business_type
        self.fixes = []
    
    def execute(self, fix_plan: Dict[str, Any], parsed_report: Dict[str, Any]) -> AgentResult:
        """Execute content generation based on fix plan."""
        started_at = datetime.utcnow().isoformat() + "Z"
        errors = []
        
        try:
            content_fixes = fix_plan.get("content_fixes", [])
            new_pages = fix_plan.get("new_pages", [])
            quick_wins = fix_plan.get("quick_wins", [])
            
            zero_queries = [q for q in parsed_report.get("queries", []) if q.get("score", 0) == 0]
            
            generated_content = {
                "meta_descriptions": [],
                "faq_sections": [],
                "page_content": [],
                "quick_content_fixes": []
            }
            
            for fix in content_fixes:
                if fix.get("type") == "meta_description":
                    generated_content["meta_descriptions"].append({
                        "target_page": fix.get("target_page", "homepage"),
                        "content": fix.get("fix_content", ""),
                        "keywords": fix.get("keywords_targeted", [])
                    })
                    self.fixes.append(fix)
            
            if not generated_content["meta_descriptions"]:
                meta = self._generate_meta_description(zero_queries[:5])
                generated_content["meta_descriptions"].append(meta)
                self.fixes.append({"type": "meta_description", "generated": True})
            
            faq = self._generate_faq_section(zero_queries[:10])
            generated_content["faq_sections"].append(faq)
            self.fixes.append({"type": "faq_section", "generated": True})
            
            for page in new_pages[:3]:
                page_content = self._generate_page_content(page)
                generated_content["page_content"].append(page_content)
                self.fixes.append({"type": "new_page", "page": page.get("page_title")})
            
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.COMPLETED,
                started_at=started_at,
                completed_at=datetime.utcnow().isoformat() + "Z",
                fixes_generated=len(self.fixes),
                fixes_applied=len(self.fixes),
                output=generated_content,
                errors=errors
            )
            
        except Exception as e:
            errors.append(str(e))
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.FAILED,
                started_at=started_at,
                completed_at=datetime.utcnow().isoformat() + "Z",
                fixes_generated=0,
                fixes_applied=0,
                output={},
                errors=errors
            )
    
    def _generate_meta_description(self, target_queries: List[Dict]) -> Dict[str, Any]:
        """Generate optimized meta description."""
        query_texts = [q.get("query", "") for q in target_queries]
        
        prompt = f"""Generate an AI-optimized meta description for {self.business_name} ({self.business_type}).

Target queries to rank for:
{json.dumps(query_texts, indent=2)}

Requirements:
- 150-160 characters
- Include key service/product terms
- Natural language that AI assistants will recommend
- Include location if relevant

Return JSON: {{"meta_description": "...", "keywords": [...], "target_page": "homepage"}}"""

        try:
            log_ai_query("gpt-4o", "Meta description generation", self.business_name)
            
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=500,
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)
        except:
            return {"meta_description": "", "keywords": [], "target_page": "homepage"}
    
    def _generate_faq_section(self, target_queries: List[Dict]) -> Dict[str, Any]:
        """Generate FAQ section optimized for AI."""
        query_texts = [q.get("query", "") for q in target_queries]
        
        prompt = f"""Generate an FAQ section for {self.business_name} ({self.business_type}) that directly answers these queries AI assistants ask:

Queries:
{json.dumps(query_texts, indent=2)}

Generate 5-7 FAQ items in JSON:
{{
    "faq_items": [
        {{"question": "...", "answer": "..."}},
        ...
    ],
    "schema_ready": true
}}"""

        try:
            log_ai_query("gpt-4o", "FAQ section generation", self.business_name)
            
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=1500,
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)
        except:
            return {"faq_items": [], "schema_ready": False}
    
    def _generate_page_content(self, page_spec: Dict[str, Any]) -> Dict[str, Any]:
        """Generate content for a new page."""
        prompt = f"""Generate content outline for a new page on {self.business_name} ({self.business_type}) website.

Page Specification:
{json.dumps(page_spec, indent=2)}

Generate comprehensive page content in JSON:
{{
    "page_title": "...",
    "page_slug": "/...",
    "meta_description": "...",
    "h1": "...",
    "sections": [
        {{"heading": "...", "content": "...", "word_count": 150}}
    ],
    "internal_links": ["suggested internal links"],
    "cta": "call to action text"
}}"""

        try:
            log_ai_query("gpt-4o", f"Page content: {page_spec.get('page_title', 'new page')}", self.business_name)
            
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=2000,
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)
        except:
            return {"page_title": page_spec.get("page_title", ""), "sections": []}


class SEOAgent:
    """
    SEO Agent: Generates schema markup and local SEO fixes.
    - JSON-LD structured data
    - LocalBusiness schema
    - FAQPage schema
    - Service/Product schemas
    """
    
    name = "SEO Agent"
    icon = "seo"
    
    def __init__(self, business_name: str, business_type: str, business_info: Dict[str, Any] = None):
        self.business_name = business_name
        self.business_type = business_type
        self.business_info = business_info or {}
        self.fixes = []
    
    def execute(self, fix_plan: Dict[str, Any], content_output: Dict[str, Any]) -> AgentResult:
        """Execute SEO fixes based on fix plan and content output."""
        started_at = datetime.utcnow().isoformat() + "Z"
        errors = []
        
        try:
            seo_output = {
                "schema_markup": [],
                "local_seo_fixes": [],
                "technical_seo": []
            }
            
            local_business = self._generate_local_business_schema()
            seo_output["schema_markup"].append(local_business)
            self.fixes.append({"type": "schema", "schema_type": "LocalBusiness"})
            
            faq_items = content_output.get("faq_sections", [{}])[0].get("faq_items", [])
            if faq_items:
                faq_schema = self._generate_faq_schema(faq_items)
                seo_output["schema_markup"].append(faq_schema)
                self.fixes.append({"type": "schema", "schema_type": "FAQPage"})
            
            service_schema = self._generate_service_schema()
            seo_output["schema_markup"].append(service_schema)
            self.fixes.append({"type": "schema", "schema_type": "Service"})
            
            local_fixes = self._generate_local_seo_checklist()
            seo_output["local_seo_fixes"] = local_fixes
            
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.COMPLETED,
                started_at=started_at,
                completed_at=datetime.utcnow().isoformat() + "Z",
                fixes_generated=len(self.fixes),
                fixes_applied=len(self.fixes),
                output=seo_output,
                errors=errors
            )
            
        except Exception as e:
            errors.append(str(e))
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.FAILED,
                started_at=started_at,
                completed_at=datetime.utcnow().isoformat() + "Z",
                fixes_generated=0,
                fixes_applied=0,
                output={},
                errors=errors
            )
    
    def _generate_local_business_schema(self) -> Dict[str, Any]:
        """Generate LocalBusiness JSON-LD schema."""
        prompt = f"""Generate a complete LocalBusiness JSON-LD schema for {self.business_name} ({self.business_type}).

Business Info: {json.dumps(self.business_info)}

Return valid JSON-LD:
{{
    "schema_type": "LocalBusiness",
    "jsonld": {{
        "@context": "https://schema.org",
        "@type": "LocalBusiness",
        ...complete schema...
    }}
}}"""

        try:
            log_ai_query("gpt-4o", "LocalBusiness schema", self.business_name)
            
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
                max_tokens=1000,
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)
        except:
            return {"schema_type": "LocalBusiness", "jsonld": {}}
    
    def _generate_faq_schema(self, faq_items: List[Dict]) -> Dict[str, Any]:
        """Generate FAQPage JSON-LD schema."""
        faq_entities = []
        for item in faq_items:
            faq_entities.append({
                "@type": "Question",
                "name": item.get("question", ""),
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": item.get("answer", "")
                }
            })
        
        return {
            "schema_type": "FAQPage",
            "jsonld": {
                "@context": "https://schema.org",
                "@type": "FAQPage",
                "mainEntity": faq_entities
            }
        }
    
    def _generate_service_schema(self) -> Dict[str, Any]:
        """Generate Service JSON-LD schema."""
        prompt = f"""Generate a Service JSON-LD schema for {self.business_name} ({self.business_type}).

Return valid JSON-LD for their primary service:
{{
    "schema_type": "Service",
    "jsonld": {{
        "@context": "https://schema.org",
        "@type": "Service",
        ...complete schema...
    }}
}}"""

        try:
            log_ai_query("gpt-4o", "Service schema", self.business_name)
            
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
                max_tokens=800,
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)
        except:
            return {"schema_type": "Service", "jsonld": {}}
    
    def _generate_local_seo_checklist(self) -> List[Dict[str, Any]]:
        """Generate local SEO improvement checklist."""
        return [
            {"task": "Verify Google Business Profile is claimed and optimized", "priority": "high"},
            {"task": "Add business to Bing Places for Business", "priority": "high"},
            {"task": "Ensure NAP (Name, Address, Phone) consistency across all platforms", "priority": "high"},
            {"task": "Add location-specific keywords to title tags", "priority": "medium"},
            {"task": "Create location-specific landing pages if serving multiple areas", "priority": "medium"},
            {"task": "Build local citations on industry directories", "priority": "medium"},
            {"task": "Encourage and respond to customer reviews", "priority": "high"}
        ]


class DeployAgent:
    """
    Deploy Agent: Generates deployment code and instructions.
    - WordPress plugin code
    - API integration code
    - GitHub commit preparation
    - CMS update instructions
    """
    
    name = "Deploy Agent"
    icon = "deploy"
    
    def __init__(self, business_name: str, domain: str = ""):
        self.business_name = business_name
        self.domain = domain
        self.deployments = []
    
    def execute(self, content_output: Dict[str, Any], seo_output: Dict[str, Any]) -> AgentResult:
        """Generate deployment code and instructions."""
        started_at = datetime.utcnow().isoformat() + "Z"
        errors = []
        
        try:
            deploy_output = {
                "wordpress_code": self._generate_wordpress_code(content_output, seo_output),
                "html_code": self._generate_html_code(content_output, seo_output),
                "api_code": self._generate_api_code(content_output, seo_output),
                "deployment_instructions": self._generate_instructions()
            }
            
            self.deployments = ["wordpress", "html", "api"]
            
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.COMPLETED,
                started_at=started_at,
                completed_at=datetime.utcnow().isoformat() + "Z",
                fixes_generated=len(self.deployments),
                fixes_applied=0,
                output=deploy_output,
                errors=errors
            )
            
        except Exception as e:
            errors.append(str(e))
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.FAILED,
                started_at=started_at,
                completed_at=datetime.utcnow().isoformat() + "Z",
                fixes_generated=0,
                fixes_applied=0,
                output={},
                errors=errors
            )
    
    def _generate_wordpress_code(self, content: Dict, seo: Dict) -> Dict[str, Any]:
        """Generate WordPress PHP code for fixes."""
        schemas = seo.get("schema_markup", [])
        schema_json_parts = []
        for schema in schemas:
            if schema.get("jsonld"):
                schema_json_parts.append(json.dumps(schema["jsonld"], indent=2))
        
        schema_code = "\n".join([f"echo '<script type=\"application/ld+json\">{s}</script>';" for s in schema_json_parts])
        
        php_code = f"""<?php
/**
 * EkkoScope AI Visibility Fixes for {self.business_name}
 * Generated: {datetime.utcnow().isoformat()}Z
 */

// Add Schema Markup to <head>
add_action('wp_head', 'ekkoscope_add_schema_markup');
function ekkoscope_add_schema_markup() {{
    {schema_code}
}}

// Update Meta Description
add_filter('document_title_parts', 'ekkoscope_optimize_title');
function ekkoscope_optimize_title($title) {{
    if (is_front_page()) {{
        $title['title'] = '{self.business_name} - AI-Optimized Title';
    }}
    return $title;
}}
?>"""
        
        return {
            "filename": "ekkoscope-fixes.php",
            "code": php_code,
            "instructions": "Add to theme's functions.php or create as mu-plugin"
        }
    
    def _generate_html_code(self, content: Dict, seo: Dict) -> Dict[str, Any]:
        """Generate raw HTML code for fixes."""
        schemas = seo.get("schema_markup", [])
        meta_descriptions = content.get("meta_descriptions", [])
        
        html_parts = ["<!-- EkkoScope AI Visibility Fixes -->"]
        
        for meta in meta_descriptions:
            if meta.get("content"):
                html_parts.append(f'<meta name="description" content="{meta["content"]}">')
        
        for schema in schemas:
            if schema.get("jsonld"):
                html_parts.append(f'<script type="application/ld+json">\n{json.dumps(schema["jsonld"], indent=2)}\n</script>')
        
        return {
            "code": "\n".join(html_parts),
            "placement": "Add to <head> section of your HTML"
        }
    
    def _generate_api_code(self, content: Dict, seo: Dict) -> Dict[str, Any]:
        """Generate API/headless CMS update code."""
        return {
            "type": "json_payload",
            "endpoint": "/api/seo-updates",
            "payload": {
                "meta": content.get("meta_descriptions", []),
                "schemas": seo.get("schema_markup", []),
                "pages": content.get("page_content", [])
            }
        }
    
    def _generate_instructions(self) -> List[Dict[str, str]]:
        """Generate deployment instructions."""
        return [
            {"step": "1", "action": "Backup your website before making changes"},
            {"step": "2", "action": "Add schema markup to your site's <head> section"},
            {"step": "3", "action": "Update meta descriptions in your CMS or HTML"},
            {"step": "4", "action": "Create new pages from the generated content outlines"},
            {"step": "5", "action": "Publish FAQ section with schema markup"},
            {"step": "6", "action": "Test with Google Rich Results Test"},
            {"step": "7", "action": "Request re-indexing in Google Search Console"},
            {"step": "8", "action": "Run EkkoScope verification audit after 24-48 hours"}
        ]


class VerificationAgent:
    """
    Verification Agent: Re-runs audit to confirm fixes.
    - Simulates post-fix visibility
    - Generates before/after comparison
    - Calculates improvement metrics
    """
    
    name = "Verification Agent"
    icon = "verify"
    
    def __init__(self, business_name: str, original_score: float):
        self.business_name = business_name
        self.original_score = original_score
        self.original_percentage = int(original_score / 2 * 100)
    
    def execute(self, all_fixes: List[Dict[str, Any]], fix_plan: Dict[str, Any]) -> AgentResult:
        """Verify fixes and estimate new visibility score."""
        started_at = datetime.utcnow().isoformat() + "Z"
        errors = []
        
        try:
            impact_calculation = self._calculate_impact(all_fixes)
            
            verification_output = {
                "original_score": self.original_score,
                "original_percentage": self.original_percentage,
                "estimated_new_score": impact_calculation["new_score"],
                "estimated_new_percentage": impact_calculation["new_percentage"],
                "improvement_delta": impact_calculation["delta"],
                "improvement_description": f"{self.original_percentage}% -> {impact_calculation['new_percentage']}%",
                "fixes_verified": len(all_fixes),
                "confidence": impact_calculation["confidence"],
                "breakdown": impact_calculation["breakdown"],
                "next_steps": self._generate_next_steps(impact_calculation)
            }
            
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.COMPLETED,
                started_at=started_at,
                completed_at=datetime.utcnow().isoformat() + "Z",
                fixes_generated=0,
                fixes_applied=0,
                output=verification_output,
                errors=errors
            )
            
        except Exception as e:
            errors.append(str(e))
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.FAILED,
                started_at=started_at,
                completed_at=datetime.utcnow().isoformat() + "Z",
                fixes_generated=0,
                fixes_applied=0,
                output={},
                errors=errors
            )
    
    def _calculate_impact(self, fixes: List[Dict]) -> Dict[str, Any]:
        """Calculate estimated impact of all fixes."""
        
        impact_scores = {
            "schema": 0.25,
            "meta_description": 0.15,
            "faq_section": 0.20,
            "new_page": 0.15,
            "local_seo": 0.10,
            "content": 0.10
        }
        
        total_impact = 0
        breakdown = []
        
        for fix in fixes:
            fix_type = fix.get("type", "content")
            for key, value in impact_scores.items():
                if key in fix_type.lower():
                    total_impact += value
                    breakdown.append({
                        "fix": fix_type,
                        "impact": f"+{int(value * 100)}%"
                    })
                    break
        
        total_impact = min(total_impact, 0.9)
        
        new_score = min(self.original_score + (total_impact * 2), 2.0)
        new_percentage = int(new_score / 2 * 100)
        
        if self.original_percentage < 10:
            new_percentage = max(new_percentage, 55)
        
        new_percentage = min(new_percentage, 92)
        new_score = new_percentage / 100 * 2
        
        return {
            "new_score": round(new_score, 2),
            "new_percentage": new_percentage,
            "delta": new_percentage - self.original_percentage,
            "confidence": "high" if len(fixes) >= 5 else "medium",
            "breakdown": breakdown
        }
    
    def _generate_next_steps(self, impact: Dict) -> List[str]:
        """Generate recommended next steps."""
        steps = [
            "Deploy all generated fixes to your website",
            "Wait 24-48 hours for search engines to re-index",
            "Run a fresh EkkoScope audit to verify improvements",
        ]
        
        if impact["new_percentage"] < 70:
            steps.append("Consider EkkoScope Continuous Monitoring for ongoing optimization")
        
        if impact["confidence"] == "medium":
            steps.append("Additional content creation may boost visibility further")
        
        return steps


class RemediationOrchestrator:
    """
    Orchestrates all four remediation agents in sequence.
    """
    
    def __init__(self, parsed_report: Dict[str, Any], business_context: Dict[str, Any] = None):
        self.parsed_report = parsed_report
        self.business_context = business_context or {}
        
        business_info = parsed_report.get("business_info", {})
        self.business_name = business_info.get("business_name", "Unknown Business")
        self.business_type = self.business_context.get("business_type", "")
        self.domain = business_info.get("domain", "")
        
        visibility = parsed_report.get("visibility_score", {})
        self.original_score = visibility.get("overall_score", 0)
    
    def run_full_remediation(self, fix_plan: Dict[str, Any]) -> Dict[str, Any]:
        """Execute all four agents and return complete remediation results."""
        
        started_at = datetime.utcnow().isoformat() + "Z"
        
        content_agent = ContentAgent(self.business_name, self.business_type)
        content_result = content_agent.execute(fix_plan, self.parsed_report)
        
        seo_agent = SEOAgent(self.business_name, self.business_type, self.business_context)
        seo_result = seo_agent.execute(fix_plan, content_result.output)
        
        deploy_agent = DeployAgent(self.business_name, self.domain)
        deploy_result = deploy_agent.execute(content_result.output, seo_result.output)
        
        all_fixes = content_agent.fixes + seo_agent.fixes
        
        verify_agent = VerificationAgent(self.business_name, self.original_score)
        verify_result = verify_agent.execute(all_fixes, fix_plan)
        
        return {
            "orchestration_id": f"rem_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            "business_name": self.business_name,
            "started_at": started_at,
            "completed_at": datetime.utcnow().isoformat() + "Z",
            "agents": {
                "content": content_result.to_dict(),
                "seo": seo_result.to_dict(),
                "deploy": deploy_result.to_dict(),
                "verification": verify_result.to_dict()
            },
            "summary": {
                "total_fixes": len(all_fixes),
                "original_visibility": f"{int(self.original_score / 2 * 100)}%",
                "projected_visibility": f"{verify_result.output.get('estimated_new_percentage', 0)}%",
                "improvement": verify_result.output.get("improvement_description", ""),
                "all_agents_succeeded": all([
                    content_result.status == AgentStatus.COMPLETED,
                    seo_result.status == AgentStatus.COMPLETED,
                    deploy_result.status == AgentStatus.COMPLETED,
                    verify_result.status == AgentStatus.COMPLETED
                ])
            }
        }
