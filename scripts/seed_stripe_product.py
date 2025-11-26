"""
Seed script to create EchoScope Snapshot product and price in Stripe.
Run this script once to set up the product:
  python scripts/seed_stripe_product.py
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.stripe_client import load_stripe_config, get_stripe_client

async def create_snapshot_product():
    """Create the EchoScope Snapshot product and price in Stripe."""
    try:
        await load_stripe_config()
        stripe = get_stripe_client()
        
        print("Checking for existing EchoScope Snapshot product...")
        products = stripe.Product.search(query="name:'EchoScope Snapshot Audit'")
        
        if products.data:
            product = products.data[0]
            print(f"Found existing product: {product.id}")
        else:
            print("Creating new product...")
            product = stripe.Product.create(
                name="EchoScope Snapshot Audit",
                description="One-time GEO (Generative Engine Optimization) audit to analyze how AI assistants like ChatGPT recommend your business.",
                metadata={
                    "type": "echoscope_snapshot",
                    "audit_type": "one_time"
                }
            )
            print(f"Created product: {product.id}")
        
        print("Checking for existing price...")
        prices = stripe.Price.list(product=product.id, active=True)
        
        if prices.data:
            price = prices.data[0]
            print(f"Found existing price: {price.id} (${price.unit_amount / 100})")
        else:
            print("Creating new price...")
            price = stripe.Price.create(
                product=product.id,
                unit_amount=4900,
                currency="usd",
                metadata={
                    "type": "echoscope_snapshot"
                }
            )
            print(f"Created price: {price.id} ($49.00)")
        
        print("\n" + "=" * 60)
        print("STRIPE SETUP COMPLETE")
        print("=" * 60)
        print(f"\nProduct ID: {product.id}")
        print(f"Price ID:   {price.id}")
        print(f"\nSet this environment variable:")
        print(f"  STRIPE_PRICE_SNAPSHOT={price.id}")
        print("=" * 60)
        
        return price.id
        
    except Exception as e:
        print(f"Error: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(create_snapshot_product())
