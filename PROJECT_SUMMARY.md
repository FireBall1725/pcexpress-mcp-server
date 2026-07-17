# Project summary

An MCP server that lets an LLM read your PC Express grocery orders, search products, and
manage your cart, so a Home Assistant voice assistant or Claude Desktop can shop for you. It
authenticates as the PC Express app and keeps itself signed in with no manual token copying.

## What it does

Six MCP tools, each backed by a `api.pcexpress.ca/pcx-bff` call: `search_past_orders`,
`get_order_items`, `search_products`, `get_product_details`, `add_to_cart`, `remove_from_cart`,
and `view_cart`. It reads data and edits the cart. It doesn't place orders.

The only thing you do by hand is one browser login. After that the server mints a fresh access
token every 3600 seconds from a stored refresh token, and it discovers your customer id and
cart id from your profile, so there's nothing else to configure per account.

## How the authentication was solved

The hard part was auth, and earlier versions of this project couldn't crack it: they replayed a
bearer token copied out of DevTools, which died within hours and had no refresh path. PC id
(Oracle IDCS) puts its login page behind Akamai bot detection, so a scripted login gets blocked.

The fix came from the PC Express Android app. Decompiling it showed the app uses an OAuth2
Authorization Code and PKCE flow with a confidential client (`client_id`
`ef9659ede6d44c7ab417f3485c11286c`), scope `openid grocery-prodgrocery-customer offline_access`,
and redirect `com.loblaw.pcx://pcx-android/login/appredirect`. The `offline_access` scope means
it gets a refresh token. The `client_secret` (`f470c525-...`) was captured by running the app in
an Android emulator through mitmproxy: the login page was passed through so Akamai stayed happy,
then a forced HTTP 401 on an API call made the app run a token refresh, which exposed the secret.

Two facts made a headless server possible. The token endpoint
`accounts.pcid.ca/oauth2/v1/token` isn't bot-walled, so plain Python refreshes there with no
browser. And a real browser passes the login page, so the one-time login runs in a browser
(automated with Playwright or manual) while everything after runs headless. Refresh tokens are
single-use and rotate, so the server persists the rotated token to `PCEXPRESS_STATE_DIR`.

Full detail is in [AUTH_NOTES.md](AUTH_NOTES.md).

## Endpoints used

| Endpoint | Method | Purpose |
| --- | --- | --- |
| `/ecommerce/v2/{banner}/customers` | GET | Profile; source of `cartId` and `customerId` |
| `/ecommerce/v2/{banner}/customers/historical-orders` | GET | Past orders |
| `/ecommerce/v2/{banner}/customers/historical-orders/{id}` | GET | Order detail |
| `/customers/{customerId}/carts?banner={banner}` | GET | Cart list |
| `/carts/{cartId}` | GET | View cart |
| `/carts/{cartId}?inventory=true` | POST | Add or update a line |
| `/products/{code}` | GET | Product detail |
| `accounts.pcid.ca/oauth2/v1/token` | POST | Refresh the access token |

See [API_REFERENCE.md](API_REFERENCE.md) for parameters and response shapes.

## Status

Verified end to end against a live account: the browser login (automatic and manual), the
headless refresh with rotation and persistence, cart auto-discovery, and a live orders call
returning real data. It runs locally, in Docker, in Home Assistant, and in Kubernetes; see
[DEPLOYMENT.md](DEPLOYMENT.md).

## Open items

- Store id is still a setting; `homeStore` in the profile means it could be auto-discovered too.
- Product search goes through the banner website's Next.js route, which sits behind Akamai; the
  app's `/products/search` route is a candidate for a token-authenticated replacement.
- Order placement, timeslots, and PC Optimum offers are visible in the API and left for later.

## Files

- `pcexpress_mcp_server.py`: the MCP server and `PCExpressAPI` client
- `pcid_token.py`: the `TokenManager` (refresh, rotation, persistence)
- `pcid_config.py`: the fixed app OAuth constants
- `login_pcid.py`, `login_pcid_auto.py`, `setup.py`: one-time login and config
- `Dockerfile`, `k8s/`: container and Kubernetes deployment
- `README.md`, `QUICKSTART.md`, `SETUP.md`, `DEPLOYMENT.md`, `AUTH_NOTES.md`, `API_REFERENCE.md`
