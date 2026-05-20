"""F.19.3.2-.3 — Tests for the WordPress Specialist database handler.

Mocks ``WordPressClient.get`` / ``post`` and asserts:

* tool spec contract: 3 tools all on scope=read
* each handler method targets the correct ``airano-mcp/v1/admin/db/*``
  route with ``use_custom_namespace=True`` and the right HTTP verb
* client-side validators (S-25 query length cap, limit cap at 100,
  empty query refusal, post_type / status filter shape)
* server-returned error envelopes (500 db_size_query_failed, 400
  invalid_query) are relayed untouched — the companion is the binding
  gate
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from plugins.wordpress.client import WordPressClient
from plugins.wordpress_specialist.handlers.database import (
    DatabaseHandler,
    _normalise_filter,
    _normalise_limit,
    _normalise_query,
    get_tool_specifications,
)

# ───── Tool spec contract ────────────────────────────────────────────


def test_tool_specs_count_and_names_match_f1932():
    specs = get_tool_specifications()
    assert len(specs) == 3, "F.19.3.2-.3 advertises 3 read tools"
    names = {s["name"] for s in specs}
    assert names == {"wp_db_size", "wp_db_tables", "wp_db_search"}


def test_all_database_tools_on_read_tier():
    """db inspection is non-destructive — read tier per F.19.3.2 spec."""
    for spec in get_tool_specifications():
        assert spec["scope"] == "read", f"{spec['name']} should be scope=read"


def test_every_spec_has_the_full_contract():
    for spec in get_tool_specifications():
        assert spec["name"] == spec["method_name"]
        assert spec["description"]
        assert isinstance(spec["schema"], dict)
        assert spec["schema"].get("type") == "object"


def test_db_search_required_and_schema_caps():
    by_name = {s["name"]: s for s in get_tool_specifications()}
    schema = by_name["wp_db_search"]["schema"]
    assert schema["required"] == ["query"]
    assert schema["properties"]["query"]["maxLength"] == 200
    assert schema["properties"]["limit"]["maximum"] == 100


def test_db_size_and_tables_take_no_args():
    by_name = {s["name"]: s for s in get_tool_specifications()}
    assert by_name["wp_db_size"]["schema"]["properties"] == {}
    assert by_name["wp_db_tables"]["schema"]["properties"] == {}


# ───── Validators ────────────────────────────────────────────────────


def test_normalise_query_strips_and_caps():
    assert _normalise_query("  hello  ") == "hello"
    long = "x" * 250
    assert _normalise_query(long) == "x" * 200


def test_normalise_query_rejects_empty_or_whitespace():
    with pytest.raises(ValueError, match="non-empty"):
        _normalise_query("   ")
    with pytest.raises(ValueError, match="non-empty"):
        _normalise_query("")


def test_normalise_query_rejects_non_string():
    with pytest.raises(ValueError, match="must be a string"):
        _normalise_query(123)
    with pytest.raises(ValueError, match="must be a string"):
        _normalise_query(["hi"])


def test_normalise_limit_default_is_20():
    assert _normalise_limit(None) == 20


def test_normalise_limit_caps_at_100():
    assert _normalise_limit(500) == 100
    assert _normalise_limit(100) == 100
    assert _normalise_limit(50) == 50


def test_normalise_limit_rejects_zero_and_negative():
    with pytest.raises(ValueError, match=">= 1"):
        _normalise_limit(0)
    with pytest.raises(ValueError, match=">= 1"):
        _normalise_limit(-3)


def test_normalise_limit_rejects_non_int():
    with pytest.raises(ValueError, match="must be an integer"):
        _normalise_limit("20")
    with pytest.raises(ValueError, match="must be an integer"):
        _normalise_limit(True)  # bool is rejected even though it's an int subtype


def test_normalise_filter_accepts_string_and_list():
    assert _normalise_filter("post", "post_type") == "post"
    assert _normalise_filter(["post", "page"], "post_type") == ["post", "page"]
    assert _normalise_filter(None, "post_type") is None
    assert _normalise_filter("", "post_type") is None


def test_normalise_filter_rejects_bad_shape():
    with pytest.raises(ValueError, match="string or array"):
        _normalise_filter(42, "post_type")
    with pytest.raises(ValueError, match="only strings"):
        _normalise_filter(["post", 42], "post_type")


# ───── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def client():
    c = WordPressClient(site_url="https://wp.example.com", username="u", app_password="p")
    c.get = AsyncMock(return_value={"ok": True})  # type: ignore[method-assign]
    c.post = AsyncMock(return_value={"ok": True})  # type: ignore[method-assign]
    return c


@pytest.fixture
def handler(client):
    return DatabaseHandler(client)


# ───── Routing — db/size, db/tables ──────────────────────────────────


@pytest.mark.asyncio
async def test_db_size_calls_route(handler, client):
    await handler.wp_db_size()
    client.get.assert_awaited_once_with(
        "airano-mcp/v1/admin/db/size",
        use_custom_namespace=True,
    )


@pytest.mark.asyncio
async def test_db_tables_calls_route(handler, client):
    await handler.wp_db_tables()
    client.get.assert_awaited_once_with(
        "airano-mcp/v1/admin/db/tables",
        use_custom_namespace=True,
    )


@pytest.mark.asyncio
async def test_db_size_relays_server_envelope(handler, client):
    """500 db_size_query_failed should pass through untouched."""
    client.get = AsyncMock(  # type: ignore[method-assign]
        return_value={"code": "db_size_query_failed", "status": 500}
    )
    handler.client = client
    result = await handler.wp_db_size()
    assert result == {"code": "db_size_query_failed", "status": 500}


# ───── Routing — db/search ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_db_search_minimal_call(handler, client):
    await handler.wp_db_search(query="hello")
    client.post.assert_awaited_once_with(
        "airano-mcp/v1/admin/db/search",
        json_data={"query": "hello", "limit": 20},
        use_custom_namespace=True,
    )


@pytest.mark.asyncio
async def test_db_search_passes_post_type_string(handler, client):
    await handler.wp_db_search(query="x", post_type="post")
    args, kwargs = client.post.call_args
    assert kwargs["json_data"]["post_type"] == "post"


@pytest.mark.asyncio
async def test_db_search_passes_post_type_array(handler, client):
    await handler.wp_db_search(query="x", post_type=["post", "page"])
    args, kwargs = client.post.call_args
    assert kwargs["json_data"]["post_type"] == ["post", "page"]


@pytest.mark.asyncio
async def test_db_search_passes_status(handler, client):
    await handler.wp_db_search(query="x", status="draft")
    args, kwargs = client.post.call_args
    assert kwargs["json_data"]["status"] == "draft"


@pytest.mark.asyncio
async def test_db_search_caps_limit_client_side(handler, client):
    await handler.wp_db_search(query="x", limit=999)
    args, kwargs = client.post.call_args
    assert kwargs["json_data"]["limit"] == 100, "client should cap limit at 100 before round-trip"


@pytest.mark.asyncio
async def test_db_search_caps_query_length_client_side(handler, client):
    """S-25 length cap mirrors the server-side 200-char cap."""
    await handler.wp_db_search(query="a" * 500)
    args, kwargs = client.post.call_args
    assert len(kwargs["json_data"]["query"]) == 200


@pytest.mark.asyncio
async def test_db_search_rejects_empty_query(handler, client):
    with pytest.raises(ValueError, match="non-empty"):
        await handler.wp_db_search(query="   ")
    client.post.assert_not_awaited()


@pytest.mark.asyncio
async def test_db_search_omits_blank_filters(handler, client):
    """Empty string filters must not be relayed — they'd confuse WP_Query."""
    await handler.wp_db_search(query="x", post_type="", status="")
    args, kwargs = client.post.call_args
    assert "post_type" not in kwargs["json_data"]
    assert "status" not in kwargs["json_data"]


@pytest.mark.asyncio
async def test_db_search_relays_invalid_query_envelope(handler, client):
    """400 invalid_query is server-bound; client relays."""
    client.post = AsyncMock(  # type: ignore[method-assign]
        return_value={"code": "invalid_query", "status": 400}
    )
    handler.client = client
    result = await handler.wp_db_search(query="hi")
    assert result == {"code": "invalid_query", "status": 400}
