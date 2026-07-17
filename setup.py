#!/usr/bin/env python3
"""Friendly one-command setup for the PC Express MCP server.

Logs you in once (in a browser), then writes/prints ready-to-use config for however
you run the server: locally, in Docker, in Home Assistant, or in Kubernetes.

    python setup.py

The browser login runs ONLY here (on a machine with a display). The server itself
never runs a browser — it refreshes tokens with plain HTTPS.
"""
import getpass
import os
import sys

import pcid_config as cfg

BANNERS = ["zehrs", "loblaws", "nofrills", "superstore", "independent", "tandt"]


def ask(prompt, default=None):
    d = f" [{default}]" if default else ""
    v = input(f"{prompt}{d}: ").strip()
    return v or (default or "")


def choose(prompt, options):
    print(prompt)
    for i, (key, label) in enumerate(options, 1):
        print(f"  {i}) {label}")
    while True:
        raw = input(f"Choose 1-{len(options)}: ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1][0]


def do_login():
    method = choose(
        "\nHow do you want to sign in?",
        [("auto", "Automatic — enter email + password, I'll drive the browser"),
         ("manual", "Manual — I open the browser, you paste the redirect URL back")],
    )
    if method == "auto":
        try:
            from login_pcid_auto import login_auto
        except ImportError:
            sys.exit("Automatic login needs Playwright:\n  pip install -r requirements-auto.txt "
                     "&& python -m playwright install chromium")
        email = ask("PC id email")
        password = getpass.getpass("PC id password (hidden): ")
        print("\nOpening a browser to sign you in... (a window will appear)")
        tokens = login_auto(email, password, headed=True)
    else:
        from login_pcid import login_manual
        tokens = login_manual()
    rt = tokens.get("refresh_token")
    if not rt:
        sys.exit(f"Login did not return a refresh token: {list(tokens)}")
    return rt


def emit(target, env):
    def kv_lines():
        return "\n".join(f"{k}={v}" for k, v in env.items())

    if target in ("local", "docker"):
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
        with open(path, "w") as f:
            f.write(kv_lines() + "\n")
        os.chmod(path, 0o600)
        print(f"\n✅ Wrote {path} (gitignored, chmod 600).")
        if target == "local":
            print("\nRun the server:\n  python pcexpress_mcp_server.py")
            print("\nOr point your MCP client (Claude Desktop, etc.) at it with these env vars.")
        else:
            print("\nRun in Docker (mount a volume for the rotating token):")
            print("  docker run --rm -i --env-file .env \\")
            print("    -v pcx-state:/data -e PCEXPRESS_STATE_DIR=/data \\")
            print("    ghcr.io/you/pcexpress-mcp   # or your image")
    elif target == "homeassistant":
        print("\n✅ Add this to your Home Assistant MCP config:\n")
        print("mcp:\n  servers:\n    - name: pcexpress\n      command: python3")
        print("      args: [/config/pcexpress-mcp/pcexpress_mcp_server.py]")
        print("      env:")
        for k, v in env.items():
            print(f"        {k}: \"{v}\"")
    elif target == "k8s":
        print("\n✅ Kubernetes: the client secret is baked into the image, so the Secret only")
        print("   needs your personal values. Create it (then seal it if you use SealedSecrets):\n")
        print("apiVersion: v1\nkind: Secret\nmetadata:\n  name: pcexpress-mcp\ntype: Opaque\nstringData:")
        for k, v in env.items():
            if k == "PCEXPRESS_STATE_DIR":
                continue  # set on the Deployment, backed by the PVC
            print(f"  {k}: \"{v}\"")
        print("\n   Then deploy with the manifests in k8s/ (Deployment has replicas: 1 and a PVC")
        print("   mounted at PCEXPRESS_STATE_DIR — that PVC is what keeps the rotating token alive).")
        print("   See DEPLOYMENT.md for the full walk-through.")


def main():
    print("=" * 60)
    print("  PC Express MCP — setup")
    print("=" * 60)
    if not cfg.CLIENT_SECRET:
        sys.exit("No client secret available. Set PCEXPRESS_CLIENT_SECRET or bake one in pcid_config.py.")

    target = choose(
        "\nWhere will you RUN the server?",
        [("local", "Locally (this machine / a script / MCP client on your desktop)"),
         ("docker", "Docker container"),
         ("homeassistant", "Home Assistant"),
         ("k8s", "Kubernetes")],
    )

    refresh_token = do_login()

    banner = ask("\nStore banner (%s)" % "/".join(BANNERS), "zehrs").lower()
    if banner not in BANNERS:
        print(f"  (unknown banner '{banner}', keeping it anyway)")
    store_id = ask("Store ID (4-digit code for your preferred store)", "1234")
    # cart_id is auto-discovered from your profile at runtime, so we don't ask for it.
    cart_id = ""

    state_dir = {
        "local": "~/.pcexpress-mcp",
        "docker": "/data",
        "k8s": "/data",
        "homeassistant": "/config/pcexpress-mcp",
    }[target]
    # PCEXPRESS_CLIENT_SECRET is baked into the code, so it is not emitted here.
    env = {
        "PCEXPRESS_REFRESH_TOKEN": refresh_token,
        "PCEXPRESS_STATE_DIR": state_dir,
        "PCEXPRESS_BANNER": banner,
        "PCEXPRESS_STORE_ID": store_id,
    }
    if cart_id:
        env["PCEXPRESS_CART_ID"] = cart_id

    emit(target, env)
    print("\nDone. Your refresh token is personal — keep it out of git (already gitignored).")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled.")
