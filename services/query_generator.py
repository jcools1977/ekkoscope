"""
Advanced Query Generation for EkkoScope GEO Visibility Analysis.
Generates 20-30 comprehensive, industry-specific queries with intent classification.
"""

from typing import List, Dict, Any


INTENT_TYPES = {
    "emergency": {
        "description": "Urgent, immediate-need situations",
        "value_score": 10,
        "templates": [
            "emergency {category} near {region}",
            "same day {category} in {region}",
            "urgent {category} service {region}",
            "24 hour {category} in {region}",
        ]
    },
    "high_ticket": {
        "description": "Large purchases or contracts",
        "value_score": 9,
        "templates": [
            "best {category} company for large orders",
            "bulk {category} supplier for businesses",
            "commercial {category} provider in {region}",
            "enterprise {category} solutions",
            "wholesale {category} for {use_case}",
            "{category} for {use_case} procurement",
        ]
    },
    "replenishment": {
        "description": "Regular, recurring purchases",
        "value_score": 7,
        "templates": [
            "where to buy {category} regularly",
            "monthly {category} supplier",
            "{category} subscription service",
            "reliable {category} vendor for businesses",
            "consistent {category} supplier in {region}",
        ]
    },
    "informational": {
        "description": "Research and comparison queries",
        "value_score": 5,
        "templates": [
            "best {category} in {region}",
            "top rated {category} companies",
            "compare {category} suppliers",
            "{category} buying guide",
            "what to look for in {category}",
            "how to choose {category} provider",
        ]
    },
    "transactional": {
        "description": "Ready-to-buy queries",
        "value_score": 8,
        "templates": [
            "buy {category} online",
            "order {category} for delivery",
            "{category} prices {region}",
            "get quote for {category}",
            "{category} near me",
        ]
    }
}

ECOM_QUERY_PATTERNS = {
    "general": [
        "best place to buy {category} online",
        "where to order {category} online",
        "top {category} suppliers online",
        "{category} wholesale distributor",
        "bulk {category} for businesses",
    ],
    "b2b": [
        "{category} supplier for {use_case}",
        "commercial {category} distributor",
        "business {category} vendor",
        "{category} for companies in {region}",
        "industrial {category} supplier",
    ],
    "comparison": [
        "best {category} brands",
        "{category} vs competitors",
        "top rated {category} suppliers",
        "most reliable {category} company",
    ],
    "specific_needs": [
        "{specific_product} supplier",
        "where to buy {specific_product} in bulk",
        "{specific_product} for {use_case}",
        "best {specific_product} vendor",
    ]
}

LOCAL_SERVICE_QUERY_PATTERNS = {
    "location": [
        "best {category} in {region}",
        "{category} near {region}",
        "top {category} company in {region}",
        "{category} contractor {region}",
        "find {category} services in {region}",
    ],
    "quality": [
        "highly rated {category} in {region}",
        "trusted {category} company {region}",
        "recommended {category} {region}",
        "best reviewed {category} near {region}",
    ],
    "service_type": [
        "{specific_service} in {region}",
        "{specific_service} contractor near me",
        "who does {specific_service} in {region}",
    ]
}

B2B_SERVICE_QUERY_PATTERNS = {
    "general": [
        "best {category} company for businesses",
        "top {category} service providers",
        "enterprise {category} solutions",
        "professional {category} services",
    ],
    "industry": [
        "{category} for {use_case}",
        "{industry} {category} provider",
        "{category} consulting for businesses",
    ],
    "scale": [
        "small business {category} services",
        "enterprise {category} solutions",
        "scalable {category} provider",
    ]
}

USE_CASES_BY_INDUSTRY = {
    "industrial packaging": [
        "warehouses", "distribution centers", "manufacturing plants",
        "school districts", "janitorial services", "hospitals",
        "food service", "retail stores", "government facilities"
    ],
    "industrial supplies": [
        "warehouses", "factories", "construction sites",
        "maintenance departments", "facilities management"
    ],
    "roofing": [
        "residential homes", "commercial buildings", "storm damage",
        "new construction", "roof replacement"
    ],
    "plumbing": [
        "residential", "commercial", "emergency repairs",
        "new construction", "remodeling"
    ],
    "hvac": [
        "residential homes", "commercial buildings", "offices",
        "restaurants", "warehouses"
    ],
    "default": [
        "businesses", "companies", "organizations", "enterprises"
    ]
}

SPECIFIC_PRODUCTS_BY_CATEGORY = {
    "industrial packaging": [
        "trash can liners", "garbage bags", "stretch film",
        "pallet wrap", "bubble wrap", "packing tape",
        "55 gallon liners", "heavy duty trash bags",
        "janitorial supplies", "can liners"
    ],
    "industrial supplies": [
        "safety equipment", "cleaning supplies", "tools",
        "maintenance supplies", "facility supplies"
    ],
    "roofing": [
        "shingle installation", "metal roofing", "flat roof repair",
        "roof inspection", "storm damage repair", "gutter installation"
    ],
    "plumbing": [
        "pipe repair", "water heater installation", "drain cleaning",
        "leak detection", "sewer line repair"
    ],
    "hvac": [
        "ac installation", "furnace repair", "duct cleaning",
        "hvac maintenance", "thermostat installation"
    ],
    "default": ["services", "products", "solutions"]
}


def get_use_cases_for_category(category: str) -> List[str]:
    """Get relevant use cases for a category."""
    category_lower = category.lower()
    for key, use_cases in USE_CASES_BY_INDUSTRY.items():
        if key in category_lower or category_lower in key:
            return use_cases
    return USE_CASES_BY_INDUSTRY["default"]


def get_specific_products_for_category(category: str) -> List[str]:
    """Get specific product/service types for a category."""
    category_lower = category.lower()
    for key, products in SPECIFIC_PRODUCTS_BY_CATEGORY.items():
        if key in category_lower or category_lower in key:
            return products
    return SPECIFIC_PRODUCTS_BY_CATEGORY["default"]


def generate_comprehensive_queries(
    name: str,
    categories: List[str],
    regions: List[str],
    business_type: str,
    max_queries: int = 25
) -> List[Dict[str, Any]]:
    """
    Generate comprehensive, industry-specific queries with intent classification.
    
    Returns list of dicts with:
    - query: The search query string
    - intent_type: emergency | high_ticket | replenishment | informational | transactional
    - intent_value: 1-10 score indicating business value
    - category_focus: Which category this query targets
    """
    queries = []
    seen_queries = set()
    
    primary_region = regions[0] if regions else "United States"
    all_regions = regions[:3] if regions else ["United States"]
    
    primary_category = categories[0] if categories else "services"
    all_categories = categories[:3] if categories else ["services"]
    
    use_cases = get_use_cases_for_category(primary_category)
    specific_products = get_specific_products_for_category(primary_category)
    
    def add_query(query: str, intent_type: str, intent_value: int, category: str):
        """Add query if not duplicate."""
        normalized = query.lower().strip()
        if normalized not in seen_queries and len(queries) < max_queries:
            seen_queries.add(normalized)
            queries.append({
                "query": query,
                "intent_type": intent_type,
                "intent_value": intent_value,
                "category_focus": category
            })
    
    if business_type == "ecom":
        for category in all_categories:
            for region in all_regions[:2]:
                add_query(f"best place to buy {category} online", "transactional", 8, category)
                add_query(f"bulk {category} supplier for businesses", "high_ticket", 9, category)
                add_query(f"wholesale {category} distributor", "high_ticket", 9, category)
                add_query(f"where to order {category} online", "transactional", 8, category)
                add_query(f"{category} supplier in {region}", "informational", 6, category)
                
            for use_case in use_cases[:4]:
                add_query(f"{category} supplier for {use_case}", "high_ticket", 9, category)
                add_query(f"bulk {category} for {use_case}", "high_ticket", 9, category)
            
            for product in specific_products[:5]:
                add_query(f"where to buy {product} in bulk", "high_ticket", 9, category)
                add_query(f"best {product} supplier", "transactional", 8, category)
                add_query(f"{product} wholesale prices", "transactional", 8, category)
                add_query(f"commercial {product} distributor", "high_ticket", 9, category)
        
        add_query(f"reliable {primary_category} vendor for businesses", "replenishment", 7, primary_category)
        add_query(f"consistent {primary_category} supplier", "replenishment", 7, primary_category)
        add_query(f"top rated {primary_category} companies online", "informational", 5, primary_category)
        add_query(f"compare {primary_category} suppliers", "informational", 5, primary_category)
        
    elif business_type == "local_service":
        for category in all_categories:
            for region in all_regions:
                add_query(f"best {category} in {region}", "informational", 6, category)
                add_query(f"{category} near {region}", "transactional", 8, category)
                add_query(f"top rated {category} company in {region}", "informational", 6, category)
                add_query(f"trusted {category} contractor in {region}", "transactional", 8, category)
                add_query(f"emergency {category} {region}", "emergency", 10, category)
                add_query(f"same day {category} service {region}", "emergency", 10, category)
            
            for product in specific_products[:4]:
                add_query(f"{product} in {primary_region}", "transactional", 8, category)
                add_query(f"best {product} company near {primary_region}", "informational", 6, category)
        
        add_query(f"highly recommended {primary_category} {primary_region}", "informational", 6, primary_category)
        add_query(f"affordable {primary_category} in {primary_region}", "transactional", 7, primary_category)
        add_query(f"24 hour {primary_category} in {primary_region}", "emergency", 10, primary_category)
        
    elif business_type == "b2b_service":
        for category in all_categories:
            add_query(f"best {category} company for businesses", "high_ticket", 9, category)
            add_query(f"top {category} service providers", "informational", 6, category)
            add_query(f"enterprise {category} solutions", "high_ticket", 9, category)
            add_query(f"professional {category} services", "transactional", 8, category)
            
            for region in all_regions[:2]:
                add_query(f"{category} services in {region}", "transactional", 8, category)
                add_query(f"business {category} provider {region}", "transactional", 8, category)
            
            for use_case in use_cases[:4]:
                add_query(f"{category} for {use_case}", "high_ticket", 9, category)
                add_query(f"{use_case} {category} solutions", "high_ticket", 9, category)
        
        add_query(f"scalable {primary_category} provider", "high_ticket", 9, primary_category)
        add_query(f"reliable {primary_category} partner for companies", "replenishment", 7, primary_category)
        
    else:
        for category in all_categories:
            for region in all_regions:
                add_query(f"best {category} in {region}", "informational", 6, category)
                add_query(f"top {category} provider in {region}", "informational", 6, category)
            
            add_query(f"where to find {category} services", "transactional", 7, category)
            add_query(f"recommended {category} company", "informational", 6, category)
    
    queries.sort(key=lambda x: -x["intent_value"])
    
    return queries[:max_queries]


def generate_query_strings(
    name: str,
    categories: List[str],
    regions: List[str],
    business_type: str,
    max_queries: int = 25
) -> List[str]:
    """
    Convenience function that returns just query strings for backward compatibility.
    """
    comprehensive = generate_comprehensive_queries(
        name=name,
        categories=categories,
        regions=regions,
        business_type=business_type,
        max_queries=max_queries
    )
    return [q["query"] for q in comprehensive]


def get_query_intent_map(
    name: str,
    categories: List[str],
    regions: List[str],
    business_type: str,
    max_queries: int = 25
) -> Dict[str, Dict[str, Any]]:
    """
    Returns a dict mapping query strings to their intent metadata.
    Useful for looking up intent info during analysis.
    """
    comprehensive = generate_comprehensive_queries(
        name=name,
        categories=categories,
        regions=regions,
        business_type=business_type,
        max_queries=max_queries
    )
    return {
        q["query"]: {
            "intent_type": q["intent_type"],
            "intent_value": q["intent_value"],
            "category_focus": q["category_focus"]
        }
        for q in comprehensive
    }
