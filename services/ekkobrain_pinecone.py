"""
EkkoBrain Pinecone Client for EkkoScope.
Provides semantic memory storage for audit patterns (blueprints, tasks).
Fully optional - gracefully disabled if PINECONE_API_KEY is not set.
"""

import os
import uuid
import logging
from typing import List, Dict, Any, Optional

from .config import (
    PINECONE_API_KEY, 
    PINECONE_INDEX_NAME, 
    PINECONE_ENABLED,
    EKKOBRAIN_EMBED_MODEL,
    OPENAI_API_KEY
)

logger = logging.getLogger(__name__)

pc = None
index = None
_initialized = False


def init_ekkobrain_index():
    """Initialize Pinecone client and create index if needed."""
    global pc, index, _initialized
    
    if _initialized:
        return
    
    if not PINECONE_ENABLED:
        logger.info("EkkoBrain/Pinecone disabled: no PINECONE_API_KEY set.")
        _initialized = True
        return
    
    try:
        from pinecone import Pinecone, ServerlessSpec
        
        pc = Pinecone(api_key=PINECONE_API_KEY)
        
        existing = [idx.name for idx in pc.list_indexes()]
        if PINECONE_INDEX_NAME not in existing:
            logger.info("Creating EkkoBrain Pinecone index: %s", PINECONE_INDEX_NAME)
            pc.create_index(
                name=PINECONE_INDEX_NAME,
                dimension=1536,
                metric="cosine",
                spec=ServerlessSpec(cloud="aws", region="us-east-1"),
            )
        
        index = pc.Index(PINECONE_INDEX_NAME)
        logger.info("EkkoBrain Pinecone index initialized: %s", PINECONE_INDEX_NAME)
        _initialized = True
        
    except ImportError:
        logger.warning("Pinecone package not installed. EkkoBrain disabled.")
        _initialized = True
    except Exception as e:
        logger.warning("Failed to initialize EkkoBrain Pinecone: %s", e)
        _initialized = True


def embed_text(text: str) -> Optional[List[float]]:
    """Generate embedding for text using OpenAI embeddings API."""
    if not OPENAI_API_KEY:
        logger.warning("No OPENAI_API_KEY for EkkoBrain embedding.")
        return None
    
    try:
        from openai import OpenAI
        
        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.embeddings.create(
            model=EKKOBRAIN_EMBED_MODEL,
            input=text[:8000],
        )
        return response.data[0].embedding
        
    except Exception as e:
        logger.warning("Error generating EkkoBrain embedding: %s", e)
        return None


def upsert_patterns(vectors: List[Dict[str, Any]]):
    """
    Upsert pattern vectors into Pinecone.
    
    Args:
        vectors: List of dicts with {id, values, metadata}
    """
    if not PINECONE_ENABLED or index is None:
        return
    
    if not vectors:
        return
    
    try:
        index.upsert(vectors=vectors)
        logger.info("Upserted %d patterns to EkkoBrain", len(vectors))
    except Exception as e:
        logger.warning("Failed to upsert EkkoBrain patterns: %s", e)


def search_patterns(
    query_text: str,
    top_k: int = 8,
    filter: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Search for similar patterns in EkkoBrain.
    
    Args:
        query_text: Text to find similar patterns for
        top_k: Maximum number of results
        filter: Optional metadata filter (e.g., {"industry": "roofing"})
    
    Returns:
        List of matches with {id, score, metadata}
    """
    if not PINECONE_ENABLED or index is None:
        return []
    
    try:
        emb = embed_text(query_text)
        if emb is None:
            return []
        
        res = index.query(
            vector=emb,
            top_k=top_k,
            include_metadata=True,
            filter=filter,
        )
        
        return [
            {
                "id": m.id,
                "score": m.score,
                "metadata": m.metadata,
            }
            for m in res.matches
        ]
        
    except Exception as e:
        logger.warning("Failed to search EkkoBrain patterns: %s", e)
        return []


def is_ekkobrain_enabled() -> bool:
    """Check if EkkoBrain is enabled and initialized."""
    return PINECONE_ENABLED and index is not None


def generate_pattern_id(prefix: str, audit_id: int, item_id: int) -> str:
    """Generate a stable pattern ID for Pinecone."""
    return f"{prefix}_{audit_id}_{item_id}"
