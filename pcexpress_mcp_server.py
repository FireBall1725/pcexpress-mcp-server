#!/usr/bin/env python3
"""
PC Express MCP Server - Model Context Protocol server for Loblaws grocery shopping

Works with all PC Express enabled banners:
- Zehrs (zehrs)
- Loblaws (loblaws)
- No Frills (nofrills)
- Real Canadian Superstore (superstore)
- Independent (independent)
- T&T Supermarket (tandt)

This server provides tools for:
- Searching past orders
- Searching for products
- Adding items to cart
- Removing items from cart
- Viewing cart contents
"""

import json
import logging
import os
from typing import Any, Optional
from datetime import datetime

import requests
from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from pcid_token import TokenManager, PcidAuthError

# Load .env if present (no-op when the launcher passes env directly)
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pcexpress-mcp")


class PCExpressAPI:
    """Wrapper for PC Express API (works across all Loblaws banners)"""

    BASE_URL = "https://api.pcexpress.ca/pcx-bff/api/v1"

    # Static web API key (not user-specific). PCID auth lives in pcid_token/pcid_config.
    API_KEY = "C1xujSegT5j3ap3yexJjqhOfELwGKYvz"

    # Banner to website mapping
    BANNER_DOMAINS = {
        "zehrs": "www.zehrs.ca",
        "loblaws": "www.loblaws.ca",
        "nofrills": "www.nofrills.ca",
        "superstore": "www.realcanadiansuperstore.ca",
        "independent": "www.yourindependentgrocer.ca",
        "tandt": "www.tntsupermarket.com",
    }

    def __init__(self, token_manager: TokenManager, cart_id: str, store_id: str = "1234", banner: str = "zehrs"):
        """
        Initialize PCExpressAPI client

        Args:
            token_manager: mints/refreshes PCID access tokens on demand
            cart_id: Active cart ID
            store_id: Store ID (4-digit code for your preferred store)
            banner: Store banner (zehrs, loblaws, nofrills, superstore, independent, tandt)
        """
        self.tokens = token_manager
        self._cart_id = cart_id
        self.store_id = store_id
        self.banner = banner.lower()
        self.domain = self.BANNER_DOMAINS.get(self.banner, "www.zehrs.ca")
        self.session = requests.Session()

    @property
    def cart_id(self) -> str:
        """The active cart id. Auto-discovered from the customer profile if not provided."""
        if not self._cart_id:
            self._cart_id = self.get_customer().get("cartId")
            if not self._cart_id:
                raise ValueError("No active cart found. Add an item to your cart, then retry.")
        return self._cart_id

    def get_customer(self) -> dict:
        """Customer profile: cartId, customerId, name, postalCode, PC Optimum status, etc."""
        url = f"{self.BASE_URL}/ecommerce/v2/{self.banner}/customers"
        return self._request("GET", url).json()

    def _get_headers(self) -> dict:
        """Get standard headers for API requests (fresh bearer each call)"""
        return {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en",
            "Authorization": f"Bearer {self.tokens.get_access_token()}",
            "Business-User-Agent": "PCXWEB",
            "Content-Type": "application/json",
            "Origin": f"https://{self.domain}",
            "Referer": f"https://{self.domain}/",
            "Site-Banner": self.banner,
            "x-apikey": self.API_KEY,
            "x-application-type": "Web",
            "x-loblaw-tenant-id": "ONLINE_GROCERIES",
            "baseSiteId": self.banner,
            "is-helios-account": "true",
        }

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        """Authenticated request with one transparent refresh-and-retry on 401."""
        headers = self._get_headers()
        resp = self.session.request(method, url, headers=headers, **kwargs)
        if resp.status_code == 401:
            headers["Authorization"] = f"Bearer {self.tokens.get_access_token(force=True)}"
            resp = self.session.request(method, url, headers=headers, **kwargs)
        resp.raise_for_status()
        return resp

    def get_historical_orders(self) -> dict:
        """
        Get list of past orders

        Returns:
            dict: Order history with list of orders
        """
        url = f"{self.BASE_URL}/ecommerce/v2/{self.banner}/customers/historical-orders"

        return self._request("GET", url).json()

    def get_order_details(self, order_id: str) -> dict:
        """
        Get details for a specific order including all items

        Args:
            order_id: The order ID

        Returns:
            dict: Order details including items, prices, etc.
        """
        url = f"{self.BASE_URL}/ecommerce/v2/{self.banner}/customers/historical-orders/{order_id}"

        return self._request("GET", url).json()

    def search_products(self, query: str, size: int = 48) -> dict:
        """
        Search for products and return the fields needed to add them to cart.

        Uses the authenticated pcx-bff product-search endpoint (the same API the
        other tools use), not website scraping. The endpoint requires lang, term,
        storeId, and banner at the top level of the body; the product array comes
        back under "results".

        Args:
            query: Search term (e.g., "milk", "ground beef")
            size: Maximum number of results to return (default: 48)

        Returns:
            dict: Search results with products including their codes
        """
        url = f"{self.BASE_URL}/products/search"

        payload = {
            "lang": "en",
            "term": query,
            "storeId": self.store_id,
            "banner": self.banner,
            "cartId": self.cart_id,
            "pagination": {"from": 0, "size": size},
        }

        data = self._request("POST", url, json=payload).json()

        products = []
        for item in data.get("results", [])[:size]:
            products.append({
                "code": item.get("code") or item.get("articleNumber"),
                "name": item.get("name"),
                "brand": item.get("brand"),
                "packageSize": item.get("packageSize"),
                "prices": item.get("prices"),
                "dealPrice": item.get("dealPrice"),
                "stockStatus": item.get("stockStatus"),
                "link": item.get("link"),
                "offerType": item.get("offerType"),
            })

        return {
            "query": query,
            "totalResults": data.get("pagination", {}).get("totalResults", len(products)),
            "products": products,
        }

    def get_product_details(self, product_code: str) -> dict:
        """
        Get detailed information about a specific product by its code

        Args:
            product_code: Product code (e.g., "20039684_EA")

        Returns:
            dict: Product details including name, price, availability, etc.
        """
        url = f"{self.BASE_URL}/products/{product_code}"

        return self._request("GET", url).json()

    def get_cart(self) -> dict:
        """
        Get current cart contents

        Returns:
            dict: Cart data including items
        """
        url = f"{self.BASE_URL}/carts/{self.cart_id}"

        return self._request("GET", url).json()

    def add_to_cart(self, product_code: str, quantity: int = 1, fulfillment_method: str = "pickup") -> dict:
        """
        Add item to cart or update quantity

        Args:
            product_code: Product code (e.g., "21657456_EA")
            quantity: Quantity to add (use 0 to remove)
            fulfillment_method: "pickup" or "delivery"

        Returns:
            dict: Updated cart data
        """
        url = f"{self.BASE_URL}/carts/{self.cart_id}?inventory=true"

        payload = {
            "entries": {
                product_code: {
                    "quantity": quantity,
                    "fulfillmentMethod": fulfillment_method,
                    "sellerId": self.store_id
                }
            }
        }

        return self._request("POST", url, json=payload).json()

    def remove_from_cart(self, product_code: str) -> dict:
        """
        Remove item from cart

        Args:
            product_code: Product code to remove

        Returns:
            dict: Updated cart data
        """
        return self.add_to_cart(product_code, quantity=0)


# Initialize MCP server
app = Server("pcexpress-mcp")

# Global API client (will be initialized with credentials)
api_client: Optional[PCExpressAPI] = None


def get_api_client() -> PCExpressAPI:
    """Get or initialize API client"""
    global api_client

    if api_client is None:
        # cart_id is optional — auto-discovered from the customer profile when omitted.
        cart_id = os.getenv("PCEXPRESS_CART_ID")
        store_id = os.getenv("PCEXPRESS_STORE_ID", "1234")
        banner = os.getenv("PCEXPRESS_BANNER", "zehrs")

        # TokenManager mints/refreshes access tokens from the stored refresh token.
        token_manager = TokenManager()
        api_client = PCExpressAPI(token_manager, cart_id, store_id, banner)

    return api_client


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available MCP tools"""
    return [
        Tool(
            name="search_past_orders",
            description=(
                "Search through past grocery orders to find previously purchased items. "
                "Returns a list of past orders with order IDs, dates, totals, and store info. "
                "Useful for finding items the user has purchased before."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "number",
                        "description": "Maximum number of orders to return (default: 10)",
                        "default": 10
                    }
                }
            }
        ),
        Tool(
            name="get_order_items",
            description=(
                "Get detailed items from a specific past order. "
                "Returns all products from that order with names, quantities, and prices. "
                "Use this after search_past_orders to see what was in a specific order."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "The order ID from search_past_orders",
                    }
                },
                "required": ["order_id"]
            }
        ),
        Tool(
            name="search_products",
            description=(
                "Search for products by name or keyword. "
                "Returns full product details including product codes, names, brands, prices, and descriptions. "
                "Use this to find products the user wants to add to cart."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search term (e.g., 'ice cream', 'milk', 'bananas')",
                    },
                    "limit": {
                        "type": "number",
                        "description": "Maximum number of results (default: 48)",
                        "default": 48
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="get_product_details",
            description=(
                "Get detailed information about a specific product by its code. "
                "Use this after finding a product code from past orders. "
                "Returns full product details including name, price, brand, and availability."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "product_code": {
                        "type": "string",
                        "description": "Product code (e.g., '20039684_EA', '21218152_EA')",
                    }
                },
                "required": ["product_code"]
            }
        ),
        Tool(
            name="add_to_cart",
            description=(
                "Add a product to the shopping cart or update its quantity. "
                "Requires the product code from search results or past orders."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "product_code": {
                        "type": "string",
                        "description": "Product code (e.g., '21657456_EA')",
                    },
                    "quantity": {
                        "type": "number",
                        "description": "Quantity to set (default: 1)",
                        "default": 1
                    },
                    "fulfillment_method": {
                        "type": "string",
                        "description": "Fulfillment method: 'pickup' or 'delivery' (default: 'pickup')",
                        "enum": ["pickup", "delivery"],
                        "default": "pickup"
                    }
                },
                "required": ["product_code"]
            }
        ),
        Tool(
            name="remove_from_cart",
            description="Remove a product from the shopping cart completely.",
            inputSchema={
                "type": "object",
                "properties": {
                    "product_code": {
                        "type": "string",
                        "description": "Product code to remove",
                    }
                },
                "required": ["product_code"]
            }
        ),
        Tool(
            name="view_cart",
            description="View current shopping cart contents with all items, quantities, and prices.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Handle tool calls"""
    try:
        client = get_api_client()

        if name == "search_past_orders":
            limit = arguments.get("limit", 10)
            result = client.get_historical_orders()

            # Limit results
            orders = result.get("orderHistory", [])[:limit]

            return [TextContent(
                type="text",
                text=json.dumps({
                    "orders": orders,
                    "totalOnlineOrders": result.get("onlineOrdersCount"),
                    "totalOfflineOrders": result.get("offlineOrdersCount")
                }, indent=2)
            )]

        elif name == "get_order_items":
            order_id = arguments["order_id"]
            result = client.get_order_details(order_id)

            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]

        elif name == "search_products":
            query = arguments["query"]
            limit = arguments.get("limit", 48)
            result = client.search_products(query, size=limit)

            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]

        elif name == "get_product_details":
            product_code = arguments["product_code"]
            result = client.get_product_details(product_code)

            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]

        elif name == "add_to_cart":
            product_code = arguments["product_code"]
            quantity = arguments.get("quantity", 1)
            fulfillment = arguments.get("fulfillment_method", "pickup")

            result = client.add_to_cart(product_code, quantity, fulfillment)

            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]

        elif name == "remove_from_cart":
            product_code = arguments["product_code"]
            result = client.remove_from_cart(product_code)

            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]

        elif name == "view_cart":
            result = client.get_cart()

            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]

        else:
            return [TextContent(
                type="text",
                text=f"Unknown tool: {name}"
            )]

    except Exception as e:
        logger.error(f"Error in {name}: {str(e)}", exc_info=True)
        return [TextContent(
            type="text",
            text=f"Error: {str(e)}"
        )]


async def main_stdio():
    """Run the MCP server over stdio (default; for Claude Desktop and local clients)."""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


def _build_http_app():
    """Starlette app serving MCP over SSE at /sse (posts to /messages/), plus an
    unauthenticated /health for probes. SSE is used rather than streamable-http because it
    proxies cleanly through Traefik. Set PCEXPRESS_MCP_BEARER to require a bearer on /sse."""
    from starlette.applications import Starlette
    from starlette.routing import Mount, Route
    from starlette.responses import JSONResponse, Response
    from mcp.server.sse import SseServerTransport

    bearer = os.getenv("PCEXPRESS_MCP_BEARER")
    sse = SseServerTransport("/messages/")

    async def handle_sse(request):
        if bearer and request.headers.get("authorization") != f"Bearer {bearer}":
            return Response(status_code=401)
        async with sse.connect_sse(request.scope, request.receive, request._send) as (r, w):
            await app.run(r, w, app.create_initialization_options())
        return Response()  # SSE response is already sent; give Starlette a callable to close cleanly

    async def health(_request):
        return JSONResponse({"status": "ok"})

    return Starlette(routes=[
        Route("/health", health, methods=["GET"]),
        Route("/sse", handle_sse, methods=["GET"]),
        Mount("/messages/", app=sse.handle_post_message),
    ])


def main_http():
    """Serve MCP over HTTP/SSE (for containers and Kubernetes)."""
    import uvicorn
    port = int(os.getenv("PCEXPRESS_HTTP_PORT", "8090"))
    logger.info("Serving MCP over SSE on 0.0.0.0:%s (endpoints: /sse, /health)", port)
    uvicorn.run(_build_http_app(), host="0.0.0.0", port=port)


if __name__ == "__main__":
    import asyncio
    import sys
    if "--http" in sys.argv or os.getenv("PCEXPRESS_HTTP") == "1":
        main_http()
    else:
        asyncio.run(main_stdio())
