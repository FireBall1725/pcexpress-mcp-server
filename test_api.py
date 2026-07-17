#!/usr/bin/env python3
"""Smoke test for the PC Express MCP server.

Exercises the real auth path (headless refresh) and a few read calls without going through
MCP. Set PCEXPRESS_REFRESH_TOKEN (and PCEXPRESS_STATE_DIR / PCEXPRESS_BANNER) first, or run
setup.py / login_pcid.py to get a refresh token.
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent))

from pcexpress_mcp_server import PCExpressAPI
from pcid_token import TokenManager, PcidAuthError


def main():
    banner = os.getenv("PCEXPRESS_BANNER", "zehrs")
    store_id = os.getenv("PCEXPRESS_STORE_ID", "1234")

    print("=" * 60)
    print("PC Express API smoke test")
    print("=" * 60)

    try:
        tokens = TokenManager()
        access = tokens.get_access_token(force=True)
    except PcidAuthError as e:
        print(f"❌ Auth failed: {e}")
        sys.exit(1)
    print(f"✅ Minted an access token headlessly ({len(access)} chars)")

    api = PCExpressAPI(tokens, cart_id=None, store_id=store_id, banner=banner)

    print("\n[1] Customer profile")
    try:
        cust = api.get_customer()
        print(f"✅ {cust.get('firstName')} {cust.get('lastName')}  cartId={cust.get('cartId')}")
    except Exception as e:
        print(f"❌ {e}")
        sys.exit(1)

    print("\n[2] Past orders")
    try:
        orders = api.get_historical_orders()
        print(f"✅ onlineOrdersCount={orders.get('onlineOrdersCount')} "
              f"returned={len(orders.get('orderHistory', []))}")
    except Exception as e:
        print(f"❌ {e}")

    print("\n[3] Cart (auto-discovered id)")
    try:
        cart = api.get_cart()
        orders_in_cart = cart.get("orders") or []
        print(f"✅ cart id={cart.get('id')} status={cart.get('status')} order-groups={len(orders_in_cart)}")
    except Exception as e:
        print(f"❌ {e}")

    print("\n✅ Done. Run the server with:  python pcexpress_mcp_server.py")


if __name__ == "__main__":
    main()
