"""
Authentication service for EkkoScope.
Handles user registration, login, and session management.
"""

from datetime import datetime
from typing import Optional
from fastapi import Request, HTTPException
from sqlalchemy.orm import Session

from services.database import User, get_db_session


def get_current_user(request: Request) -> Optional[User]:
    """Get the currently logged-in user from session."""
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    
    db = get_db_session()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        return user
    finally:
        db.close()


def require_user(request: Request) -> User:
    """Require a logged-in user. Raises HTTPException if not authenticated."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(
            status_code=302,
            headers={"Location": "/auth/login?next=" + request.url.path}
        )
    return user


def login_user(request: Request, user: User):
    """Log in a user by setting session data."""
    request.session["user_id"] = user.id
    request.session["user_email"] = user.email


def logout_user(request: Request):
    """Log out the current user."""
    request.session.pop("user_id", None)
    request.session.pop("user_email", None)


def create_user(
    db: Session,
    email: str,
    password: str,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None
) -> User:
    """Create a new user account."""
    existing = db.query(User).filter(User.email == email.lower()).first()
    if existing:
        raise ValueError("An account with this email already exists")
    
    user = User(
        email=email.lower().strip(),
        first_name=first_name,
        last_name=last_name
    )
    user.set_password(password)
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    return user


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    """Authenticate a user with email and password."""
    user = db.query(User).filter(User.email == email.lower()).first()
    if not user:
        return None
    if not user.verify_password(password):
        return None
    
    user.last_login_at = datetime.utcnow()
    db.commit()
    
    return user


def user_has_access(user: User, business_id: int, db: Session) -> bool:
    """Check if user has access to a business (ownership or purchase)."""
    from services.database import Business, Purchase
    
    business = db.query(Business).filter(Business.id == business_id).first()
    if not business:
        return False
    
    if business.owner_user_id == user.id:
        return True
    
    purchase = db.query(Purchase).filter(
        Purchase.user_id == user.id,
        Purchase.business_id == business_id,
        Purchase.status == "paid"
    ).first()
    
    return purchase is not None


def user_has_snapshot_credit(user: User, business_id: int, db: Session) -> bool:
    """Check if user has unused snapshot credit for a business."""
    from services.database import Purchase
    
    purchase = db.query(Purchase).filter(
        Purchase.user_id == user.id,
        Purchase.business_id == business_id,
        Purchase.kind == "snapshot",
        Purchase.status == "paid",
        Purchase.used == False
    ).first()
    
    return purchase is not None


def user_has_active_subscription(user: User, business_id: int, db: Session) -> bool:
    """Check if user has active ongoing subscription for a business."""
    from services.database import Business
    
    business = db.query(Business).filter(Business.id == business_id).first()
    if not business:
        return False
    
    if business.owner_user_id != user.id:
        return False
    
    return business.subscription_active and business.plan == "ongoing"
