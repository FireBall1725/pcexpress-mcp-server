#!/usr/bin/env python3
"""
Test script for PC Express API

Tests the basic API functionality without using MCP
Works with all Loblaws banners (Zehrs, Loblaws, No Frills, Superstore, etc.)
"""

import os
import sys
from pathlib import Path

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Add current directory to path to import the server module
sys.path.insert(0, str(Path(__file__).parent))

from pcexpress_mcp_server import PCExpressAPI


def test_api():
    """Test the PC Express API client"""

    # Get credentials from environment
    bearer_token = os.getenv("PCEXPRESS_BEARER_TOKEN")
    customer_id = os.getenv("PCEXPRESS_CUSTOMER_ID")
    cart_id = os.getenv("PCEXPRESS_CART_ID")
    store_id = os.getenv("PCEXPRESS_STORE_ID", "1234")
    banner = os.getenv("PCEXPRESS_BANNER", "zehrs")

    if not all([bearer_token, customer_id, cart_id]):
        print("❌ Missing credentials in .env file")
        print("\nRequired environment variables:")
        print("  - PCEXPRESS_BEARER_TOKEN")
        print("  - PCEXPRESS_CUSTOMER_ID")
        print("  - PCEXPRESS_CART_ID")
        sys.exit(1)

    if bearer_token == "YOUR_TOKEN_HERE":
        print("❌ Please update .env file with your actual bearer token")
        print("\nYou can get it from the curl command you shared earlier:")
        print("  Authorization: Bearer <YOUR_TOKEN>")
        sys.exit(1)

    print("="*60)
    print("Testing PC Express API Client")
    print("="*60)
    print(f"\nBanner: {banner}")
    print(f"Customer ID: {customer_id}")
    print(f"Cart ID: {cart_id}")
    print(f"Store ID: {store_id}")
    print(f"Token: {bearer_token[:30]}...{bearer_token[-20:]}")
    print()

    # Initialize API client
    api = PCExpressAPI(bearer_token, customer_id, cart_id, store_id, banner)

    # Test 1: Get historical orders
    print("\n" + "="*60)
    print("TEST 1: Get Historical Orders")
    print("="*60)
    try:
        orders = api.get_historical_orders()
        print(f"✅ Success! Found {orders.get('onlineOrdersCount', 0)} online orders")

        if orders.get('orderHistory'):
            print("\nMost recent orders:")
            for i, order in enumerate(orders['orderHistory'][:3], 1):
                print(f"  {i}. Order {order['id']} - ${order['total']:.2f} on {order['placed'][:10]}")
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False

    # Test 2: Search for products
    print("\n" + "="*60)
    print("TEST 2: Search Products (query: 'ice cream')")
    print("="*60)
    try:
        results = api.search_products("ice cream", size=5)
        print(f"✅ Success! Found {len(results)} suggestions")

        if results:
            print("\nSuggestions:")
            for i, item in enumerate(results, 1):
                print(f"  {i}. {item.get('suggestion', item)}")
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False

    # Test 3: Get cart
    print("\n" + "="*60)
    print("TEST 3: View Cart")
    print("="*60)
    try:
        cart = api.get_cart()
        print(f"✅ Success! Cart ID: {cart.get('code', 'N/A')}")

        entries = cart.get('entries', [])
        if entries:
            print(f"\nCart has {len(entries)} items:")
            for entry in entries[:5]:
                product = entry.get('product', {})
                print(f"  - {product.get('name', 'Unknown')} x{entry.get('quantity', 0)}")
        else:
            print("\nCart is empty")
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False

    print("\n" + "="*60)
    print("✅ All tests passed!")
    print("="*60)
    print("\nYour API credentials are working correctly.")
    print("You can now run the MCP server with:")
    print("  python pcexpress_mcp_server.py")

    return True


if __name__ == "__main__":
    test_api()
