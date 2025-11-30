"""
Demo PDF Report Generation for EkkoScope
Generates a sample report with realistic but fake data for prospect demos.
"""

from datetime import datetime
from typing import Dict, Any


def get_demo_tenant() -> Dict[str, Any]:
    """Return mock tenant configuration for demo PDF."""
    return {
        "id": "demo",
        "name": "Apex Plumbing & HVAC",
        "primary_domain": "apexplumbinghvac.com",
        "extra_domains": ["apexhvac.com"],
        "business_type": "local_service",
        "regions": ["Denver Metro", "Aurora", "Lakewood", "Boulder"],
        "categories": ["Emergency Plumbing", "HVAC Installation", "Water Heater Repair", "AC Repair"],
        "products_services": [
            "24/7 Emergency Plumbing",
            "Furnace Installation & Repair",
            "Air Conditioning Services",
            "Water Heater Replacement",
            "Drain Cleaning",
            "Sewer Line Repair"
        ]
    }


def get_demo_analysis() -> Dict[str, Any]:
    """Return mock analysis data for demo PDF."""
    
    demo_queries = [
        {
            "query": "emergency plumber near me Denver",
            "intent_type": "emergency",
            "score": 0,
            "ai_response": "For emergency plumbing in Denver, I recommend contacting RotoRooter Denver, Mr. Rooter Plumbing, or Denver Emergency Plumbing. These services offer 24/7 availability and fast response times for urgent plumbing issues like burst pipes, severe leaks, and sewage backups.",
            "competitors": ["RotoRooter Denver", "Mr. Rooter Plumbing", "Denver Emergency Plumbing", "Plumbline Services"],
            "brand_mentioned": False,
            "mention_position": None,
            "multi_llm_visibility": {
                "openai_sim": {"mentioned": False, "position": None, "context": "Not mentioned in recommendations"},
                "perplexity_web": {"mentioned": False, "position": None, "context": "Not found in search results"},
                "gemini_sim": {"mentioned": False, "position": None, "context": "Not included in response"}
            }
        },
        {
            "query": "best HVAC company Denver reviews",
            "intent_type": "high_ticket",
            "score": 1,
            "ai_response": "Based on customer reviews, top HVAC companies in Denver include Plumbline Services with 4.8 stars, Apex Plumbing & HVAC with excellent emergency response, and Brothers Plumbing Heating & Electric. Each offers comprehensive heating and cooling services.",
            "competitors": ["Plumbline Services", "Brothers Plumbing Heating & Electric", "AAA Service Plumbing"],
            "brand_mentioned": True,
            "mention_position": 2,
            "multi_llm_visibility": {
                "openai_sim": {"mentioned": True, "position": 2, "context": "Mentioned as having excellent emergency response"},
                "perplexity_web": {"mentioned": False, "position": None, "context": "Not found in top results"},
                "gemini_sim": {"mentioned": True, "position": 3, "context": "Listed among recommended providers"}
            }
        },
        {
            "query": "water heater installation cost Denver",
            "intent_type": "transactional",
            "score": 0,
            "ai_response": "Water heater installation in Denver typically costs between $1,200-$3,500 depending on the type. Popular installers include Home Depot installation services, Plumbline Services, and local contractors. Tankless water heaters cost more but offer long-term savings.",
            "competitors": ["Home Depot", "Plumbline Services", "Lowes Installation"],
            "brand_mentioned": False,
            "mention_position": None,
            "multi_llm_visibility": {
                "openai_sim": {"mentioned": False, "position": None, "context": "Not mentioned"},
                "perplexity_web": {"mentioned": False, "position": None, "context": "Not in search results"},
                "gemini_sim": {"mentioned": False, "position": None, "context": "Not included"}
            }
        },
        {
            "query": "furnace repair Aurora Colorado",
            "intent_type": "emergency",
            "score": 2,
            "ai_response": "For furnace repair in Aurora, Colorado, I recommend Apex Plumbing & HVAC for their fast same-day service. Other reliable options include Swan Plumbing Heating & Air and One Hour Heating & Air Conditioning. Most offer emergency services during winter months.",
            "competitors": ["Swan Plumbing Heating & Air", "One Hour Heating & Air Conditioning"],
            "brand_mentioned": True,
            "mention_position": 1,
            "multi_llm_visibility": {
                "openai_sim": {"mentioned": True, "position": 1, "context": "Recommended first for fast same-day service"},
                "perplexity_web": {"mentioned": True, "position": 2, "context": "Listed in top local results"},
                "gemini_sim": {"mentioned": True, "position": 1, "context": "Top recommendation"}
            }
        },
        {
            "query": "how to fix a leaky faucet",
            "intent_type": "informational",
            "score": 0,
            "ai_response": "To fix a leaky faucet: 1) Turn off water supply 2) Remove the handle and packing nut 3) Replace the washer or O-ring 4) Reassemble. If the leak persists, you may need to replace the entire faucet cartridge or contact a professional plumber.",
            "competitors": [],
            "brand_mentioned": False,
            "mention_position": None,
            "multi_llm_visibility": {
                "openai_sim": {"mentioned": False, "position": None, "context": "DIY content, no brands mentioned"},
                "perplexity_web": {"mentioned": False, "position": None, "context": "Tutorial content"},
                "gemini_sim": {"mentioned": False, "position": None, "context": "How-to response"}
            }
        },
        {
            "query": "AC repair service Lakewood CO",
            "intent_type": "high_ticket",
            "score": 1,
            "ai_response": "For AC repair in Lakewood, CO, consider Applewood Plumbing Heating & Electric, Apex Plumbing & HVAC, or Blue Sky Plumbing. These companies offer diagnostic services and repairs for all major AC brands with warranty coverage.",
            "competitors": ["Applewood Plumbing Heating & Electric", "Blue Sky Plumbing", "Grand Home Services"],
            "brand_mentioned": True,
            "mention_position": 2,
            "multi_llm_visibility": {
                "openai_sim": {"mentioned": True, "position": 2, "context": "Listed as option for AC repair"},
                "perplexity_web": {"mentioned": False, "position": None, "context": "Not in top results"},
                "gemini_sim": {"mentioned": True, "position": 2, "context": "Mentioned for Lakewood area"}
            }
        },
        {
            "query": "drain cleaning service near me",
            "intent_type": "replenishment",
            "score": 0,
            "ai_response": "For drain cleaning services, popular options include Roto-Rooter, Mr. Rooter Plumbing, and local plumbers. Most charge $100-$300 for basic drain clearing. For severe clogs, hydro jetting services are available from specialized companies.",
            "competitors": ["Roto-Rooter", "Mr. Rooter Plumbing", "Drain Masters"],
            "brand_mentioned": False,
            "mention_position": None,
            "multi_llm_visibility": {
                "openai_sim": {"mentioned": False, "position": None, "context": "National chains recommended"},
                "perplexity_web": {"mentioned": False, "position": None, "context": "Generic results"},
                "gemini_sim": {"mentioned": False, "position": None, "context": "Not mentioned"}
            }
        },
        {
            "query": "sewer line replacement Boulder",
            "intent_type": "high_ticket",
            "score": 0,
            "ai_response": "Sewer line replacement in Boulder costs $3,000-$25,000 depending on length and method. Trenchless replacement is less disruptive. Contact Boulder Plumbing, Planet Plumbing, or Flatirons Plumbing for estimates. Most offer camera inspections first.",
            "competitors": ["Boulder Plumbing", "Planet Plumbing", "Flatirons Plumbing", "Save Home Heat"],
            "brand_mentioned": False,
            "mention_position": None,
            "multi_llm_visibility": {
                "openai_sim": {"mentioned": False, "position": None, "context": "Local Boulder companies mentioned"},
                "perplexity_web": {"mentioned": False, "position": None, "context": "Not in results"},
                "gemini_sim": {"mentioned": False, "position": None, "context": "Not included"}
            }
        },
        {
            "query": "24 hour plumber Denver emergency",
            "intent_type": "emergency",
            "score": 1,
            "ai_response": "For 24-hour emergency plumbing in Denver, top options include Apex Plumbing & HVAC with rapid response times, Denver Emergency Plumbing, and Plumbline Services. All offer after-hours service for burst pipes, flooding, and sewage emergencies.",
            "competitors": ["Denver Emergency Plumbing", "Plumbline Services", "High 5 Plumbing"],
            "brand_mentioned": True,
            "mention_position": 1,
            "multi_llm_visibility": {
                "openai_sim": {"mentioned": True, "position": 1, "context": "First recommendation for rapid response"},
                "perplexity_web": {"mentioned": True, "position": 3, "context": "Found in emergency services"},
                "gemini_sim": {"mentioned": False, "position": None, "context": "Not in top results"}
            }
        },
        {
            "query": "heat pump installation Denver area",
            "intent_type": "high_ticket",
            "score": 0,
            "ai_response": "Heat pump installation in Denver ranges from $4,000-$12,000. Consider Trane, Carrier, or Lennox systems. Installation companies include Brothers Plumbing Heating & Electric, Comfort Pros, and local HVAC contractors. Many offer financing options.",
            "competitors": ["Brothers Plumbing Heating & Electric", "Comfort Pros", "Efficient Home Solutions"],
            "brand_mentioned": False,
            "mention_position": None,
            "multi_llm_visibility": {
                "openai_sim": {"mentioned": False, "position": None, "context": "National brands mentioned"},
                "perplexity_web": {"mentioned": False, "position": None, "context": "Not found"},
                "gemini_sim": {"mentioned": False, "position": None, "context": "Not included"}
            }
        }
    ]
    
    genius_insights = {
        "patterns": [
            "Your brand visibility is strongest for emergency and urgent service queries, indicating good local SEO for time-sensitive searches",
            "You're consistently outranked by national chains (Roto-Rooter, Mr. Rooter) for generic service queries without location modifiers",
            "AI assistants favor mentioning you when users search for Aurora and Lakewood areas, but Denver core market shows weaker presence",
            "High-ticket service queries (HVAC installation, water heaters) show lower visibility - competitors with strong review profiles dominate"
        ],
        "opportunities": [
            "Create dedicated landing pages for each service area to improve AI training data recognition",
            "Develop comprehensive pricing guides for water heater and HVAC installation to capture transactional queries",
            "Build out FAQ content addressing common plumbing and HVAC questions to capture informational searches",
            "Strengthen Google Business Profile with more photos, posts, and review responses"
        ],
        "quick_wins": [
            "Add structured data markup (LocalBusiness schema) to all service pages",
            "Claim and optimize Bing Places listing for Perplexity/Bing AI visibility",
            "Respond to all Google reviews within 24 hours to boost engagement signals",
            "Add emergency service hours prominently to homepage and contact pages"
        ],
        "page_blueprints": [
            {
                "title": "Emergency Plumbing Denver - 24/7 Same-Day Service",
                "url_slug": "/emergency-plumbing-denver",
                "target_keywords": ["emergency plumber Denver", "24 hour plumber Denver", "burst pipe repair Denver"],
                "content_outline": "Hero with phone number, service areas map, common emergencies handled, response time guarantee, customer testimonials, FAQ section",
                "word_count": 1500,
                "priority": "HIGH"
            },
            {
                "title": "Water Heater Installation & Replacement Denver",
                "url_slug": "/water-heater-installation-denver",
                "target_keywords": ["water heater installation Denver", "water heater replacement cost", "tankless water heater Denver"],
                "content_outline": "Types of water heaters, cost breakdown, installation process, brand options, financing, warranty info, before/after gallery",
                "word_count": 2000,
                "priority": "HIGH"
            },
            {
                "title": "HVAC Services Aurora CO - Heating & Cooling Experts",
                "url_slug": "/hvac-services-aurora-colorado",
                "target_keywords": ["HVAC Aurora CO", "furnace repair Aurora", "AC repair Aurora Colorado"],
                "content_outline": "Service area details, seasonal maintenance packages, emergency services, equipment brands serviced, certifications, reviews",
                "word_count": 1800,
                "priority": "MEDIUM"
            },
            {
                "title": "Drain Cleaning & Sewer Services Denver Metro",
                "url_slug": "/drain-cleaning-denver",
                "target_keywords": ["drain cleaning Denver", "sewer line repair", "clogged drain service"],
                "content_outline": "Service types, pricing guide, camera inspection, hydro jetting, root removal, preventive maintenance plans",
                "word_count": 1200,
                "priority": "MEDIUM"
            }
        ],
        "roadmap_tasks": [
            {"task": "Implement LocalBusiness schema markup on all pages", "week": 1, "impact": "HIGH", "effort": "LOW"},
            {"task": "Create emergency plumbing landing page with 24/7 messaging", "week": 1, "impact": "HIGH", "effort": "MEDIUM"},
            {"task": "Optimize Google Business Profile with new photos and posts", "week": 1, "impact": "MEDIUM", "effort": "LOW"},
            {"task": "Build water heater installation guide with pricing", "week": 2, "impact": "HIGH", "effort": "HIGH"},
            {"task": "Set up review response workflow (24-hour SLA)", "week": 2, "impact": "MEDIUM", "effort": "LOW"},
            {"task": "Create Aurora-specific HVAC service page", "week": 2, "impact": "MEDIUM", "effort": "MEDIUM"},
            {"task": "Claim and optimize Bing Places listing", "week": 3, "impact": "MEDIUM", "effort": "LOW"},
            {"task": "Develop drain cleaning service page with pricing", "week": 3, "impact": "MEDIUM", "effort": "MEDIUM"},
            {"task": "Add customer testimonial videos to key pages", "week": 3, "impact": "MEDIUM", "effort": "HIGH"},
            {"task": "Create seasonal HVAC maintenance content series", "week": 4, "impact": "LOW", "effort": "MEDIUM"},
            {"task": "Build out FAQ section with 20+ common questions", "week": 4, "impact": "MEDIUM", "effort": "MEDIUM"},
            {"task": "Launch email capture for maintenance reminders", "week": 4, "impact": "LOW", "effort": "MEDIUM"}
        ]
    }
    
    suggestions = [
        {
            "type": "content",
            "title": "Create Emergency Service Landing Pages",
            "description": "Develop dedicated pages for 24/7 emergency plumbing and HVAC services. Include prominent phone numbers, response time guarantees, and service area maps. AI assistants favor pages with clear emergency service indicators.",
            "priority": "high",
            "impact": "Capture high-intent emergency queries where you're currently invisible"
        },
        {
            "type": "technical",
            "title": "Implement Structured Data Markup",
            "description": "Add LocalBusiness, Service, and FAQ schema to all pages. This helps AI systems understand your business offerings and service areas, improving chances of being recommended.",
            "priority": "high",
            "impact": "Improve AI understanding of your services and locations"
        },
        {
            "type": "content",
            "title": "Build Comprehensive Pricing Guides",
            "description": "Create detailed pricing pages for water heater installation, HVAC systems, and major plumbing services. Include cost ranges, factors affecting price, and financing options.",
            "priority": "medium",
            "impact": "Capture transactional queries from users ready to purchase"
        },
        {
            "type": "local_seo",
            "title": "Expand Location-Specific Content",
            "description": "Create dedicated pages for each service area (Aurora, Lakewood, Boulder) with local testimonials, service area maps, and area-specific information.",
            "priority": "medium",
            "impact": "Improve visibility in suburban markets where you show strength"
        },
        {
            "type": "reputation",
            "title": "Accelerate Review Generation",
            "description": "Implement a systematic review request process. AI assistants heavily weight review signals when making recommendations. Aim for 10+ new reviews monthly.",
            "priority": "high",
            "impact": "Increase trust signals that influence AI recommendations"
        }
    ]
    
    return {
        "tenant_name": "Apex Plumbing & HVAC",
        "total_queries": len(demo_queries),
        "results": demo_queries,
        "genius_insights": genius_insights,
        "suggestions": suggestions,
        "multi_llm_summary": {
            "openai_sim": {"total": 10, "mentioned": 5, "avg_position": 1.6},
            "perplexity_web": {"total": 10, "mentioned": 2, "avg_position": 2.5},
            "gemini_sim": {"total": 10, "mentioned": 4, "avg_position": 1.75}
        },
        "report_generated_at": datetime.utcnow().isoformat(),
        "is_demo": True
    }


def generate_demo_pdf() -> bytes:
    """Generate a complete demo PDF report."""
    from services.reporting import build_ekkoscope_pdf
    
    tenant = get_demo_tenant()
    analysis = get_demo_analysis()
    
    return build_ekkoscope_pdf(tenant, analysis)
