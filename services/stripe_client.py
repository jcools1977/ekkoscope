"""
Stripe Client for EchoScope
Fetches credentials from Replit connector API with environment variable fallback.
"""

import os
import httpx
import stripe
from dataclasses import dataclass
from typing import Optional

@dataclass
class StripeConfig:
    api_key: str
    publishable_key: str
    webhook_secret: Optional[str] = None
    price_id: Optional[str] = None

_cached_config: Optional[StripeConfig] = None

async def fetch_replit_credentials() -> Optional[dict]:
    """
    Fetch Stripe credentials from Replit connector API.
    Returns None if not available (falls back to env vars).
    """
    hostname = os.getenv("REPLIT_CONNECTORS_HOSTNAME")
    
    repl_identity = os.getenv("REPL_IDENTITY")
    web_repl_renewal = os.getenv("WEB_REPL_RENEWAL")
    
    if repl_identity:
        x_replit_token = f"repl {repl_identity}"
    elif web_repl_renewal:
        x_replit_token = f"depl {web_repl_renewal}"
    else:
        return None
    
    if not hostname:
        return None
    
    is_production = os.getenv("REPLIT_DEPLOYMENT") == "1"
    target_environment = "production" if is_production else "development"
    
    try:
        async with httpx.AsyncClient() as client:
            url = f"https://{hostname}/api/v2/connection"
            params = {
                "include_secrets": "true",
                "connector_names": "stripe",
                "environment": target_environment
            }
            headers = {
                "Accept": "application/json",
                "X_REPLIT_TOKEN": x_replit_token
            }
            
            response = await client.get(url, params=params, headers=headers)
            data = response.json()
            
            if data.get("items") and len(data["items"]) > 0:
                settings = data["items"][0].get("settings", {})
                secret_key = settings.get("secret")
                publishable_key = settings.get("publishable")
                
                if secret_key and publishable_key:
                    return {
                        "secret_key": secret_key,
                        "publishable_key": publishable_key
                    }
    except Exception as e:
        print(f"Warning: Could not fetch Stripe credentials from Replit: {e}")
    
    return None

async def load_stripe_config() -> StripeConfig:
    """
    Load Stripe configuration from Replit connector or environment variables.
    Caches the result for subsequent calls.
    """
    global _cached_config
    
    if _cached_config:
        return _cached_config
    
    replit_creds = await fetch_replit_credentials()
    
    if replit_creds:
        api_key = replit_creds["secret_key"]
        publishable_key = replit_creds["publishable_key"]
    else:
        api_key = os.getenv("STRIPE_SECRET_KEY", "")
        publishable_key = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
    
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    price_id = os.getenv("STRIPE_PRICE_SNAPSHOT")
    
    if not api_key:
        raise ValueError("Stripe API key not configured. Set up Stripe connection or STRIPE_SECRET_KEY environment variable.")
    
    _cached_config = StripeConfig(
        api_key=api_key,
        publishable_key=publishable_key,
        webhook_secret=webhook_secret,
        price_id=price_id
    )
    
    stripe.api_key = api_key
    
    return _cached_config

def get_stripe_client():
    """
    Get the configured stripe module.
    Must call load_stripe_config() first.
    """
    if not stripe.api_key:
        raise RuntimeError("Stripe not initialized. Call load_stripe_config() first.")
    return stripe

async def create_checkout_session(
    business_id: int,
    success_url: str,
    cancel_url: str
) -> stripe.checkout.Session:
    """
    Create a Stripe Checkout session for a one-time Snapshot Audit payment.
    """
    config = await load_stripe_config()
    
    if not config.price_id:
        raise ValueError("STRIPE_PRICE_SNAPSHOT environment variable not set")
    
    stripe.api_key = config.api_key
    
    session = stripe.checkout.Session.create(
        mode="payment",
        line_items=[{
            "price": config.price_id,
            "quantity": 1
        }],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={
            "business_id": str(business_id),
            "product": "echoscope_snapshot"
        }
    )
    
    return session

def verify_webhook_signature(payload: bytes, sig_header: str, webhook_secret: str) -> stripe.Event:
    """
    Verify Stripe webhook signature and construct event.
    Raises stripe.error.SignatureVerificationError if invalid.
    """
    return stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
