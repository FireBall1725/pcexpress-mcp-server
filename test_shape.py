#!/usr/bin/env python3
"""Unit tests for slim response shaping (no network)."""
import unittest

from pcx_shape import (
    flatten_prices,
    is_open_shopping_cart,
    json_text,
    map_search_product,
    summarize_cart,
    summarize_mutate,
    summarize_order_items,
    summarize_order_list,
    summarize_product_details,
)


class TestFlattenPrices(unittest.TestCase):
    def test_nested_price(self):
        flat = flatten_prices({
            "price": {"value": 3.49, "unit": "ea", "type": "SALE"},
            "wasPrice": {"value": 4.99},
            "comparisonPrices": [{"value": 0.25, "unit": "/100g"}],
        })
        self.assertEqual(flat["price"], 3.49)
        self.assertEqual(flat["wasPrice"], 4.99)
        self.assertEqual(flat["unitPrice"], 0.25)
        self.assertEqual(flat["unit"], "ea")


class TestMapSearch(unittest.TestCase):
    def test_maps_slim_fields(self):
        item = {
            "code": "123_EA",
            "name": "Milk",
            "brand": "Beatrice",
            "packageSize": "2 L",
            "prices": {"price": {"value": 5.49}},
            "dealPrice": 4.99,
            "stockStatus": "OK",
            "link": "https://example/long",
            "offerType": "OG",
        }
        mapped = map_search_product(item)
        self.assertEqual(mapped["code"], "123_EA")
        self.assertEqual(mapped["price"], 5.49)
        self.assertNotIn("link", mapped)
        self.assertNotIn("prices", mapped)


class TestSummarizeCart(unittest.TestCase):
    def test_entries_and_subtotal(self):
        cart = {
            "id": "cart-1",
            "status": "OPEN",
            "bannerId": "zehrs",
            "orders": [{
                "sellerId": "0545",
                "entries": [{
                    "quantity": 2,
                    "prices": {"totalPrice": 7.0},
                    "offer": {
                        "liam": "111_EA",
                        "product": {"name": "Eggs", "brand": "PC", "packageSize": "12"},
                    },
                }],
            }],
            "orderAggregations": {"open": {"totals": {"subTotal": 7.0}}},
        }
        slim = summarize_cart(cart)
        self.assertEqual(slim["cartId"], "cart-1")
        self.assertEqual(slim["subTotal"], 7.0)
        self.assertEqual(slim["entryCount"], 1)
        self.assertEqual(slim["entries"][0]["code"], "111_EA")
        self.assertEqual(slim["entries"][0]["price"], 3.5)
        self.assertEqual(slim["storeId"], "0545")

        mutate = summarize_mutate(cart, ["111_EA"])
        self.assertTrue(mutate["ok"])
        self.assertEqual(mutate["updated"], ["111_EA"])


class TestOpenCart(unittest.TestCase):
    def test_rejects_submitted_and_wrong_banner(self):
        self.assertFalse(is_open_shopping_cart({"status": "SUBMITTED"}, "zehrs"))
        self.assertFalse(is_open_shopping_cart(
            {"status": "OPEN", "bannerId": "loblaws"}, "zehrs"
        ))
        self.assertTrue(is_open_shopping_cart(
            {"status": "OPEN", "bannerId": "zehrs"}, "zehrs", "0545"
        ))
        self.assertFalse(is_open_shopping_cart(
            {
                "status": "OPEN",
                "bannerId": "zehrs",
                "orders": [{"sellerId": "9999"}],
            },
            "zehrs",
            "0545",
        ))


class TestOrdersAndProduct(unittest.TestCase):
    def test_order_list_and_items(self):
        orders = summarize_order_list([
            {"orderId": "o1", "placedDate": "2026-01-01", "total": 10, "extra": "drop"},
        ])
        self.assertEqual(orders[0]["orderId"], "o1")
        self.assertNotIn("extra", orders[0])

        detail = summarize_order_items({
            "orderId": "o1",
            "items": [{"productCode": "a_EA", "name": "A", "quantity": 1, "price": 2}],
        })
        self.assertEqual(detail["items"][0]["code"], "a_EA")

        product = summarize_product_details({
            "code": "p_EA",
            "name": "Bread",
            "prices": {"price": {"value": 3.0}},
            "imageAssets": [{"url": "http://x"}],
            "nutritionFacts": {"huge": True},
        })
        self.assertEqual(product["price"], 3.0)
        self.assertNotIn("imageAssets", product)
        self.assertNotIn("nutritionFacts", product)


class TestJsonText(unittest.TestCase):
    def test_compact(self):
        text = json_text({"a": 1, "b": [2]})
        self.assertNotIn("\n", text)
        self.assertNotIn(" ", text)


if __name__ == "__main__":
    unittest.main()
