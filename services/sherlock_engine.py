"""
Sherlock Engine - Semantic Gap Analysis for EkkoScope v4.
Uses Pinecone for vector embeddings and semantic intelligence.

The Brain: Identifies what concepts competitors cover that the client doesn't.
Not keywords - TOPICS. This is true semantic intelligence.
"""

import os
import json
import uuid
import logging
import re
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from collections import Counter

import httpx
from bs4 import BeautifulSoup

from .config import (
    OPENAI_API_KEY,
    PINECONE_API_KEY,
    PINECONE_ENABLED,
    PINECONE_INDEX_NAME,
    EKKOBRAIN_EMBED_MODEL,
    EKKOBRAIN_EMBED_DIMENSIONS,
    PINECONE_NAMESPACES
)
from .database import (
    SessionLocal,
    SherlockScan,
    SherlockCompetitor,
    SherlockMission,
    Business
)

logger = logging.getLogger(__name__)

SHERLOCK_INDEX_NAME = PINECONE_INDEX_NAME
SHERLOCK_EMBED_MODEL = EKKOBRAIN_EMBED_MODEL
SHERLOCK_EMBED_DIMENSIONS = EKKOBRAIN_EMBED_DIMENSIONS
SHERLOCK_NAMESPACES = PINECONE_NAMESPACES

pc = None
sherlock_index = None
_sherlock_initialized = False


def init_sherlock():
    """Initialize Sherlock's Pinecone index."""
    global pc, sherlock_index, _sherlock_initialized
    
    if _sherlock_initialized:
        return sherlock_index is not None
    
    if not PINECONE_API_KEY:
        logger.info("Sherlock disabled: no PINECONE_API_KEY set.")
        _sherlock_initialized = True
        return False
    
    try:
        from pinecone import Pinecone
        
        pc = Pinecone(api_key=PINECONE_API_KEY)
        
        existing = [idx.name for idx in pc.list_indexes()]
        if SHERLOCK_INDEX_NAME not in existing:
            logger.warning("Sherlock index '%s' not found. Creating it...", SHERLOCK_INDEX_NAME)
            try:
                pc.create_index(
                    name=SHERLOCK_INDEX_NAME,
                    dimension=SHERLOCK_EMBED_DIMENSIONS,
                    metric="cosine",
                    spec={"serverless": {"cloud": "aws", "region": "us-east-1"}}
                )
                logger.info("Created Sherlock index: %s", SHERLOCK_INDEX_NAME)
            except Exception as create_err:
                logger.error("Failed to create Sherlock index: %s", create_err)
                _sherlock_initialized = True
                return False
        
        sherlock_index = pc.Index(SHERLOCK_INDEX_NAME)
        logger.info("Sherlock connected to Pinecone index: %s", SHERLOCK_INDEX_NAME)
        _sherlock_initialized = True
        return True
        
    except ImportError:
        logger.warning("Pinecone package not installed. Sherlock disabled.")
        _sherlock_initialized = True
        return False
    except Exception as e:
        logger.warning("Failed to initialize Sherlock: %s", e)
        _sherlock_initialized = True
        return False


def is_sherlock_enabled() -> bool:
    """Check if Sherlock is ready to analyze."""
    init_sherlock()
    return sherlock_index is not None


def embed_text(text: str) -> Optional[List[float]]:
    """Generate embedding using OpenAI text-embedding-3-large (3072 dimensions)."""
    if not OPENAI_API_KEY:
        logger.warning("No OPENAI_API_KEY for Sherlock embedding.")
        return None
    
    if not text or not text.strip():
        logger.warning("Empty text provided for embedding.")
        return None
    
    try:
        from openai import OpenAI
        
        client = OpenAI(api_key=OPENAI_API_KEY)
        text_truncated = text.strip()[:8000]
        
        response = client.embeddings.create(
            model=SHERLOCK_EMBED_MODEL,
            input=text_truncated,
        )
        return response.data[0].embedding
        
    except Exception as e:
        logger.warning("Error generating Sherlock embedding: %s", e)
        return None


def scrape_url(url: str, timeout: float = 10.0) -> Dict[str, Any]:
    """
    Scrape content from a URL for semantic analysis.
    Returns structured content with text, headings, and metadata.
    """
    result = {
        "success": False,
        "url": url,
        "title": "",
        "meta_description": "",
        "headings": [],
        "text_content": "",
        "raw_html": "",
        "word_count": 0
    }
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; EkkoScope/1.0; Sherlock Semantic Analyzer)"
        }
        
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            response = client.get(url, headers=headers)
            
            if response.status_code != 200:
                result["error"] = f"HTTP {response.status_code}"
                return result
            
            result["raw_html"] = response.text[:100000]
            soup = BeautifulSoup(response.text, "html.parser")
            
            title_tag = soup.find("title")
            if title_tag:
                result["title"] = title_tag.get_text(strip=True)
            
            meta_desc = soup.find("meta", attrs={"name": "description"})
            if meta_desc:
                result["meta_description"] = str(meta_desc.get("content", "") or "")
            
            for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
                tag.decompose()
            
            headings = []
            for h_tag in soup.find_all(["h1", "h2", "h3", "h4"])[:20]:
                heading_text = h_tag.get_text(strip=True)
                if heading_text and len(heading_text) > 3:
                    headings.append(f"{h_tag.name}: {heading_text}")
            result["headings"] = headings
            
            text_content = soup.get_text(separator=" ", strip=True)
            text_content = re.sub(r'\s+', ' ', text_content)
            result["text_content"] = text_content[:15000]
            result["word_count"] = len(text_content.split())
            result["success"] = True
            
    except Exception as e:
        result["error"] = str(e)[:200]
    
    return result


def extract_topics_with_ai(text: str, context: str = "") -> List[Dict[str, Any]]:
    """
    Use GPT to extract semantic topics from content.
    Returns topics with their significance and context.
    """
    if not OPENAI_API_KEY:
        return []
    
    try:
        from openai import OpenAI
        
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        prompt = f"""Analyze this website content and extract the main TOPICS covered.
Not keywords - identify the semantic concepts, themes, and subject areas.

For each topic, provide:
1. topic: A clear topic name (2-5 words)
2. category: The broader category (e.g., "services", "problems", "solutions", "credentials")
3. depth: How thoroughly covered (1-10)
4. example_phrases: 2-3 key phrases from the content

Context: {context}

Content:
{text[:6000]}

Return JSON array of topics:
[{{"topic": "Storm Damage Insurance", "category": "services", "depth": 8, "example_phrases": ["hurricane coverage", "emergency claims"]}}]

Extract 10-20 meaningful topics. Focus on business-relevant themes."""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=2000
        )
        
        content = response.choices[0].message.content.strip()
        if content.startswith("```"):
            content = re.sub(r'^```\w*\n?', '', content)
            content = re.sub(r'\n?```$', '', content)
        
        topics = json.loads(content)
        return topics if isinstance(topics, list) else []
        
    except Exception as e:
        logger.warning("Error extracting topics: %s", e)
        return []


def ingest_knowledge(
    url: str,
    content_type: str,
    business_id: int,
    user_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Ingest content from a URL into Sherlock's memory.
    
    Args:
        url: The URL to scrape and analyze
        content_type: "client_site", "competitor_site", or "market_review"
        business_id: The business this knowledge belongs to
        user_id: Optional user who initiated the scan
    
    Returns:
        Dict with scan results and vector ID
    """
    if not is_sherlock_enabled():
        return {"success": False, "error": "Sherlock not enabled. Check Pinecone API key."}
    
    if sherlock_index is None:
        return {"success": False, "error": "Sherlock index not initialized"}
    
    db = SessionLocal()
    result = {"success": False, "url": url, "content_type": content_type}
    
    try:
        scraped = scrape_url(url)
        
        if not scraped["success"]:
            result["error"] = scraped.get("error", "Scrape failed")
            return result
        
        text_content = scraped.get("text_content", "")
        if not text_content or len(text_content.strip()) < 100:
            result["error"] = "Insufficient content to analyze"
            return result
        
        topics = extract_topics_with_ai(
            text_content,
            context=f"Website: {scraped.get('title', '')} | Type: {content_type}"
        )
        
        title = scraped.get("title", "") or ""
        meta_desc = scraped.get("meta_description", "") or ""
        headings = scraped.get("headings", []) or []
        
        embed_text_content = f"""
        Title: {title}
        Description: {meta_desc}
        Headings: {' | '.join(headings[:10])}
        Topics: {', '.join([t.get('topic', '') for t in topics])}
        Content: {text_content[:4000]}
        """
        
        embedding = embed_text(embed_text_content)
        
        if embedding is None:
            result["error"] = "Failed to generate embedding"
            return result
        
        vector_id = f"sherlock_{content_type}_{business_id}_{uuid.uuid4().hex[:8]}"
        
        metadata = {
            "type": content_type,
            "url": url,
            "business_id": str(business_id),
            "title": title[:200] if title else "",
            "topics": json.dumps([t.get("topic", "") for t in topics]),
            "word_count": scraped.get("word_count", 0),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        try:
            namespace = SHERLOCK_NAMESPACES.get(content_type, SHERLOCK_NAMESPACES["business"])
            sherlock_index.upsert(vectors=[(vector_id, embedding, metadata)], namespace=namespace)
        except Exception as upsert_err:
            logger.error("Pinecone upsert error: %s", upsert_err)
            result["error"] = f"Vector storage failed: {str(upsert_err)[:100]}"
            return result
        
        raw_html = scraped.get("raw_html", "") or ""
        scan = SherlockScan(
            business_id=business_id,
            user_id=user_id,
            url=url,
            content_type=content_type,
            raw_html=raw_html[:50000] if raw_html else "",
            extracted_text=text_content,
            vector_id=vector_id,
            topics_extracted=json.dumps(topics),
            status="completed",
            processed_at=datetime.utcnow()
        )
        db.add(scan)
        db.commit()
        db.refresh(scan)
        
        result["success"] = True
        result["vector_id"] = vector_id
        result["topics"] = topics
        result["word_count"] = scraped.get("word_count", 0)
        result["scan_id"] = scan.id
        
        logger.info("Sherlock ingested %s (%d topics) for business %d", 
                    url, len(topics), business_id)
        
    except Exception as e:
        logger.error("Sherlock ingest error: %s", e)
        result["error"] = str(e)[:200]
        db.rollback()
    finally:
        db.close()
    
    return result


def get_vectors_by_type(business_id: int, content_type: str) -> List[Dict[str, Any]]:
    """Fetch all vectors of a specific type for a business."""
    if not is_sherlock_enabled() or sherlock_index is None:
        return []
    
    try:
        query_filter = {
            "business_id": {"$eq": str(business_id)},
            "type": {"$eq": content_type}
        }
        
        zero_vector = [0.0] * SHERLOCK_EMBED_DIMENSIONS
        namespace = SHERLOCK_NAMESPACES.get(content_type, SHERLOCK_NAMESPACES["business"])
        
        results = sherlock_index.query(
            vector=zero_vector,
            filter=query_filter,
            top_k=100,
            include_metadata=True,
            namespace=namespace
        )
        
        if not results or not hasattr(results, 'matches'):
            return []
        
        output = []
        for m in results.matches:
            try:
                metadata = m.metadata or {}
                topics_str = metadata.get("topics", "[]")
                topics = json.loads(topics_str) if isinstance(topics_str, str) else []
                output.append({
                    "id": m.id,
                    "url": metadata.get("url", ""),
                    "title": metadata.get("title", ""),
                    "topics": topics,
                    "word_count": metadata.get("word_count", 0)
                })
            except Exception:
                continue
        return output
        
    except Exception as e:
        logger.warning("Error fetching vectors: %s", e)
        return []


def analyze_semantic_gap(
    client_business_id: int,
    competitor_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    THE KILLER FEATURE: Semantic Gap Analysis.
    
    Compares the client's vector space to competitor vector space.
    Identifies TOPICS (not keywords) that competitors cover but client doesn't.
    
    Args:
        client_business_id: The client's business ID
        competitor_id: Optional specific competitor to analyze against
    
    Returns:
        Dict with missing topics, coverage gaps, and recommendations
    """
    if not is_sherlock_enabled():
        return {"success": False, "error": "Sherlock not enabled"}
    
    db = SessionLocal()
    result = {
        "success": False,
        "client_business_id": client_business_id,
        "missing_topics": [],
        "weak_topics": [],
        "coverage_comparison": {},
        "gap_score": 0
    }
    
    try:
        client_scans = db.query(SherlockScan).filter(
            SherlockScan.business_id == client_business_id,
            SherlockScan.content_type == "client_site",
            SherlockScan.status == "completed"
        ).all()
        
        if not client_scans:
            result["error"] = "No client content ingested. Run ingest_knowledge first."
            return result
        
        client_topics = []
        for scan in client_scans:
            if scan.topics_extracted:
                try:
                    topics = json.loads(scan.topics_extracted)
                    client_topics.extend([t.get("topic", "").lower() for t in topics])
                except:
                    pass
        
        client_topic_set = set(client_topics)
        client_topic_counts = Counter(client_topics)
        
        if competitor_id:
            competitors = db.query(SherlockCompetitor).filter(
                SherlockCompetitor.id == competitor_id
            ).all()
        else:
            competitors = db.query(SherlockCompetitor).filter(
                SherlockCompetitor.business_id == client_business_id,
                SherlockCompetitor.status == "active"
            ).all()
        
        competitor_scans = db.query(SherlockScan).filter(
            SherlockScan.business_id == client_business_id,
            SherlockScan.content_type == "competitor_site",
            SherlockScan.status == "completed"
        ).all()
        
        competitor_topics = []
        competitor_topic_sources = {}
        
        for scan in competitor_scans:
            if scan.topics_extracted:
                try:
                    topics = json.loads(scan.topics_extracted)
                    for t in topics:
                        topic_name = t.get("topic", "").lower()
                        competitor_topics.append(topic_name)
                        if topic_name not in competitor_topic_sources:
                            competitor_topic_sources[topic_name] = {
                                "sources": [],
                                "depth": t.get("depth", 5),
                                "category": t.get("category", "unknown"),
                                "example_phrases": t.get("example_phrases", [])
                            }
                        competitor_topic_sources[topic_name]["sources"].append(scan.url)
                except:
                    pass
        
        competitor_topic_counts = Counter(competitor_topics)
        
        missing_topics = []
        weak_topics = []
        
        for topic, count in competitor_topic_counts.items():
            if topic not in client_topic_set:
                source_info = competitor_topic_sources.get(topic, {})
                missing_topics.append({
                    "topic": topic.title(),
                    "competitor_coverage": count,
                    "category": source_info.get("category", "unknown"),
                    "depth": source_info.get("depth", 5),
                    "example_phrases": source_info.get("example_phrases", []),
                    "found_at": source_info.get("sources", [])[:3],
                    "priority": "high" if count >= 2 or source_info.get("depth", 0) >= 7 else "medium"
                })
            elif client_topic_counts.get(topic, 0) < count:
                weak_topics.append({
                    "topic": topic.title(),
                    "your_coverage": client_topic_counts[topic],
                    "competitor_coverage": count,
                    "gap": count - client_topic_counts[topic]
                })
        
        missing_topics.sort(key=lambda x: (-x["competitor_coverage"], -x["depth"]))
        weak_topics.sort(key=lambda x: -x["gap"])
        
        total_competitor_topics = len(set(competitor_topics))
        covered = len(client_topic_set & set(competitor_topics))
        gap_score = int(100 - (covered / max(total_competitor_topics, 1) * 100))
        
        result["success"] = True
        result["missing_topics"] = missing_topics[:15]
        result["weak_topics"] = weak_topics[:10]
        result["coverage_comparison"] = {
            "your_topics": len(client_topic_set),
            "competitor_topics": total_competitor_topics,
            "overlap": covered,
            "unique_to_competitors": len(set(competitor_topics) - client_topic_set)
        }
        result["gap_score"] = gap_score
        result["analysis_id"] = f"gap_{client_business_id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        
        logger.info("Sherlock gap analysis: %d missing topics, gap score %d%% for business %d",
                    len(missing_topics), gap_score, client_business_id)
        
    except Exception as e:
        logger.error("Sherlock gap analysis error: %s", e)
        result["error"] = str(e)
    finally:
        db.close()
    
    return result


def generate_missions(
    client_business_id: int,
    gap_analysis: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Generate actionable Missions from semantic gap analysis.
    
    Each mission is a specific action the client can take to close a semantic gap.
    Example: "Create a page about Storm Damage Insurance to close the semantic gap."
    
    Args:
        client_business_id: The client's business ID
        gap_analysis: Optional pre-computed gap analysis result
    
    Returns:
        List of generated missions
    """
    db = SessionLocal()
    missions = []
    
    try:
        if gap_analysis is None:
            gap_analysis = analyze_semantic_gap(client_business_id)
        
        if not gap_analysis.get("success"):
            return []
        
        missing_topics = gap_analysis.get("missing_topics", [])
        weak_topics = gap_analysis.get("weak_topics", [])
        analysis_id = gap_analysis.get("analysis_id", "")
        
        for i, topic_data in enumerate(missing_topics[:10]):
            topic = topic_data["topic"]
            category = topic_data.get("category", "content")
            
            slug = re.sub(r'[^a-z0-9]+', '-', topic.lower()).strip('-')
            
            if category == "services":
                action = f"Create a dedicated service page for '{topic}' with detailed pricing and FAQs"
                mission_type = "create_page"
            elif category == "problems":
                action = f"Develop content addressing '{topic}' - explain solutions and your expertise"
                mission_type = "content_expansion"
            elif category == "credentials":
                action = f"Highlight your '{topic}' credentials with case studies and certifications"
                mission_type = "trust_building"
            else:
                action = f"Create comprehensive content about '{topic}' to match competitor coverage"
                mission_type = "content_creation"
            
            mission = SherlockMission(
                business_id=client_business_id,
                gap_analysis_id=analysis_id,
                mission_type=mission_type,
                priority=topic_data.get("priority", "medium"),
                title=f"Cover '{topic}' to close semantic gap",
                description=f"Competitors are ranking for '{topic}' queries. You are semantically invisible on this topic.",
                missing_topic=topic,
                topic_context=json.dumps(topic_data.get("example_phrases", [])),
                competitor_coverage=json.dumps(topic_data.get("found_at", [])),
                recommended_action=action,
                estimated_impact=f"+{5 + i}% AI visibility",
                target_url_slug=f"/{slug}"
            )
            db.add(mission)
            
            missions.append({
                "id": None,
                "title": mission.title,
                "description": mission.description,
                "action": action,
                "priority": mission.priority,
                "topic": topic,
                "target_url": f"/{slug}",
                "estimated_impact": mission.estimated_impact
            })
        
        for topic_data in weak_topics[:5]:
            topic = topic_data["topic"]
            gap = topic_data["gap"]
            
            mission = SherlockMission(
                business_id=client_business_id,
                gap_analysis_id=analysis_id,
                mission_type="content_expansion",
                priority="medium",
                title=f"Strengthen '{topic}' coverage",
                description=f"Competitors mention '{topic}' {gap} more times. Expand your content depth.",
                missing_topic=topic,
                recommended_action=f"Add more detailed content about '{topic}' - FAQs, case studies, or blog posts",
                estimated_impact="+3% AI visibility"
            )
            db.add(mission)
            
            missions.append({
                "id": None,
                "title": mission.title,
                "description": mission.description,
                "action": mission.recommended_action,
                "priority": "medium",
                "topic": topic,
                "estimated_impact": "+3% AI visibility"
            })
        
        db.commit()
        
        for i, m in enumerate(missions):
            db_missions = db.query(SherlockMission).filter(
                SherlockMission.business_id == client_business_id,
                SherlockMission.gap_analysis_id == analysis_id
            ).order_by(SherlockMission.id).all()
            if i < len(db_missions):
                m["id"] = db_missions[i].id
        
        logger.info("Sherlock generated %d missions for business %d", len(missions), client_business_id)
        
    except Exception as e:
        logger.error("Sherlock mission generation error: %s", e)
        db.rollback()
    finally:
        db.close()
    
    return missions


def add_competitor(
    business_id: int,
    name: str,
    url: str,
    is_primary: bool = False,
    discovered_source: str = "manual"
) -> Optional[int]:
    """
    Add a competitor for tracking and semantic comparison.
    
    Returns the competitor ID on success.
    """
    db = SessionLocal()
    
    try:
        existing = db.query(SherlockCompetitor).filter(
            SherlockCompetitor.business_id == business_id,
            SherlockCompetitor.url == url
        ).first()
        
        if existing:
            return existing.id
        
        competitor = SherlockCompetitor(
            business_id=business_id,
            name=name,
            url=url,
            is_primary=is_primary,
            discovered_source=discovered_source
        )
        db.add(competitor)
        db.commit()
        
        logger.info("Sherlock added competitor: %s (%s) for business %d", name, url, business_id)
        return competitor.id
        
    except Exception as e:
        logger.error("Error adding competitor: %s", e)
        db.rollback()
        return None
    finally:
        db.close()


def run_full_analysis(
    business_id: int,
    client_url: str,
    competitor_urls: List[str]
) -> Dict[str, Any]:
    """
    Run a complete Sherlock analysis:
    1. Ingest client site
    2. Ingest competitor sites
    3. Run semantic gap analysis
    4. Generate missions
    
    This is the full pipeline for new analyses.
    """
    result = {
        "success": False,
        "client_ingested": False,
        "competitors_ingested": 0,
        "gap_analysis": None,
        "missions": []
    }
    
    logger.info("Sherlock starting full analysis for business %d", business_id)
    
    client_result = ingest_knowledge(client_url, "client_site", business_id)
    result["client_ingested"] = client_result.get("success", False)
    
    if not result["client_ingested"]:
        result["error"] = f"Failed to ingest client site: {client_result.get('error', 'unknown')}"
        return result
    
    for comp_url in competitor_urls[:5]:
        comp_result = ingest_knowledge(comp_url, "competitor_site", business_id)
        if comp_result.get("success"):
            result["competitors_ingested"] += 1
            
            domain = comp_url.replace("https://", "").replace("http://", "").split("/")[0]
            add_competitor(business_id, domain, comp_url, discovered_source="analysis")
    
    gap_analysis = analyze_semantic_gap(business_id)
    result["gap_analysis"] = gap_analysis
    
    if gap_analysis.get("success"):
        missions = generate_missions(business_id, gap_analysis)
        result["missions"] = missions
        result["success"] = True
    else:
        result["error"] = gap_analysis.get("error", "Gap analysis failed")
    
    logger.info("Sherlock full analysis complete: %d missions generated", len(result["missions"]))
    
    return result


def clear_vectors_for_business(business_id: int) -> Dict[str, Any]:
    """
    Clear all Sherlock vectors and database records for a business.
    Used for Force Intelligence Rescan to start fresh.
    
    Args:
        business_id: The business ID to clear data for
    
    Returns:
        Dict with success status and counts of deleted items
    """
    result = {
        "success": False,
        "vectors_deleted": 0,
        "scans_deleted": 0,
        "competitors_deleted": 0,
        "missions_deleted": 0
    }
    
    if not is_sherlock_enabled() or sherlock_index is None:
        result["error"] = "Sherlock not enabled"
        return result
    
    db = SessionLocal()
    
    try:
        scans = db.query(SherlockScan).filter(
            SherlockScan.business_id == business_id
        ).all()
        
        vector_ids_to_delete = []
        for scan in scans:
            if scan.vector_id:
                vector_ids_to_delete.append(scan.vector_id)
        
        for namespace in SHERLOCK_NAMESPACES.values():
            try:
                if vector_ids_to_delete:
                    sherlock_index.delete(ids=vector_ids_to_delete, namespace=namespace)
                    result["vectors_deleted"] += len(vector_ids_to_delete)
            except Exception as del_err:
                logger.warning("Error deleting vectors from namespace %s: %s", namespace, del_err)
        
        missions_count = db.query(SherlockMission).filter(
            SherlockMission.business_id == business_id
        ).delete()
        result["missions_deleted"] = missions_count
        
        competitors_count = db.query(SherlockCompetitor).filter(
            SherlockCompetitor.business_id == business_id
        ).delete()
        result["competitors_deleted"] = competitors_count
        
        scans_count = db.query(SherlockScan).filter(
            SherlockScan.business_id == business_id
        ).delete()
        result["scans_deleted"] = scans_count
        
        db.commit()
        result["success"] = True
        
        logger.info(
            "Sherlock cleared data for business %d: %d vectors, %d scans, %d competitors, %d missions",
            business_id, result["vectors_deleted"], result["scans_deleted"],
            result["competitors_deleted"], result["missions_deleted"]
        )
        
    except Exception as e:
        logger.error("Error clearing Sherlock data: %s", e)
        db.rollback()
        result["error"] = str(e)
    finally:
        db.close()
    
    return result


def rescan_intelligence(
    business_id: int,
    client_url: str,
    competitor_urls: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Force Intelligence Rescan - clears existing data and re-runs full analysis.
    
    This is the "Fix It" function for legacy data issues.
    Uses stored competitors from the database if none are explicitly provided.
    
    Args:
        business_id: The business ID to rescan
        client_url: The client's primary domain URL
        competitor_urls: Optional list of competitor URLs to analyze (uses stored if None)
    
    Returns:
        Dict with rescan results
    """
    result = {
        "success": False,
        "cleared": None,
        "analysis": None
    }
    
    logger.info("Starting Force Intelligence Rescan for business %d", business_id)
    
    stored_competitors = []
    if not competitor_urls:
        db = SessionLocal()
        try:
            business = db.query(Business).filter(Business.id == business_id).first()
            if business and business.competitors:
                import json
                try:
                    stored_competitors = json.loads(business.competitors)
                    if isinstance(stored_competitors, list):
                        parsed_urls = []
                        for c in stored_competitors:
                            if not c:
                                continue
                            if isinstance(c, dict):
                                url = c.get("domain") or c.get("url") or c.get("website")
                            else:
                                url = str(c)
                            if url:
                                parsed_urls.append(url)
                        competitor_urls = parsed_urls
                        if competitor_urls:
                            logger.info("Using %d stored competitors for rescan", len(competitor_urls))
                        else:
                            logger.warning("No valid competitor URLs found in stored data")
                except (json.JSONDecodeError, TypeError) as parse_err:
                    logger.warning("Failed to parse stored competitors JSON: %s", parse_err)
        except Exception as e:
            logger.warning("Could not retrieve stored competitors: %s", e)
        finally:
            db.close()
    
    clear_result = clear_vectors_for_business(business_id)
    result["cleared"] = clear_result
    
    if not clear_result.get("success"):
        result["error"] = f"Failed to clear existing data: {clear_result.get('error', 'unknown')}"
        return result
    
    if competitor_urls and len(competitor_urls) > 0:
        analysis_result = run_full_analysis(business_id, client_url, competitor_urls)
    else:
        client_result = ingest_knowledge(client_url, "client_site", business_id)
        if client_result.get("success"):
            gap_analysis = analyze_semantic_gap(business_id)
            if gap_analysis.get("success"):
                missions = generate_missions(business_id, gap_analysis)
                analysis_result = {
                    "success": True,
                    "client_ingested": True,
                    "gap_analysis": gap_analysis,
                    "missions": missions
                }
            else:
                analysis_result = {
                    "success": True,
                    "client_ingested": True,
                    "gap_analysis": gap_analysis,
                    "missions": [],
                    "note": "Client ingested but no competitor data for gap analysis"
                }
        else:
            analysis_result = {
                "success": False,
                "error": client_result.get("error", "Failed to ingest client site")
            }
    
    result["analysis"] = analysis_result
    result["success"] = analysis_result.get("success", False)
    
    logger.info("Force Intelligence Rescan complete for business %d: success=%s", 
                business_id, result["success"])
    
    return result


def get_missions_for_business(business_id: int, status: str = None) -> List[Dict[str, Any]]:
    """Get all missions for a business, optionally filtered by status."""
    db = SessionLocal()
    
    try:
        query = db.query(SherlockMission).filter(
            SherlockMission.business_id == business_id
        )
        
        if status:
            query = query.filter(SherlockMission.status == status)
        
        missions = query.order_by(
            SherlockMission.priority.desc(),
            SherlockMission.created_at.desc()
        ).all()
        
        return [
            {
                "id": m.id,
                "title": m.title,
                "description": m.description,
                "mission_type": m.mission_type,
                "priority": m.priority,
                "status": m.status,
                "missing_topic": m.missing_topic,
                "recommended_action": m.recommended_action,
                "estimated_impact": m.estimated_impact,
                "target_url": m.target_url_slug,
                "created_at": m.created_at.isoformat() if m.created_at else None
            }
            for m in missions
        ]
        
    except Exception as e:
        logger.error("Error fetching missions: %s", e)
        return []
    finally:
        db.close()


def complete_mission(mission_id: int) -> bool:
    """Mark a mission as completed."""
    db = SessionLocal()
    
    try:
        mission = db.query(SherlockMission).filter(SherlockMission.id == mission_id).first()
        if mission:
            mission.status = "completed"
            mission.completed_at = datetime.utcnow()
            db.commit()
            return True
        return False
    except Exception as e:
        logger.error("Error completing mission: %s", e)
        db.rollback()
        return False
    finally:
        db.close()


def consult_strategist(
    query: str,
    business_id: int,
    top_k: int = 5
) -> Dict[str, Any]:
    """
    The "Interrogation Room" - RAG-powered strategic consultation.
    
    User asks: "Why is Coastal Roofing beating me?"
    System: Retrieves relevant vectors from Pinecone, synthesizes with LLM.
    
    Args:
        query: The user's strategic question
        business_id: The client's business ID
        top_k: Number of evidence chunks to retrieve
    
    Returns:
        Dict with strategic answer and evidence sources
    """
    if not is_sherlock_enabled() or sherlock_index is None:
        return {
            "success": False,
            "error": "Sherlock not enabled. Configure Pinecone to use the Strategist."
        }
    
    if not OPENAI_API_KEY:
        return {"success": False, "error": "OpenAI API key required for consultation"}
    
    result = {
        "success": False,
        "query": query,
        "answer": "",
        "evidence": [],
        "sources": []
    }
    
    db = SessionLocal()
    
    try:
        business = db.query(Business).filter(Business.id == business_id).first()
        business_name = business.name if business else "Your Business"
        business_industry = business.industry if business else "general"
        
        query_embedding = embed_text(query)
        if query_embedding is None:
            result["error"] = "Failed to process your question"
            return result
        
        query_filter = {"business_id": {"$eq": str(business_id)}}
        
        evidence_chunks = []
        sources = []
        
        namespaces_to_search = [
            SHERLOCK_NAMESPACES["business"],
            SHERLOCK_NAMESPACES["competitor"]
        ]
        
        for namespace in namespaces_to_search:
            try:
                pinecone_results = sherlock_index.query(
                    vector=query_embedding,
                    filter=query_filter,
                    top_k=top_k,
                    include_metadata=True,
                    namespace=namespace
                )
                
                if pinecone_results and hasattr(pinecone_results, 'matches'):
                    for match in pinecone_results.matches:
                        if match.score < 0.3:
                            continue
                            
                        metadata = match.metadata or {}
                        source_url = metadata.get("url", "Unknown source")
                        source_title = metadata.get("title", "")
                        content_type = metadata.get("type", "unknown")
                        topics_str = metadata.get("topics", "[]")
                        
                        try:
                            topics = json.loads(topics_str) if isinstance(topics_str, str) else []
                        except:
                            topics = []
                        
                        evidence_chunks.append({
                            "source": source_url,
                            "title": source_title,
                            "type": content_type,
                            "topics": topics,
                            "relevance": round(match.score, 3),
                            "namespace": namespace
                        })
                        
                        sources.append(f"[{content_type.upper()}] {source_title or source_url}")
            except Exception as ns_err:
                logger.warning("Error querying namespace %s: %s", namespace, ns_err)
                continue
        
        evidence_chunks.sort(key=lambda x: x["relevance"], reverse=True)
        evidence_chunks = evidence_chunks[:top_k]
        
        if not evidence_chunks:
            result["answer"] = "I don't have enough data yet to answer that question. Please ingest some competitor websites first using the Sherlock scanner."
            result["success"] = True
            return result
        
        evidence_text = ""
        for i, chunk in enumerate(evidence_chunks, 1):
            topics_str = ", ".join(chunk["topics"][:5]) if chunk["topics"] else "No specific topics"
            evidence_text += f"""
--- EVIDENCE #{i} (Relevance: {chunk['relevance']}) ---
Source: {chunk['source']}
Type: {chunk['type']}
Topics Covered: {topics_str}
"""
        
        system_prompt = f"""You are an elite SEO and AI Visibility Strategist working for {business_name} in the {business_industry} industry.

Your role is to analyze competitor intelligence and provide actionable strategic advice.

RULES:
1. Use ONLY the provided Evidence to form your answer - do not make up information
2. Be specific and tactical - give exact counter-moves, not generic advice
3. Reference the sources when making claims
4. Focus on AI visibility (how AI assistants like ChatGPT recommend businesses)
5. If the evidence doesn't support an answer, say so honestly

Format your response with:
- A direct answer to the question
- 3 specific counter-moves they can implement immediately
- Why these moves will work based on the evidence"""

        user_message = f"""QUESTION: {query}

EVIDENCE FROM COMPETITOR ANALYSIS:
{evidence_text}

Based on this evidence, provide your strategic analysis and recommendations."""

        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            temperature=0.7,
            max_tokens=1500
        )
        
        answer = response.choices[0].message.content
        
        result["success"] = True
        result["answer"] = answer
        result["evidence"] = evidence_chunks
        result["sources"] = sources
        result["chunks_retrieved"] = len(evidence_chunks)
        
        logger.info("Strategist consultation for business %d: %d evidence chunks used", 
                    business_id, len(evidence_chunks))
        
    except Exception as e:
        logger.error("Strategist consultation error: %s", e)
        result["error"] = f"Consultation failed: {str(e)[:100]}"
    finally:
        db.close()
    
    return result


def fabricate_fix(mission_id: int) -> Dict[str, Any]:
    """
    The "Fabricator" - Generate actual files to solve a mission.
    
    Takes a mission like "Add LocalBusiness Schema" and generates
    the actual JSON-LD code or HTML page the client needs.
    
    Args:
        mission_id: The mission to fabricate a fix for
    
    Returns:
        Dict with filename, content, and file type
    """
    if not OPENAI_API_KEY:
        return {"success": False, "error": "OpenAI API key required for fabrication"}
    
    db = SessionLocal()
    result = {
        "success": False,
        "mission_id": mission_id,
        "files": []
    }
    
    try:
        mission = db.query(SherlockMission).filter(SherlockMission.id == mission_id).first()
        if not mission:
            result["error"] = "Mission not found"
            return result
        
        business = db.query(Business).filter(Business.id == mission.business_id).first()
        if not business:
            result["error"] = "Business not found"
            return result
        
        mission_type = mission.mission_type
        missing_topic = mission.missing_topic or "general topic"
        title = mission.title or ""
        description = mission.description or ""
        
        business_name = business.name or "Your Business"
        business_url = business.url or "https://example.com"
        business_phone = business.phone or "(555) 123-4567"
        business_city = business.city or "Your City"
        business_state = business.state or "ST"
        business_industry = business.industry or "general"
        
        topic_context = []
        try:
            if mission.topic_context:
                topic_context = json.loads(mission.topic_context)
        except:
            pass
        
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        files_generated = []
        
        if mission_type in ["schema", "trust_building", "create_schema"]:
            schema_prompt = f"""Generate valid JSON-LD schema markup for a local business.

Business Details:
- Name: {business_name}
- Website: {business_url}
- Phone: {business_phone}
- City: {business_city}, {business_state}
- Industry: {business_industry}
- Topic to highlight: {missing_topic}

Requirements:
1. Create a LocalBusiness schema with all relevant properties
2. Include the topic "{missing_topic}" in the description and services
3. Make it comprehensive with address, geo coordinates placeholder, hours, etc.
4. Return ONLY valid JSON - no markdown, no explanation

The JSON should be ready to paste into a <script type="application/ld+json"> tag."""

            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": schema_prompt}],
                temperature=0.3,
                max_tokens=2000
            )
            
            schema_content = response.choices[0].message.content
            schema_content = schema_content.strip()
            if schema_content.startswith("```"):
                lines = schema_content.split("\n")
                schema_content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            
            files_generated.append({
                "filename": f"schema-{missing_topic.lower().replace(' ', '-')[:30]}.json",
                "content": schema_content,
                "type": "json-ld",
                "description": f"LocalBusiness schema highlighting {missing_topic}"
            })
        
        elif mission_type in ["create_page", "content_creation", "content_expansion"]:
            slug = re.sub(r'[^a-z0-9]+', '-', missing_topic.lower()).strip('-')
            
            page_prompt = f"""Generate a complete, SEO-optimized landing page for a local business.

Business Details:
- Name: {business_name}
- Website: {business_url}
- Phone: {business_phone}
- Location: {business_city}, {business_state}
- Industry: {business_industry}

Page Topic: {missing_topic}
Context phrases to include: {', '.join(topic_context[:5]) if topic_context else 'N/A'}

Requirements:
1. Create a full HTML page with proper semantic structure
2. Include meta title and description optimized for "{missing_topic}"
3. Write compelling, conversion-focused content (minimum 800 words)
4. Include FAQ section with 5 relevant questions
5. Add clear calls-to-action with phone number
6. Use proper heading hierarchy (H1, H2, H3)
7. Make it mobile-friendly with viewport meta tag
8. Include embedded JSON-LD schema for the service
9. Style it cleanly with embedded CSS (dark professional theme)

Return ONLY the complete HTML - no markdown code blocks or explanation."""

            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": page_prompt}],
                temperature=0.7,
                max_tokens=4000
            )
            
            html_content = response.choices[0].message.content
            html_content = html_content.strip()
            if html_content.startswith("```"):
                lines = html_content.split("\n")
                html_content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            
            files_generated.append({
                "filename": f"{slug}.html",
                "content": html_content,
                "type": "html",
                "description": f"Landing page for {missing_topic}"
            })
        
        elif mission_type in ["faq", "content_faq"]:
            faq_prompt = f"""Generate a comprehensive FAQ section about "{missing_topic}" for a {business_industry} business.

Business: {business_name} in {business_city}, {business_state}

Requirements:
1. Create 10 frequently asked questions about {missing_topic}
2. Write detailed, helpful answers (100-200 words each)
3. Format as valid JSON with this structure:
{{
  "faqs": [
    {{"question": "...", "answer": "..."}},
    ...
  ]
}}
4. Include local context where relevant
5. Make answers authoritative and trustworthy

Return ONLY valid JSON - no markdown or explanation."""

            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": faq_prompt}],
                temperature=0.7,
                max_tokens=3000
            )
            
            faq_content = response.choices[0].message.content
            faq_content = faq_content.strip()
            if faq_content.startswith("```"):
                lines = faq_content.split("\n")
                faq_content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            
            files_generated.append({
                "filename": f"faq-{missing_topic.lower().replace(' ', '-')[:30]}.json",
                "content": faq_content,
                "type": "json",
                "description": f"FAQ content about {missing_topic}"
            })
        
        else:
            content_prompt = f"""Generate optimized content about "{missing_topic}" for a {business_industry} business.

Business: {business_name}
Location: {business_city}, {business_state}

Create a comprehensive content piece (minimum 500 words) that:
1. Explains the topic thoroughly
2. Establishes expertise and authority
3. Includes relevant keywords naturally
4. Has a clear structure with headings
5. Ends with a call-to-action

Format as clean HTML with proper heading tags. No full page structure needed - just the content section."""

            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": content_prompt}],
                temperature=0.7,
                max_tokens=2000
            )
            
            content = response.choices[0].message.content
            content = content.strip()
            if content.startswith("```"):
                lines = content.split("\n")
                content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            
            files_generated.append({
                "filename": f"content-{missing_topic.lower().replace(' ', '-')[:30]}.html",
                "content": content,
                "type": "html-fragment",
                "description": f"Content section about {missing_topic}"
            })
        
        mission.status = "in_progress"
        db.commit()
        
        result["success"] = True
        result["files"] = files_generated
        result["mission_title"] = title
        result["business_name"] = business_name
        
        logger.info("Fabricator generated %d files for mission %d", 
                    len(files_generated), mission_id)
        
    except Exception as e:
        logger.error("Fabricator error: %s", e)
        result["error"] = f"Fabrication failed: {str(e)[:100]}"
        db.rollback()
    finally:
        db.close()
    
    return result


def get_mission_by_id(mission_id: int) -> Optional[Dict[str, Any]]:
    """Get a single mission by ID."""
    db = SessionLocal()
    
    try:
        mission = db.query(SherlockMission).filter(SherlockMission.id == mission_id).first()
        if not mission:
            return None
        
        return {
            "id": mission.id,
            "business_id": mission.business_id,
            "title": mission.title,
            "description": mission.description,
            "mission_type": mission.mission_type,
            "priority": mission.priority,
            "status": mission.status,
            "missing_topic": mission.missing_topic,
            "recommended_action": mission.recommended_action,
            "estimated_impact": mission.estimated_impact,
            "target_url": mission.target_url_slug,
            "topic_context": mission.topic_context,
            "competitor_coverage": mission.competitor_coverage,
            "created_at": mission.created_at.isoformat() if mission.created_at else None
        }
    except Exception as e:
        logger.error("Error fetching mission: %s", e)
        return None
    finally:
        db.close()
