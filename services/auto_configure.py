"""
Auto-Configure Module for EkkoScope Sales Mode.
Automatically infers business configuration from a URL using web scraping and LLM analysis.
"""

import re
import json
import logging
from typing import Dict, Any, Optional
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from services.config import OPENAI_API_KEY

logger = logging.getLogger(__name__)


def scrape_url_for_inference(url: str, timeout: float = 15.0) -> Dict[str, Any]:
    """
    Scrape a URL to extract text content for business inference.
    
    Args:
        url: The website URL to scrape
        timeout: Request timeout in seconds
    
    Returns:
        Dict with scraped content and metadata
    """
    result = {
        "success": False,
        "url": url,
        "domain": "",
        "title": "",
        "meta_description": "",
        "headings": [],
        "text_content": "",
        "phone": "",
        "address_hints": [],
        "error": None
    }
    
    try:
        parsed = urlparse(url)
        if not parsed.scheme:
            url = f"https://{url}"
            parsed = urlparse(url)
        
        result["domain"] = parsed.netloc.replace("www.", "")
        
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; EkkoScope/1.0; Business Analyzer)"
        }
        
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            response = client.get(url, headers=headers)
            
            if response.status_code != 200:
                result["error"] = f"HTTP {response.status_code}"
                return result
            
            soup = BeautifulSoup(response.text, "html.parser")
            
            title_tag = soup.find("title")
            if title_tag:
                result["title"] = title_tag.get_text(strip=True)[:200]
            
            meta_desc = soup.find("meta", attrs={"name": "description"})
            if meta_desc:
                result["meta_description"] = str(meta_desc.get("content", "") or "")[:500]
            
            for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript", "iframe"]):
                tag.decompose()
            
            headings = []
            for h_tag in soup.find_all(["h1", "h2", "h3"])[:15]:
                heading_text = h_tag.get_text(strip=True)
                if heading_text and len(heading_text) > 3:
                    headings.append(heading_text[:100])
            result["headings"] = headings
            
            text_content = soup.get_text(separator=" ", strip=True)
            text_content = re.sub(r'\s+', ' ', text_content)
            result["text_content"] = text_content[:8000]
            
            phone_pattern = r'[\+]?[(]?[0-9]{1,3}[)]?[-\s\.]?[(]?[0-9]{1,4}[)]?[-\s\.]?[0-9]{1,4}[-\s\.]?[0-9]{1,9}'
            phones = re.findall(phone_pattern, response.text)
            valid_phones = [p for p in phones if len(re.sub(r'\D', '', p)) >= 10]
            if valid_phones:
                result["phone"] = valid_phones[0]
            
            state_pattern = r'\b(AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY)\b'
            states = re.findall(state_pattern, response.text)
            if states:
                from collections import Counter
                state_counts = Counter(states)
                result["address_hints"] = [s for s, _ in state_counts.most_common(3)]
            
            result["success"] = True
            
    except Exception as e:
        result["error"] = str(e)[:200]
        logger.warning(f"Failed to scrape {url}: {e}")
    
    return result


def infer_business_config(scraped_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Use GPT-4o-mini to infer business configuration from scraped website content.
    
    Args:
        scraped_data: Output from scrape_url_for_inference()
    
    Returns:
        BusinessConfig-compatible dict with inferred values
    """
    if not OPENAI_API_KEY:
        logger.warning("No OPENAI_API_KEY for auto-configure inference")
        return _fallback_inference(scraped_data)
    
    try:
        from openai import OpenAI
        
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        content_summary = f"""
Website: {scraped_data.get('domain', 'Unknown')}
Title: {scraped_data.get('title', '')}
Description: {scraped_data.get('meta_description', '')}
Headings: {', '.join(scraped_data.get('headings', [])[:10])}
Content Preview: {scraped_data.get('text_content', '')[:3000]}
Location Hints: {', '.join(scraped_data.get('address_hints', []))}
"""

        prompt = f"""Analyze this website and infer the business configuration.

{content_summary}

Return a JSON object with these exact fields:
{{
    "business_name": "The company/business name (extract from title or content)",
    "industry": "The broad industry (e.g., 'Construction', 'Manufacturing', 'Retail', 'Professional Services', 'Healthcare')",
    "category": "The specific service/product category (e.g., 'Roofing', 'Industrial Packaging', 'Plumbing', 'HVAC')",
    "business_type": "One of: 'local_service', 'ecom', 'b2b_service', 'other'",
    "service_area": "Primary geographic service area (e.g., 'Charleston SC', 'Greater Houston', 'United States')",
    "confidence": "HIGH, MEDIUM, or LOW based on how clear the business info is"
}}

Be specific about the category - use industry terminology. If it's a local service business, include the city/region in service_area.
Only return valid JSON, no markdown or explanation."""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=500
        )
        
        content = response.choices[0].message.content
        if not content:
            return _fallback_inference(scraped_data)
        raw = content.strip()
        
        if raw.startswith("```"):
            raw = re.sub(r'^```\w*\n?', '', raw)
            raw = re.sub(r'\n?```$', '', raw)
        
        config = json.loads(raw)
        
        config["domain"] = scraped_data.get("domain", "")
        config["url"] = scraped_data.get("url", "")
        config["phone"] = scraped_data.get("phone", "")
        config["inference_method"] = "gpt-4o-mini"
        
        logger.info(f"Auto-configured business: {config.get('business_name')} ({config.get('category')})")
        
        return config
        
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse LLM inference response: {e}")
        return _fallback_inference(scraped_data)
    except Exception as e:
        logger.warning(f"LLM inference failed: {e}")
        return _fallback_inference(scraped_data)


def _fallback_inference(scraped_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fallback inference when LLM is unavailable.
    Uses simple heuristics based on scraped content.
    """
    domain = scraped_data.get("domain", "")
    title = scraped_data.get("title", "")
    text = scraped_data.get("text_content", "").lower()
    
    business_name = title.split("|")[0].split("-")[0].strip() if title else domain
    
    category = "services"
    business_type = "other"
    industry = "General Business"
    
    service_keywords = {
        "roofing": ("Roofing", "local_service", "Construction"),
        "roof": ("Roofing", "local_service", "Construction"),
        "plumbing": ("Plumbing", "local_service", "Construction"),
        "plumber": ("Plumbing", "local_service", "Construction"),
        "hvac": ("HVAC", "local_service", "Construction"),
        "air conditioning": ("HVAC", "local_service", "Construction"),
        "heating": ("HVAC", "local_service", "Construction"),
        "electrician": ("Electrical", "local_service", "Construction"),
        "electrical": ("Electrical", "local_service", "Construction"),
        "landscaping": ("Landscaping", "local_service", "Home Services"),
        "lawn": ("Lawn Care", "local_service", "Home Services"),
        "cleaning": ("Cleaning", "local_service", "Home Services"),
        "packaging": ("Industrial Packaging", "ecom", "Manufacturing"),
        "wholesale": ("Wholesale Distribution", "ecom", "Distribution"),
        "manufacturing": ("Manufacturing", "b2b_service", "Manufacturing"),
        "consulting": ("Consulting", "b2b_service", "Professional Services"),
        "marketing": ("Marketing", "b2b_service", "Professional Services"),
        "legal": ("Legal Services", "b2b_service", "Professional Services"),
        "law firm": ("Legal Services", "b2b_service", "Professional Services"),
        "accounting": ("Accounting", "b2b_service", "Professional Services"),
        "dental": ("Dental", "local_service", "Healthcare"),
        "dentist": ("Dental", "local_service", "Healthcare"),
        "medical": ("Medical", "local_service", "Healthcare"),
        "clinic": ("Medical", "local_service", "Healthcare"),
        "restaurant": ("Restaurant", "local_service", "Food Service"),
        "real estate": ("Real Estate", "local_service", "Real Estate"),
        "realtor": ("Real Estate", "local_service", "Real Estate"),
    }
    
    for keyword, (cat, btype, ind) in service_keywords.items():
        if keyword in text:
            category = cat
            business_type = btype
            industry = ind
            break
    
    service_area = "United States"
    address_hints = scraped_data.get("address_hints", [])
    if address_hints:
        state_names = {
            "TX": "Texas", "CA": "California", "FL": "Florida", "NY": "New York",
            "SC": "South Carolina", "NC": "North Carolina", "GA": "Georgia",
            "OH": "Ohio", "PA": "Pennsylvania", "IL": "Illinois", "AZ": "Arizona",
            "CO": "Colorado", "WA": "Washington", "VA": "Virginia", "MA": "Massachusetts"
        }
        primary_state = address_hints[0]
        service_area = state_names.get(primary_state, primary_state)
    
    return {
        "business_name": business_name[:100],
        "industry": industry,
        "category": category,
        "business_type": business_type,
        "service_area": service_area,
        "confidence": "LOW",
        "domain": domain,
        "url": scraped_data.get("url", ""),
        "phone": scraped_data.get("phone", ""),
        "inference_method": "fallback_heuristics"
    }


def auto_configure_business(url: str) -> Dict[str, Any]:
    """
    Main entry point: Scrape a URL and infer business configuration.
    
    Args:
        url: Website URL to analyze
    
    Returns:
        Complete business configuration dict ready for teaser audit
    """
    logger.info(f"Auto-configuring business from URL: {url}")
    
    scraped = scrape_url_for_inference(url)
    
    if not scraped["success"]:
        return {
            "success": False,
            "error": scraped.get("error", "Failed to scrape URL"),
            "url": url
        }
    
    config = infer_business_config(scraped)
    config["success"] = True
    
    return config
