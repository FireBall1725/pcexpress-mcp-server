# PC Express auth notes (confirmed working)

How the PC Express MCP server authenticates, reverse-engineered from the official
Android app and verified end to end.

## Summary

PC ID (`accounts.pcid.ca`) is Oracle Identity Cloud (IDCS). The PC Express Android app
uses an OAuth2 Authorization Code + PKCE flow with a **confidential** client. The grocery
API (`api.pcexpress.ca/pcx-bff`) takes a PC ID access token plus a static web apikey.

The old problem (a scripted login getting blocked) came from Akamai Bot Manager on the
login page. We avoid it: the one-time login happens in a real browser (Akamai is fine with
that), and everything after (the token endpoint and the grocery API) is plain HTTPS that is
not bot-walled. So the server refreshes on its own with ordinary Python, no browser.

## Confirmed OAuth client (the Android app)

- client_id: `ef9659ede6d44c7ab417f3485c11286c`
- client_secret: confidential; captured once, set as `PCEXPRESS_CLIENT_SECRET` (see below)
- authorize: `https://accounts.pcid.ca/oauth2/v1/authorize`
- token: `https://accounts.pcid.ca/oauth2/v1/token`
- revoke: `https://accounts.pcid.ca/oauth2/v1/revoke`
- scope: `openid grocery-prodgrocery-customer offline_access`
  (IDCS concatenates the audience `grocery-prod` onto `grocery-customer` with no space)
- redirect_uri: `com.loblaw.pcx://pcx-android/login/appredirect`
- PKCE: S256. Extra headers on PCID calls: `source: ANDROID`, `relying-party: pcexpress-android`.

Note the app also has a separate **web** client (`48bb30478e1d4b0698f0324bb1fc3b4c`) used by
the websites; its secret lives server-side and is not usable headless. We use the app client.

## Token grants (verified)

Authorization code -> tokens (`POST /oauth2/v1/token`, form-encoded), fields exactly as the app sends:
`grant_type=authorization_code, code, client_id, client_secret, code_verifier` (no redirect_uri).

Refresh (`POST /oauth2/v1/token`): `grant_type=refresh_token, client_id, client_secret, refresh_token`.

- **Refresh tokens are single-use and rotate**: every refresh returns a new refresh token and
  invalidates the old one ("The token has already been consumed"). The server must persist the
  rotated token (it does, to `PCEXPRESS_STATE_DIR`). Only one refresher may run per token chain.
  If the state file is lost, the env seed is already spent -> re-run `login_pcid.py`.
- Access token lifetime: 3600s. The manager refreshes ~60s early and on any API 401.

## Grocery API (verified)

- Base: `https://api.pcexpress.ca/pcx-bff/api/v1` (not bot-walled; plain Python works)
- Header `x-apikey`: `C1xujSegT5j3ap3yexJjqhOfELwGKYvz` (static web apikey, not user-specific)
- `Authorization: Bearer <PC ID access token>`, `Business-User-Agent: PCXWEB`, `Site-Banner: <banner>`,
  `x-application-type: Web`, `x-loblaw-tenant-id: ONLINE_GROCERIES`, `baseSiteId: <banner>`, `is-helios-account: true`
- The user's customer id is the `sub` claim of the access token.
- Verified: `GET /ecommerce/v2/{banner}/customers/historical-orders` returns 200 with real orders
  using an app-client access token minted headlessly.

## App-profile fallback (not needed today)

The app itself uses host `rapid.pcexpress.ca`, `Business-User-Agent: PCXANDROID`, and apikey header
`x-lcl-apikey` (a runtime-provisioned value, not captured). The web profile above works, so this is
only a reserve if the web profile ever starts getting challenged.

## How the secret and first refresh token were obtained (one time)

Android emulator (API 33, Google APIs, no cert pinning) + mitmproxy with the app installed. The
browser login page is Akamai-walled, so mitmproxy passed `accounts.pcid.ca` through for the login,
then a forced 401 on an API call made the app run a token refresh, which we intercepted to read the
`client_secret`. Ordinary users never need the emulator: `login_pcid.py` gets a refresh token in a
real browser, and the secret is a fixed app constant supplied via env.
