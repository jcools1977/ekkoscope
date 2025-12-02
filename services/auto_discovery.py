"""
Auto-Discovery Intelligence Service for EkkoScope v4
Transforms a URL into complete business intelligence: tech stack, location, competitors.
The "Magic Wand" for sales demos.
"""

import os
import re
import json
import httpx
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup
from openai import OpenAI


SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")


TECH_SIGNATURES = {
    "wordpress": [
        "/wp-content/",
        "/wp-includes/",
        "wp-json",
        'name="generator" content="WordPress',
        "wordpress.org",
    ],
    "shopify": [
        "cdn.shopify.com",
        "myshopify.com",
        "Shopify.theme",
        "/cdn/shop/",
    ],
    "squarespace": [
        "squarespace.com",
        "static1.squarespace.com",
        "squarespace-cdn.com",
    ],
    "webflow": [
        "webflow.com",
        "assets.website-files.com",
        "webflow.io",
    ],
    "wix": [
        "wix.com",
        "wixstatic.com",
        "parastorage.com",
    ],
    "hubspot": [
        "hubspot.com",
        "hs-scripts.com",
        "hubspot.net",
    ],
    "godaddy": [
        "godaddy.com",
        "secureserver.net",
    ],
    "duda": [
        "dudaone.com",
        "duda.co",
    ],
}

DIRECTORY_BLACKLIST = [
    "yelp.com",
    "yellowpages.com",
    "facebook.com",
    "instagram.com",
    "twitter.com",
    "linkedin.com",
    "youtube.com",
    "bbb.org",
    "angi.com",
    "angieslist.com",
    "homeadvisor.com",
    "thumbtack.com",
    "google.com/maps",
    "google.com/search",
    "tripadvisor.com",
    "mapquest.com",
    "manta.com",
    "chamberofcommerce.com",
    "nextdoor.com",
    "houzz.com",
    "porch.com",
    "buildzoom.com",
]


async def auto_discover(url: str) -> Dict[str, Any]:
    """
    Main entry point for auto-discovery.
    Takes a URL and returns complete business intelligence.
    
    Returns:
        {
            "success": bool,
            "url": str,
            "tech_stack": str,
            "title": str,
            "business_name": str,
            "location": str,
            "industry": str,
            "keywords": List[str],
            "suggested_competitors": List[Dict],
            "raw_metadata": Dict
        }
    """
    result = {
        "success": False,
        "url": url,
        "tech_stack": "Unknown",
        "title": "",
        "business_name": "",
        "location": "",
        "industry": "",
        "keywords": [],
        "suggested_competitors": [],
        "raw_metadata": {},
        "errors": []
    }
    
    normalized_url = normalize_url(url)
    result["url"] = normalized_url
    
    html_content, metadata = await fetch_and_parse(normalized_url)
    if not html_content:
        result["errors"].append("Failed to fetch website content")
        return result
    
    result["raw_metadata"] = metadata
    result["title"] = metadata.get("title", "")
    result["tech_stack"] = detect_tech_stack(html_content)
    
    llm_analysis = await analyze_with_llm(metadata, html_content[:15000])
    if llm_analysis:
        result["business_name"] = llm_analysis.get("business_name", "")
        result["location"] = llm_analysis.get("location", "")
        result["industry"] = llm_analysis.get("industry", "")
        result["keywords"] = llm_analysis.get("keywords", [])
    
    if result["business_name"] and result["location"]:
        competitors = await find_competitors(
            result["business_name"],
            result["location"],
            result["industry"],
            normalized_url
        )
        result["suggested_competitors"] = competitors
    
    result["success"] = True
    return result


def normalize_url(url: str) -> str:
    """Normalize URL to include https:// if missing."""
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    return url.rstrip("/")


async def fetch_and_parse(url: str) -> tuple[Optional[str], Dict[str, Any]]:
    """
    Fetch HTML content and extract metadata.
    Returns (html_content, metadata_dict)
    """
    metadata = {
        "title": "",
        "meta_description": "",
        "headings": [],
        "footer_text": "",
        "body_text": "",
        "phone": "",
        "address_candidates": [],
    }
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
            
            if response.status_code != 200:
                return None, metadata
            
            html_content = response.text
            soup = BeautifulSoup(html_content, "html.parser")
            
            title_tag = soup.find("title")
            if title_tag:
                metadata["title"] = title_tag.get_text(strip=True)
            
            meta_desc = soup.find("meta", attrs={"name": "description"})
            if meta_desc:
                metadata["meta_description"] = str(meta_desc.get("content", "") or "")
            
            headings = []
            for tag in soup.find_all(["h1", "h2"], limit=10):
                text = tag.get_text(strip=True)
                if text:
                    headings.append(text)
            metadata["headings"] = headings
            
            footer = soup.find("footer")
            if footer:
                metadata["footer_text"] = footer.get_text(separator=" ", strip=True)[:2000]
            
            body_text = soup.get_text(separator=" ", strip=True)
            body_text = re.sub(r'\s+', ' ', body_text)
            metadata["body_text"] = body_text[:5000]
            
            phone_patterns = [
                r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',
                r'\d{3}[-.\s]\d{3}[-.\s]\d{4}',
            ]
            for pattern in phone_patterns:
                match = re.search(pattern, body_text)
                if match:
                    metadata["phone"] = match.group()
                    break
            
            address_pattern = r'\d+\s+[\w\s]+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Boulevard|Blvd|Way|Court|Ct|Circle|Cir|Highway|Hwy)\.?(?:\s*,?\s*(?:Suite|Ste|Unit|#)\s*\d+)?(?:\s*,?\s*[\w\s]+,?\s*[A-Z]{2}\s*\d{5}(?:-\d{4})?)?'
            addresses = re.findall(address_pattern, body_text, re.IGNORECASE)
            metadata["address_candidates"] = addresses[:3]
            
            return html_content, metadata
            
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None, metadata


def detect_tech_stack(html_content: str) -> str:
    """
    Detect the technology platform used to build the website.
    """
    html_lower = html_content.lower()
    
    detected = []
    for platform, signatures in TECH_SIGNATURES.items():
        for sig in signatures:
            if sig.lower() in html_lower:
                detected.append(platform)
                break
    
    if detected:
        return detected[0].title()
    
    return "Custom/Unknown"


async def analyze_with_llm(metadata: Dict[str, Any], html_excerpt: str) -> Optional[Dict[str, Any]]:
    """
    Use GPT to extract business intelligence from the scraped content.
    """
    if not OPENAI_API_KEY:
        return None
    
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        context = f"""
Page Title: {metadata.get('title', 'N/A')}
Meta Description: {metadata.get('meta_description', 'N/A')}
Headings: {', '.join(metadata.get('headings', [])[:5])}
Footer Text: {metadata.get('footer_text', 'N/A')[:500]}
Phone Found: {metadata.get('phone', 'N/A')}
Address Candidates: {metadata.get('address_candidates', [])}
Body Text Excerpt: {metadata.get('body_text', '')[:2000]}
"""
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": """You are an expert business analyst. Extract business information from website content.
Return a JSON object with:
- business_name: The company/business name (not tagline)
- location: City and State (e.g., "Morehead City, NC") - extract from footer, address, or content
- industry: Primary industry category (e.g., "Roofing", "Plumbing", "Law Firm", "Restaurant")
- keywords: List of 3-5 main service/product keywords this business offers

Be precise. If you can't find something, return empty string or empty list.
Return ONLY valid JSON, no markdown."""
                },
                {
                    "role": "user",
                    "content": f"Extract business intelligence from this website:\n\n{context}"
                }
            ],
            temperature=0.1,
            max_tokens=500
        )
        
        content = response.choices[0].message.content.strip()
        content = content.replace("```json", "").replace("```", "").strip()
        
        return json.loads(content)
        
    except Exception as e:
        print(f"LLM analysis error: {e}")
        return None


async def find_competitors(
    business_name: str,
    location: str,
    industry: str,
    exclude_url: str
) -> List[Dict[str, Any]]:
    """
    Use Serper API to find top competitors via Google Search.
    """
    if not SERPER_API_KEY:
        return await find_competitors_fallback(business_name, location, industry)
    
    try:
        search_query = f"{industry} near {location}"
        if not industry:
            search_query = f"{business_name} competitors {location}"
        
        headers = {
            "X-API-KEY": SERPER_API_KEY,
            "Content-Type": "application/json"
        }
        
        payload = {
            "q": search_query,
            "location": "United States",
            "gl": "us",
            "hl": "en",
            "num": 10
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "https://google.serper.dev/search",
                headers=headers,
                json=payload
            )
            
            if response.status_code != 200:
                return await find_competitors_fallback(business_name, location, industry)
            
            data = response.json()
            competitors = []
            
            exclude_domain = extract_domain(exclude_url)
            
            organic_results = data.get("organic", [])
            for result in organic_results:
                link = result.get("link", "")
                domain = extract_domain(link)
                
                if domain == exclude_domain:
                    continue
                
                if any(blacklisted in domain for blacklisted in DIRECTORY_BLACKLIST):
                    continue
                
                competitors.append({
                    "url": link,
                    "domain": domain,
                    "title": result.get("title", ""),
                    "snippet": result.get("snippet", ""),
                    "position": result.get("position", 0)
                })
                
                if len(competitors) >= 3:
                    break
            
            return competitors
            
    except Exception as e:
        print(f"Serper API error: {e}")
        return await find_competitors_fallback(business_name, location, industry)


async def find_competitors_fallback(
    business_name: str,
    location: str,
    industry: str
) -> List[Dict[str, Any]]:
    """
    Fallback: Use LLM to suggest likely competitors when Serper is unavailable.
    """
    if not OPENAI_API_KEY:
        return []
    
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": """You are a local business expert. Given a business and location, suggest 3 likely competitors.
Return a JSON array with objects containing:
- domain: A realistic domain name (e.g., "competitorname.com")
- title: Business name
- reason: Why they're a competitor

Return ONLY valid JSON array, no markdown."""
                },
                {
                    "role": "user",
                    "content": f"Suggest 3 competitors for a {industry} business named '{business_name}' in {location}."
                }
            ],
            temperature=0.3,
            max_tokens=400
        )
        
        content = response.choices[0].message.content.strip()
        content = content.replace("```json", "").replace("```", "").strip()
        competitors = json.loads(content)
        
        formatted = []
        for comp in competitors[:3]:
            formatted.append({
                "url": f"https://{comp.get('domain', '')}",
                "domain": comp.get("domain", ""),
                "title": comp.get("title", ""),
                "snippet": comp.get("reason", "AI-suggested competitor"),
                "position": 0,
                "ai_suggested": True
            })
        
        return formatted
        
    except Exception as e:
        print(f"Fallback competitor search error: {e}")
        return []


def extract_domain(url: str) -> str:
    """Extract clean domain from URL."""
    try:
        url = url.lower()
        url = url.replace("https://", "").replace("http://", "")
        url = url.split("/")[0]
        url = url.replace("www.", "")
        return url
    except:
        return ""
