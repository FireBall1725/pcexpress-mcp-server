"""Token state and expiry, with no network.

The rotation behaviour here is the thing most likely to break in a way that is
painful to debug: refresh tokens are single-use, so persisting the newer one is
what stops the whole server locking itself out with `invalid_grant`.
"""

import json
import os
import time

import pytest

import pcid_token


def _mgr(tmp_path, monkeypatch, seed=None):
    if seed is None:
        monkeypatch.delenv("PCEXPRESS_REFRESH_TOKEN", raising=False)
    else:
        monkeypatch.setenv("PCEXPRESS_REFRESH_TOKEN", seed)
    return pcid_token.TokenManager(state_dir=str(tmp_path))


def test_persisted_refresh_token_wins_over_the_env_seed(tmp_path, monkeypatch):
    """The env seed is the bootstrap value. Once a refresh has rotated it, the
    persisted one is newer, and preferring the env var would replay a token
    that has already been spent."""
    state = tmp_path / "pcid_token_state.json"
    state.write_text(json.dumps({"refresh_token": "rotated", "expires_at": 0}))

    mgr = _mgr(tmp_path, monkeypatch, seed="original-from-env")

    assert mgr._refresh_token == "rotated"


def test_env_seed_is_used_when_there_is_no_state(tmp_path, monkeypatch):
    mgr = _mgr(tmp_path, monkeypatch, seed="original-from-env")

    assert mgr._refresh_token == "original-from-env"


def test_no_token_anywhere_is_a_clear_error(tmp_path, monkeypatch):
    with pytest.raises(pcid_token.PcidAuthError, match="No refresh token"):
        _mgr(tmp_path, monkeypatch)


def test_unreadable_state_falls_back_to_the_env_seed(tmp_path, monkeypatch):
    """A truncated or corrupt state file must not be fatal: the env seed can
    still bootstrap a refresh."""
    (tmp_path / "pcid_token_state.json").write_text("{not json")

    mgr = _mgr(tmp_path, monkeypatch, seed="original-from-env")

    assert mgr._refresh_token == "original-from-env"


def test_a_live_access_token_is_reused(tmp_path, monkeypatch):
    mgr = _mgr(tmp_path, monkeypatch, seed="seed")
    mgr._access_token = "still-good"
    mgr._expires_at = time.time() + 3600

    assert mgr.get_access_token() == "still-good"


def test_a_token_inside_the_refresh_window_is_not_reused(tmp_path, monkeypatch):
    """Expiry is treated as 60 seconds early, so a request that takes a moment
    to reach PC Express does not arrive with a token that expired in flight."""
    mgr = _mgr(tmp_path, monkeypatch, seed="seed")
    mgr._access_token = "about-to-expire"
    mgr._expires_at = time.time() + 30

    refreshed = []
    monkeypatch.setattr(mgr, "_refresh_now", lambda: refreshed.append(1) or "fresh")

    assert mgr.get_access_token() == "fresh"
    assert refreshed == [1]


def test_saved_state_round_trips_and_is_owner_only(tmp_path, monkeypatch):
    mgr = _mgr(tmp_path, monkeypatch, seed="seed")
    mgr._refresh_token = "rotated"
    mgr._access_token = "access"
    mgr._expires_at = 123.0
    mgr._save()

    written = json.loads((tmp_path / "pcid_token_state.json").read_text())
    assert written == {
        "refresh_token": "rotated",
        "access_token": "access",
        "expires_at": 123.0,
    }
    # The file holds a credential; it must not be world-readable.
    assert oct(os.stat(tmp_path / "pcid_token_state.json").st_mode)[-3:] == "600"
