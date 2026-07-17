"""Headless PCID access-token manager for the PC Express MCP server.

Given a refresh token (from login_pcid.py) plus the app client_id/secret, this mints
short-lived access tokens on demand against accounts.pcid.ca/oauth2/v1/token — plain
HTTPS, no browser, not bot-walled. Handles refresh-token rotation by persisting the
current refresh token to a writable state file so it survives restarts.
"""
import json
import logging
import os
import threading
import time

import requests

import pcid_config as cfg

logger = logging.getLogger("pcexpress-mcp.pcid")


class PcidAuthError(Exception):
    """Refresh failed unrecoverably; the user must re-run login_pcid.py."""


class TokenManager:
    def __init__(self, state_dir: str | None = None):
        state_dir = state_dir or os.getenv("PCEXPRESS_STATE_DIR", os.path.expanduser("~/.pcexpress-mcp"))
        os.makedirs(state_dir, exist_ok=True)
        self._state_path = os.path.join(state_dir, "pcid_token_state.json")
        self._lock = threading.Lock()
        self._session = requests.Session()
        self._access_token: str | None = None
        self._expires_at: float = 0.0
        self._refresh_token: str | None = None
        self._load()

    def _load(self):
        seed = os.getenv("PCEXPRESS_REFRESH_TOKEN")
        state = {}
        if os.path.exists(self._state_path):
            try:
                with open(self._state_path) as f:
                    state = json.load(f)
            except Exception as e:
                logger.warning("Could not read token state (%s); reseeding from env", e)
        # A refresh token in the persisted state is newer than the env seed (rotation).
        self._refresh_token = state.get("refresh_token") or seed
        self._access_token = state.get("access_token")
        self._expires_at = state.get("expires_at", 0.0)
        if not self._refresh_token:
            raise PcidAuthError(
                "No refresh token. Run login_pcid.py and set PCEXPRESS_REFRESH_TOKEN."
            )

    def _save(self):
        tmp = self._state_path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(
                {
                    "refresh_token": self._refresh_token,
                    "access_token": self._access_token,
                    "expires_at": self._expires_at,
                },
                f,
            )
        os.replace(tmp, self._state_path)
        try:
            os.chmod(self._state_path, 0o600)
        except OSError:
            pass

    def get_access_token(self, force: bool = False) -> str:
        with self._lock:
            if not force and self._access_token and time.time() < self._expires_at - 60:
                return self._access_token
            return self._refresh_now()

    def _refresh_now(self) -> str:
        if not cfg.CLIENT_SECRET:
            raise PcidAuthError("PCEXPRESS_CLIENT_SECRET is not set.")
        body = {
            "grant_type": "refresh_token",
            "client_id": cfg.CLIENT_ID,
            "client_secret": cfg.CLIENT_SECRET,
            "refresh_token": self._refresh_token,
        }
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "okhttp/4.12.0",
            **cfg.PCID_HEADERS,
        }
        r = self._session.post(cfg.TOKEN_ENDPOINT, data=body, headers=headers, timeout=30)
        if r.status_code != 200:
            # invalid_grant => refresh token expired/revoked; user must re-auth.
            raise PcidAuthError(
                f"Token refresh failed (HTTP {r.status_code}: {r.text[:200]}). "
                "Re-run login_pcid.py to get a new refresh token."
            )
        data = r.json()
        self._access_token = data["access_token"]
        self._expires_at = time.time() + int(data.get("expires_in", 3600))
        # IDCS rotates the refresh token on each use — persist the new one.
        if data.get("refresh_token"):
            self._refresh_token = data["refresh_token"]
        self._save()
        logger.info("Refreshed PCID access token (expires in %ss)", data.get("expires_in"))
        return self._access_token
