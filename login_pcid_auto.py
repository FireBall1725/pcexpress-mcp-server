#!/usr/bin/env python3
"""Automated one-time PCID login for the PC Express MCP server.

Drives a real browser (Playwright) through the PC ID sign-in using credentials from
the environment, captures the authorization code, and prints the refresh token. This
saves users from the manual "copy the redirect URL" step in login_pcid.py.

The browser runs ONLY for this one-time login (ideally on your laptop). The MCP server
itself never runs a browser — it refreshes with plain HTTPS.

Usage:
    PCEXPRESS_CLIENT_SECRET=... PCEXPRESS_EMAIL=you@example.com PCEXPRESS_PASSWORD=... \
        python login_pcid_auto.py [--headed]

Notes:
  - The login page is behind Akamai bot detection. Testing showed headless Chromium is
    blocked (the page never loads) while a headed/real browser passes. So this defaults to
    headed. On a headless box, run it under a virtual display (xvfb-run) or use --headless
    to try anyway. Best practice: run this once on your laptop, then copy the refresh token
    to the server.
  - Accounts with 2FA cannot be automated — use login_pcid.py (manual) for those.
"""
import base64
import hashlib
import os
import secrets
import sys
import urllib.parse

import login_pcid as manual  # reuse build_authorize_url + exchange_code
import pcid_config as cfg


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _code_from_success_url(url: str) -> str:
    """PCID lands on .../login/success?redirectURL=<com.loblaw.pcx://...?code=...>."""
    q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    if "redirectURL" in q:
        inner = urllib.parse.unquote(q["redirectURL"][0])
        return manual.extract_code(inner, "")
    return manual.extract_code(url, "")


def login_auto(email: str, password: str, headed: bool = True) -> dict:
    """Drive a browser through the PCID login and return the token response dict."""
    if not (email and password and cfg.CLIENT_SECRET):
        raise SystemExit("Email, password and a client secret are required.")

    verifier = _b64url(secrets.token_bytes(64))
    challenge = _b64url(hashlib.sha256(verifier.encode()).digest())
    state = _b64url(secrets.token_bytes(24))
    nonce = _b64url(secrets.token_bytes(16))
    auth_url = manual.build_authorize_url(challenge, state, nonce)

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=not headed,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Linux; Android 13; Pixel 6) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36"
            ),
            viewport={"width": 412, "height": 915},
            is_mobile=True,
        )
        # light anti-detection
        context.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined});")
        try:
            from playwright_stealth import stealth_sync  # optional
            page = context.new_page(); stealth_sync(page)
        except Exception:
            page = context.new_page()

        page.goto(auth_url, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_selector("input[type='email'], input[type='text']", timeout=30000)
        page.fill("input[type='email'], input[type='text']", email)
        page.fill("input[type='password']", password)
        page.click("button:has-text('Sign In'), button[type='submit']")

        try:
            page.wait_for_url("**/login/success**", timeout=45000)
        except Exception:
            shot = os.path.abspath("pcid_login_failure.png")
            try:
                page.screenshot(path=shot)
            except Exception:
                pass
            body = ""
            try:
                body = page.inner_text("body")[:300]
            except Exception:
                pass
            browser.close()
            raise SystemExit(
                "Did not reach login success. Likely a wrong password, 2FA, or a bot block.\n"
                f"Current URL: {page.url}\nPage said: {body}\nScreenshot: {shot}\n"
                "For 2FA accounts, use login_pcid.py (manual)."
            )
        success_url = page.url
        browser.close()

    code = _code_from_success_url(success_url)
    return manual.exchange_code(code, verifier)


def run():
    email = os.getenv("PCEXPRESS_EMAIL")
    password = os.getenv("PCEXPRESS_PASSWORD")
    if not (email and password):
        raise SystemExit("Set PCEXPRESS_EMAIL and PCEXPRESS_PASSWORD.")
    # Headless is blocked by Akamai; default to headed. --headless forces headless (e.g. under xvfb).
    headed = not ("--headless" in sys.argv or os.getenv("PCEXPRESS_LOGIN_HEADLESS") == "1")
    tokens = login_auto(email, password, headed=headed)
    refresh = tokens.get("refresh_token")
    if not refresh:
        raise SystemExit(f"No refresh_token in response: {list(tokens)}")
    print("\n=== Success. Set these on the MCP server: ===\n")
    print(f"PCEXPRESS_CLIENT_SECRET={cfg.CLIENT_SECRET}")
    print(f"PCEXPRESS_REFRESH_TOKEN={refresh}")


if __name__ == "__main__":
    run()
