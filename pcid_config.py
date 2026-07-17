"""PCID (PC ID / Oracle IDCS) OAuth client configuration for PC Express.

These identify the official PC Express Android app's OAuth client. The client_id,
endpoints, scope and redirect_uri are fixed app constants.

The client_secret is a fixed value extracted from the app (a mobile "confidential"
client can't really keep a secret). It ships baked in so the tool works out of the box.
Resolution order lets you override it without editing code:
    1. PCEXPRESS_CLIENT_SECRET env var
    2. a client_secret.txt file next to this module, or ~/.pcexpress-mcp/client_secret
    3. the baked-in default below
If Loblaw ever rotates it, update the baked value (or drop a new one via 1 or 2).
"""
import os

CLIENT_ID = os.getenv("PCEXPRESS_CLIENT_ID", "ef9659ede6d44c7ab417f3485c11286c")

# Baked-in default app client secret (override via env or a local file; see above).
_BAKED_CLIENT_SECRET = "f470c525-c422-4070-832b-ae0a2490ea64"


def _resolve_secret() -> str | None:
    v = os.getenv("PCEXPRESS_CLIENT_SECRET")
    if v:
        return v
    here = os.path.dirname(os.path.abspath(__file__))
    for path in (os.path.join(here, "client_secret.txt"),
                 os.path.expanduser("~/.pcexpress-mcp/client_secret")):
        try:
            with open(path) as f:
                s = f.read().strip()
                if s:
                    return s
        except OSError:
            pass
    return _BAKED_CLIENT_SECRET or None


CLIENT_SECRET = _resolve_secret()

AUTHORIZE_ENDPOINT = "https://accounts.pcid.ca/oauth2/v1/authorize"
TOKEN_ENDPOINT = "https://accounts.pcid.ca/oauth2/v1/token"
REVOKE_ENDPOINT = "https://accounts.pcid.ca/oauth2/v1/revoke"

# IDCS concatenates the resource audience ("grocery-prod") onto the "grocery-customer"
# scope with no separating space. offline_access yields the refresh token.
SCOPE = "openid grocery-prodgrocery-customer offline_access"
REDIRECT_URI = "com.loblaw.pcx://pcx-android/login/appredirect"

# The app sends these on every PCID token/API call.
PCID_HEADERS = {
    "source": "ANDROID",
    "relying-party": "pcexpress-android",
}
