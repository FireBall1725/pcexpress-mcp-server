# Architecture

The server exposes a handful of MCP tools over stdio, translates each tool call into a
`api.pcexpress.ca/pcx-bff` request, and keeps itself authenticated against PC id without a
browser. This document describes how the pieces fit. For the login internals see
[AUTH_NOTES.md](AUTH_NOTES.md); for the endpoints see [API_REFERENCE.md](API_REFERENCE.md).

## Layers

```
MCP client (Claude Desktop, Home Assistant)
        │  MCP over stdio
        ▼
pcexpress_mcp_server.py
  ├── MCP handlers: list_tools(), call_tool()
  ├── PCExpressAPI: one method per tool, builds and sends the HTTP request
  └── TokenManager: mints/rotates PC id access tokens
        │  HTTPS
        ▼
api.pcexpress.ca/pcx-bff/api/v1     accounts.pcid.ca/oauth2/v1
  (grocery data)                    (token endpoint)
```

## Components

**pcexpress_mcp_server.py** implements the MCP protocol, registers the tools, routes each
call to a `PCExpressAPI` method, and handles errors. It loads configuration from the
environment (and a `.env` file if present).

**PCExpressAPI** builds each request, injects the auth and banner headers, and parses the
response. Its `_request()` wrapper uses connect/read timeouts, retries once on HTTP 401 after
forcing a token refresh, and retries once on HTTP 429. It holds the banner, the store id, and
a TTL-cached cart id resolved via `GET /customers/{id}/carts?banner=` (OPEN cart for the
configured store — not a blind `customer.cartId`, which can point at another banner). Live
orders lock cart mutations. Optional product-search responses are cached under
`PCEXPRESS_STATE_DIR/search-cache`.

**pcx_shape.py** projects raw BFF JSON into slim agent-facing payloads (search hits, cart
entries, order lines, product details) so MCP tool results stay small in the LLM context.

**TokenManager** (`pcid_token.py`) owns authentication. It reads the refresh token from the
state file, or from `PCEXPRESS_REFRESH_TOKEN` on first run, exchanges it for an access token
at `accounts.pcid.ca/oauth2/v1/token`, caches that token until 60 seconds before it expires,
and writes the rotated refresh token back to `PCEXPRESS_STATE_DIR`. If the exchange fails with
`invalid_grant`, it raises a `PcidAuthError` that tells the user to run the login again.

**pcid_config.py** holds the fixed app OAuth constants: `client_id`, the baked `client_secret`
(overridable by env or a local file), the endpoints, the scope, and the redirect uri.

**login_pcid.py / login_pcid_auto.py / setup.py** run the one-time browser login that produces
the first refresh token. They're used once, on a machine with a display, and never at server
runtime.

## Authentication flow

There are two phases, and they run in different places.

The login happens once, in a real browser. The user signs into PC id, the browser is
redirected to `com.loblaw.pcx://pcx-android/login/appredirect?code=...`, and the helper
exchanges that code (with the PKCE verifier and the client secret) for a refresh token. A real
browser is required here because the PC id login page is behind Akamai bot detection, which
blocks a scripted or headless login.

Everything after runs headless. The `TokenManager` posts the refresh token to the token
endpoint and gets back an access token good for 3600 seconds. That endpoint isn't bot-walled,
so ordinary Python reaches it. Because PC id refresh tokens are single-use, each refresh
returns a new refresh token and kills the old one; the manager persists the new one so a
restart continues the chain. Only one instance may run per chain.

## Tools

Eight tools. Handlers are async and run blocking BFF I/O via `asyncio.to_thread`; results are
compact JSON (no indent) and field-projected via `pcx_shape`:

- `search_past_orders` -> `GET /ecommerce/v2/{banner}/customers/historical-orders`
- `get_order_items` -> `GET /ecommerce/v2/{banner}/customers/historical-orders/{orderId}`
- `search_products` -> `POST /products/search` (default limit 12; optional file cache)
- `get_product_details` -> `GET /products/{productCode}`
- `add_to_cart` / `add_to_cart_batch` / `remove_from_cart` -> `POST /carts/{cartId}?inventory=true`
  (batch packs multiple `entries` into one POST; mutate tools return a slim cart summary)
- `view_cart` -> `GET /carts/{cartId}?inventory=true` (slim entries + subTotal)

## Configuration

The server reads these environment variables (also loadable from `.env`):
`PCEXPRESS_REFRESH_TOKEN`, `PCEXPRESS_STATE_DIR`, `PCEXPRESS_BANNER`, `PCEXPRESS_STORE_ID`,
`PCEXPRESS_CART_ID` (optional, safely auto-discovered), `PCEXPRESS_CART_TTL_SEC`,
`PCEXPRESS_SEARCH_CACHE`, `PCEXPRESS_SEARCH_CACHE_TTL_SEC`, and `PCEXPRESS_CLIENT_SECRET` (optional,
baked default). The static web apikey `C1xujSegT5j3ap3yexJjqhOfELwGKYvz` and the base url are
constants in the code. See [SETUP.md](SETUP.md) for the full table.

## Error handling

- HTTP 401: the `_request()` wrapper forces one token refresh and retries. If it still fails,
  the error propagates.
- Token refresh failure (`invalid_grant`): a `PcidAuthError` asks the user to re-run the login.
- HTTP 400 on a cart list: the call needs `?banner=`; the server always sends it.
- Other 4xx/5xx and network errors: raised as the underlying `requests` exception, returned to
  the MCP client as an error string.

## Security

Only the refresh token is personal, and it never enters git; the `.gitignore` excludes `.env`,
the state directory, and the token files, and the state file is written mode 600. The
`client_id` and `client_secret` are the app's own shared credentials, not tied to any account.
No password is stored: the automatic login reads email and password from the environment for
the one-time browser step and keeps nothing.

## Limits and future work

The server serves one account per token chain and does one store at a time. It reads data and
edits the cart; it does not place orders. `homeStore` in the customer profile means the store
id could be auto-discovered the same way the cart id already is. Redis / multi-instance shared
caches remain optional for multi-replica deployments.
Redis caching, async I/O, and connection pooling are open if throughput ever matters, which for
a personal grocery account it doesn't.
