"""Slim BFF payloads into agent-sized MCP tool results.

Raw Loblaw cart/order/product trees are large (images, fulfillment, nested prices).
MCP clients inject tool results into the LLM context, so compact JSON matters as
much as HTTP round-trip time.
"""
from __future__ import annotations

from typing import Any, Optional


def json_text(obj: Any) -> str:
    """Compact JSON for MCP TextContent (no indent)."""
    return json_dumps(obj)


def json_dumps(obj: Any) -> str:
    import json

    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)


def _num(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _str(value: Any) -> Optional[str]:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def flatten_prices(prices: Any) -> dict[str, Any]:
    """Collapse nested prices.price / wasPrice into scalars."""
    out: dict[str, Any] = {"price": None, "wasPrice": None, "unitPrice": None, "unit": None}
    if not isinstance(prices, dict):
        return out
    price = prices.get("price") if isinstance(prices.get("price"), dict) else None
    was = prices.get("wasPrice") if isinstance(prices.get("wasPrice"), dict) else None
    if price:
        out["price"] = _num(price.get("value"))
        out["unit"] = _str(price.get("unit")) or _str(price.get("type"))
    if was:
        out["wasPrice"] = _num(was.get("value"))
    comparison = prices.get("comparisonPrices")
    if isinstance(comparison, list) and comparison:
        first = comparison[0] if isinstance(comparison[0], dict) else None
        if first:
            out["unitPrice"] = _num(first.get("value"))
            if not out["unit"]:
                out["unit"] = _str(first.get("unit"))
    return out


def map_search_product(item: dict) -> dict[str, Any]:
    flat = flatten_prices(item.get("prices"))
    return {
        "code": item.get("code") or item.get("articleNumber"),
        "name": item.get("name"),
        "brand": item.get("brand"),
        "packageSize": item.get("packageSize"),
        "price": flat["price"],
        "wasPrice": flat["wasPrice"],
        "unitPrice": flat["unitPrice"],
        "dealPrice": item.get("dealPrice") if isinstance(item.get("dealPrice"), (int, float)) else None,
        "stockStatus": item.get("stockStatus"),
        "offerType": item.get("offerType"),
    }


def _as_store_id(value: Any) -> Optional[str]:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(int(value)) if float(value).is_integer() else str(value)
    return None


def store_id_from_order(order: dict) -> Optional[str]:
    fulfillment = order.get("fulfillment") if isinstance(order.get("fulfillment"), dict) else {}
    pickup = fulfillment.get("pickupBooking") if isinstance(fulfillment.get("pickupBooking"), dict) else {}
    loc = pickup.get("pickupLocation") if isinstance(pickup.get("pickupLocation"), dict) else {}
    courier = fulfillment.get("courier") if isinstance(fulfillment.get("courier"), dict) else {}
    return (
        _as_store_id(loc.get("storeId"))
        or _as_store_id(courier.get("storeId"))
        or _as_store_id(order.get("sellerId"))
        or _as_store_id(order.get("storeId"))
    )


def store_id_from_cart(cart: dict) -> Optional[str]:
    for order in cart.get("orders") or []:
        if isinstance(order, dict):
            sid = store_id_from_order(order)
            if sid:
                return sid
    return None


def is_open_shopping_cart(cart: dict, banner: str, store_id: Optional[str] = None) -> bool:
    """True when cart is an OPEN shopping cart for this banner (and optional store)."""
    status = str(cart.get("status") or "").upper()
    if status and status != "OPEN":
        return False
    cart_banner = str(cart.get("bannerId") or "").lower()
    if cart_banner and cart_banner != banner.lower():
        return False
    cart_store = store_id_from_cart(cart)
    # Brand-new empty carts may omit store until first add.
    if store_id and cart_store and cart_store != str(store_id):
        return False
    return True


def _unit_price_from_entry(prices: Any, quantity: float) -> Optional[float]:
    if not isinstance(prices, dict):
        return None
    total = _num(prices.get("totalPrice") if not isinstance(prices.get("totalPrice"), dict) else prices["totalPrice"].get("value"))
    if total is None:
        price = prices.get("price")
        if isinstance(price, dict):
            total = _num(price.get("value"))
        else:
            total = _num(price)
    if total is None:
        return None
    if quantity and quantity > 0:
        return round(total / quantity, 4)
    return total


def summarize_cart(cart: dict) -> dict[str, Any]:
    """Agent-facing cart snapshot (entries + subtotal only)."""
    entries: list[dict[str, Any]] = []
    store_id = store_id_from_cart(cart)
    for order in cart.get("orders") or []:
        if not isinstance(order, dict):
            continue
        for e in order.get("entries") or []:
            if not isinstance(e, dict):
                continue
            offer = e.get("offer") if isinstance(e.get("offer"), dict) else {}
            product = offer.get("product") if isinstance(offer.get("product"), dict) else {}
            quantity = float(e.get("quantity") or 0)
            code = offer.get("liam") or offer.get("id") or product.get("code")
            entries.append({
                "code": code,
                "name": product.get("name") or offer.get("name"),
                "brand": product.get("brand"),
                "packageSize": product.get("packageSize") or offer.get("packageSize"),
                "quantity": quantity,
                "price": _unit_price_from_entry(e.get("prices"), quantity),
            })

    sub_total = None
    agg = cart.get("orderAggregations") if isinstance(cart.get("orderAggregations"), dict) else {}
    open_agg = agg.get("open") if isinstance(agg.get("open"), dict) else {}
    totals = open_agg.get("totals") if isinstance(open_agg.get("totals"), dict) else {}
    if isinstance(totals.get("subTotal"), (int, float)):
        sub_total = float(totals["subTotal"])

    return {
        "cartId": cart.get("id") or cart.get("cartId"),
        "status": cart.get("status"),
        "storeId": store_id,
        "subTotal": sub_total,
        "entryCount": len(entries),
        "entries": entries,
    }


def summarize_mutate(cart: dict, product_codes: list[str] | None = None) -> dict[str, Any]:
    """Compact add/remove result: ok + slim cart (no need for a follow-up view_cart)."""
    slim = summarize_cart(cart)
    slim["ok"] = True
    if product_codes:
        slim["updated"] = product_codes
    return slim


def summarize_order_list(orders: list, *, limit: int = 10) -> list[dict[str, Any]]:
    out = []
    for order in orders[:limit]:
        if not isinstance(order, dict):
            continue
        out.append({
            "orderId": order.get("orderId") or order.get("id"),
            "placedDate": order.get("placedDate") or order.get("submittedDate") or order.get("date"),
            "status": order.get("status"),
            "total": order.get("total") or order.get("totalPrice") or order.get("orderTotal"),
            "storeName": order.get("storeName") or order.get("store"),
            "itemCount": order.get("itemCount") or order.get("numberOfItems"),
        })
    return out


def summarize_order_items(order: dict) -> dict[str, Any]:
    items = []
    raw_items = (
        order.get("items")
        or order.get("entries")
        or order.get("orderItems")
        or []
    )
    # Some payloads nest under orders[0].entries
    if not raw_items and isinstance(order.get("orders"), list):
        for nested in order["orders"]:
            if isinstance(nested, dict):
                raw_items = nested.get("entries") or nested.get("items") or []
                if raw_items:
                    break

    for item in raw_items:
        if not isinstance(item, dict):
            continue
        offer = item.get("offer") if isinstance(item.get("offer"), dict) else {}
        product = offer.get("product") if isinstance(offer.get("product"), dict) else {}
        code = (
            item.get("productCode")
            or item.get("code")
            or offer.get("liam")
            or offer.get("id")
            or product.get("code")
        )
        name = item.get("name") or product.get("name") or offer.get("name")
        qty = item.get("quantity")
        price = item.get("price") or item.get("totalPrice")
        if isinstance(price, dict):
            price = price.get("value")
        items.append({
            "code": code,
            "name": name,
            "quantity": qty,
            "price": price,
            "brand": product.get("brand") or item.get("brand"),
            "packageSize": product.get("packageSize") or item.get("packageSize"),
        })

    return {
        "orderId": order.get("orderId") or order.get("id"),
        "placedDate": order.get("placedDate") or order.get("submittedDate") or order.get("date"),
        "status": order.get("status"),
        "total": order.get("total") or order.get("totalPrice") or order.get("orderTotal"),
        "itemCount": len(items),
        "items": items,
    }


def summarize_product_details(product: dict) -> dict[str, Any]:
    flat = flatten_prices(product.get("prices"))
    return {
        "code": product.get("code") or product.get("articleNumber"),
        "name": product.get("name"),
        "brand": product.get("brand"),
        "packageSize": product.get("packageSize"),
        "description": _str(product.get("description")) or _str(product.get("shortDescription")),
        "price": flat["price"],
        "wasPrice": flat["wasPrice"],
        "dealPrice": product.get("dealPrice") if isinstance(product.get("dealPrice"), (int, float)) else None,
        "stockStatus": product.get("stockStatus"),
        "offerType": product.get("offerType"),
        "uom": product.get("uom"),
    }
