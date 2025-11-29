"""
Automatic Audit Scheduler for EkkoScope.
Runs audits every 2 weeks for active subscribers.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional
from services.database import get_db_session, Business, Audit
from services.audit_runner import run_audit_for_business


def get_next_audit_date(from_date: Optional[datetime] = None) -> datetime:
    """Calculate the next audit date (14 days from given date or now)."""
    base_date = from_date or datetime.utcnow()
    return base_date + timedelta(days=14)


def schedule_first_audit(business_id: int) -> datetime:
    """
    Schedule the first audit for a new subscriber.
    Runs immediately and schedules next one for 14 days out.
    """
    db = get_db_session()
    try:
        business = db.query(Business).filter(Business.id == business_id).first()
        if business:
            now = datetime.utcnow()
            business.subscription_start_at = now
            business.next_audit_at = get_next_audit_date(now)
            db.commit()
            return business.next_audit_at
    finally:
        db.close()
    return None


def update_next_audit_date(business_id: int) -> datetime:
    """Update the next audit date after an audit completes."""
    db = get_db_session()
    try:
        business = db.query(Business).filter(Business.id == business_id).first()
        if business and business.subscription_active:
            now = datetime.utcnow()
            business.last_audit_at = now
            business.next_audit_at = get_next_audit_date(now)
            db.commit()
            return business.next_audit_at
    finally:
        db.close()
    return None


def get_businesses_due_for_audit() -> list:
    """Get all businesses that are due for their scheduled audit."""
    db = get_db_session()
    try:
        now = datetime.utcnow()
        businesses = db.query(Business).filter(
            Business.subscription_active == True,
            Business.next_audit_at <= now
        ).all()
        return [b.id for b in businesses]
    finally:
        db.close()


async def run_scheduled_audit(business_id: int) -> Optional[int]:
    """
    Run a scheduled audit for a business.
    Returns the audit ID if successful.
    """
    db = get_db_session()
    try:
        business = db.query(Business).filter(Business.id == business_id).first()
        if not business or not business.subscription_active:
            return None
        
        audit = Audit(
            business_id=business.id,
            channel="scheduled",
            status="pending"
        )
        db.add(audit)
        db.commit()
        db.refresh(audit)
        
        audit_id = audit.id
        
        try:
            run_audit_for_business(business.id, audit_id)
            update_next_audit_date(business.id)
        except Exception as e:
            print(f"Scheduled audit failed for business {business.id}: {e}")
            audit.status = "error"
            audit.error_message = str(e)[:500]
            db.commit()
        
        return audit_id
    finally:
        db.close()


async def run_scheduler_cycle():
    """
    Run one cycle of the scheduler.
    Checks for due audits and runs them.
    """
    business_ids = get_businesses_due_for_audit()
    
    for business_id in business_ids:
        try:
            print(f"[SCHEDULER] Running scheduled audit for business {business_id}")
            await run_scheduled_audit(business_id)
        except Exception as e:
            print(f"[SCHEDULER] Error running audit for business {business_id}: {e}")
    
    return len(business_ids)


async def scheduler_loop(interval_minutes: int = 60):
    """
    Main scheduler loop. Runs continuously.
    Checks for due audits every interval_minutes.
    """
    print(f"[SCHEDULER] Starting audit scheduler, checking every {interval_minutes} minutes")
    
    while True:
        try:
            count = await run_scheduler_cycle()
            if count > 0:
                print(f"[SCHEDULER] Processed {count} scheduled audits")
        except Exception as e:
            print(f"[SCHEDULER] Error in scheduler cycle: {e}")
        
        await asyncio.sleep(interval_minutes * 60)
