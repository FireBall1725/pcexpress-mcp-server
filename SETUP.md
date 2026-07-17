# Setup guide

This is the detailed version of the [quick start](QUICKSTART.md). It covers how the login
works, the two ways to do it, every environment variable, and Home Assistant wiring. For
Docker and Kubernetes see [DEPLOYMENT.md](DEPLOYMENT.md); for the endpoints themselves see
[API_REFERENCE.md](API_REFERENCE.md).

## How authentication works

The server authenticates as the PC Express app's OAuth client against PC id (Oracle IDCS).
You log in once in a browser and get a refresh token. From then on the server exchanges that
refresh token for a short-lived access token (3600 seconds), calls the API, and repeats. No
browser runs at server time, and you never copy an access token by hand.

One detail drives the whole design: PC id refresh tokens are single-use. Each refresh returns
a new refresh token and invalidates the old one. The server writes the new one to
`PCEXPRESS_STATE_DIR` after every refresh, so that directory must be writable and it must
persist. The [AUTH_NOTES.md](AUTH_NOTES.md) file explains the flow in full.

## Getting a refresh token

### Automatic (no copy-paste)

```bash
pip install -r requirements-auto.txt && python -m playwright install chromium
PCEXPRESS_EMAIL=you@example.com PCEXPRESS_PASSWORD='your-password' python login_pcid_auto.py
```

It drives a real browser through the login and prints your `PCEXPRESS_REFRESH_TOKEN`. It runs
a headed browser, because PC id's login page is behind Akamai bot detection and a headless
browser gets blocked. Run it on a machine with a display, or under `xvfb-run` on a headless
box. An account with two-factor sign-in can't be automated; use the manual method for those.

### Manual (paste one URL)

```bash
python login_pcid.py
```

It opens your browser to the PC id sign-in. After you log in, the browser tries to open a
`com.loblaw.pcx://...` link and shows an error. That's expected. Copy the full address from
the address bar and paste it back into the script. It prints your `PCEXPRESS_REFRESH_TOKEN`.

The `setup.py` wizard wraps both of these and also writes the config for your deployment
target, so most people should just run `python setup.py`.

## Environment variables

| Variable | Required | Notes |
| --- | --- | --- |
| `PCEXPRESS_REFRESH_TOKEN` | yes | From the login above. The seed for the first refresh; the server rotates it after that. |
| `PCEXPRESS_STATE_DIR` | recommended | Writable, persistent directory for the rotating token and cached access token. Defaults to `~/.pcexpress-mcp`. |
| `PCEXPRESS_BANNER` | no | `zehrs`, `loblaws`, `nofrills`, `superstore`, `independent`, `tandt`. Defaults to `zehrs`. |
| `PCEXPRESS_STORE_ID` | no | Four-digit store code. Defaults to `1234`. |
| `PCEXPRESS_CART_ID` | no | Auto-discovered from your profile; set it only to force a specific cart. |
| `PCEXPRESS_CLIENT_SECRET` | no | Baked into the code; set only to override the default app secret. |

You don't set a customer id or cart id. The server reads both from
`GET /ecommerce/v2/{banner}/customers` at runtime.

## Home Assistant

Run the login on a machine with a browser, then put the values in the HA MCP config. Point
`PCEXPRESS_STATE_DIR` at a path under `/config` so the rotating token survives add-on
restarts.

```yaml
mcp:
  servers:
    - name: pcexpress
      command: python3
      args: [/config/pcexpress-mcp/pcexpress_mcp_server.py]
      env:
        PCEXPRESS_REFRESH_TOKEN: "your_refresh_token"
        PCEXPRESS_STATE_DIR: "/config/pcexpress-mcp"
        PCEXPRESS_BANNER: "zehrs"
        PCEXPRESS_STORE_ID: "1234"
```

## Security notes

- Your refresh token grants access to your PC Express account. Keep it out of git; the
  `.gitignore` already excludes `.env`, the state directory, and the token files.
- The `client_id` and `client_secret` are the app's own credentials, shared by every install,
  not tied to your account. Only your refresh token is personal.
- Run one server instance per token chain. Two would each consume the other's rotated token
  and one would fail with `invalid_grant`.

## Troubleshooting

- **"No refresh token"**: set `PCEXPRESS_REFRESH_TOKEN`, or the state file is empty; run the
  login again.
- **"Token refresh failed ... re-run login_pcid.py"**: the refresh token was consumed or
  revoked. Run the login and update the seed.
- **The login page never loads (automatic method)**: that's Akamai blocking headless; use a
  headed browser (the default), or `xvfb-run`, or fall back to `login_pcid.py`.
- **HTTP 400 from a cart call by hand**: add `?banner=<your banner>`; the server does this for
  you.
