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
- Adding items to cart (single or batch)
- Removing items from cart
- Viewing cart contents

Performance notes:
- Tool results are slimmed (see pcx_shape) and compact JSON (no indent).
- Search defaults to 12 hits; optional file cache under PCEXPRESS_STATE_DIR.
- Cart id is resolved via banner carts list (not blind profile cartId) with TTL.
- Blocking HTTP runs in asyncio.to_thread so SSE clients are not stalled.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Optional

import requests
from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from pcid_token import TokenManager
from pcx_shape import (
    is_open_shopping_cart,
    json_text,
    map_search_product,
    summarize_cart,
    summarize_mutate,
    summarize_order_items,
    summarize_order_list,
    summarize_product_details,
)

# Load .env if present (no-op when the launcher passes env directly)
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pcexpress-mcp")

DEFAULT_SEARCH_SIZE = 12
REQUEST_TIMEOUT = (10, 30)  # connect, read seconds
CART_TTL_SEC = int(os.getenv("PCEXPRESS_CART_TTL_SEC", "900"))  # 15 min
SESSION_RECHECK_SEC = int(os.getenv("PCEXPRESS_SESSION_RECHECK_SEC", "60"))
SEARCH_CACHE_TTL_SEC = int(os.getenv("PCEXPRESS_SEARCH_CACHE_TTL_SEC", "259200"))  # 3 days
SEARCH_CACHE_ENABLED = os.getenv("PCEXPRESS_SEARCH_CACHE", "1") != "0"


class ShoppingLockedError(ValueError):
    """Raised when liveOrders blocks cart mutations for this banner."""


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

    def __init__(
        self,
        token_manager: TokenManager,
        cart_id: Optional[str],
        store_id: str = "1234",
        banner: str = "zehrs",
        state_dir: Optional[str] = None,
    ):
        """
        Initialize PCExpressAPI client

        Args:
            token_manager: mints/refreshes PCID access tokens on demand
            cart_id: Optional fixed cart ID (skips safe discovery when set)
            store_id: Store ID (4-digit code for your preferred store)
            banner: Store banner (zehrs, loblaws, nofrills, superstore, independent, tandt)
            state_dir: Writable dir for cart-id / search caches (defaults to PCEXPRESS_STATE_DIR)
        """
        self.tokens = token_manager
        self._cart_id_override = cart_id or None
        self._cart_id: Optional[str] = cart_id or None
        self._cart_id_at: float = time.time() if cart_id else 0.0
        self._session_checked_at: float = 0.0
        self._live_order_ids: list[str] = []
        self._shopping_locked = False
        self._lock_reason: Optional[str] = None
        self.store_id = store_id
        self.banner = banner.lower()
        self.domain = self.BANNER_DOMAINS.get(self.banner, "www.zehrs.ca")
        self.session = requests.Session()
        self.state_dir = Path(
            state_dir
            or os.getenv("PCEXPRESS_STATE_DIR", os.path.expanduser("~/.pcexpress-mcp"))
        )
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self._search_cache_dir = self.state_dir / "search-cache"
        if SEARCH_CACHE_ENABLED:
            self._search_cache_dir.mkdir(parents=True, exist_ok=True)
        if not self._cart_id:
            self._load_persisted_cart_id()

    # --- cart resolution -------------------------------------------------

    def _cart_cache_path(self) -> Path:
        return self.state_dir / f"cart_id_{self.banner}_{self.store_id}.json"

    def _load_persisted_cart_id(self) -> None:
        path = self._cart_cache_path()
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text())
            if data.get("banner") != self.banner or str(data.get("storeId")) != str(self.store_id):
                return
            age = time.time() - float(data.get("at", 0))
            if age > CART_TTL_SEC:
                return
            cid = data.get("cartId")
            if isinstance(cid, str) and cid:
                self._cart_id = cid
                self._cart_id_at = float(data.get("at", 0))
        except Exception as e:
            logger.warning("Could not read cart id cache (%s)", e)

    def _persist_cart_id(self, cart_id: str) -> None:
        path = self._cart_cache_path()
        tmp = path.with_suffix(".tmp")
        payload = {
            "cartId": cart_id,
            "banner": self.banner,
            "storeId": self.store_id,
            "at": time.time(),
        }
        try:
            tmp.write_text(json.dumps(payload))
            os.replace(tmp, path)
            try:
                os.chmod(path, 0o600)
            except OSError:
                pass
        except Exception as e:
            logger.warning("Could not persist cart id (%s)", e)

    def _clear_cart_cache(self) -> None:
        self._cart_id = None
        self._cart_id_at = 0.0
        self._session_checked_at = 0.0
        self._live_order_ids = []
        self._shopping_locked = False
        self._lock_reason = None
        try:
            self._cart_cache_path().unlink(missing_ok=True)
        except OSError:
            pass

    def _customer_id(self, cust: Optional[dict] = None) -> str:
        cust = cust or self.get_customer()
        cid = cust.get("customerId") or cust.get("id")
        if not cid:
            raise ValueError("Customer profile missing customerId")
        return str(cid)

    def list_customer_carts(self, customer_id: Optional[str] = None) -> dict:
        """List carts / liveOrders for this banner."""
        cid = customer_id or self._customer_id()
        url = f"{self.BASE_URL}/customers/{cid}/carts?banner={self.banner}"
        return self._request("GET", url).json()

    def _fetch_cart_raw(self, cart_id: str) -> dict:
        url = f"{self.BASE_URL}/carts/{cart_id}?inventory=true"
        return self._request("GET", url).json()

    def _resolve_shopping_cart(self, force: bool = False) -> str:
        """Resolve an OPEN shopping cart for this banner/store. Never returns liveOrders ids."""
        if self._cart_id_override:
            return self._cart_id_override

        now = time.time()
        cart_fresh = self._cart_id and (now - self._cart_id_at) < CART_TTL_SEC
        session_fresh = (now - self._session_checked_at) < SESSION_RECHECK_SEC
        if not force and cart_fresh and session_fresh:
            if self._shopping_locked:
                raise ShoppingLockedError(self._lock_reason or "Shopping locked by live order")
            return self._cart_id

        cust = self.get_customer()
        listing = self.list_customer_carts(self._customer_id(cust))
        self._session_checked_at = time.time()
        carts_raw = listing.get("carts") or []
        live_raw = listing.get("liveOrders") or []

        live_ids = []
        for raw in live_raw:
            if isinstance(raw, dict):
                lid = raw.get("id") or raw.get("cartId")
                if isinstance(lid, str) and lid:
                    live_ids.append(lid)
        self._live_order_ids = live_ids
        self._shopping_locked = bool(live_ids)
        self._lock_reason = (
            "A live order is in progress for this banner. Cart writes are blocked until it completes."
            if live_ids
            else None
        )

        preferred = cust.get("cartId") if isinstance(cust.get("cartId"), str) else None
        cart_ids = []
        for c in carts_raw:
            if isinstance(c, dict):
                cid = c.get("id") or c.get("cartId")
                if isinstance(cid, str) and cid:
                    cart_ids.append(cid)

        # Prefer profile cartId only if it also appears under this banner's carts[].
        ordered: list[str] = []
        if preferred and preferred in cart_ids:
            ordered.append(preferred)
        for cid in cart_ids:
            if cid not in ordered:
                ordered.append(cid)

        chosen = None
        for cid in ordered:
            if cid in live_ids:
                continue
            try:
                cart = self._fetch_cart_raw(cid)
            except requests.HTTPError:
                continue
            if is_open_shopping_cart(cart, self.banner, self.store_id):
                chosen = cid
                break

        if self._shopping_locked:
            # Never mutate while a live order is in flight for this banner.
            raise ShoppingLockedError(self._lock_reason)

        if not chosen:
            # Fall back to profile cartId only when list is empty —
            # still validate OPEN/banner when fetchable.
            if preferred and preferred not in live_ids:
                try:
                    cart = self._fetch_cart_raw(preferred)
                    if is_open_shopping_cart(cart, self.banner, self.store_id):
                        chosen = preferred
                except requests.HTTPError:
                    pass

        if not chosen:
            raise ValueError(
                "No open shopping cart for this banner/store. "
                "Open the PC Express app or website once to create a cart, then retry."
            )

        self._cart_id = chosen
        self._cart_id_at = time.time()
        self._persist_cart_id(chosen)
        return chosen

    @property
    def cart_id(self) -> str:
        """The active cart id (safe banner/store resolution with TTL cache)."""
        return self._resolve_shopping_cart()

    def _refresh_cart_id(self) -> Optional[str]:
        """Force re-discovery after a stale/expired cart 404."""
        self._clear_cart_cache()
        try:
            return self._resolve_shopping_cart(force=True)
        except (ValueError, ShoppingLockedError):
            return None

    def _request_cart(self, method: str, path: str, **kwargs) -> requests.Response:
        """Request a cart-scoped endpoint, self-healing a stale/expired cart.

        `path` must contain a literal ``{cart_id}`` placeholder. On a 404 (the
        cached cart was deleted server-side) the cart id is re-discovered once
        and the request retried; if no fresh cart exists, a clear error is
        raised instead of a bare 404.
        """
        stale_id = self.cart_id
        url = f"{self.BASE_URL}{path.format(cart_id=stale_id)}"
        try:
            return self._request(method, url, **kwargs)
        except requests.HTTPError as e:
            if e.response is None or e.response.status_code != 404:
                raise
            fresh_id = self._refresh_cart_id()
            if not fresh_id or fresh_id == stale_id:
                raise ValueError(
                    "The active cart no longer exists and the account has no "
                    "current cart. Add an item in the PC Express app or website "
                    "to create a fresh cart, then retry."
                ) from e
            url = f"{self.BASE_URL}{path.format(cart_id=fresh_id)}"
            return self._request(method, url, **kwargs)

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
        """Authenticated request with timeout, 401 refresh, and one 429 retry."""
        kwargs.setdefault("timeout", REQUEST_TIMEOUT)
        headers = self._get_headers()
        resp = self.session.request(method, url, headers=headers, **kwargs)
        if resp.status_code == 401:
            headers["Authorization"] = f"Bearer {self.tokens.get_access_token(force=True)}"
            resp = self.session.request(method, url, headers=headers, **kwargs)
        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After", "1")
            try:
                delay = min(float(retry_after), 5.0)
            except ValueError:
                delay = 1.0
            time.sleep(delay)
            resp = self.session.request(method, url, headers=headers, **kwargs)
        resp.raise_for_status()
        return resp

    # --- search cache ----------------------------------------------------

    def _search_cache_key(self, query: str, size: int) -> Path:
        raw = f"{self.banner}|{self.store_id}|{query.strip().lower()}|{size}"
        digest = hashlib.sha256(raw.encode()).hexdigest()[:32]
        return self._search_cache_dir / f"{digest}.json"

    def _read_search_cache(self, query: str, size: int) -> Optional[dict]:
        if not SEARCH_CACHE_ENABLED:
            return None
        path = self._search_cache_key(query, size)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
            if time.time() - float(data.get("at", 0)) > SEARCH_CACHE_TTL_SEC:
                return None
            return data.get("result")
        except Exception:
            return None

    def _write_search_cache(self, query: str, size: int, result: dict) -> None:
        if not SEARCH_CACHE_ENABLED:
            return
        path = self._search_cache_key(query, size)
        tmp = path.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps({"at": time.time(), "result": result}))
            os.replace(tmp, path)
        except Exception as e:
            logger.warning("Could not write search cache (%s)", e)

    # --- API methods -----------------------------------------------------

    def get_historical_orders(self) -> dict:
        """Get list of past orders."""
        url = f"{self.BASE_URL}/ecommerce/v2/{self.banner}/customers/historical-orders"
        return self._request("GET", url).json()

    def get_order_details(self, order_id: str) -> dict:
        """Get details for a specific order including all items."""
        url = (
            f"{self.BASE_URL}/ecommerce/v2/{self.banner}/customers/historical-orders/{order_id}"
        )
        return self._request("GET", url).json()

    def search_products(self, query: str, size: int = DEFAULT_SEARCH_SIZE) -> dict:
        """
        Search for products and return slim fields needed to add them to cart.

        Uses the authenticated pcx-bff product-search endpoint. cartId is optional
        for the BFF; we attach it when an open cart is available without blocking
        search behind a live order.
        """
        cached = self._read_search_cache(query, size)
        if cached is not None:
            cached = dict(cached)
            cached["cached"] = True
            return cached

        url = f"{self.BASE_URL}/products/search"
        payload: dict[str, Any] = {
            "lang": "en",
            "term": query,
            "storeId": self.store_id,
            "banner": self.banner,
            "pagination": {"from": 0, "size": size},
        }
        # Prefer attaching cartId when cheap/cached; never fail search on lock.
        try:
            if self._cart_id_override:
                payload["cartId"] = self._cart_id_override
            elif self._cart_id and (time.time() - self._cart_id_at) < CART_TTL_SEC:
                payload["cartId"] = self._cart_id
            else:
                # Soft resolve: ignore lock / missing cart for read-only search.
                try:
                    payload["cartId"] = self._resolve_shopping_cart()
                except ShoppingLockedError:
                    pass
                except ValueError:
                    pass
        except Exception:
            pass

        data = self._request("POST", url, json=payload).json()
        products = [map_search_product(item) for item in data.get("results", [])[:size]]
        result = {
            "query": query,
            "totalResults": data.get("pagination", {}).get("totalResults", len(products)),
            "products": products,
            "cached": False,
        }
        self._write_search_cache(query, size, {k: v for k, v in result.items() if k != "cached"})
        return result

    def get_product_details(self, product_code: str) -> dict:
        """Get detailed information about a specific product by its code."""
        url = f"{self.BASE_URL}/products/{product_code}"
        return self._request("GET", url).json()

    def get_cart(self) -> dict:
        """Get current cart contents (raw BFF; callers should summarize)."""
        return self._request_cart("GET", "/carts/{cart_id}?inventory=true").json()

    def add_entries(
        self,
        entries: dict[str, int],
        fulfillment_method: str = "pickup",
    ) -> dict:
        """Add/update multiple cart lines in one POST. quantity 0 removes."""
        if not entries:
            raise ValueError("entries must not be empty")
        payload = {
            "entries": {
                code: {
                    "quantity": int(qty),
                    "fulfillmentMethod": fulfillment_method,
                    "sellerId": self.store_id,
                }
                for code, qty in entries.items()
            }
        }
        return self._request_cart(
            "POST", "/carts/{cart_id}?inventory=true", json=payload
        ).json()

    def add_to_cart(
        self, product_code: str, quantity: int = 1, fulfillment_method: str = "pickup"
    ) -> dict:
        """Add item to cart or update quantity."""
        return self.add_entries({product_code: quantity}, fulfillment_method)

    def remove_from_cart(self, product_code: str) -> dict:
        """Remove item from cart."""
        return self.add_to_cart(product_code, quantity=0)


# Initialize MCP server
app = Server("pcexpress-mcp")

# Global API client (will be initialized with credentials)
api_client: Optional[PCExpressAPI] = None


def get_api_client() -> PCExpressAPI:
    """Get or initialize API client"""
    global api_client

    if api_client is None:
        # cart_id is optional — safely auto-discovered when omitted.
        cart_id = os.getenv("PCEXPRESS_CART_ID") or None
        store_id = os.getenv("PCEXPRESS_STORE_ID", "1234")
        banner = os.getenv("PCEXPRESS_BANNER", "zehrs")

        token_manager = TokenManager()
        api_client = PCExpressAPI(token_manager, cart_id, store_id, banner)

    return api_client


def _text(obj: Any) -> list[TextContent]:
    return [TextContent(type="text", text=json_text(obj))]


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available MCP tools"""
    return [
        Tool(
            name="search_past_orders",
            description=(
                "Search through past grocery orders to find previously purchased items. "
                "Returns a slim list of past orders with order IDs, dates, totals, and store info."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "number",
                        "description": "Maximum number of orders to return (default: 10)",
                        "default": 10,
                    }
                },
            },
        ),
        Tool(
            name="get_order_items",
            description=(
                "Get slim line items from a specific past order (codes, names, quantities, prices). "
                "Use after search_past_orders."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "The order ID from search_past_orders",
                    }
                },
                "required": ["order_id"],
            },
        ),
        Tool(
            name="search_products",
            description=(
                "Search for products by name or keyword. "
                "Returns compact results (code, name, brand, price, stock). "
                "Default limit is 12; raise limit only when needed."
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
                        "description": f"Maximum number of results (default: {DEFAULT_SEARCH_SIZE})",
                        "default": DEFAULT_SEARCH_SIZE,
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="get_product_details",
            description=(
                "Get compact product details by code (name, brand, price, stock). "
                "Use after finding a product code from past orders or search."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "product_code": {
                        "type": "string",
                        "description": "Product code (e.g., '20039684_EA', '21218152_EA')",
                    }
                },
                "required": ["product_code"],
            },
        ),
        Tool(
            name="add_to_cart",
            description=(
                "Add a product to the shopping cart or update its quantity. "
                "Returns a slim cart summary — a follow-up view_cart is usually unnecessary."
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
                        "default": 1,
                    },
                    "fulfillment_method": {
                        "type": "string",
                        "description": "Fulfillment method: 'pickup' or 'delivery' (default: 'pickup')",
                        "enum": ["pickup", "delivery"],
                        "default": "pickup",
                    },
                },
                "required": ["product_code"],
            },
        ),
        Tool(
            name="add_to_cart_batch",
            description=(
                "Add or update multiple products in one cart request. "
                "Prefer this over repeated add_to_cart for multi-item lists. "
                "Returns a slim cart summary."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "description": "Products to set in the cart",
                        "items": {
                            "type": "object",
                            "properties": {
                                "product_code": {"type": "string"},
                                "quantity": {"type": "number", "default": 1},
                            },
                            "required": ["product_code"],
                        },
                    },
                    "fulfillment_method": {
                        "type": "string",
                        "enum": ["pickup", "delivery"],
                        "default": "pickup",
                    },
                },
                "required": ["items"],
            },
        ),
        Tool(
            name="remove_from_cart",
            description=(
                "Remove a product from the shopping cart completely. "
                "Returns a slim cart summary."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "product_code": {
                        "type": "string",
                        "description": "Product code to remove",
                    }
                },
                "required": ["product_code"],
            },
        ),
        Tool(
            name="view_cart",
            description=(
                "View current shopping cart as a slim summary "
                "(entries with code/name/qty/price and subTotal)."
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Handle tool calls (BFF I/O runs in a worker thread)."""
    try:
        client = get_api_client()
        arguments = arguments or {}

        if name == "search_past_orders":
            limit = int(arguments.get("limit", 10))
            result = await asyncio.to_thread(client.get_historical_orders)
            orders = summarize_order_list(result.get("orderHistory") or [], limit=limit)
            return _text({
                "orders": orders,
                "totalOnlineOrders": result.get("onlineOrdersCount"),
                "totalOfflineOrders": result.get("offlineOrdersCount"),
            })

        if name == "get_order_items":
            order_id = arguments["order_id"]
            result = await asyncio.to_thread(client.get_order_details, order_id)
            return _text(summarize_order_items(result))

        if name == "search_products":
            query = arguments["query"]
            limit = int(arguments.get("limit", DEFAULT_SEARCH_SIZE))
            result = await asyncio.to_thread(client.search_products, query, limit)
            return _text(result)

        if name == "get_product_details":
            product_code = arguments["product_code"]
            result = await asyncio.to_thread(client.get_product_details, product_code)
            return _text(summarize_product_details(result))

        if name == "add_to_cart":
            product_code = arguments["product_code"]
            quantity = int(arguments.get("quantity", 1))
            fulfillment = arguments.get("fulfillment_method", "pickup")
            result = await asyncio.to_thread(
                client.add_to_cart, product_code, quantity, fulfillment
            )
            return _text(summarize_mutate(result, [product_code]))

        if name == "add_to_cart_batch":
            items = arguments.get("items") or []
            fulfillment = arguments.get("fulfillment_method", "pickup")
            entries = {
                str(item["product_code"]): int(item.get("quantity", 1))
                for item in items
                if item.get("product_code")
            }
            if not entries:
                return _text({"ok": False, "error": "items must include at least one product_code"})
            result = await asyncio.to_thread(client.add_entries, entries, fulfillment)
            return _text(summarize_mutate(result, list(entries.keys())))

        if name == "remove_from_cart":
            product_code = arguments["product_code"]
            result = await asyncio.to_thread(client.remove_from_cart, product_code)
            return _text(summarize_mutate(result, [product_code]))

        if name == "view_cart":
            result = await asyncio.to_thread(client.get_cart)
            return _text(summarize_cart(result))

        return _text({"error": f"Unknown tool: {name}"})

    except Exception as e:
        logger.error("Error in %s: %s", name, e, exc_info=True)
        return [TextContent(type="text", text=f"Error: {e}")]


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
    import sys
    if "--http" in sys.argv or os.getenv("PCEXPRESS_HTTP") == "1":
        main_http()
    else:
        asyncio.run(main_stdio())
