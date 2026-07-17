# Quick start

Five steps, and the only manual part is one browser login. After that the server keeps
itself authenticated with no further copying of tokens.

## 1. Install

```bash
pip install -r requirements.txt
# optional, for the automatic login below:
pip install -r requirements-auto.txt && python -m playwright install chromium
```

## 2. Log in once and write your config

```bash
python setup.py
```

The wizard signs you into PC id (automatically with your email and password, or manually in
a browser), asks where you'll run the server, and writes the config for that target. It
prints or writes a `PCEXPRESS_REFRESH_TOKEN`. That token is the only credential you handle,
and it's tied to your account, not committed anywhere.

You don't set a cart id or customer id. The server reads those from your profile at runtime.

## 3. Test it

```bash
python test_api.py
```

You should see your past orders and cart come back. If you see a message about re-running
the login, the refresh token was consumed or revoked; run `python login_pcid.py` again.

## 4. Run the server

```bash
python pcexpress_mcp_server.py
```

The server speaks MCP over stdio. It mints a fresh access token from your refresh token,
rotates the refresh token on each use, and stores the current one in `PCEXPRESS_STATE_DIR`.
An expired access token is refreshed automatically on the next call.

## 5. Connect a client (Claude Desktop shown)

Add this to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or
`%APPDATA%/Claude/claude_desktop_config.json` (Windows), then restart the app:

```json
{
  "mcpServers": {
    "pcexpress": {
      "command": "python3",
      "args": ["/path/to/pcexpress_mcp_server.py"],
      "env": {
        "PCEXPRESS_REFRESH_TOKEN": "your_refresh_token",
        "PCEXPRESS_STATE_DIR": "~/.pcexpress-mcp",
        "PCEXPRESS_BANNER": "zehrs",
        "PCEXPRESS_STORE_ID": "1234"
      }
    }
  }
}
```

`PCEXPRESS_CLIENT_SECRET` is baked into the code, so you don't set it unless you want to
override the default. For Docker, Home Assistant, and Kubernetes, see
[DEPLOYMENT.md](DEPLOYMENT.md).

## Example queries

Once a client is connected:

- Past orders: "What did I order from Zehrs last week?", "What was in order 531900018513724?"
- Product search: "Search for ice cream", "Find organic bananas"
- Cart: "What's in my cart?", "Add product 20143653_EA", "Remove 21657456_EA from my cart"
- Shopping: "I want milk, what did I buy last time?", "Add greek yogurt to my cart"

## Troubleshooting

**"No refresh token" at startup.** You haven't set `PCEXPRESS_REFRESH_TOKEN`, or the state
file is empty. Run `python setup.py` (or `login_pcid.py`) and set the value it prints.

**"Token refresh failed ... re-run login_pcid.py".** The refresh token was consumed or
revoked. Refresh tokens are single-use, so if two processes share one token chain, one of
them breaks. Run one instance, run the login again, and update the seed.

**HTTP 400 on cart calls.** The cart list needs a banner. The server sends it; if you're
calling the API by hand, add `?banner=zehrs`.

**"No module named 'mcp'".** Run `pip install -r requirements.txt` in the same environment
that runs the server.
