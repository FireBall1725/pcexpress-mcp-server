# PC Express API reference

This documents the `api.pcexpress.ca` endpoints the MCP server uses, reconstructed from
the PC Express app and website traffic. There's no official public API, so treat this as
observed behaviour that Loblaw can change without notice. Endpoints marked "verified" were
captured returning HTTP 200 against a live account; endpoints marked "from app" were read
out of the decompiled app and haven't been exercised here yet.

## Base and auth

All calls go to `https://api.pcexpress.ca/pcx-bff/api/v1`. Every request carries:

| Header | Value |
| --- | --- |
| `Authorization` | `Bearer <PC id access token>` |
| `x-apikey` | `C1xujSegT5j3ap3yexJjqhOfELwGKYvz` (static web key, not user-specific) |
| `Business-User-Agent` | `PCXWEB` |
| `Site-Banner` / `baseSiteId` | your banner, for example `zehrs` |
| `x-application-type` | `Web` |
| `x-loblaw-tenant-id` | `ONLINE_GROCERIES` |
| `is-helios-account` | `true` |

The `{banner}` path segment is one of `zehrs`, `loblaws`, `nofrills`, `superstore`,
`independent`, `tandt`. `{customerId}` is the `sub` claim of the access token. `{cartId}`
comes from the customer profile (see below).

## Customer and identity

### GET /ecommerce/v2/{banner}/customers: verified
Your profile. This is how the server auto-discovers `cartId` and `customerId`, so you never
paste them. Optional query: `syncRippleMembership`.

Response fields include `id`, `cartId`, `customerId`, `firstName`, `lastName`, `postalCode`,
`language`, `pcOptimum`, `pcInsiderMembership`, `pcPlus`, `homeStore`, `is2SVEnabled`,
`wholesaleClubMembership`. `homeStore` also gives your preferred store, so store discovery is
possible from the same call.

### GET /ecommerce/v2/{banner}/customers/preferences: verified
Saved customer preferences. Response: `{ "customerPreferences": ... }`.

### POST /ecommerce/v2/customers/update-token: verified
The app posts its id token here after login. Request body: `{ "idToken": "<jwt>" }`. The MCP
server does not need this; the token flow is handled by the PC id endpoints instead.

## Orders

### GET /ecommerce/v2/{banner}/customers/historical-orders: verified
Past orders. Optional query: `cartId`. Response: `offlineOrdersCount`, `onlineOrdersCount`,
`orderHistory` (array of orders). Used by the `search_past_orders` tool.

### GET /ecommerce/v2/{banner}/customers/historical-orders/{orderId}: from app
A single past order with its line items. Used by the `get_order_items` tool.

## Cart

### GET /customers/{customerId}/carts?banner={banner}: verified
Lists your carts. The `banner` query param is required; without it the call returns HTTP 400.
Response: `carts`, `liveOrders`, `saveForLaterCart`.

### GET /carts/{cartId}: verified
The full cart. Optional query: `inventory=true`. Response includes `id`, `status`, `bannerId`,
`customer`, `orders`, `minCartValue`, `orderAggregations`. Used by the `view_cart` tool.

### GET /carts/{cartId}/heartbeat: verified
Keeps the cart session alive. Response: `{ "cartId", "lastModifiedTime" }`.

### POST /carts/{cartId}?inventory=true: from app / current server
Add or update a line. Body:
`{ "entries": { "<productCode>": { "quantity": N, "fulfillmentMethod": "pickup", "sellerId": "<storeId>" } } }`.
Set `quantity` to 0 to remove. Used by the `add_to_cart` and `remove_from_cart` tools.

## Products

### GET /products/{productCode}: from app / current server
Product detail by code, for example `20039684_EA`. Used by the `get_product_details` tool.

### POST /products/search: token-authenticated (current server)
Product search over the pcx-bff, used by the `search_products` tool. Request body:

```json
{"lang": "en", "term": "milk", "storeId": "0545", "banner": "zehrs", "cartId": "<cartId>", "pagination": {"from": 0, "size": 48}}
```

Required top-level fields: `lang`, `term`, `storeId`, `banner`. `storeId` must be top level
(inside `fulfillmentInfo` or as a `?storeId=` query param it is rejected); `cartId` is optional.
Products come back under `results` (array); each item has `code` (= `articleNumber`), `name`,
`brand`, `prices`, `dealPrice`, `stockStatus`, `packageSize`, `link`, `offerType`. Response
paging is under `pagination` (`pageNumber`, `pageSize`, `totalResults`).

An earlier build scraped the website Next.js route
(`/_next/data/{buildId}/en/search.json`); that broke when the site stopped exposing `buildId`
in page HTML, so search was moved to this token-authenticated pcx-bff endpoint.

### POST /products/type-ahead: token-authenticated
Search suggestions. Body `{"lang": "en", "term": "milk", "storeId": "0545", "banner": "zehrs"}`
(a POST, not a GET). Returns a bare JSON array of `{"suggestion": "..."}` objects. Not yet
wired to a tool.

## Fulfillment

### GET /pickup-locations/{storeId}?bannerId={banner}: verified
Store pickup details. Response includes `pickupLocationId`, `storeId`, `name`, `pickupType`,
`timeZone`, `minCartValue`, `geoFenceRadius`, `totalStorageUnit`.

## Notes for future expansion

- `homeStore` in the customer profile means `PCEXPRESS_STORE_ID` could be auto-discovered the
  same way `cartId` already is.
- Timeslot, checkout, and delivery-serviceability routes (`/api/v2/delivery/serviceability`,
  the timeslot endpoints) appear in the app and would enable order placement, which the MCP
  server intentionally does not do today.
