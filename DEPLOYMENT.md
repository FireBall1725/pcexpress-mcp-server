# Deploying the PC Express MCP server

## The model in one picture

There are two phases, and they run in different places.

1. **Login (once, needs a browser).** You sign in and get a refresh token. This is the only
   step that needs a real browser, because the PC id login page is behind Akamai bot
   detection and a scripted/headless login gets blocked.
2. **Runtime (forever, no browser).** The server trades the refresh token for a short-lived
   access token, calls the API, and repeats. Plain HTTPS, nothing bot-walled.

The one rule that shapes every deployment: **PC id refresh tokens are single-use.** Each
refresh returns a new refresh token and kills the old one. So the server writes the new
token to `PCEXPRESS_STATE_DIR` after every refresh, and reads it back from there next time.
The `PCEXPRESS_REFRESH_TOKEN` env var is only the seed for the first refresh.

Two consequences fall out of that:
- Wherever the server runs, `PCEXPRESS_STATE_DIR` must be **writable and persistent**.
- Only **one** instance may use a given token chain. Two would spend each other's tokens.

## Fastest path: the setup wizard

On any machine with a browser (usually your laptop):

```bash
pip install -r requirements.txt
pip install -r requirements-auto.txt && python -m playwright install chromium   # for automatic login
python setup.py
```

It signs you in, asks where you'll run the server, and prints/writes the exact config for
that target. You can also run the login helpers directly: `login_pcid_auto.py` (email +
password) or `login_pcid.py` (browser + paste).

## Local / MCP client (Claude Desktop, a script)

Everything is on one machine that has a browser, so this is the simple case.

1. `python setup.py`, choose "Locally". It writes `.env` with your values and
   `PCEXPRESS_STATE_DIR=~/.pcexpress-mcp`.
2. Point your MCP client at `pcexpress_mcp_server.py` with those env vars, or run it directly.

The rotated token lives in `~/.pcexpress-mcp` and survives restarts.

## Docker

The container is stateless except for the token, so give it a volume.

```bash
docker run --rm -i --env-file .env \
  -v pcx-state:/data -e PCEXPRESS_STATE_DIR=/data \
  ghcr.io/fireball1725/pcexpress-mcp
```

The named volume `pcx-state` is what keeps the rotating token across container restarts.
Drop the volume and you have to re-run `setup.py`.

## Home Assistant

Run the login on your laptop, then put the values in the HA MCP config. `setup.py` prints
the exact block when you choose "Home Assistant". Point `PCEXPRESS_STATE_DIR` at a path under
`/config` so it persists across add-on restarts.

## Kubernetes

Bootstrap and runtime are on different machines, and the state file needs a home.

1. **On your laptop:** `python setup.py`, choose "Kubernetes". It prints a `Secret` with your
   personal values (the client secret is baked into the image, so it is not in the Secret).
2. **Seal it** if you use SealedSecrets, and commit it.
3. **Apply `k8s/`:** a `Deployment` with `replicas: 1` and a small PVC mounted at
   `PCEXPRESS_STATE_DIR=/data`, a `PersistentVolumeClaim`, and a `Service`.

Why each piece:
- `replicas: 1` and `strategy: Recreate`: the single-use token means two pods would fight and
  both lose. One replica is also plenty for a personal grocery account.
- The PVC at `/data`: this holds the rotating refresh token. It is the load-bearing piece.
  If the PVC is wiped, the seed in the Secret is already spent, so you re-run `setup.py` and
  update the Secret. That is the only re-bootstrap trigger.
- The Secret going stale in git is expected: after the first refresh the PVC is the source of
  truth and the seed is never read again.

The server speaks stdio. To reach it over the network, wrap it with a stdio-to-SSE bridge
(supergateway), the same way as other MCP servers; `k8s/deployment.yaml` shows the command.

## When auth breaks

If the refresh chain is ever invalidated (revoked, or idle long enough that PC id expires the
refresh token), the tools return a clear "re-run login_pcid.py" error instead of failing
silently. Re-run the login on a browser machine and update the seed. Because the MCP is used
regularly, the chain normally stays alive on its own.
