"""F.19.7 — Tests for the WordPress Specialist theme dev handler.

Mocks ``WordPressClient.get`` / ``post`` / ``put`` / ``delete`` and
asserts:

* tool spec contract: 7 tools (3 management + 4 file CRUD), reads at
  ``scope=read``, writes at ``scope=editor``
* each handler method targets the correct ``airano-mcp/v1/admin/*``
  route with ``use_custom_namespace=True``
* client-side guards reject malformed slugs (S-15), traversal-shaped
  paths (S-16), oversized payloads (S-18), and bad expected_sha256
  (S-19)
* mutually-exclusive zip_url / zip_base64 contract is enforced
"""

from __future__ import annotations

import base64
from unittest.mock import AsyncMock

import pytest

from plugins.wordpress.client import WordPressClient
from plugins.wordpress_specialist.handlers.themes import (
    ThemesHandler,
    _validate_theme_file_path,
    _validate_theme_slug,
    get_tool_specifications,
)

# ───── Tool spec contract ────────────────────────────────────────────


def test_tool_specs_count_and_names_match_f197():
    specs = get_tool_specifications()
    assert len(specs) == 7, "F.19.7 advertises 3 management + 4 file CRUD"
    names = {s["name"] for s in specs}
    assert names == {
        "wp_theme_install_from_zip",
        "wp_theme_activate",
        "wp_theme_delete",
        "wp_theme_file_list",
        "wp_theme_file_read",
        "wp_theme_file_write",
        "wp_theme_file_delete",
    }


def test_reads_are_read_scope_writes_are_editor_scope():
    specs_by_name = {s["name"]: s for s in get_tool_specifications()}
    expected_scope = {
        "wp_theme_install_from_zip": "editor",
        "wp_theme_activate": "editor",
        "wp_theme_delete": "editor",
        "wp_theme_file_list": "read",
        "wp_theme_file_read": "read",
        "wp_theme_file_write": "editor",
        "wp_theme_file_delete": "editor",
    }
    for name, scope in expected_scope.items():
        assert specs_by_name[name]["scope"] == scope, f"{name} should be scope={scope}"


def test_every_spec_has_the_full_contract():
    """Each F.19.7 spec must carry name, method_name, description, schema."""
    for spec in get_tool_specifications():
        assert spec["name"] == spec["method_name"]
        assert spec["description"]
        assert isinstance(spec["schema"], dict)
        assert spec["schema"].get("type") == "object"


def test_file_list_schema_caps_max_files_at_1000():
    spec = next(s for s in get_tool_specifications() if s["name"] == "wp_theme_file_list")
    assert spec["schema"]["properties"]["max_files"]["maximum"] == 1000


# ───── Slug + path validation (S-15 + S-16 client-side) ──────────────


@pytest.mark.parametrize(
    "good",
    [
        "twentytwentyfive",
        "palebluedot",
        "my-child-theme",
        "theme_v2",
        "T1",
    ],
)
def test_validate_theme_slug_accepts_well_formed(good):
    assert _validate_theme_slug(good) == good


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "../etc",
        "slug/with/slash",
        "slug.with.dot",
        "-leading-dash",
        "_leading-underscore-fine?",  # actually valid? No: starts with _, our regex requires alnum start
        "slug with spaces",
        "x" * 65,
        None,
        42,
    ],
)
def test_validate_theme_slug_rejects_malformed(bad):
    with pytest.raises(ValueError):
        _validate_theme_slug(bad)


@pytest.mark.parametrize(
    "good",
    [
        "style.css",
        "parts/header.html",
        "templates/page-home.html",
        "assets/img/hero.jpg",
        "..foo/bar",  # `..foo` is a real filename, not traversal
    ],
)
def test_validate_theme_file_path_accepts_clean_paths(good):
    out = _validate_theme_file_path(good)
    assert "/" in out or out == good
    assert ".." not in out.split("/")


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "../etc/passwd",
        "/absolute/path",
        "parts/../../escape",
        "parts/\x00null",
        "parts\\windows.html",
        "parts/..",  # `..` segment
    ],
)
def test_validate_theme_file_path_rejects_traversal(bad):
    with pytest.raises(ValueError):
        _validate_theme_file_path(bad)


# ───── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def client():
    c = WordPressClient(site_url="https://wp.example.com", username="u", app_password="p")
    c.get = AsyncMock(return_value={"ok": True})  # type: ignore[method-assign]
    c.post = AsyncMock(return_value={"ok": True})  # type: ignore[method-assign]
    c.put = AsyncMock(return_value={"ok": True})  # type: ignore[method-assign]
    c.delete = AsyncMock(return_value={"ok": True})  # type: ignore[method-assign]
    return c


@pytest.fixture
def handler(client):
    return ThemesHandler(client)


# ───── Theme management routing ──────────────────────────────────────


@pytest.mark.asyncio
async def test_install_from_zip_url_calls_install_route(handler, client):
    await handler.wp_theme_install_from_zip(
        zip_url="https://example.com/theme.zip", activate=True, overwrite=False
    )
    client.post.assert_awaited_once_with(
        "airano-mcp/v1/admin/themes/install",
        json_data={
            "zip_url": "https://example.com/theme.zip",
            "activate": True,
            "overwrite": False,
        },
        use_custom_namespace=True,
    )


@pytest.mark.asyncio
async def test_install_from_zip_base64_calls_install_route(handler, client):
    payload = base64.b64encode(b"PK\x03\x04 fake zip").decode()
    await handler.wp_theme_install_from_zip(zip_base64=payload)
    args, kwargs = client.post.call_args
    assert args[0] == "airano-mcp/v1/admin/themes/install"
    assert kwargs["json_data"]["zip_base64"] == payload
    assert kwargs["json_data"]["activate"] is False
    assert "zip_url" not in kwargs["json_data"]


@pytest.mark.asyncio
async def test_install_requires_one_of_url_or_base64(handler, client):
    with pytest.raises(ValueError, match="zip_url or zip_base64"):
        await handler.wp_theme_install_from_zip()
    client.post.assert_not_awaited()


@pytest.mark.asyncio
async def test_install_rejects_both_url_and_base64(handler, client):
    with pytest.raises(ValueError, match="not both"):
        await handler.wp_theme_install_from_zip(
            zip_url="https://example.com/x.zip", zip_base64="aGVsbG8="
        )
    client.post.assert_not_awaited()


@pytest.mark.asyncio
async def test_install_rejects_oversized_zip_base64(handler, client):
    # 60 MB worth of base64 chars (~45 MB decoded? no — 60M chars × 3/4 = 45M).
    # We need the upper bound > 50 MB, so 70M chars should do it.
    huge = "A" * (70 * 1024 * 1024)
    with pytest.raises(ValueError, match=r"exceeds .* byte cap \(S-18\)"):
        await handler.wp_theme_install_from_zip(zip_base64=huge)
    client.post.assert_not_awaited()


@pytest.mark.asyncio
async def test_activate_calls_activate_route(handler, client):
    await handler.wp_theme_activate(slug="palebluedot")
    client.post.assert_awaited_once_with(
        "airano-mcp/v1/admin/themes/palebluedot/activate",
        json_data={},
        use_custom_namespace=True,
    )


@pytest.mark.asyncio
async def test_activate_rejects_bad_slug(handler, client):
    with pytest.raises(ValueError):
        await handler.wp_theme_activate(slug="../etc")
    client.post.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_calls_delete_route(handler, client):
    await handler.wp_theme_delete(slug="oldtheme")
    client.delete.assert_awaited_once_with(
        "airano-mcp/v1/admin/themes/oldtheme",
        use_custom_namespace=True,
    )


# ───── Theme file CRUD routing ───────────────────────────────────────


@pytest.mark.asyncio
async def test_file_list_calls_list_route_with_glob_and_max(handler, client):
    await handler.wp_theme_file_list(theme_slug="palebluedot", glob="**/*.php", max_files=500)
    client.get.assert_awaited_once_with(
        "airano-mcp/v1/admin/themes/files/palebluedot",
        params={"glob": "**/*.php", "max_files": 500},
        use_custom_namespace=True,
    )


@pytest.mark.asyncio
async def test_file_list_uses_default_glob_and_max(handler, client):
    await handler.wp_theme_file_list(theme_slug="palebluedot")
    args, kwargs = client.get.call_args
    assert kwargs["params"]["glob"] == "**/*"
    assert kwargs["params"]["max_files"] == 1000


@pytest.mark.asyncio
async def test_file_list_rejects_oversized_max_files(handler, client):
    with pytest.raises(ValueError, match="exceeds the 1000"):
        await handler.wp_theme_file_list(theme_slug="palebluedot", max_files=2000)
    client.get.assert_not_awaited()


@pytest.mark.asyncio
async def test_file_read_calls_read_route_with_quoted_path(handler, client):
    await handler.wp_theme_file_read(theme_slug="palebluedot", path="parts/header.html")
    client.get.assert_awaited_once_with(
        "airano-mcp/v1/admin/themes/files/palebluedot/parts/header.html",
        use_custom_namespace=True,
    )


@pytest.mark.asyncio
async def test_file_read_quotes_special_characters_in_path(handler, client):
    """Spaces and other URL-unsafe chars must be percent-encoded; / stays literal."""
    await handler.wp_theme_file_read(theme_slug="palebluedot", path="parts/hero image.html")
    args, kwargs = client.get.call_args
    # Forward slashes preserved; space encoded.
    assert "parts/hero%20image.html" in args[0]


@pytest.mark.asyncio
async def test_file_read_rejects_traversal(handler, client):
    with pytest.raises(ValueError):
        await handler.wp_theme_file_read(theme_slug="palebluedot", path="../wp-config.php")
    client.get.assert_not_awaited()


@pytest.mark.asyncio
async def test_file_write_calls_put_route_with_body(handler, client):
    payload = base64.b64encode(b"body { color: red; }").decode()
    await handler.wp_theme_file_write(
        theme_slug="palebluedot", path="style.css", content_base64=payload
    )
    client.put.assert_awaited_once_with(
        "airano-mcp/v1/admin/themes/files/palebluedot/style.css",
        json_data={"content_base64": payload, "create_dirs": True},
        use_custom_namespace=True,
    )


@pytest.mark.asyncio
async def test_file_write_passes_expected_sha256_when_supplied(handler, client):
    sha = "a" * 64
    payload = base64.b64encode(b"hi").decode()
    await handler.wp_theme_file_write(
        theme_slug="palebluedot",
        path="style.css",
        content_base64=payload,
        expected_sha256=sha,
    )
    args, kwargs = client.put.call_args
    assert kwargs["json_data"]["expected_sha256"] == sha


@pytest.mark.asyncio
async def test_file_write_rejects_invalid_expected_sha256(handler, client):
    with pytest.raises(ValueError, match="64-char hex"):
        await handler.wp_theme_file_write(
            theme_slug="palebluedot",
            path="style.css",
            content_base64=base64.b64encode(b"hi").decode(),
            expected_sha256="not-a-hash",
        )
    client.put.assert_not_awaited()


@pytest.mark.asyncio
async def test_file_write_rejects_oversized_content(handler, client):
    huge = "A" * (8 * 1024 * 1024)  # ~8 MB base64 → ~6 MB decoded > 5 MB cap
    with pytest.raises(ValueError, match=r"exceeds .* byte cap \(S-18\)"):
        await handler.wp_theme_file_write(
            theme_slug="palebluedot", path="style.css", content_base64=huge
        )
    client.put.assert_not_awaited()


@pytest.mark.asyncio
async def test_file_write_passes_create_dirs_false(handler, client):
    payload = base64.b64encode(b"x").decode()
    await handler.wp_theme_file_write(
        theme_slug="palebluedot",
        path="parts/new.html",
        content_base64=payload,
        create_dirs=False,
    )
    args, kwargs = client.put.call_args
    assert kwargs["json_data"]["create_dirs"] is False


@pytest.mark.asyncio
async def test_file_delete_calls_delete_route(handler, client):
    await handler.wp_theme_file_delete(theme_slug="palebluedot", path="style.css")
    client.delete.assert_awaited_once_with(
        "airano-mcp/v1/admin/themes/files/palebluedot/style.css",
        use_custom_namespace=True,
    )


@pytest.mark.asyncio
async def test_file_delete_rejects_traversal(handler, client):
    with pytest.raises(ValueError):
        await handler.wp_theme_file_delete(theme_slug="palebluedot", path="../config.php")
    client.delete.assert_not_awaited()
