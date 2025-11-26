"""
Seed script to create EkkoScope Ongoing product and prices in Stripe.
Run this script once to set up the subscription product:
  python scripts/seed_stripe_ongoing.py
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.stripe_client import load_stripe_config, get_stripe_client

async def create_ongoing_product():
    """Create the EkkoScope Ongoing product and prices in Stripe."""
    try:
        await load_stripe_config()
        stripe = get_stripe_client()
        
        print("Checking for existing EkkoScope Ongoing product...")
        products = stripe.Product.search(query="name:'EkkoScope Ongoing Monitoring'")
        
        if products.data:
            product = products.data[0]
            print(f"Found existing product: {product.id}")
        else:
            print("Creating new product...")
            product = stripe.Product.create(
                name="EkkoScope Ongoing Monitoring",
                description="Monthly GEO (Generative Engine Optimization) monitoring with regular audits to track and improve your AI visibility.",
                metadata={
                    "type": "ekkoscope_ongoing",
                    "audit_type": "subscription"
                }
            )
            print(f"Created product: {product.id}")
        
        print("\nChecking for existing prices...")
        prices = stripe.Price.list(product=product.id, active=True)
        
        setup_price = None
        monthly_price = None
        
        for price in prices.data:
            if price.recurring is None and price.unit_amount == 19700:
                setup_price = price
                print(f"Found existing setup price: {price.id} (${price.unit_amount / 100})")
            elif price.recurring and price.recurring.interval == "month" and price.unit_amount == 9900:
                monthly_price = price
                print(f"Found existing monthly price: {price.id} (${price.unit_amount / 100}/mo)")
        
        if not setup_price:
            print("\nCreating setup fee price ($197)...")
            setup_price = stripe.Price.create(
                product=product.id,
                unit_amount=19700,
                currency="usd",
                metadata={
                    "type": "ekkoscope_ongoing_setup"
                }
            )
            print(f"Created setup price: {setup_price.id} ($197.00)")
        
        if not monthly_price:
            print("\nCreating monthly subscription price ($99/mo)...")
            monthly_price = stripe.Price.create(
                product=product.id,
                unit_amount=9900,
                currency="usd",
                recurring={
                    "interval": "month"
                },
                metadata={
                    "type": "ekkoscope_ongoing_monthly"
                }
            )
            print(f"Created monthly price: {monthly_price.id} ($99.00/mo)")
        
        print("\n" + "=" * 60)
        print("STRIPE ONGOING SETUP COMPLETE")
        print("=" * 60)
        print(f"\nProduct ID: {product.id}")
        print(f"Setup Fee Price ID:   {setup_price.id}")
        print(f"Monthly Price ID:     {monthly_price.id}")
        print(f"\nSet these environment variables:")
        print(f"  STRIPE_PRICE_ONGOING_SETUP={setup_price.id}")
        print(f"  STRIPE_PRICE_ONGOING_MONTHLY={monthly_price.id}")
        print("=" * 60)
        
        return {
            "setup_price_id": setup_price.id,
            "monthly_price_id": monthly_price.id
        }
        
    except Exception as e:
        print(f"Error: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(create_ongoing_product())
