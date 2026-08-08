"""Where the OAuth client secret comes from, and in what order.

Getting the precedence wrong is a bad failure: a stale baked-in secret silently
beating an env var means every token refresh fails with an opaque 401, and the
obvious fix (setting the env var) appears not to work.
"""

import importlib

import pcid_config


def _resolve(monkeypatch, env=None, files=()):
    """Re-resolve with a controlled environment. The module reads files
    relative to its own directory, so anything not explicitly created must be
    made to look absent."""
    if env is None:
        monkeypatch.delenv("PCEXPRESS_CLIENT_SECRET", raising=False)
    else:
        monkeypatch.setenv("PCEXPRESS_CLIENT_SECRET", env)

    real_open = open

    def fake_open(path, *a, **kw):
        for candidate, contents in files:
            if str(path).endswith(candidate):
                import io

                return io.StringIO(contents)
        raise OSError("not found")

    monkeypatch.setattr("builtins.open", fake_open)
    try:
        return pcid_config._resolve_secret()
    finally:
        monkeypatch.setattr("builtins.open", real_open)


def test_env_var_wins(monkeypatch):
    assert _resolve(monkeypatch, env="from-env") == "from-env"


def test_a_file_is_used_when_the_env_var_is_absent(monkeypatch):
    got = _resolve(monkeypatch, files=[("client_secret.txt", "from-file\n")])
    assert got == "from-file"


def test_a_blank_file_does_not_win(monkeypatch):
    """An empty file is someone's half-finished setup, not an intent to
    authenticate with the empty string."""
    got = _resolve(monkeypatch, files=[("client_secret.txt", "   \n")])
    assert got == pcid_config._BAKED_CLIENT_SECRET


def test_the_baked_secret_is_the_last_resort(monkeypatch):
    assert _resolve(monkeypatch) == pcid_config._BAKED_CLIENT_SECRET


def test_the_module_still_imports_cleanly():
    """The module runs resolution at import time; a change that raises there
    takes the whole server down at startup rather than at first use."""
    importlib.reload(pcid_config)
    assert pcid_config.CLIENT_ID
