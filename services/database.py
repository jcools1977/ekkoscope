"""
Database configuration and models for EkkoScope.
Uses SQLite with SQLAlchemy for persistence.
"""

import os
import json
from datetime import datetime
from typing import Optional, List
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
import bcrypt

SQLITE_DATABASE_PATH = "ekkoscope.db"
DATABASE_URL = f"sqlite:///./{SQLITE_DATABASE_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    """User accounts for authentication and ownership."""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    is_admin = Column(Boolean, default=False)
    email_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login_at = Column(DateTime, nullable=True)
    follow_up_sent_at = Column(DateTime, nullable=True)
    
    businesses = relationship("Business", back_populates="owner")
    purchases = relationship("Purchase", back_populates="user")
    
    def set_password(self, password: str):
        """Hash and store password. Truncates to 72 bytes for bcrypt compatibility."""
        password_bytes = password.encode('utf-8')[:72]
        salt = bcrypt.gensalt()
        self.password_hash = bcrypt.hashpw(password_bytes, salt).decode('utf-8')
    
    def verify_password(self, password: str) -> bool:
        """Verify password against stored hash."""
        password_bytes = password.encode('utf-8')[:72]
        stored_hash = self.password_hash.encode('utf-8')
        return bcrypt.checkpw(password_bytes, stored_hash)
    
    @property
    def full_name(self) -> str:
        """Return user's full name or email."""
        if self.first_name or self.last_name:
            return f"{self.first_name or ''} {self.last_name or ''}".strip()
        return self.email.split('@')[0]


class Purchase(Base):
    """Track user purchases and entitlements."""
    __tablename__ = "purchases"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    kind = Column(String(20), nullable=False)
    status = Column(String(20), default="pending")
    stripe_checkout_session_id = Column(String(255), nullable=True)
    stripe_payment_intent_id = Column(String(255), nullable=True)
    used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    user = relationship("User", back_populates="purchases")
    business = relationship("Business", back_populates="purchases")


class Business(Base):
    __tablename__ = "businesses"
    
    id = Column(Integer, primary_key=True, index=True)
    owner_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    name = Column(String(255), nullable=False)
    primary_domain = Column(String(255), nullable=False)
    extra_domains = Column(Text, default="[]")
    business_type = Column(String(50), default="local_service")
    regions = Column(Text, default="[]")
    categories = Column(Text, default="[]")
    contact_name = Column(String(255), nullable=True)
    contact_email = Column(String(255), nullable=True)
    source = Column(String(20), default="public")
    subscription_active = Column(Boolean, default=False)
    stripe_subscription_id = Column(String(255), nullable=True)
    plan = Column(String(20), default="snapshot")
    created_at = Column(DateTime, default=datetime.utcnow)
    
    owner = relationship("User", back_populates="businesses")
    audits = relationship("Audit", back_populates="business", order_by="desc(Audit.created_at)")
    purchases = relationship("Purchase", back_populates="business")
    
    def get_extra_domains(self) -> List[str]:
        try:
            return json.loads(self.extra_domains or "[]")
        except:
            return []
    
    def set_extra_domains(self, domains: List[str]):
        self.extra_domains = json.dumps(domains)
    
    def get_regions(self) -> List[str]:
        try:
            return json.loads(self.regions or "[]")
        except:
            return []
    
    def set_regions(self, regions: List[str]):
        self.regions = json.dumps(regions)
    
    def get_categories(self) -> List[str]:
        try:
            return json.loads(self.categories or "[]")
        except:
            return []
    
    def set_categories(self, categories: List[str]):
        self.categories = json.dumps(categories)
    
    def get_all_domains(self) -> List[str]:
        domains = [self.primary_domain]
        domains.extend(self.get_extra_domains())
        return [d for d in domains if d]
    
    def to_tenant_config(self) -> dict:
        """Convert Business to tenant_config format for existing analysis logic."""
        regions = self.get_regions()
        categories = self.get_categories()
        
        brand_aliases = [self.name]
        name_parts = self.name.split()
        if len(name_parts) > 1:
            brand_aliases.append(name_parts[0])
        
        geo_focus = regions if regions else ["United States"]
        
        queries = generate_default_queries(
            name=self.name,
            categories=categories,
            regions=regions,
            business_type=self.business_type
        )
        
        return {
            "id": f"business_{self.id}",
            "display_name": self.name,
            "domains": self.get_all_domains(),
            "brand_aliases": brand_aliases,
            "geo_focus": geo_focus,
            "priority_queries": queries,
            "categories": categories,
            "business_type": self.business_type
        }


class Audit(Base):
    __tablename__ = "audits"
    
    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    channel = Column(String(20), default="self_serve")
    status = Column(String(20), default="pending")
    visibility_summary_json = Column(Text, nullable=True)
    suggestions_json = Column(Text, nullable=True)
    site_inspector_used = Column(Boolean, default=False)
    pdf_path = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    business = relationship("Business", back_populates="audits")
    
    audit_queries = relationship("AuditQuery", back_populates="audit", cascade="all, delete-orphan")
    page_blueprints = relationship("PageBlueprint", back_populates="audit", cascade="all, delete-orphan")
    roadmap_tasks = relationship("RoadmapTask", back_populates="audit", cascade="all, delete-orphan")
    
    def get_visibility_summary(self) -> Optional[dict]:
        if not self.visibility_summary_json:
            return None
        try:
            return json.loads(self.visibility_summary_json)
        except:
            return None
    
    def set_visibility_summary(self, data: dict):
        self.visibility_summary_json = json.dumps(data)
    
    def get_suggestions(self) -> Optional[dict]:
        if not self.suggestions_json:
            return None
        try:
            return json.loads(self.suggestions_json)
        except:
            return None
    
    def set_suggestions(self, data: dict):
        self.suggestions_json = json.dumps(data)


class AuditQuery(Base):
    """Normalized queries from an audit with intent classification."""
    __tablename__ = "audit_queries"
    
    id = Column(Integer, primary_key=True, index=True)
    audit_id = Column(Integer, ForeignKey("audits.id"), nullable=False, index=True)
    query_text = Column(String(500), nullable=False, index=True)
    intent = Column(String(50), index=True)
    region = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    audit = relationship("Audit", back_populates="audit_queries")
    visibility_results = relationship("QueryVisibilityResult", back_populates="audit_query", cascade="all, delete-orphan")


class QueryVisibilityResult(Base):
    """Multi-LLM visibility results for a query (who was recommended by each provider)."""
    __tablename__ = "query_visibility_results"
    
    id = Column(Integer, primary_key=True, index=True)
    audit_query_id = Column(Integer, ForeignKey("audit_queries.id"), nullable=False, index=True)
    provider = Column(String(50), nullable=False, index=True)
    brand_name = Column(String(255), index=True)
    brand_url = Column(String(500), nullable=True)
    reason = Column(Text, nullable=True)
    rank = Column(Integer, nullable=True)
    
    audit_query = relationship("AuditQuery", back_populates="visibility_results")


class PageBlueprint(Base):
    """Page blueprints generated by Genius Mode - stored for EkkoBrain pattern learning."""
    __tablename__ = "page_blueprints"
    
    id = Column(Integer, primary_key=True, index=True)
    audit_id = Column(Integer, ForeignKey("audits.id"), nullable=False, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False, index=True)
    
    intent_cluster = Column(String(100), index=True)
    url_slug = Column(String(255))
    seo_title = Column(String(255))
    meta_description = Column(Text)
    h1 = Column(String(255))
    outline_json = Column(Text)
    target_keywords = Column(Text)
    
    industry = Column(String(100), index=True)
    business_type = Column(String(50), index=True)
    region_group = Column(String(100), index=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    audit = relationship("Audit", back_populates="page_blueprints")
    business = relationship("Business")


class RoadmapTask(Base):
    """30-day roadmap tasks generated by Genius Mode - stored for EkkoBrain pattern learning."""
    __tablename__ = "roadmap_tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    audit_id = Column(Integer, ForeignKey("audits.id"), nullable=False, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False, index=True)
    
    week_number = Column(Integer, index=True)
    task_text = Column(Text)
    intent_cluster = Column(String(100), nullable=True)
    impact = Column(String(20), nullable=True)
    effort = Column(String(20), nullable=True)
    owner_role = Column(String(50), nullable=True)
    
    industry = Column(String(100), index=True)
    business_type = Column(String(50), index=True)
    region_group = Column(String(100), index=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    audit = relationship("Audit", back_populates="roadmap_tasks")
    business = relationship("Business")


def derive_region_group(regions: List[str]) -> str:
    """Derive a region group from a list of regions for pattern matching."""
    if not regions:
        return "US_national"
    
    regions_lower = [r.lower() for r in regions]
    
    southeast = ["florida", "georgia", "north carolina", "south carolina", "alabama", "mississippi", "tennessee", "louisiana"]
    northeast = ["new york", "new jersey", "pennsylvania", "massachusetts", "connecticut", "maine", "vermont", "new hampshire", "rhode island"]
    midwest = ["ohio", "michigan", "indiana", "illinois", "wisconsin", "minnesota", "iowa", "missouri", "kansas", "nebraska"]
    southwest = ["texas", "arizona", "new mexico", "oklahoma"]
    west = ["california", "washington", "oregon", "nevada", "colorado", "utah"]
    
    for region in regions_lower:
        if any(s in region for s in southeast):
            return "US_southeast"
        if any(s in region for s in northeast):
            return "US_northeast"
        if any(s in region for s in midwest):
            return "US_midwest"
        if any(s in region for s in southwest):
            return "US_southwest"
        if any(s in region for s in west):
            return "US_west"
    
    if any("united states" in r.lower() or "usa" in r.lower() or "national" in r.lower() for r in regions):
        return "US_national"
    
    return "US_national"


def generate_default_queries(
    name: str,
    categories: List[str],
    regions: List[str],
    business_type: str
) -> List[str]:
    """
    Generate comprehensive search queries based on business profile.
    Uses advanced query generator for 20-30 industry-specific queries.
    """
    from services.query_generator import generate_query_strings
    
    return generate_query_strings(
        name=name,
        categories=categories,
        regions=regions,
        business_type=business_type,
        max_queries=25
    )


def migrate_db():
    """Run migrations to add new columns to existing tables."""
    from sqlalchemy import text
    with engine.connect() as conn:
        result = conn.execute(text("PRAGMA table_info(businesses)"))
        columns = [row[1] for row in result.fetchall()]
        
        if "plan" not in columns:
            conn.execute(text("ALTER TABLE businesses ADD COLUMN plan VARCHAR(20) DEFAULT 'snapshot'"))
            conn.commit()
            print("Migration: Added 'plan' column to businesses table")
        
        if "stripe_subscription_id" not in columns:
            conn.execute(text("ALTER TABLE businesses ADD COLUMN stripe_subscription_id VARCHAR(255)"))
            conn.commit()
            print("Migration: Added 'stripe_subscription_id' column to businesses table")
        
        if "owner_user_id" not in columns:
            conn.execute(text("ALTER TABLE businesses ADD COLUMN owner_user_id INTEGER REFERENCES users(id)"))
            conn.commit()
            print("Migration: Added 'owner_user_id' column to businesses table")


def init_db():
    """Create all tables if they don't exist."""
    Base.metadata.create_all(bind=engine)
    migrate_db()


def get_db():
    """Get database session - use as dependency or context manager."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_session() -> Session:
    """Get a new database session directly."""
    return SessionLocal()
