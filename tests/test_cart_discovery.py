"""Cart discovery and self-healing, with no network.

The profile's cartId can point at a stale anonymous cart on another banner. Adding
to it fails with a 400, and before this check the server kept using it until the pod
restarted.
"""

import pytest
import requests

import pcexpress_mcp_server as server

GUEST_SUPERSTORE = {
    "id": "guest-cart",
    "status": "OPEN",
    "bannerId": "superstore",
    "customer": {"name": "Anonymous"},
}
# The carts list returns only these two fields per cart, so the rest is fetched.
LISTED_ZEHRS = {"id": "zehrs-cart", "modifiedTime": "2026-10-12T10:00:00Z"}
ZEHRS = {
    "id": "zehrs-cart",
    "status": "OPEN",
    "bannerId": "zehrs",
    "customer": {"name": "Real Name"},
    "modifiedTime": "2026-10-12T10:00:00Z",
}


class _Resp:
    def __init__(self, body, status=200):
        self._body = body
        self.status_code = status

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}", response=self)


class _Tokens:
    def get_access_token(self, force=False):
        return "token"


def _api(monkeypatch, routes, cart_id=None):
    """An API client whose HTTP layer is a dict of {(method, path suffix): body or status}."""
    api = server.PCExpressAPI(_Tokens(), cart_id, "0545", "zehrs")
    calls = []

    def fake_request(method, url, **kwargs):
        calls.append((method, url.removeprefix(api.BASE_URL), kwargs.get("params")))
        for (m, suffix), result in routes.items():
            if m == method and url.endswith(suffix):
                resp = result(url) if callable(result) else result
                if isinstance(resp, int):
                    resp = _Resp({}, resp)
                elif not isinstance(resp, _Resp):
                    resp = _Resp(resp)
                resp.raise_for_status()
                return resp
        raise AssertionError(f"unexpected request {method} {url}")

    monkeypatch.setattr(api, "_request", fake_request)
    return api, calls


def test_profile_cart_is_used_when_it_belongs_to_the_banner(monkeypatch):
    api, calls = _api(
        monkeypatch,
        {
            ("GET", "/ecommerce/v2/zehrs/customers"): {"cartId": "zehrs-cart", "customerId": "c1"},
            ("GET", "/carts/zehrs-cart"): ZEHRS,
        },
    )

    assert api.cart_id == "zehrs-cart"
    assert all("/carts?" not in c[1] and not c[1].endswith("/carts") for c in calls)


def test_guest_cart_on_another_banner_falls_back_to_the_carts_list(monkeypatch):
    api, calls = _api(
        monkeypatch,
        {
            ("GET", "/ecommerce/v2/zehrs/customers"): {"cartId": "guest-cart", "customerId": "c1"},
            ("GET", "/carts/guest-cart"): GUEST_SUPERSTORE,
            ("GET", "/customers/c1/carts"): {"carts": [LISTED_ZEHRS]},
            ("GET", "/carts/zehrs-cart"): ZEHRS,
        },
    )

    assert api.cart_id == "zehrs-cart"
    assert ("GET", "/customers/c1/carts", {"banner": "zehrs"}) in calls


def test_newest_matching_cart_wins(monkeypatch):
    older = {"id": "older", "modifiedTime": "2026-09-01T10:00:00Z"}
    api, _ = _api(
        monkeypatch,
        {
            ("GET", "/ecommerce/v2/zehrs/customers"): {"cartId": "guest-cart", "customerId": "c1"},
            ("GET", "/carts/guest-cart"): GUEST_SUPERSTORE,
            ("GET", "/customers/c1/carts"): {"carts": [older, LISTED_ZEHRS]},
            ("GET", "/carts/zehrs-cart"): ZEHRS,
            ("GET", "/carts/older"): {**ZEHRS, "id": "older"},
        },
    )

    assert api.cart_id == "zehrs-cart"


def test_no_matching_cart_raises_instead_of_using_the_wrong_one(monkeypatch):
    api, _ = _api(
        monkeypatch,
        {
            ("GET", "/ecommerce/v2/zehrs/customers"): {"cartId": "guest-cart", "customerId": "c1"},
            ("GET", "/carts/guest-cart"): GUEST_SUPERSTORE,
            ("GET", "/customers/c1/carts"): {"carts": [{"id": "guest-cart", "modifiedTime": "x"}]},
        },
    )

    with pytest.raises(ValueError, match="No open zehrs cart"):
        _ = api.cart_id


def test_400_on_a_wrong_banner_cart_rediscovers_and_retries(monkeypatch):
    posted = []

    def post(url):
        posted.append(url)
        return 400 if "guest-cart" in url else {"id": "zehrs-cart"}

    api, _ = _api(
        monkeypatch,
        {
            ("GET", "/ecommerce/v2/zehrs/customers"): {"cartId": "guest-cart", "customerId": "c1"},
            ("GET", "/carts/guest-cart"): GUEST_SUPERSTORE,
            ("GET", "/customers/c1/carts"): {"carts": [LISTED_ZEHRS]},
            ("GET", "/carts/zehrs-cart"): ZEHRS,
            ("POST", "?inventory=true"): post,
        },
        cart_id="guest-cart",
    )

    api.add_to_cart("20039684_EA", 1)

    assert [u.split("/carts/")[1] for u in posted] == [
        "guest-cart?inventory=true",
        "zehrs-cart?inventory=true",
    ]


def test_400_on_the_right_cart_is_not_swallowed(monkeypatch):
    """A bad product code 400s on a good cart. Rediscovery finds the same cart,
    so the original error has to come through, not a misleading 'cart expired'."""
    api, _ = _api(
        monkeypatch,
        {
            ("GET", "/ecommerce/v2/zehrs/customers"): {"cartId": "zehrs-cart", "customerId": "c1"},
            ("GET", "/carts/zehrs-cart"): ZEHRS,
            ("POST", "?inventory=true"): 400,
        },
        cart_id="zehrs-cart",
    )

    with pytest.raises(requests.HTTPError):
        api.add_to_cart("bad-code", 1)
