"""
Site Inspector Module for EchoScope v0.3
Fetches and summarizes key pages from tenant websites for Genius Mode site awareness.
"""

import re
import httpx
from typing import Dict, Any, List
from bs4 import BeautifulSoup


def fetch_site_snapshot(tenant: Dict[str, Any], timeout: float = 5.0) -> Dict[str, Any]:
    """
    Best-effort snapshot of the tenant's web presence.
    
    - Uses domains / website URL from tenant config.
    - Fetches 1-3 key pages (homepage + important paths if configured).
    - Returns a dict with page data for Genius Mode consumption.
    
    If anything fails (network, parsing, etc.), returns a structure with empty pages list.
    Never raises exceptions to the caller.
    
    Args:
        tenant: Tenant configuration dictionary
        timeout: HTTP request timeout in seconds
    
    Returns:
        Dict with "pages" list containing url, status, title, text_excerpt for each page
    """
    result = {"pages": [], "fetch_status": "success"}
    
    try:
        urls_to_fetch = _get_urls_from_tenant(tenant)
        
        if not urls_to_fetch:
            result["fetch_status"] = "no_urls_configured"
            return result
        
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            for url in urls_to_fetch[:3]:
                page_data = _fetch_single_page(client, url)
                if page_data:
                    result["pages"].append(page_data)
        
        if not result["pages"]:
            result["fetch_status"] = "all_fetches_failed"
        
    except Exception as e:
        print(f"Site inspector error: {e}")
        result["fetch_status"] = f"error: {str(e)[:100]}"
    
    return result


def _get_urls_from_tenant(tenant: Dict[str, Any]) -> List[str]:
    """
    Extract fetchable URLs from tenant config.
    Handles various formats: full URLs, bare domains, placeholders.
    """
    urls = []
    domains = tenant.get("domains", [])
    important_paths = tenant.get("important_paths", [])
    
    for domain in domains:
        if not domain or domain.startswith("AD_") or "_SITE_URL" in domain:
            continue
        
        if domain.startswith("http://") or domain.startswith("https://"):
            base_url = domain.rstrip("/")
        else:
            base_url = f"https://{domain}"
        
        urls.append(base_url)
        
        for path in important_paths:
            if path.startswith("/"):
                urls.append(f"{base_url}{path}")
            else:
                urls.append(f"{base_url}/{path}")
    
    return urls


def _fetch_single_page(client: httpx.Client, url: str) -> Dict[str, Any] | None:
    """
    Fetch a single page and extract key content.
    Returns None on any failure.
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; EchoScope/1.0; +https://echoscope.ai)"
        }
        response = client.get(url, headers=headers)
        
        if response.status_code != 200:
            return None
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        title = ""
        title_tag = soup.find("title")
        if title_tag:
            title = title_tag.get_text(strip=True)
        
        meta_description = ""
        meta_desc_tag = soup.find("meta", attrs={"name": "description"})
        if meta_desc_tag:
            meta_description = str(meta_desc_tag.get("content", "") or "")
        
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        
        text_content = soup.get_text(separator=" ", strip=True)
        text_content = re.sub(r'\s+', ' ', text_content)
        
        headings = []
        for h_tag in soup.find_all(["h1", "h2", "h3"])[:10]:
            heading_text = h_tag.get_text(strip=True)
            if heading_text:
                headings.append(f"{h_tag.name}: {heading_text}")
        
        text_excerpt = text_content[:2000]
        
        return {
            "url": url,
            "status": response.status_code,
            "title": title[:200],
            "meta_description": meta_description[:300],
            "headings": headings,
            "text_excerpt": text_excerpt
        }
    
    except Exception as e:
        print(f"Failed to fetch {url}: {e}")
        return None


def summarize_site_content(snapshot: Dict[str, Any]) -> str:
    """
    Create a text summary of site snapshot for inclusion in Genius Mode prompts.
    Returns a concise summary suitable for LLM context.
    """
    if not snapshot.get("pages"):
        return "Site content could not be retrieved for analysis."
    
    summary_parts = []
    
    for page in snapshot["pages"]:
        page_summary = f"URL: {page.get('url', 'Unknown')}\n"
        page_summary += f"Title: {page.get('title', 'No title')}\n"
        
        if page.get("meta_description"):
            page_summary += f"Meta Description: {page['meta_description']}\n"
        
        if page.get("headings"):
            page_summary += f"Headings: {', '.join(page['headings'][:5])}\n"
        
        if page.get("text_excerpt"):
            page_summary += f"Content Preview: {page['text_excerpt'][:800]}...\n"
        
        summary_parts.append(page_summary)
    
    return "\n---\n".join(summary_parts)
