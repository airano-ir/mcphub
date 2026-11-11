"""Tests for the Cloudflare plugin.

Covers:
- CloudflareClient init, headers, requests, error handling
- Token verification and account id resolution
- Zone / DNS / Workers / KV / R2 handler functions (mocked HTTP)
- Plugin registration and tool specifications (25 tools)
- Scope classification (read / write / admin tiers)
- Health check and credential probe
- Connection validation (_validate_cloudflare_connection)
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from plugins.cloudflare import handlers
from plugins.cloudflare.client import CloudflareClient
from plugins.cloudflare.plugin import CloudflarePlugin

# ── Fixtures ───────────────────────────────────────────────────


@pytest.fixture
def cf_client():
    """Create a CloudflareClient with a fake token."""
    return CloudflareClient(api_token="mock_api_token")


def _mock_json_response(status: int, payload: dict | str):
    """Build the aiohttp response mock chain used across tests."""
    mock_response = MagicMock()
    mock_response.status = status
    mock_response.headers = {"Content-Type": "application/json"}
    if isinstance(payload, str):
        mock_response.text = AsyncMock(return_value=payload)
        mock_response.json = AsyncMock(return_value={})
    else:
        mock_response.text = AsyncMock(return_value=json.dumps(payload))
        mock_response.json = AsyncMock(return_value=payload)

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_response)
    mock_ctx.__aexit__ = AsyncMock(return_value=None)

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.request = MagicMock(return_value=mock_ctx)
    # Validation code paths call session.get/post/put directly (not .request)
    for verb in ("get", "post", "put", "delete"):
        setattr(mock_session, verb, MagicMock(return_value=mock_ctx))
    return mock_response, mock_session


def _patch_session(mock_session):
    return patch("plugins.cloudflare.client.aiohttp.ClientSession", return_value=mock_session)


# ── Client tests ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_client_init():
    """Test CloudflareClient initialization."""
    client = CloudflareClient(api_token="token123")
    assert client.api_token == "token123"
    assert client.account_id == ""
    assert client.api_base == "https://api.cloudflare.com/client/v4"


@pytest.mark.asyncio
async def test_client_init_with_account_id():
    """Test CloudflareClient initialization with pinned account id."""
    client = CloudflareClient(api_token="token123", account_id="acc123")
    assert client.account_id == "acc123"


@pytest.mark.asyncio
async def test_get_headers_bearer():
    """Test headers carry Bearer auth."""
    client = CloudflareClient(api_token="tok")
    headers = client._get_headers()
    assert headers["Authorization"] == "Bearer tok"
    assert headers["Accept"] == "application/json"
    assert "Content-Type" not in headers
    json_headers = client._get_headers(json_body=True)
    assert json_headers["Content-Type"] == "application/json"


@pytest.mark.asyncio
async def test_request_success():
    """Test a successful GET request."""
    client = CloudflareClient(api_token="tok")
    mock_response, mock_session = _mock_json_response(
        200, {"success": True, "result": [{"id": "z1"}]}
    )
    with _patch_session(mock_session):
        data = await client._request("GET", "/zones", params={"per_page": 10})
    assert data["result"][0]["id"] == "z1"
    # Verifies the URL was built with the API base
    call_url = mock_session.request.call_args[0][1]
    assert call_url == "https://api.cloudflare.com/client/v4/zones"


@pytest.mark.asyncio
async def test_request_drops_none_params():
    """Test None query params are dropped."""
    client = CloudflareClient(api_token="tok")
    mock_response, mock_session = _mock_json_response(200, {"success": True, "result": []})
    with _patch_session(mock_session):
        await client._request(
            "GET", "/zones", params={"name": None, "status": "active", "page": None}
        )
    call_kwargs = mock_session.request.call_args[1]
    assert call_kwargs["params"] == {"status": "active"}


@pytest.mark.asyncio
async def test_request_error_includes_cloudflare_message():
    """Test HTTP errors surface Cloudflare's error messages."""
    client = CloudflareClient(api_token="tok")
    payload = {
        "success": False,
        "errors": [{"code": 9109, "message": "Invalid API Token"}],
    }
    mock_response, mock_session = _mock_json_response(400, payload)
    with _patch_session(mock_session):
        with pytest.raises(Exception, match="Invalid API Token"):
            await client._request("GET", "/user/tokens/verify")


@pytest.mark.asyncio
async def test_verify_token():
    """Test token verification."""
    client = CloudflareClient(api_token="tok")
    mock_response, mock_session = _mock_json_response(
        200, {"success": True, "result": {"id": "t1", "status": "active"}}
    )
    with _patch_session(mock_session):
        result = await client.verify_token()
    assert result["status"] == "active"
    assert result["id"] == "t1"


@pytest.mark.asyncio
async def test_resolve_account_id_pinned():
    """Test pinned account id is returned directly."""
    client = CloudflareClient(api_token="tok", account_id="acc_pinned")
    assert await client._resolve_account_id() == "acc_pinned"


@pytest.mark.asyncio
async def test_resolve_account_id_discovers():
    """Test account id discovery via /accounts."""
    client = CloudflareClient(api_token="tok")
    mock_response, mock_session = _mock_json_response(
        200, {"success": True, "result": [{"id": "acc_found", "name": "My Account"}]}
    )
    with _patch_session(mock_session):
        acc = await client._resolve_account_id()
    assert acc == "acc_found"
    assert client._resolved_account_id == "acc_found"
    # Second call must not hit the API again
    with patch("plugins.cloudflare.client.aiohttp.ClientSession", return_value=mock_session) as s:
        assert await client._resolve_account_id() == "acc_found"
    s.assert_not_called()


@pytest.mark.asyncio
async def test_resolve_account_id_none_raises():
    """Test discovery failure raises a clear error."""
    client = CloudflareClient(api_token="tok")
    mock_response, mock_session = _mock_json_response(200, {"success": True, "result": []})
    with _patch_session(mock_session):
        with pytest.raises(Exception, match="No account found"):
            await client._resolve_account_id()


# ── Handler tests ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_verify_token_handler(cf_client):
    """Test verify_token handler output shape."""
    with patch.object(cf_client, "verify_token", new_callable=AsyncMock) as mock:
        mock.return_value = {"id": "t1", "status": "active"}
        out = await handlers.user.verify_token(cf_client)
    data = json.loads(out)
    assert data["success"] is True
    assert data["token_id"] == "t1"
    assert data["status"] == "active"


@pytest.mark.asyncio
async def test_list_zones_handler(cf_client):
    """Test list zones handler with mock zone data."""
    with patch.object(cf_client, "list_zones", new_callable=AsyncMock) as mock:
        mock.return_value = [
            {
                "id": "z1",
                "name": "example.com",
                "status": "active",
                "name_servers": ["ns1.example.com"],
                "plan": {"name": "Free"},
            }
        ]
        out = await handlers.zones.list_zones(cf_client)
    data = json.loads(out)
    assert data["count"] == 1
    assert data["zones"][0]["name"] == "example.com"
    assert data["zones"][0]["plan"] == "Free"


@pytest.mark.asyncio
async def test_list_zones_handler_empty(cf_client):
    """Test list zones handler with no results."""
    with patch.object(cf_client, "list_zones", new_callable=AsyncMock) as mock:
        mock.return_value = []
        out = await handlers.zones.list_zones(cf_client)
    assert json.loads(out)["count"] == 0


@pytest.mark.asyncio
async def test_purge_cache_handler(cf_client):
    """Test purge cache handler passes through the zone id."""
    with patch.object(cf_client, "purge_cache", new_callable=AsyncMock) as mock:
        mock.return_value = {"id": "purge1"}
        out = await handlers.zones.purge_cache(cf_client, zone_id="z1", purge_everything=True)
    mock.assert_awaited_once()
    assert json.loads(out)["purged"] == "zone cache"


@pytest.mark.asyncio
async def test_create_dns_record_handler(cf_client):
    """Test create DNS record handler forwards fields."""
    with patch.object(cf_client, "create_dns_record", new_callable=AsyncMock) as mock:
        mock.return_value = {"id": "r1", "type": "A", "name": "www", "content": "1.2.3.4"}
        out = await handlers.dns.create_dns_record(
            cf_client, zone_id="z1", type="A", name="www.example.com", content="1.2.3.4"
        )
    data = json.loads(out)
    assert data["record"]["id"] == "r1"
    mock.assert_awaited_once_with(
        zone_id="z1",
        type="A",
        name="www.example.com",
        content="1.2.3.4",
        ttl=None,
        proxied=None,
        priority=None,
        comment=None,
    )


@pytest.mark.asyncio
async def test_delete_dns_record_handler(cf_client):
    """Test delete DNS record handler."""
    with patch.object(cf_client, "delete_dns_record", new_callable=AsyncMock) as mock:
        mock.return_value = {"id": "r1"}
        out = await handlers.dns.delete_dns_record(cf_client, zone_id="z1", record_id="r1")
    assert json.loads(out)["deleted_record_id"] == "r1"


@pytest.mark.asyncio
async def test_list_workers_handler_uses_account(cf_client):
    """Test list workers handler resolves the account."""
    with patch.object(cf_client, "list_workers_scripts", new_callable=AsyncMock) as mock:
        mock.return_value = [{"id": "w1", "name": "my-worker"}]
        out = await handlers.workers.list_workers_scripts(cf_client)
    assert json.loads(out)["count"] == 1


@pytest.mark.asyncio
async def test_get_kv_value_handler(cf_client):
    """Test get KV value handler."""
    with patch.object(cf_client, "get_kv_value", new_callable=AsyncMock) as mock:
        mock.return_value = "hello"
        out = await handlers.kv.get_kv_value(cf_client, namespace_id="ns1", key_name="greeting")
    data = json.loads(out)
    assert data["value"] == "hello"


@pytest.mark.asyncio
async def test_put_kv_value_handler(cf_client):
    """Test put KV value handler."""
    with patch.object(cf_client, "put_kv_value", new_callable=AsyncMock) as mock:
        mock.return_value = {}
        out = await handlers.kv.put_kv_value(cf_client, namespace_id="ns1", key_name="k", value="v")
    assert json.loads(out)["written"] is True


@pytest.mark.asyncio
async def test_delete_r2_bucket_handler(cf_client):
    """Test delete R2 bucket handler."""
    with patch.object(cf_client, "delete_r2_bucket", new_callable=AsyncMock) as mock:
        mock.return_value = {"name": "old-bucket"}
        out = await handlers.r2.delete_r2_bucket(cf_client, bucket_name="old-bucket")
    assert json.loads(out)["deleted_bucket"] == "old-bucket"


# ── Plugin tests ───────────────────────────────────────────────


def test_plugin_registration():
    """Test the plugin is registered in the global registry."""
    from plugins import registry

    assert registry.is_registered("cloudflare")


def test_plugin_name_and_config_keys():
    """Test plugin identity and required keys."""
    assert CloudflarePlugin.get_plugin_name() == "cloudflare"
    assert CloudflarePlugin.get_required_config_keys() == ["api_token"]


def test_tool_specs_count_and_names():
    """Test all 25 tool specs are returned with unique names."""
    specs = CloudflarePlugin.get_tool_specifications()
    names = [s["name"] for s in specs]
    assert len(specs) == 25
    assert len(set(names)) == 25
    assert all(s["method_name"] == s["name"] for s in specs)


def test_tool_specs_scope_classification():
    """Test scope tiers: read / write / admin."""
    specs = CloudflarePlugin.get_tool_specifications()
    by_name = {s["name"]: s["scope"] for s in specs}
    assert set(by_name.values()) <= {"read", "write", "admin"}

    # All deletes are destructive → admin
    for name, scope in by_name.items():
        if name.startswith("delete_"):
            assert scope == "admin", f"{name} should be admin, got {scope}"

    # Non-destructive mutations → write
    for name in [
        "create_dns_record",
        "update_dns_record",
        "purge_cache",
        "create_kv_namespace",
        "put_kv_value",
        "create_r2_bucket",
    ]:
        assert by_name[name] == "write", name

    # Inventory/diagnostics → read
    for name in [
        "verify_token",
        "get_user",
        "list_accounts",
        "list_zones",
        "get_zone",
        "list_dns_records",
        "get_dns_record",
        "list_workers_scripts",
        "get_workers_script",
        "list_kv_namespaces",
        "list_kv_keys",
        "get_kv_value",
        "list_r2_buckets",
        "get_r2_bucket",
    ]:
        assert by_name[name] == "read", name


def test_required_params_present():
    """Test every tool schema requiring params declares them."""
    specs = CloudflarePlugin.get_tool_specifications()
    for s in specs:
        required = s["schema"].get("required", [])
        props = s["schema"].get("properties", {})
        for r in required:
            assert r in props, f"{s['name']} requires undeclared param {r}"


def test_plugin_delegates_to_handlers():
    """Test __getattr__ resolves handler functions."""
    import asyncio

    plugin = CloudflarePlugin({"api_token": "tok"})
    with patch.object(plugin.client, "verify_token", new_callable=AsyncMock) as mock:
        mock.return_value = {"id": "t", "status": "active"}
        result = asyncio.run(plugin.verify_token())
    assert '"status": "active"' in result


@pytest.mark.asyncio
async def test_health_check_success(cf_client):
    """Test health check with an active token."""
    plugin = CloudflarePlugin({"api_token": "tok"})
    plugin.client = cf_client
    with patch.object(cf_client, "verify_token", new_callable=AsyncMock) as mock:
        mock.return_value = {"id": "t1", "status": "active"}
        result = await plugin.health_check()
    assert result["healthy"] is True
    assert "active" in result["message"]


@pytest.mark.asyncio
async def test_health_check_failure(cf_client):
    """Test health check when verification raises."""
    plugin = CloudflarePlugin({"api_token": "tok"})
    plugin.client = cf_client
    with patch.object(cf_client, "verify_token", new_callable=AsyncMock) as mock:
        mock.side_effect = Exception("Invalid API Token")
        result = await plugin.health_check()
    assert result["healthy"] is False


@pytest.mark.asyncio
async def test_probe_credential_capabilities(cf_client):
    """Test credential probe reports a verified active token."""
    plugin = CloudflarePlugin({"api_token": "tok"})
    plugin.client = cf_client
    with patch.object(cf_client, "verify_token", new_callable=AsyncMock) as mock:
        mock.return_value = {"id": "t1", "status": "active"}
        result = await plugin.probe_credential_capabilities()
    assert result["probe_available"] is True
    assert result["granted"] == ["token_active"]
    assert result["source"] == "cloudflare_token_verify"


@pytest.mark.asyncio
async def test_probe_credential_capabilities_failure(cf_client):
    """Test credential probe degrades cleanly on failure."""
    plugin = CloudflarePlugin({"api_token": "tok"})
    plugin.client = cf_client
    with patch.object(cf_client, "verify_token", new_callable=AsyncMock) as mock:
        mock.side_effect = Exception("boom")
        result = await plugin.probe_credential_capabilities()
    assert result["probe_available"] is False
    assert result["granted"] == []


# ── Connection validation tests ────────────────────────────────


@pytest.mark.asyncio
async def test_validate_cloudflare_connection_success():
    """Test site connection validation with an active token."""
    from core.site_api import _validate_cloudflare_connection

    payload = {"success": True, "result": {"id": "t1", "status": "active"}}
    mock_response, mock_session = _mock_json_response(200, payload)

    with patch("core.site_api.aiohttp.ClientSession", return_value=mock_session):
        ok, msg = await _validate_cloudflare_connection({"api_token": "tok"})
    assert ok is True
    assert "t1" in msg


@pytest.mark.asyncio
async def test_validate_cloudflare_connection_bad_token():
    """Test site connection validation with an invalid token."""
    from core.site_api import _validate_cloudflare_connection

    payload = {
        "success": False,
        "errors": [{"code": 9109, "message": "Invalid API Token"}],
    }
    mock_response, mock_session = _mock_json_response(400, payload)

    with patch("core.site_api.aiohttp.ClientSession", return_value=mock_session):
        ok, msg = await _validate_cloudflare_connection({"api_token": "bad"})
    assert ok is False
    assert "Invalid API Token" in msg


@pytest.mark.asyncio
async def test_validate_cloudflare_connection_missing_token():
    """Test site connection validation with no token."""
    from core.site_api import _validate_cloudflare_connection

    ok, msg = await _validate_cloudflare_connection({})
    assert ok is False
    assert "Missing api_token" in msg


@pytest.mark.asyncio
async def test_validate_site_connection_routes_cloudflare():
    """Test validate_site_connection routes cloudflare to the token check."""
    from core.site_api import validate_site_connection

    payload = {"success": True, "result": {"id": "t1", "status": "active"}}
    mock_response, mock_session = _mock_json_response(200, payload)

    with patch("core.site_api.aiohttp.ClientSession", return_value=mock_session):
        ok, msg = await validate_site_connection(
            "cloudflare", "https://api.cloudflare.com", {"api_token": "tok"}
        )
    assert ok is True
    assert "active" in msg
    # Must NOT hit the generic static path (site URL + path)
    call_url = mock_session.get.call_args[0][0]
    assert call_url == "https://api.cloudflare.com/client/v4/user/tokens/verify"
