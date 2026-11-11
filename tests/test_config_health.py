"""Unit tests for core.config_health operator warnings."""

import logging

import pytest

from core.config_health import get_config_warnings, log_startup_config_health

_ALL_VARS = (
    "MASTER_API_KEY",
    "DASHBOARD_SESSION_SECRET",
    "OAUTH_JWT_SECRET_KEY",
    "ENCRYPTION_KEY",
    "OAUTH_BASE_URL",
    "PUBLIC_URL",
    "DISABLE_MASTER_KEY_LOGIN",
)


@pytest.fixture
def clean_env(monkeypatch):
    """Remove every config var so each test sets only what it needs."""
    for var in _ALL_VARS:
        monkeypatch.delenv(var, raising=False)
    return monkeypatch


@pytest.mark.unit
def test_all_unset_reports_every_warning(clean_env):
    codes = {w["code"] for w in get_config_warnings()}
    assert codes == {
        "master_key_missing",
        "session_secret_ephemeral",
        "encryption_key_missing",
        "public_url_missing",
    }


@pytest.mark.unit
def test_fully_configured_reports_nothing(clean_env):
    clean_env.setenv("MASTER_API_KEY", "x" * 40)
    clean_env.setenv("DASHBOARD_SESSION_SECRET", "y" * 40)
    clean_env.setenv("ENCRYPTION_KEY", "z" * 44)
    clean_env.setenv("OAUTH_BASE_URL", "https://mcp.example.com")
    assert get_config_warnings() == []


@pytest.mark.unit
def test_empty_string_counts_as_unset(clean_env):
    clean_env.setenv("MASTER_API_KEY", "   ")  # whitespace only
    codes = {w["code"] for w in get_config_warnings()}
    assert "master_key_missing" in codes


@pytest.mark.unit
def test_disabled_master_key_login_suppresses_master_key_warning(clean_env):
    clean_env.setenv("DISABLE_MASTER_KEY_LOGIN", "true")
    codes = {w["code"] for w in get_config_warnings()}
    assert "master_key_missing" not in codes
    assert "session_secret_ephemeral" in codes
    assert "encryption_key_missing" in codes
    assert "public_url_missing" in codes


@pytest.mark.unit
def test_oauth_jwt_secret_satisfies_session_secret(clean_env):
    clean_env.setenv("OAUTH_JWT_SECRET_KEY", "fallback-secret")
    codes = {w["code"] for w in get_config_warnings()}
    assert "session_secret_ephemeral" not in codes


@pytest.mark.unit
def test_public_url_satisfies_oauth_base_url(clean_env):
    clean_env.setenv("PUBLIC_URL", "https://mcp.example.com")
    codes = {w["code"] for w in get_config_warnings()}
    assert "public_url_missing" not in codes


@pytest.mark.unit
def test_every_warning_has_bilingual_copy(clean_env):
    for w in get_config_warnings():
        for field in ("title_en", "title_fa", "detail_en", "detail_fa", "env", "severity"):
            assert w.get(field), f"{w['code']} missing {field}"
        assert w["severity"] in ("critical", "warning")


@pytest.mark.unit
def test_log_startup_is_noop_when_clean(clean_env, caplog):
    clean_env.setenv("MASTER_API_KEY", "x" * 40)
    clean_env.setenv("DASHBOARD_SESSION_SECRET", "y" * 40)
    clean_env.setenv("ENCRYPTION_KEY", "z" * 44)
    clean_env.setenv("OAUTH_BASE_URL", "https://mcp.example.com")
    with caplog.at_level(logging.WARNING):
        log_startup_config_health(logging.getLogger("test"))
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


@pytest.mark.unit
def test_log_startup_warns_when_misconfigured(clean_env, caplog):
    with caplog.at_level(logging.WARNING):
        log_startup_config_health(logging.getLogger("test"))
    warning_text = "\n".join(r.message for r in caplog.records if r.levelno >= logging.WARNING)
    assert "CONFIGURATION HEALTH" in warning_text
    assert "MASTER_API_KEY" in warning_text


@pytest.mark.unit
def test_multi_endpoint_app_registers_config_health_before_spa_catch_all():
    from pathlib import Path

    source = (Path(__file__).resolve().parent.parent / "server.py").read_text()
    route = 'Route("/api/dashboard/config-health", dashboard_config_health, methods=["GET"])'
    catch_all = 'routes.append(Route("/{path:path}", catch_all_404, methods=["GET"]))'

    assert "dashboard_config_health," in source
    assert route in source
    assert source.index(route) < source.index(catch_all)
