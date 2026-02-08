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
import re
from typing import Any, Optional
from datetime import datetime

import requests
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pcexpress-mcp")


class PCExpressAPI:
    """Wrapper for PC Express API (works across all Loblaws banners)"""

    BASE_URL = "https://api.pcexpress.ca/pcx-bff/api/v1"
    AUTH_URL = "https://accounts.pcid.ca/oauth2/v1/token"

    # Static API key extracted from HAR file
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

    def __init__(self, bearer_token: str, customer_id: str, cart_id: str, store_id: str = "1234", banner: str = "zehrs"):
        """
        Initialize PCExpressAPI client

        Args:
            bearer_token: OAuth bearer token from login
            customer_id: Customer/user ID
            cart_id: Active cart ID
            store_id: Store ID (4-digit code for your preferred store)
            banner: Store banner (zehrs, loblaws, nofrills, superstore, independent, tandt)
        """
        self.bearer_token = bearer_token
        self.customer_id = customer_id
        self.cart_id = cart_id
        self.store_id = store_id
        self.banner = banner.lower()
        self.domain = self.BANNER_DOMAINS.get(self.banner, "www.zehrs.ca")

    def _get_headers(self) -> dict:
        """Get standard headers for API requests"""
        return {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en",
            "Authorization": f"Bearer {self.bearer_token}",
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

    def get_historical_orders(self) -> dict:
        """
        Get list of past orders

        Returns:
            dict: Order history with list of orders
        """
        url = f"{self.BASE_URL}/ecommerce/v2/{self.banner}/customers/historical-orders"

        response = requests.get(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()

    def get_order_details(self, order_id: str) -> dict:
        """
        Get details for a specific order including all items

        Args:
            order_id: The order ID

        Returns:
            dict: Order details including items, prices, etc.
        """
        url = f"{self.BASE_URL}/ecommerce/v2/{self.banner}/customers/historical-orders/{order_id}"

        response = requests.get(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()

    def _get_build_id(self) -> str:
        """
        Get the current Next.js build ID from the website

        Returns:
            str: Build ID for Next.js data URLs
        """
        url = f"https://{self.domain}/en"
        response = requests.get(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        })
        response.raise_for_status()

        # Extract build ID from page HTML
        match = re.search(r'buildId":"([^"]+)"', response.text)
        if match:
            return match.group(1)
        raise ValueError("Could not extract build ID from website")

    def search_products(self, query: str, size: int = 48) -> dict:
        """
        Search for products and return full product details with codes

        Args:
            query: Search term (e.g., "milk", "ground beef")
            size: Maximum number of results to return (default: 48)

        Returns:
            dict: Search results with products including articleNumber codes
        """
        # Get current build ID
        build_id = self._get_build_id()

        # Use Next.js data endpoint for search results
        url = f"https://{self.domain}/_next/data/{build_id}/en/search.json"

        params = {
            "search-bar": query,
            "storeId": self.store_id,
            "cartId": self.cart_id
        }

        response = requests.get(url, params=params, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "application/json"
        })
        response.raise_for_status()
        data = response.json()

        # Extract products from Next.js response structure
        products = []
        try:
            page_props = data.get("pageProps", {})
            search_data = page_props.get("initialSearchData", {})
            layout = search_data.get("layout", {})
            sections = layout.get("sections", {})
            main_content = sections.get("mainContentCollection", {})

            for component in main_content.get("components", []):
                comp_data = component.get("data", {})
                if "productTiles" in comp_data:
                    tiles = comp_data["productTiles"]
                    for tile in tiles[:size]:
                        # Extract key product info
                        description = tile.get("description") or ""
                        product = {
                            "code": tile.get("articleNumber"),
                            "name": tile.get("title"),
                            "brand": tile.get("brand"),
                            "description": description.replace("<br/>", " ") if description else "",
                            "price": tile.get("pricing", {}).get("price"),
                            "packageSizing": tile.get("packageSizing"),
                            "link": tile.get("link"),
                            "offerType": tile.get("offerType"),
                        }
                        products.append(product)

            return {
                "query": query,
                "totalResults": search_data.get("searchResultsCount", 0),
                "products": products[:size]
            }
        except Exception as e:
            logger.error(f"Error parsing search results: {e}")
            return {
                "query": query,
                "totalResults": 0,
                "products": [],
                "error": str(e)
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

        response = requests.get(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()

    def get_cart(self) -> dict:
        """
        Get current cart contents

        Returns:
            dict: Cart data including items
        """
        url = f"{self.BASE_URL}/carts/{self.cart_id}"

        response = requests.get(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()

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

        response = requests.post(url, headers=self._get_headers(), json=payload)
        response.raise_for_status()
        return response.json()

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
        # Load credentials from environment or config file
        bearer_token = os.getenv("PCEXPRESS_BEARER_TOKEN")
        customer_id = os.getenv("PCEXPRESS_CUSTOMER_ID")
        cart_id = os.getenv("PCEXPRESS_CART_ID")
        store_id = os.getenv("PCEXPRESS_STORE_ID", "1234")
        banner = os.getenv("PCEXPRESS_BANNER", "zehrs")

        if not all([bearer_token, customer_id, cart_id]):
            raise ValueError(
                "Missing required credentials. Set environment variables: "
                "PCEXPRESS_BEARER_TOKEN, PCEXPRESS_CUSTOMER_ID, PCEXPRESS_CART_ID"
            )

        api_client = PCExpressAPI(bearer_token, customer_id, cart_id, store_id, banner)

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
            limit = arguments.get("limit", 7)
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


async def main():
    """Run the MCP server"""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
