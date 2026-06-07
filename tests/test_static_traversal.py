"""Regression tests for the SPA static-file path-traversal guard.

The catch-all frontend route previously did ``FRONTEND_DIR / full_path`` with no
containment check, so URL-encoded ``../`` (``%2e%2e`` / ``..%2f`` — decoded to
``..`` by the ASGI stack before reaching the handler) escaped the frontend dir
and exposed arbitrary process-readable files. ``_safe_static_file`` must keep all
served paths inside the base directory.
"""

from pathlib import Path

from app.main import _safe_static_file


def _make_tree(tmp_path: Path) -> Path:
    base = tmp_path / "dist"
    (base / "assets").mkdir(parents=True)
    (base / "index.html").write_text("INDEX")
    (base / "assets" / "app.js").write_text("APP")
    # Sensitive file OUTSIDE the served base — must never be reachable.
    (tmp_path / "secret.env").write_text("SECRET")
    return base


def test_serves_legitimate_file(tmp_path):
    base = _make_tree(tmp_path)
    assert _safe_static_file(base, "index.html") == (base / "index.html").resolve()
    assert _safe_static_file(base, "assets/app.js") == (base / "assets" / "app.js").resolve()


def test_missing_file_returns_none(tmp_path):
    base = _make_tree(tmp_path)
    assert _safe_static_file(base, "does/not/exist.js") is None


def test_directory_is_not_served(tmp_path):
    base = _make_tree(tmp_path)
    assert _safe_static_file(base, "assets") is None


def test_traversal_decoded_dotdot_is_blocked(tmp_path):
    # The ASGI server percent-decodes %2e%2e / ..%2f BEFORE routing, so the
    # handler receives literal ``..`` segments — exactly these payloads.
    base = _make_tree(tmp_path)
    for payload in ["../secret.env", "../../secret.env", "..//secret.env"]:
        assert _safe_static_file(base, payload) is None, payload


def test_absolute_path_is_blocked(tmp_path):
    base = _make_tree(tmp_path)
    assert _safe_static_file(base, str(tmp_path / "secret.env")) is None
    assert _safe_static_file(base, "/etc/passwd") is None
