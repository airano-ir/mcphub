"""Read-only health diagnostics for WordPress sites and WooCommerce stores.

Each check targets a failure we kept finding by hand on real sites and turns
it into a finding with a concrete fix:

* REST API behind HTTP Basic auth (staging) — Application Passwords use the
  same ``Authorization`` header, so every authenticated call fails.
* ``Authorization`` header stripped by the web server (Apache/CGI) —
  credentials are valid but WordPress answers ``rest_not_logged_in``.
* ``WP_DEBUG`` on in production — on the official WordPress Docker image,
  ``WORDPRESS_DEBUG='false'`` turns debug **on** (``!!getenv()``).
* "Discourage search engines" left on after launch (``noindex``).
* Two ``<title>`` tags (block theme + SEO plugin) and markup leaking into the
  title (a plugin/theme option injecting code into the site title).
* Several SEO or page-cache plugins active at once.
* Mixed content on an HTTPS site.
* WooCommerce: Coming-soon mode hiding the store, block vs classic checkout
  (theme overrides of ``form-checkout.php`` never run with the Checkout
  block), no enabled payment gateway, no shipping method, outdated template
  overrides, PHP errors displayed to visitors.

Everything is read-only: anonymous GETs of public pages plus authenticated
GETs of REST endpoints. Requests go through :mod:`core.net_guard`, so the
SSRF policy for user-supplied sites applies here too.
"""

from __future__ import annotations

import asyncio
import json
import re
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlparse

import aiohttp

from core import net_guard

_TIMEOUT = aiohttp.ClientTimeout(total=20, connect=8)
_MAX_HTML_BYTES = 2 * 1024 * 1024
_STATUS_RANK = {"fail": 0, "warn": 1, "info": 2, "ok": 3, "skip": 4}

# Plugin directory slugs (the part before "/" in the plugin file path).
SEO_PLUGINS = {
    "wordpress-seo": "Yoast SEO",
    "seo-by-rank-math": "Rank Math",
    "all-in-one-seo-pack": "All in One SEO",
    "wp-seopress": "SEOPress",
    "autodescription": "The SEO Framework",
    "slim-seo": "Slim SEO",
    "squirrly-seo": "Squirrly SEO",
}
PAGE_CACHE_PLUGINS = {
    "wp-rocket": "WP Rocket",
    "w3-total-cache": "W3 Total Cache",
    "wp-super-cache": "WP Super Cache",
    "litespeed-cache": "LiteSpeed Cache",
    "wp-fastest-cache": "WP Fastest Cache",
    "sg-cachepress": "SiteGround Speed Optimizer",
    "breeze": "Breeze",
    "hummingbird-performance": "Hummingbird",
    "cache-enabler": "Cache Enabler",
    "comet-cache": "Comet Cache",
    "swift-performance-lite": "Swift Performance",
}
SITE_HEALTH_TESTS = (
    "https-status",
    "authorization-header",
    "loopback-requests",
    "background-updates",
    "dotorg-communication",
    "page-cache",
)


# --------------------------------------------------------------- specs


def get_tool_specifications() -> list[dict[str, Any]]:
    """WordPress plugin: ``wordpress_diagnose_site``."""
    return [
        {
            "name": "diagnose_site",
            "method_name": "diagnose_site",
            "description": (
                "Run a read-only health diagnosis of the WordPress site and return "
                "prioritised findings (fail / warn / info / ok / skip), each with a "
                "concrete fix. Checks: REST API reachability (incl. HTTP Basic auth "
                "walls), Application-Password authentication (incl. a stripped "
                "Authorization header), WP_DEBUG in production, search-engine "
                "noindex, duplicate <title> tags and markup in the title, "
                "conflicting SEO / page-cache plugins, mixed content, and "
                "WordPress core Site Health tests. Changes nothing on the site."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "include_site_health_tests": {
                        "type": "boolean",
                        "description": (
                            "Also run WordPress core Site Health REST tests "
                            "(slower: loopback and page-cache checks). Default true."
                        ),
                        "default": True,
                    },
                },
            },
            "scope": "read",
        }
    ]


def get_wc_tool_specifications() -> list[dict[str, Any]]:
    """WooCommerce plugin: ``woocommerce_diagnose_store``."""
    return [
        {
            "name": "diagnose_store",
            "method_name": "diagnose_store",
            "description": (
                "Run a read-only health diagnosis of the WooCommerce store and "
                "return prioritised findings, each with a concrete fix. Checks: "
                "Coming-soon mode, cart/checkout pages (block vs classic, missing "
                "or unpublished), theme overrides that the Checkout block ignores, "
                "outdated template overrides, enabled payment gateways, shipping "
                "methods, HTTPS, PHP errors shown to visitors, WP_DEBUG, and "
                "conflicting SEO / page-cache plugins. Changes nothing on the store."
            ),
            "schema": {"type": "object", "properties": {}},
            "scope": "read",
        }
    ]


# --------------------------------------------------------------- helpers


def _finding(cid: str, status: str, title: str, detail: str = "", fix: str = "") -> dict[str, str]:
    out = {"id": cid, "status": status, "title": title}
    if detail:
        out["detail"] = detail
    if fix:
        out["fix"] = fix
    return out


def _report(site: str, findings: list[dict[str, str]]) -> str:
    findings = sorted(findings, key=lambda f: _STATUS_RANK.get(f["status"], 9))
    counts = {s: sum(1 for f in findings if f["status"] == s) for s in _STATUS_RANK}
    overall = next((s for s in ("fail", "warn") if counts[s]), "ok")
    return json.dumps(
        {"site": site, "summary": {"overall": overall, **counts}, "findings": findings},
        indent=2,
        ensure_ascii=False,
    )


def _strip_html(text: str, limit: int = 300) -> str:
    plain = re.sub(r"<[^>]+>", " ", text or "")
    plain = re.sub(r"\s+", " ", plain).strip()
    return plain[:limit]


def _slug(plugin_file: str) -> str:
    return (plugin_file or "").split("/", 1)[0].strip().lower()


def plugin_conflicts(plugin_files: list[str]) -> list[dict[str, str]]:
    """Flag several SEO or page-cache plugins active at the same time."""
    slugs = {_slug(p) for p in plugin_files}
    findings = []
    for cid, group, label, why in (
        (
            "seo_plugin_conflict",
            SEO_PLUGINS,
            "SEO",
            "Each one prints its own <title>, meta description, canonical and "
            "schema, so search engines get duplicated or contradictory tags.",
        ),
        (
            "page_cache_conflict",
            PAGE_CACHE_PLUGINS,
            "page-cache",
            "Stacked page caches serve stale pages and make purges unreliable.",
        ),
    ):
        active = sorted(name for slug, name in group.items() if slug in slugs)
        if len(active) > 1:
            findings.append(
                _finding(
                    cid,
                    "warn",
                    f"{len(active)} {label} plugins are active: {', '.join(active)}",
                    why,
                    f"Keep one {label} plugin and deactivate the others.",
                )
            )
        else:
            findings.append(_finding(cid, "ok", f"No conflicting {label} plugins"))
    return findings


class _HeadScanner(HTMLParser):
    """Collect <head> signals: titles, robots meta, insecure resources."""

    _RESOURCE_ATTRS = {
        "script": "src",
        "img": "src",
        "iframe": "src",
        "source": "src",
        "video": "src",
        "audio": "src",
        "link": "href",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_head = False
        self.svg_depth = 0
        self.head_titles: list[str] = []
        self.title_has_markup = False
        self.robots: list[str] = []
        self.http_resources: list[str] = []
        self._in_title = False
        self._title_buf: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k.lower(): (v or "") for k, v in attrs}
        if self._in_title and tag != "title":
            self.title_has_markup = True
        if tag == "head":
            self.in_head = True
        elif tag == "body":
            self.in_head = False
        elif tag == "svg":
            self.svg_depth += 1
        elif tag == "title" and self.in_head and not self.svg_depth:
            self._in_title = True
            self._title_buf = []
        elif tag == "meta" and a.get("name", "").lower() in ("robots", "googlebot"):
            self.robots.append(a.get("content", "").lower())
        attr = self._RESOURCE_ATTRS.get(tag)
        if attr:
            value = a.get(attr, "")
            rel = a.get("rel", "").lower()
            if tag == "link" and not any(
                r in rel for r in ("stylesheet", "preload", "modulepreload", "icon")
            ):
                return
            if value.startswith("http://"):
                self.http_resources.append(value)

    def handle_endtag(self, tag: str) -> None:
        if tag == "head":
            self.in_head = False
        elif tag == "svg":
            self.svg_depth = max(0, self.svg_depth - 1)
        elif tag == "title" and self._in_title:
            self.head_titles.append("".join(self._title_buf).strip())
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._title_buf.append(data)


def analyze_homepage(url: str, html: str, headers: dict[str, str]) -> list[dict[str, str]]:
    """Front-end checks on the public home page HTML (no credentials)."""
    scanner = _HeadScanner()
    try:
        scanner.feed(html)
        scanner.close()
    except Exception:  # noqa: BLE001 - malformed HTML must not break the report
        pass
    findings: list[dict[str, str]] = []

    titles = scanner.head_titles
    if len(titles) > 1:
        findings.append(
            _finding(
                "duplicate_title",
                "warn",
                f"The home page has {len(titles)} <title> tags",
                "Titles: " + " | ".join(t[:80] for t in titles),
                "Usually a block theme and an SEO plugin both print a title. Let the "
                "SEO plugin own it (disable the theme's title output) so only one remains.",
            )
        )
    elif not titles:
        findings.append(
            _finding(
                "duplicate_title",
                "warn",
                "The home page has no <title> in <head>",
                fix="Make sure the theme supports 'title-tag' or the SEO plugin is configured.",
            )
        )
    else:
        findings.append(_finding("duplicate_title", "ok", "Exactly one <title> tag"))

    joined = " ".join(titles)
    if scanner.title_has_markup or re.search(r"<|&lt;|https?://", joined):
        findings.append(
            _finding(
                "title_markup",
                "warn",
                "The page title contains markup or a URL",
                "Title: " + joined[:160],
                "A plugin or theme option is injecting code (e.g. a trust-seal or "
                "tracking snippet) into the site title. Move that code to a widget, "
                "footer or header-scripts setting and keep the title plain text.",
            )
        )

    x_robots = (headers.get("X-Robots-Tag") or headers.get("x-robots-tag") or "").lower()
    if any("noindex" in r for r in scanner.robots) or "noindex" in x_robots:
        findings.append(
            _finding(
                "search_visibility",
                "warn",
                "The home page tells search engines not to index it (noindex)",
                f"robots meta: {scanner.robots or '-'}; X-Robots-Tag: {x_robots or '-'}",
                "If the site is live, untick Settings → Reading → 'Discourage search "
                "engines' (or the SEO plugin's noindex setting). Ignore if this is an "
                "intentional staging or pilot site.",
            )
        )
    else:
        findings.append(_finding("search_visibility", "ok", "Home page is indexable"))

    if urlparse(url).scheme == "https":
        insecure = sorted(set(scanner.http_resources))
        if insecure:
            findings.append(
                _finding(
                    "mixed_content",
                    "warn",
                    f"{len(insecure)} resource(s) load over plain http:// on an https page",
                    "Examples: " + ", ".join(insecure[:5]),
                    "Browsers block or warn on these. Update the URLs to https:// "
                    "(search-replace the database or fix the theme/plugin setting).",
                )
            )
        else:
            findings.append(_finding("mixed_content", "ok", "No mixed content on the home page"))
    else:
        findings.append(
            _finding(
                "https",
                "warn",
                "The site URL is not https",
                fix="Serve the site over HTTPS and update the WordPress and Site URLs.",
            )
        )
    return findings


class _Http:
    """Minimal raw HTTP helper (exact status/headers, no retries)."""

    def __init__(self, site_url: str, auth_header: str | None) -> None:
        self.site_url = site_url.rstrip("/")
        self.auth_header = auth_header

    async def get(
        self, path_or_url: str, *, auth: bool, params: dict[str, Any] | None = None
    ) -> tuple[int, dict[str, str], str]:
        url = path_or_url if "://" in path_or_url else f"{self.site_url}{path_or_url}"
        headers = {"User-Agent": "MCPHub-Diagnostics/1.0", "Accept": "*/*"}
        if auth and self.auth_header:
            headers["Authorization"] = self.auth_header
        async with net_guard.client_session(timeout=_TIMEOUT) as s:
            async with s.get(url, headers=headers, params=params) as resp:
                # StreamReader.read(n) returns as soon as *some* data is
                # buffered, so a single read truncates large bodies (seen live:
                # the /wp/v2/plugins list). Read chunks until EOF or the cap.
                buf = bytearray()
                async for chunk in resp.content.iter_chunked(64 * 1024):
                    buf.extend(chunk)
                    if len(buf) >= _MAX_HTML_BYTES:
                        break
                text = bytes(buf[:_MAX_HTML_BYTES]).decode(
                    resp.charset or "utf-8", errors="replace"
                )
                return resp.status, dict(resp.headers), text

    async def get_json(
        self, path: str, *, auth: bool = True, params: dict[str, Any] | None = None
    ) -> tuple[int, Any]:
        status, _, text = await self.get(path, auth=auth, params=params)
        try:
            return status, json.loads(text)
        except json.JSONDecodeError:
            return status, None


def _error_code(body: Any) -> str:
    return str(body.get("code", "")) if isinstance(body, dict) else ""


async def _guarded(check, *args) -> list[dict[str, str]]:
    """Run one check; a crash becomes a 'skip' finding instead of an error."""
    try:
        result = await check(*args)
        return result if isinstance(result, list) else [result]
    except net_guard.SSRFBlockedError as e:
        return [
            _finding(check.__name__.strip("_"), "fail", "Request blocked by SSRF guard", str(e))
        ]
    except Exception as e:  # noqa: BLE001
        return [
            _finding(
                check.__name__.strip("_"),
                "skip",
                "Check could not run",
                f"{type(e).__name__}: {str(e)[:200]}",
            )
        ]


# --------------------------------------------------------------- WordPress


class DiagnosticsHandler:
    """``wordpress_diagnose_site``."""

    def __init__(self, client: Any) -> None:
        self.client = client
        self.http = _Http(client.site_url, getattr(client, "auth_header", None))

    async def diagnose_site(self, include_site_health_tests: bool = True) -> str:
        checks = [
            _guarded(self._rest_api),
            _guarded(self._authentication),
            _guarded(self._homepage),
            _guarded(self._companion_signals),
            _guarded(self._plugins),
        ]
        if include_site_health_tests:
            checks.append(_guarded(self._site_health_tests))
        results = await asyncio.gather(*checks)
        return _report(self.http.site_url, [f for group in results for f in group])

    async def _rest_api(self) -> list[dict[str, str]]:
        status, headers, text = await self.http.get("/wp-json/", auth=False)
        www_auth = headers.get("WWW-Authenticate") or headers.get("www-authenticate") or ""
        if status == 401 and "basic" in www_auth.lower():
            return [
                _finding(
                    "rest_api",
                    "fail",
                    "The site is behind HTTP Basic authentication",
                    "The server asks for Basic credentials before WordPress runs. "
                    "Application Passwords travel in the same Authorization header, so "
                    "WordPress receives the wrong username (invalid_username) and every "
                    "authenticated tool call fails.",
                    "Exclude /wp-json/ from the Basic-auth rule (or allow the hub's IP), "
                    "or remove Basic auth once the staging phase is over.",
                )
            ]
        if status == 404:
            alt_status, _, _ = await self.http.get("/?rest_route=/", auth=False)
            if alt_status == 200:
                return [
                    _finding(
                        "rest_api",
                        "warn",
                        "/wp-json/ returns 404 but ?rest_route=/ works",
                        "Pretty REST URLs are broken (plain permalinks or missing rewrite rules).",
                        "Settings → Permalinks → choose any non-plain structure and save "
                        "(this also flushes rewrite rules).",
                    )
                ]
            return [
                _finding(
                    "rest_api",
                    "fail",
                    "The REST API is not reachable",
                    f"/wp-json/ returned HTTP {status}.",
                    "Check that a security plugin or the server is not blocking the REST API.",
                )
            ]
        if status >= 400:
            return [
                _finding(
                    "rest_api",
                    "fail",
                    f"The REST API answered HTTP {status}",
                    _strip_html(text),
                    "A firewall/WAF or security plugin may be blocking /wp-json/.",
                )
            ]
        namespaces: list[str] = []
        try:
            namespaces = list(json.loads(text).get("namespaces") or [])
        except (json.JSONDecodeError, AttributeError):
            pass
        interesting = [
            n
            for n in namespaces
            if n.split("/")[0] in {"wc", "airano-mcp", "rankmath", "yoast", "wp-site-health"}
        ]
        return [
            _finding(
                "rest_api",
                "ok",
                "REST API reachable",
                ("Namespaces: " + ", ".join(interesting)) if interesting else "",
            )
        ]

    async def _authentication(self) -> list[dict[str, str]]:
        status, body = await self.http.get_json(
            "/wp-json/wp/v2/users/me", params={"context": "edit"}
        )
        if status == 200 and isinstance(body, dict):
            roles = body.get("roles") or []
            caps = body.get("capabilities") or {}
            if "administrator" in roles or caps.get("manage_options"):
                return [
                    _finding("authentication", "ok", "Application Password works (administrator)")
                ]
            return [
                _finding(
                    "authentication",
                    "warn",
                    f"Authenticated, but the user is not an administrator (roles: {roles or '-'})",
                    "Plugin, settings and Site Health tools need an administrator account.",
                    "Create the Application Password on an administrator account.",
                )
            ]
        code = _error_code(body)
        if code == "rest_not_logged_in":
            return [
                _finding(
                    "authentication",
                    "fail",
                    "Credentials were sent but WordPress saw no login",
                    "The web server stripped the Authorization header before PHP "
                    "(common with Apache + CGI/FastCGI).",
                    'Apache: add `SetEnvIf Authorization "(.*)" HTTP_AUTHORIZATION=$1` '
                    "(or `CGIPassAuth On`) to .htaccess; nginx/proxies: forward the "
                    "Authorization header.",
                )
            ]
        if code in ("invalid_username", "incorrect_password", "invalid_email"):
            return [
                _finding(
                    "authentication",
                    "fail",
                    f"WordPress rejected the credentials ({code})",
                    "Use the WordPress username (not the email) and an Application "
                    "Password (not the login password).",
                    "Users → Profile → Application Passwords → create a new one and "
                    "update the site in the dashboard.",
                )
            ]
        if code == "application_passwords_disabled":
            return [
                _finding(
                    "authentication",
                    "fail",
                    "Application Passwords are disabled on this site",
                    "A security plugin or a filter turned the feature off.",
                    "Re-enable Application Passwords in the security plugin settings.",
                )
            ]
        return [
            _finding(
                "authentication",
                "fail",
                f"Authentication check failed (HTTP {status}{', ' + code if code else ''})",
                fix="Verify the site URL and the Application Password in the dashboard.",
            )
        ]

    async def _homepage(self) -> list[dict[str, str]]:
        status, headers, html = await self.http.get("/", auth=False)
        if status >= 400:
            return [
                _finding(
                    "homepage",
                    "fail",
                    f"The home page answered HTTP {status}",
                    _strip_html(html, 200),
                )
            ]
        return analyze_homepage(self.http.site_url, html, headers)

    async def _companion_signals(self) -> list[dict[str, str]]:
        status, body = await self.http.get_json("/wp-json/airano-mcp/v1/site-health")
        if status == 404:
            return [
                _finding(
                    "debug_mode",
                    "skip",
                    "WP_DEBUG not checked (Airano MCP Bridge companion not installed)",
                    fix="Install the Airano MCP Bridge plugin to enable server-side checks.",
                )
            ]
        if status != 200 or not isinstance(body, dict):
            return [
                _finding("debug_mode", "skip", f"Companion site-health unavailable (HTTP {status})")
            ]
        wp = body.get("wordpress") or body.get("wp") or {}
        findings = []
        if wp.get("debug_mode"):
            findings.append(
                _finding(
                    "debug_mode",
                    "warn",
                    "WP_DEBUG is ON",
                    "Debug mode slows the site and can expose paths and errors.",
                    "Turn WP_DEBUG off in wp-config.php. On the official WordPress Docker "
                    "image, WORDPRESS_DEBUG='false' turns debug ON (the image uses "
                    "!!getenv); remove the variable or set it to an empty string.",
                )
            )
        else:
            findings.append(_finding("debug_mode", "ok", "WP_DEBUG is off"))

        opt_status, opt = await self.http.get_json(
            "/wp-json/airano-mcp/v1/admin/options/blog_public"
        )
        if opt_status == 200 and isinstance(opt, dict) and opt.get("exists"):
            if str(opt.get("value")) == "0":
                findings.append(
                    _finding(
                        "discourage_search_engines",
                        "warn",
                        "'Discourage search engines' is ON (blog_public = 0)",
                        fix="Settings → Reading → untick 'Discourage search engines from "
                        "indexing this site' once the site is live.",
                    )
                )
            else:
                findings.append(
                    _finding("discourage_search_engines", "ok", "Search engines are allowed")
                )
        return findings

    async def _plugins(self) -> list[dict[str, str]]:
        status, body = await self.http.get_json(
            "/wp-json/wp/v2/plugins", params={"status": "active"}
        )
        files: list[str] = []
        if status == 200 and isinstance(body, list):
            files = [str(p.get("plugin", "")) for p in body if isinstance(p, dict)]
        else:
            c_status, c_body = await self.http.get_json("/wp-json/airano-mcp/v1/site-health")
            plugins = (c_body or {}).get("plugins") if isinstance(c_body, dict) else None
            active = (plugins or {}).get("active") if isinstance(plugins, dict) else None
            if c_status == 200 and isinstance(active, list):
                files = [str(p.get("file", "")) for p in active if isinstance(p, dict)]
            else:
                return [
                    _finding(
                        "plugin_conflicts",
                        "skip",
                        f"Active plugins not readable (HTTP {status})",
                        fix="Use an administrator Application Password.",
                    )
                ]
        return plugin_conflicts(files)

    async def _site_health_tests(self) -> list[dict[str, str]]:
        async def one(test: str) -> dict[str, str]:
            try:
                status, body = await asyncio.wait_for(
                    self.http.get_json(f"/wp-json/wp-site-health/v1/tests/{test}"), timeout=25
                )
            except TimeoutError:
                return _finding(f"site_health:{test}", "skip", f"Site Health '{test}' timed out")
            if status != 200 or not isinstance(body, dict):
                return _finding(
                    f"site_health:{test}",
                    "skip",
                    f"Site Health '{test}' unavailable (HTTP {status})",
                )
            mapped = {"good": "ok", "recommended": "warn", "critical": "fail"}.get(
                str(body.get("status")), "info"
            )
            return _finding(
                f"site_health:{test}",
                mapped,
                _strip_html(str(body.get("label") or test), 160),
                _strip_html(str(body.get("description") or "")),
                _strip_html(str(body.get("actions") or ""), 200),
            )

        return list(await asyncio.gather(*(one(t) for t in SITE_HEALTH_TESTS)))


# --------------------------------------------------------------- WooCommerce


class StoreDiagnosticsHandler:
    """``woocommerce_diagnose_store`` (works with WooCommerce consumer keys)."""

    def __init__(self, client: Any) -> None:
        self.client = client
        self.http = _Http(client.site_url, getattr(client, "auth_header", None))

    async def diagnose_store(self) -> str:
        results = await asyncio.gather(
            _guarded(self._coming_soon),
            _guarded(self._system_status),
            _guarded(self._payment_gateways),
            _guarded(self._shipping),
        )
        return _report(self.http.site_url, [f for group in results for f in group])

    async def _coming_soon(self) -> list[dict[str, str]]:
        status, body = await self.http.get_json(
            "/wp-json/wc-admin/options",
            params={"options": "woocommerce_coming_soon,woocommerce_store_pages_only"},
        )
        if status != 200 or not isinstance(body, dict):
            return [
                _finding(
                    "coming_soon",
                    "skip",
                    f"Coming-soon status not readable (HTTP {status})",
                    "Needs WooCommerce 9.1+ and an API key of a shop manager/administrator.",
                )
            ]
        if body.get("woocommerce_coming_soon") == "yes":
            scope = (
                "the store pages"
                if body.get("woocommerce_store_pages_only") == "yes"
                else "the entire site"
            )
            return [
                _finding(
                    "coming_soon",
                    "fail",
                    f"Coming-soon mode is ON for {scope}",
                    "Logged-out visitors see a 'coming soon' page instead of the shop; "
                    "logged-in admins still see everything, so it is easy to miss.",
                    "WooCommerce → Settings → Site visibility → Live.",
                )
            ]
        return [_finding("coming_soon", "ok", "Store is live (not in Coming-soon mode)")]

    async def _system_status(self) -> list[dict[str, str]]:
        status, body = await self.http.get_json(
            "/wp-json/wc/v3/system_status",
            params={"_fields": "environment,theme,pages,security,active_plugins"},
        )
        if status != 200 or not isinstance(body, dict):
            return [
                _finding(
                    "system_status",
                    "skip",
                    f"WooCommerce system status not readable (HTTP {status})",
                    fix="Use an API key with Read access from an administrator.",
                )
            ]
        findings: list[dict[str, str]] = []
        pages = {str(p.get("page_name", "")).lower(): p for p in body.get("pages") or []}
        theme = body.get("theme") or {}
        overrides = [
            str(o.get("file", "")) for o in theme.get("overrides") or [] if isinstance(o, dict)
        ]

        for key, label in (("checkout", "Checkout"), ("cart", "Cart")):
            page = next((p for name, p in pages.items() if key in name), None)
            if page is None:
                continue
            if not page.get("page_set") or not page.get("page_exists"):
                findings.append(
                    _finding(
                        f"{key}_page",
                        "fail",
                        f"No {label} page is set",
                        fix=f"WooCommerce → Settings → Advanced → Page setup → choose a {label} page.",
                    )
                )
                continue
            if not page.get("page_visible"):
                findings.append(
                    _finding(
                        f"{key}_page",
                        "fail",
                        f"The {label} page is not published",
                        fix=f"Publish the {label} page (ID {page.get('page_id')}).",
                    )
                )
                continue
            if page.get("block_present"):
                kind = "block"
            elif page.get("shortcode_present"):
                kind = "classic"
            else:
                findings.append(
                    _finding(
                        f"{key}_page",
                        "fail",
                        f"The {label} page has neither the {label} block nor the shortcode",
                        fix=f"Add the {label} block (or the {page.get('shortcode') or 'shortcode'}) to page ID {page.get('page_id')}.",
                    )
                )
                continue
            findings.append(
                _finding(
                    f"{key}_type",
                    "info",
                    f"{label} uses the {'block-based' if kind == 'block' else 'classic (shortcode)'} {label.lower()}",
                    (
                        "Extensions that only hook into the classic checkout (custom "
                        "checkout fields, some regional payment/shipping plugins) do not "
                        "run in the Checkout block."
                        if key == "checkout" and kind == "block"
                        else ""
                    ),
                )
            )
            if key == "checkout" and kind == "block":
                classic_overrides = [
                    f for f in overrides if "/checkout/" in f or f.endswith("form-checkout.php")
                ]
                if classic_overrides:
                    findings.append(
                        _finding(
                            "checkout_overrides_ignored",
                            "warn",
                            "The theme overrides classic checkout templates, but checkout uses the Checkout block",
                            "These overrides never run: " + ", ".join(classic_overrides[:6]),
                            "Either switch the Checkout page to the [woocommerce_checkout] "
                            "shortcode, or move the customisation to the block (or a "
                            "block-compatible extension).",
                        )
                    )

        if theme.get("has_outdated_templates"):
            outdated = [
                f"{o.get('file')} ({o.get('version') or '?'} < {o.get('core_version')})"
                for o in theme.get("overrides") or []
                if isinstance(o, dict) and o.get("version") != o.get("core_version")
            ]
            findings.append(
                _finding(
                    "outdated_templates",
                    "warn",
                    f"The theme has {len(outdated) or 'some'} outdated WooCommerce template override(s)",
                    ", ".join(outdated[:6]),
                    "Update the theme (or its child-theme overrides) to the current WooCommerce templates.",
                )
            )

        security = body.get("security") or {}
        if security.get("secure_connection") is False:
            findings.append(
                _finding(
                    "https",
                    "warn",
                    "The store is not served over HTTPS",
                    fix="Enable HTTPS; payment gateways and browsers require it.",
                )
            )
        if security.get("hide_errors") is False:
            findings.append(
                _finding(
                    "errors_displayed",
                    "warn",
                    "PHP errors are displayed to visitors",
                    "WP_DEBUG + WP_DEBUG_DISPLAY (or display_errors) is on.",
                    "Set WP_DEBUG_DISPLAY to false (and WP_DEBUG off in production).",
                )
            )
        env = body.get("environment") or {}
        if env.get("wp_debug_mode"):
            findings.append(
                _finding(
                    "debug_mode",
                    "warn",
                    "WP_DEBUG is ON",
                    fix="Turn WP_DEBUG off in wp-config.php. On the official WordPress Docker "
                    "image, WORDPRESS_DEBUG='false' turns debug ON; remove the variable.",
                )
            )
        if env.get("version"):
            findings.append(
                _finding(
                    "versions",
                    "info",
                    f"WooCommerce {env.get('version')} on WordPress {env.get('wp_version', '?')}",
                )
            )

        plugin_files = [
            str(p.get("plugin", ""))
            for p in body.get("active_plugins") or []
            if isinstance(p, dict)
        ]
        if plugin_files:
            findings.extend(plugin_conflicts(plugin_files))
        return findings

    async def _payment_gateways(self) -> list[dict[str, str]]:
        status, body = await self.http.get_json("/wp-json/wc/v3/payment_gateways")
        if status != 200 or not isinstance(body, list):
            return [
                _finding(
                    "payment_gateways", "skip", f"Payment gateways not readable (HTTP {status})"
                )
            ]
        enabled = [
            str(g.get("title") or g.get("id"))
            for g in body
            if isinstance(g, dict) and g.get("enabled")
        ]
        if not enabled:
            return [
                _finding(
                    "payment_gateways",
                    "fail",
                    "No payment gateway is enabled",
                    "Customers cannot complete a purchase.",
                    "WooCommerce → Settings → Payments → enable at least one method.",
                )
            ]
        return [
            _finding(
                "payment_gateways",
                "ok",
                f"{len(enabled)} payment gateway(s) enabled",
                ", ".join(enabled[:8]),
            )
        ]

    async def _shipping(self) -> list[dict[str, str]]:
        status, zones = await self.http.get_json("/wp-json/wc/v3/shipping/zones")
        if status != 200 or not isinstance(zones, list):
            return [_finding("shipping", "skip", f"Shipping zones not readable (HTTP {status})")]
        total = 0
        names: list[str] = []
        for zone in zones[:20]:
            if not isinstance(zone, dict):
                continue
            m_status, methods = await self.http.get_json(
                f"/wp-json/wc/v3/shipping/zones/{zone.get('id')}/methods"
            )
            if m_status == 200 and isinstance(methods, list):
                live = [m for m in methods if isinstance(m, dict) and m.get("enabled")]
                total += len(live)
                if live:
                    names.append(str(zone.get("name")))
        if total == 0:
            return [
                _finding(
                    "shipping",
                    "warn",
                    "No enabled shipping method in any zone",
                    "Orders with physical products cannot be checked out.",
                    "WooCommerce → Settings → Shipping → add a zone with at least one method "
                    "(ignore for digital-only stores).",
                )
            ]
        return [
            _finding(
                "shipping",
                "ok",
                f"{total} enabled shipping method(s)",
                "Zones: " + ", ".join(names[:8]),
            )
        ]
