"""wordpress_diagnose_site / woocommerce_diagnose_store.

Unit tests for the HTML/plugin analysers plus end-to-end runs against a fake
WordPress + WooCommerce server (real HTTP), one healthy and one reproducing
the failures the checks were built from.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from aiohttp import web

from core.net_guard import allow_private_destinations
from plugins.wordpress.client import WordPressClient
from plugins.wordpress.handlers.diagnostics import (
    DiagnosticsHandler,
    StoreDiagnosticsHandler,
    analyze_homepage,
    plugin_conflicts,
)

pytestmark = pytest.mark.unit


def _by_id(findings: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {f["id"]: f for f in findings}


# ----------------------------------------------------------- HTML analysis


def test_single_title_indexable_https_is_clean():
    html = (
        "<html><head><title>Shop</title><meta name='robots' content='index, follow'>"
        "<link rel='stylesheet' href='https://cdn.example.com/a.css'></head>"
        "<body><svg><title>icon</title></svg></body></html>"
    )
    f = _by_id(analyze_homepage("https://shop.example.com", html, {}))
    assert f["duplicate_title"]["status"] == "ok"  # svg <title> in body is not counted
    assert f["search_visibility"]["status"] == "ok"
    assert f["mixed_content"]["status"] == "ok"
    assert "title_markup" not in f


def test_duplicate_title_noindex_and_mixed_content():
    html = (
        "<html><head><title>Home</title><title>Home - Shop</title>"
        "<meta name='robots' content='noindex, nofollow'>"
        "<script src='http://shop.example.com/x.js'></script></head><body></body></html>"
    )
    f = _by_id(analyze_homepage("https://shop.example.com", html, {}))
    assert f["duplicate_title"]["status"] == "warn"
    assert f["search_visibility"]["status"] == "warn"
    assert f["mixed_content"]["status"] == "warn"
    assert "http://shop.example.com/x.js" in f["mixed_content"]["detail"]


def test_markup_injected_into_title_is_flagged():
    html = (
        "<html><head><title>Shop <a href='https://trustseal.example/?id=1'>"
        "<img src='https://trustseal.example/logo.png'></a></title></head></html>"
    )
    f = _by_id(analyze_homepage("https://shop.example.com", html, {}))
    assert f["title_markup"]["status"] == "warn"


def test_x_robots_header_noindex():
    f = _by_id(
        analyze_homepage(
            "https://a.example", "<head><title>A</title></head>", {"X-Robots-Tag": "noindex"}
        )
    )
    assert f["search_visibility"]["status"] == "warn"


def test_plain_http_site_is_flagged():
    f = _by_id(analyze_homepage("http://a.example", "<head><title>A</title></head>", {}))
    assert f["https"]["status"] == "warn"


def test_plugin_conflicts():
    f = _by_id(
        plugin_conflicts(
            [
                "wordpress-seo/wp-seo.php",
                "seo-by-rank-math/rank-math.php",
                "wp-rocket/wp-rocket.php",
                "litespeed-cache/litespeed-cache.php",
            ]
        )
    )
    assert f["seo_plugin_conflict"]["status"] == "warn"
    assert "Rank Math" in f["seo_plugin_conflict"]["title"]
    assert f["page_cache_conflict"]["status"] == "warn"
    ok = _by_id(plugin_conflicts(["wordpress-seo/wp-seo.php", "woocommerce/woocommerce.php"]))
    assert ok["seo_plugin_conflict"]["status"] == "ok"
    assert ok["page_cache_conflict"]["status"] == "ok"


# ------------------------------------------------------- fake WordPress


def _site_app(state: dict[str, Any]) -> web.Application:
    async def rest_root(request: web.Request) -> web.Response:
        if state.get("basic_auth_wall"):
            return web.Response(status=401, headers={"WWW-Authenticate": 'Basic realm="staging"'})
        return web.json_response({"namespaces": ["wp/v2", "wc/v3", "airano-mcp/v1"]})

    async def users_me(request: web.Request) -> web.Response:
        if state.get("auth_stripped"):
            return web.json_response({"code": "rest_not_logged_in", "message": "x"}, status=401)
        return web.json_response({"id": 1, "roles": ["administrator"]})

    async def home(request: web.Request) -> web.Response:
        return web.Response(text=state["home_html"], content_type="text/html")

    async def companion_health(request: web.Request) -> web.Response:
        return web.json_response(
            {
                "wordpress": {"debug_mode": state.get("debug", False)},
                "plugins": {"active": [{"file": f} for f in state["plugins"]]},
            }
        )

    async def option(request: web.Request) -> web.Response:
        return web.json_response(
            {"option": "blog_public", "exists": True, "value": state.get("blog_public", "1")}
        )

    async def plugins(request: web.Request) -> web.Response:
        return web.json_response([{"plugin": f, "status": "active"} for f in state["plugins"]])

    async def site_health_test(request: web.Request) -> web.Response:
        test = request.match_info["test"]
        status = state.get("site_health", {}).get(test, "good")
        return web.json_response(
            {"label": f"<strong>{test}</strong>", "status": status, "description": "<p>d</p>"}
        )

    # --- WooCommerce -----------------------------------------------------
    async def wc_options(request: web.Request) -> web.Response:
        return web.json_response(
            {
                "woocommerce_coming_soon": state.get("coming_soon", "no"),
                "woocommerce_store_pages_only": state.get("store_pages_only", "no"),
            }
        )

    async def wc_system_status(request: web.Request) -> web.Response:
        assert "environment" in request.query.get("_fields", "")
        return web.json_response(state["system_status"])

    async def wc_gateways(request: web.Request) -> web.Response:
        return web.json_response(state.get("gateways", []))

    async def wc_zones(request: web.Request) -> web.Response:
        return web.json_response([{"id": 0, "name": "Rest of world"}, {"id": 1, "name": "Iran"}])

    async def wc_zone_methods(request: web.Request) -> web.Response:
        return web.json_response(state.get("methods", {}).get(request.match_info["zid"], []))

    app = web.Application()
    app.router.add_get("/wp-json/", rest_root)
    app.router.add_get("/wp-json/wp/v2/users/me", users_me)
    app.router.add_get("/", home)
    app.router.add_get("/wp-json/airano-mcp/v1/site-health", companion_health)
    app.router.add_get("/wp-json/airano-mcp/v1/admin/options/blog_public", option)
    app.router.add_get("/wp-json/wp/v2/plugins", plugins)
    app.router.add_get("/wp-json/wp-site-health/v1/tests/{test}", site_health_test)
    app.router.add_get("/wp-json/wc-admin/options", wc_options)
    app.router.add_get("/wp-json/wc/v3/system_status", wc_system_status)
    app.router.add_get("/wp-json/wc/v3/payment_gateways", wc_gateways)
    app.router.add_get("/wp-json/wc/v3/shipping/zones", wc_zones)
    app.router.add_get("/wp-json/wc/v3/shipping/zones/{zid}/methods", wc_zone_methods)
    return app


@pytest.fixture
async def fake_site():
    state: dict[str, Any] = {
        "home_html": "<html><head><title>Shop</title></head><body></body></html>",
        "plugins": ["wordpress-seo/wp-seo.php", "woocommerce/woocommerce.php"],
        "system_status": {"pages": [], "theme": {}, "security": {}, "environment": {}},
    }
    runner = web.AppRunner(_site_app(state))
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]  # type: ignore[union-attr]
    state["url"] = f"http://127.0.0.1:{port}"
    yield state
    await runner.cleanup()


async def _diagnose_site(url: str) -> dict[str, Any]:
    handler = DiagnosticsHandler(WordPressClient(url, "admin", "app pass word"))
    with allow_private_destinations(True):  # local fake site (admin/self-hosted)
        return json.loads(await handler.diagnose_site())


async def _diagnose_store(url: str) -> dict[str, Any]:
    handler = StoreDiagnosticsHandler(WordPressClient(url, "ck_x", "cs_y"))
    with allow_private_destinations(True):
        return json.loads(await handler.diagnose_store())


async def test_healthy_site_reports_ok(fake_site):
    report = await _diagnose_site(fake_site["url"])
    f = _by_id(report["findings"])
    # Only the "not https" warning is expected for a plain-http test server.
    assert f["https"]["status"] == "warn"
    for cid in (
        "rest_api",
        "authentication",
        "duplicate_title",
        "search_visibility",
        "debug_mode",
        "discourage_search_engines",
        "seo_plugin_conflict",
        "page_cache_conflict",
        "site_health:https-status",
    ):
        assert f[cid]["status"] == "ok", (cid, f[cid])
    assert report["summary"]["fail"] == 0


async def test_broken_site_reproduces_real_failures(fake_site):
    fake_site.update(
        basic_auth_wall=True,
        auth_stripped=True,
        debug=True,
        blog_public="0",
        plugins=[
            "wordpress-seo/wp-seo.php",
            "seo-by-rank-math/rank-math.php",
            "wp-rocket/wp-rocket.php",
            "litespeed-cache/litespeed-cache.php",
        ],
        home_html=(
            "<html><head><title>Home</title><title>Home | Shop</title>"
            "<meta name='robots' content='noindex'></head></html>"
        ),
        site_health={"loopback-requests": "critical", "page-cache": "recommended"},
    )
    report = await _diagnose_site(fake_site["url"])
    f = _by_id(report["findings"])
    assert report["summary"]["overall"] == "fail"
    assert f["rest_api"]["status"] == "fail" and "Basic" in f["rest_api"]["title"]
    assert f["authentication"]["status"] == "fail"
    assert "Authorization header" in f["authentication"]["detail"]
    assert f["debug_mode"]["status"] == "warn" and "WORDPRESS_DEBUG" in f["debug_mode"]["fix"]
    assert f["discourage_search_engines"]["status"] == "warn"
    assert f["duplicate_title"]["status"] == "warn"
    assert f["search_visibility"]["status"] == "warn"
    assert f["seo_plugin_conflict"]["status"] == "warn"
    assert f["page_cache_conflict"]["status"] == "warn"
    assert f["site_health:loopback-requests"]["status"] == "fail"
    assert f["site_health:page-cache"]["status"] == "warn"
    # findings are ordered worst-first
    ranks = [
        {"fail": 0, "warn": 1, "info": 2, "ok": 3, "skip": 4}[x["status"]]
        for x in report["findings"]
    ]
    assert ranks == sorted(ranks)


async def test_store_with_coming_soon_and_ignored_checkout_overrides(fake_site):
    fake_site.update(
        coming_soon="yes",
        store_pages_only="yes",
        gateways=[{"id": "bacs", "title": "Bank transfer", "enabled": False}],
        methods={"0": [], "1": [{"id": "flat_rate", "enabled": False}]},
        system_status={
            "environment": {"version": "10.3.0", "wp_version": "6.9", "wp_debug_mode": True},
            "security": {"secure_connection": False, "hide_errors": False},
            "theme": {
                "has_outdated_templates": True,
                "overrides": [
                    {
                        "file": "wp-content/themes/shop/woocommerce/checkout/form-checkout.php",
                        "version": "3.5.0",
                        "core_version": "9.4.0",
                    }
                ],
            },
            "pages": [
                {
                    "page_name": "Checkout",
                    "page_id": 8,
                    "page_set": True,
                    "page_exists": True,
                    "page_visible": True,
                    "shortcode_present": False,
                    "block_present": True,
                },
                {
                    "page_name": "Cart",
                    "page_id": 7,
                    "page_set": True,
                    "page_exists": True,
                    "page_visible": False,
                },
            ],
            "active_plugins": [
                {"plugin": "woocommerce/woocommerce.php"},
                {"plugin": "wordpress-seo/wp-seo.php"},
            ],
        },
    )
    report = await _diagnose_store(fake_site["url"])
    f = _by_id(report["findings"])
    assert f["coming_soon"]["status"] == "fail" and "store pages" in f["coming_soon"]["title"]
    assert f["checkout_type"]["status"] == "info" and "block" in f["checkout_type"]["title"]
    assert f["checkout_overrides_ignored"]["status"] == "warn"
    assert "form-checkout.php" in f["checkout_overrides_ignored"]["detail"]
    assert f["outdated_templates"]["status"] == "warn"
    assert f["cart_page"]["status"] == "fail"  # unpublished
    assert f["payment_gateways"]["status"] == "fail"
    assert f["shipping"]["status"] == "warn"
    assert f["errors_displayed"]["status"] == "warn"
    assert f["https"]["status"] == "warn"
    assert f["debug_mode"]["status"] == "warn"


async def test_healthy_store(fake_site):
    fake_site.update(
        gateways=[{"id": "zibal", "title": "Zibal", "enabled": True}],
        methods={"1": [{"id": "flat_rate", "enabled": True}]},
        system_status={
            "environment": {"version": "10.3.0", "wp_version": "6.9"},
            "security": {"secure_connection": True, "hide_errors": True},
            "theme": {"overrides": []},
            "pages": [
                {
                    "page_name": "Checkout",
                    "page_set": True,
                    "page_exists": True,
                    "page_visible": True,
                    "shortcode_present": True,
                }
            ],
            "active_plugins": [{"plugin": "woocommerce/woocommerce.php"}],
        },
    )
    report = await _diagnose_store(fake_site["url"])
    f = _by_id(report["findings"])
    assert report["summary"]["fail"] == 0 and report["summary"]["warn"] == 0
    assert f["coming_soon"]["status"] == "ok"
    assert "classic" in f["checkout_type"]["title"]
    assert f["payment_gateways"]["status"] == "ok"
    assert f["shipping"]["status"] == "ok"


async def test_diagnostics_respect_the_ssrf_guard(fake_site, monkeypatch):
    """Without an admin context, a private site address is refused, not probed."""
    monkeypatch.delenv("ALLOW_PRIVATE_SITE_URLS", raising=False)
    handler = DiagnosticsHandler(WordPressClient(fake_site["url"], "admin", "pw"))
    report = json.loads(await handler.diagnose_site(include_site_health_tests=False))
    statuses = {f["status"] for f in report["findings"]}
    assert statuses == {"fail"}
    assert all("SSRF" in f["title"] for f in report["findings"])


async def test_large_chunked_json_is_read_completely():
    """Regression (seen live): a single StreamReader.read(n) truncated big
    REST bodies, so a 21-plugin /wp/v2/plugins list failed to parse."""
    import asyncio

    from plugins.wordpress.handlers.diagnostics import _Http

    plugins = [{"plugin": f"p{i}/p{i}.php", "description": "x" * 400} for i in range(300)]
    payload = json.dumps(plugins).encode()

    async def handler(request: web.Request) -> web.StreamResponse:
        resp = web.StreamResponse(headers={"Content-Type": "application/json"})
        await resp.prepare(request)
        for i in range(0, len(payload), 4096):
            await resp.write(payload[i : i + 4096])
            await asyncio.sleep(0)
        await resp.write_eof()
        return resp

    app = web.Application()
    app.router.add_get("/wp-json/wp/v2/plugins", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]  # type: ignore[union-attr]
    try:
        with allow_private_destinations(True):
            status, body = await _Http(f"http://127.0.0.1:{port}", None).get_json(
                "/wp-json/wp/v2/plugins", auth=False
            )
    finally:
        await runner.cleanup()
    assert status == 200
    assert isinstance(body, list) and len(body) == 300
