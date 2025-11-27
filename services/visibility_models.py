"""
Visibility Models for Multi-LLM Visibility Analysis.
Defines the unified data structures that all visibility providers use.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class BrandHit(BaseModel):
    """A brand/business recommended by an AI provider."""
    name: str
    url: Optional[str] = None
    reason: Optional[str] = None


class ProviderVisibility(BaseModel):
    """Visibility results from a single provider for a single query."""
    provider: str
    query: str
    intent: Optional[str] = None
    recommended_brands: List[BrandHit] = Field(default_factory=list)
    target_found: bool = False
    target_position: Optional[int] = None
    raw_response: Optional[str] = None
    success: bool = True


class QueryVisibilityAggregate(BaseModel):
    """Aggregated visibility results across all providers for a single query."""
    query: str
    intent: Optional[str] = None
    intent_value: Optional[int] = None
    providers: List[ProviderVisibility] = Field(default_factory=list)
    
    def get_provider(self, provider_name: str) -> Optional[ProviderVisibility]:
        """Get results for a specific provider."""
        for p in self.providers:
            if p.provider == provider_name:
                return p
        return None
    
    def target_found_count(self) -> int:
        """Count how many providers found the target business."""
        return sum(1 for p in self.providers if p.target_found)
    
    def all_competitors(self) -> List[str]:
        """Get list of all competitor names across all providers."""
        competitors = []
        for p in self.providers:
            for brand in p.recommended_brands:
                if brand.name not in competitors:
                    competitors.append(brand.name)
        return competitors


class VisibilitySummary(BaseModel):
    """Summary statistics across all queries and providers."""
    total_queries: int = 0
    
    provider_stats: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    
    overall_target_found: int = 0
    overall_target_percent: float = 0.0
    
    top_competitors: List[Dict[str, Any]] = Field(default_factory=list)
    
    competitor_by_provider: Dict[str, List[Dict[str, Any]]] = Field(default_factory=dict)
    
    intent_breakdown: Dict[str, int] = Field(default_factory=dict)


class MultiLLMVisibilityResult(BaseModel):
    """Complete result from multi-LLM visibility analysis."""
    queries: List[QueryVisibilityAggregate] = Field(default_factory=list)
    summary: VisibilitySummary = Field(default_factory=VisibilitySummary)
    providers_used: List[str] = Field(default_factory=list)
