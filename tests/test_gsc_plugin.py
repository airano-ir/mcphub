"""Tests for the Google Search Console plugin.

Covers:
- GSCClient token refresh, API calls, error handling
- Property listing with permission levels
- Sitemap listing
- URL Inspection
- Search Analytics with bounded dimensions/date ranges
- Read-only enforcement (no write endpoints called)
- Multi-property isolation (cross-property URL rejection)
- Plugin registration and tool specifications
- Health check and credential probe
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from plugins.google_search_console.client import GSCClient
from plugins.google_search_console.plugin import GoogleSearchConsolePlugin

# ── Fixtures ───────────────────────────────────────────────────


@pytest.fixture
def gsc_client():
    """Create a GSCClient with a mock refresh token."""
    return GSCClient(refresh_token="mock_refresh_token")


@pytest.fixture
def mock_token_refresh():
    """Mock the OAuth token refresh to return a fake access token."""
    with patch.object(GSCClient, "_ensure_access_token", new_callable=AsyncMock) as mock:
        mock.return_value = "mock_access_token"
        yield mock


# ── Client tests ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_client_init():
    """Test GSCClient initialization."""
    client = GSCClient(refresh_token="token123")
    assert client.refresh_token == "token123"
    assert client._access_token is None
    assert client._expires_at == 0.0


@pytest.mark.asyncio
async def test_client_init_with_access_token():
    """Test GSCClient initialization with pre-existing access token."""
    client = GSCClient(
        refresh_token="token123",
        access_token="existing_token",
        token_expires_at="2099-01-01T00:00:00Z",
    )
    assert client._access_token == "existing_token"
    assert client._expires_at > 0


@pytest.mark.asyncio
async def test_token_refresh_no_env_vars(gsc_client):
    """Test that token refresh fails without GOOGLE_CLIENT_ID/SECRET env vars."""
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(Exception, match="GOOGLE_CLIENT_ID"):
            await gsc_client._ensure_access_token()


@pytest.mark.asyncio
async def test_token_refresh_success(gsc_client):
    """Test successful token refresh."""
    env_vars = {
        "GOOGLE_CLIENT_ID": "test_client_id",
        "GOOGLE_CLIENT_SECRET": "test_client_secret",
    }
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={"access_token": "new_token", "expires_in": 3600})

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_response)
    mock_ctx.__aexit__ = AsyncMock(return_value=None)

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.post = MagicMock(return_value=mock_ctx)

    with patch.dict("os.environ", env_vars):
        with patch(
            "plugins.google_search_console.client.aiohttp.ClientSession", return_value=mock_session
        ):
            token = await gsc_client._ensure_access_token()
            assert token == "new_token"
            assert gsc_client._access_token == "new_token"
            assert gsc_client._expires_at > 0


@pytest.mark.asyncio
async def test_token_refresh_failure(gsc_client):
    """Test token refresh failure with HTTP error."""
    env_vars = {
        "GOOGLE_CLIENT_ID": "test_client_id",
        "GOOGLE_CLIENT_SECRET": "test_client_secret",
    }
    mock_response = MagicMock()
    mock_response.status = 400
    mock_response.text = AsyncMock(return_value='{"error": "invalid_grant"}')

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_response)
    mock_ctx.__aexit__ = AsyncMock(return_value=None)

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.post = MagicMock(return_value=mock_ctx)

    with patch.dict("os.environ", env_vars):
        with patch(
            "plugins.google_search_console.client.aiohttp.ClientSession", return_value=mock_session
        ):
            with pytest.raises(Exception, match="GSC token refresh failed"):
                await gsc_client._ensure_access_token()


# ── Property listing tests ────────────────────────────────────


@pytest.mark.asyncio
async def test_list_properties(gsc_client, mock_token_refresh):
    """Test listing Search Console properties."""
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(
        return_value={
            "siteEntry": [
                {
                    "siteUrl": "sc-domain:example.com",
                    "permissionLevel": "siteOwner",
                },
                {
                    "siteUrl": "https://blog.example.com/",
                    "permissionLevel": "siteFullUser",
                },
            ]
        }
    )

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_response)
    mock_ctx.__aexit__ = AsyncMock(return_value=None)

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.request = MagicMock(return_value=mock_ctx)

    with patch(
        "plugins.google_search_console.client.aiohttp.ClientSession", return_value=mock_session
    ):
        from plugins.google_search_console.handlers.properties import list_properties

        result_str = await list_properties(gsc_client)
        result = json.loads(result_str)

        assert result["success"] is True
        assert result["count"] == 2
        assert result["properties"][0]["site_url"] == "sc-domain:example.com"
        assert result["properties"][0]["type"] == "domain"
        assert result["properties"][1]["site_url"] == "https://blog.example.com/"
        assert result["properties"][1]["type"] == "url-prefix"


@pytest.mark.asyncio
async def test_list_properties_empty(gsc_client, mock_token_refresh):
    """Test listing properties when user has no properties."""
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={"siteEntry": []})

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_response)
    mock_ctx.__aexit__ = AsyncMock(return_value=None)

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.request = MagicMock(return_value=mock_ctx)

    with patch(
        "plugins.google_search_console.client.aiohttp.ClientSession", return_value=mock_session
    ):
        from plugins.google_search_console.handlers.properties import list_properties

        result_str = await list_properties(gsc_client)
        result = json.loads(result_str)

        assert result["success"] is True
        assert result["count"] == 0
        assert result["properties"] == []


# ── Sitemap listing tests ─────────────────────────────────────


@pytest.mark.asyncio
async def test_list_sitemaps(gsc_client, mock_token_refresh):
    """Test listing sitemaps for a property."""
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(
        return_value={
            "sitemap": [
                {
                    "path": "https://example.com/sitemap.xml",
                    "lastSubmitted": "2024-01-15T10:00:00Z",
                    "isPending": False,
                    "isErrors": False,
                    "errors": 0,
                    "warnings": 2,
                    "type": "sitemap",
                },
            ]
        }
    )

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_response)
    mock_ctx.__aexit__ = AsyncMock(return_value=None)

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.request = MagicMock(return_value=mock_ctx)

    with patch(
        "plugins.google_search_console.client.aiohttp.ClientSession", return_value=mock_session
    ):
        from plugins.google_search_console.handlers.sitemaps import list_sitemaps

        result_str = await list_sitemaps(gsc_client, "sc-domain:example.com")
        result = json.loads(result_str)

        assert result["success"] is True
        assert result["site_url"] == "sc-domain:example.com"
        assert result["count"] == 1
        assert result["total_errors"] == 0
        assert result["total_warnings"] == 2
        assert result["sitemaps"][0]["path"] == "https://example.com/sitemap.xml"


# ── URL Inspection tests ─────────────────────────────────────


@pytest.mark.asyncio
async def test_inspect_url(gsc_client, mock_token_refresh):
    """Test URL inspection."""
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(
        return_value={
            "inspectionResult": {
                "indexStatusResult": {
                    "verdict": "PASS",
                    "indexingState": "INDEXED",
                    "lastCrawlTime": "2024-01-20T12:00:00Z",
                    "googleCanonical": "https://example.com/page",
                    "userCanonical": "https://example.com/page",
                    "robotsTxtState": "ALLOWED",
                    "pageFetchState": "SUCCESSFUL",
                },
                "mobileUsabilityResult": {"verdict": "PASS"},
                "richResultsResult": {"verdict": "PASS"},
            }
        }
    )

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_response)
    mock_ctx.__aexit__ = AsyncMock(return_value=None)

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.post = MagicMock(return_value=mock_ctx)

    with patch(
        "plugins.google_search_console.client.aiohttp.ClientSession", return_value=mock_session
    ):
        from plugins.google_search_console.handlers.url_inspection import inspect_url

        result_str = await inspect_url(
            gsc_client,
            site_url="sc-domain:example.com",
            inspection_url="https://example.com/page",
        )
        result = json.loads(result_str)

        assert result["success"] is True
        assert result["verdict"] == "PASS"
        assert result["indexing_state"] == "INDEXED"
        assert result["last_crawl_time"] == "2024-01-20T12:00:00Z"
        assert result["mobile_usability"] == "PASS"
        assert result["rich_results"] == "PASS"


@pytest.mark.asyncio
async def test_inspect_url_cross_property_rejected(gsc_client, mock_token_refresh):
    """Test that cross-property URL inspection returns an error from the API."""
    mock_response = MagicMock()
    mock_response.status = 400
    mock_response.json = AsyncMock(
        return_value={
            "error": {
                "message": "The inspection URL must be under the property's scope",
                "code": 400,
            }
        }
    )

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_response)
    mock_ctx.__aexit__ = AsyncMock(return_value=None)

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.post = MagicMock(return_value=mock_ctx)

    with patch(
        "plugins.google_search_console.client.aiohttp.ClientSession", return_value=mock_session
    ):
        from plugins.google_search_console.handlers.url_inspection import inspect_url

        with pytest.raises(Exception, match="GSC URL Inspection error"):
            await inspect_url(
                gsc_client,
                site_url="sc-domain:example.com",
                inspection_url="https://other.com/page",
            )


# ── Search Analytics tests ───────────────────────────────────


@pytest.mark.asyncio
async def test_search_analytics(gsc_client, mock_token_refresh):
    """Test Search Analytics query."""
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(
        return_value={
            "rows": [
                {
                    "keys": ["how to bake bread"],
                    "clicks": 150,
                    "impressions": 3200,
                    "ctr": 0.046875,
                    "position": 3.5,
                },
                {
                    "keys": ["bread recipes"],
                    "clicks": 80,
                    "impressions": 2100,
                    "ctr": 0.0380952,
                    "position": 5.2,
                },
            ]
        }
    )

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_response)
    mock_ctx.__aexit__ = AsyncMock(return_value=None)

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.post = MagicMock(return_value=mock_ctx)

    with patch(
        "plugins.google_search_console.client.aiohttp.ClientSession", return_value=mock_session
    ):
        from plugins.google_search_console.handlers.analytics import search_analytics

        result_str = await search_analytics(
            gsc_client,
            site_url="sc-domain:example.com",
            start_date="2024-01-01",
            end_date="2024-01-31",
            dimensions=["query"],
        )
        result = json.loads(result_str)

        assert result["success"] is True
        assert result["row_count"] == 2
        assert result["total_clicks"] == 230
        assert result["total_impressions"] == 5300
        assert result["dimensions"] == ["query"]


@pytest.mark.asyncio
async def test_search_analytics_invalid_dimension(gsc_client, mock_token_refresh):
    """Test that invalid dimensions are rejected before the API call."""
    from plugins.google_search_console.handlers.analytics import search_analytics

    result_str = await search_analytics(
        gsc_client,
        site_url="sc-domain:example.com",
        start_date="2024-01-01",
        end_date="2024-01-31",
        dimensions=["invalid_dim"],
    )
    result = json.loads(result_str)

    assert result["success"] is False
    assert "Invalid dimensions" in result["error"]


@pytest.mark.asyncio
async def test_search_analytics_invalid_type_filter(gsc_client, mock_token_refresh):
    """Test that invalid search type is rejected."""
    from plugins.google_search_console.handlers.analytics import search_analytics

    result_str = await search_analytics(
        gsc_client,
        site_url="sc-domain:example.com",
        start_date="2024-01-01",
        end_date="2024-01-31",
        type_filter="invalid_type",
    )
    result = json.loads(result_str)

    assert result["success"] is False
    assert "Invalid type_filter" in result["error"]


# ── Plugin registration and tool spec tests ───────────────────


def test_plugin_registration():
    """Test that the GSC plugin is properly registered."""
    from plugins import registry

    assert registry.is_registered("google_search_console")
    assert registry._plugin_classes["google_search_console"] is GoogleSearchConsolePlugin


def test_plugin_name():
    """Test plugin name."""
    assert GoogleSearchConsolePlugin.get_plugin_name() == "google_search_console"


def test_required_config_keys():
    """Test required configuration keys."""
    keys = GoogleSearchConsolePlugin.get_required_config_keys()
    assert keys == ["refresh_token"]


def test_tool_specifications():
    """Test that tool specifications are complete."""
    specs = GoogleSearchConsolePlugin.get_tool_specifications()
    tool_names = [s["name"] for s in specs]

    # All required tools from issue #137
    assert "list_properties" in tool_names
    assert "list_sitemaps" in tool_names
    assert "inspect_url" in tool_names
    assert "search_analytics" in tool_names

    # All tools must be read-only
    for spec in specs:
        assert spec["scope"] == "read", f"Tool {spec['name']} is not read-only"
        assert spec["category"] == "read", f"Tool {spec['name']} category is not read"


def test_tool_specifications_count():
    """Test that we have exactly 4 tool specifications."""
    specs = GoogleSearchConsolePlugin.get_tool_specifications()
    assert len(specs) == 4


def test_tool_schemas_require_property():
    """Test that property-dependent tools require a site_url parameter."""
    specs = GoogleSearchConsolePlugin.get_tool_specifications()

    for spec in specs:
        if spec["name"] == "list_properties":
            # list_properties doesn't need a site_url
            continue
        schema = spec["schema"]
        assert "site_url" in schema.get(
            "properties", {}
        ), f"Tool {spec['name']} missing site_url parameter"
        assert "site_url" in schema.get(
            "required", []
        ), f"Tool {spec['name']} does not require site_url"


# ── Read-only enforcement tests ───────────────────────────────


def test_client_has_no_write_methods():
    """Test that GSCClient does not expose any write methods.

    The GSC API uses POST for URL Inspection and Search Analytics,
    but these are read-only operations (they query data, they don't
    modify it). This test verifies that no mutating methods exist.
    """
    client = GSCClient(refresh_token="token")
    # These methods should NOT exist
    assert not hasattr(client, "submit_sitemap")
    assert not hasattr(client, "delete_sitemap")
    assert not hasattr(client, "request_indexing")
    assert not hasattr(client, "start_validation")
    assert not hasattr(client, "remove_url")
    assert not hasattr(client, "update_site")


def test_all_tool_specs_are_read_scope():
    """Test that all tool specs have scope=read (no write tools)."""
    specs = GoogleSearchConsolePlugin.get_tool_specifications()
    for spec in specs:
        assert spec.get("scope") == "read"
        assert spec.get("category") == "read"


# ── Plugin instance tests ─────────────────────────────────────


def test_plugin_init():
    """Test plugin initialization with config."""
    config = {"refresh_token": "test_token"}
    plugin = GoogleSearchConsolePlugin(config)
    assert plugin.client.refresh_token == "test_token"


def test_plugin_init_with_access_token():
    """Test plugin initialization with pre-existing access token."""
    config = {
        "refresh_token": "test_token",
        "access_token": "existing_token",
        "token_expires_at": "2099-01-01T00:00:00Z",
    }
    plugin = GoogleSearchConsolePlugin(config)
    assert plugin.client._access_token == "existing_token"


@pytest.mark.asyncio
async def test_health_check_success():
    """Test health check when API is accessible."""
    config = {"refresh_token": "test_token"}
    plugin = GoogleSearchConsolePlugin(config)

    with patch.object(GSCClient, "list_sites", new_callable=AsyncMock) as mock:
        mock.return_value = {"siteEntry": [{"siteUrl": "sc-domain:example.com"}]}
        result = await plugin.health_check()
        assert result["healthy"] is True
        assert "1 properties" in result["message"]


@pytest.mark.asyncio
async def test_health_check_failure():
    """Test health check when API is not accessible."""
    config = {"refresh_token": "test_token"}
    plugin = GoogleSearchConsolePlugin(config)

    with patch.object(GSCClient, "list_sites", new_callable=AsyncMock) as mock:
        mock.side_effect = Exception("Token refresh failed")
        result = await plugin.health_check()
        assert result["healthy"] is False
        assert "GSC health check failed" in result["message"]


@pytest.mark.asyncio
async def test_probe_credential_capabilities_success():
    """Test credential probe when API is accessible."""
    config = {"refresh_token": "test_token"}
    plugin = GoogleSearchConsolePlugin(config)

    with patch.object(GSCClient, "list_sites", new_callable=AsyncMock) as mock:
        mock.return_value = {"siteEntry": [{"siteUrl": "sc-domain:example.com"}]}
        result = await plugin.probe_credential_capabilities()
        assert result["probe_available"] is True
        assert "gsc.read" in result["granted"]
        assert result["source"] == "gsc_oauth_scope"


@pytest.mark.asyncio
async def test_probe_credential_capabilities_failure():
    """Test credential probe when API is not accessible."""
    config = {"refresh_token": "test_token"}
    plugin = GoogleSearchConsolePlugin(config)

    with patch.object(GSCClient, "list_sites", new_callable=AsyncMock) as mock:
        mock.side_effect = Exception("invalid_grant")
        result = await plugin.probe_credential_capabilities()
        assert result["probe_available"] is False
        assert result["granted"] == []
        assert "sites_list_failed" in result["reason"]


# ── Dynamic method delegation test ────────────────────────────


@pytest.mark.asyncio
async def test_plugin_method_delegation():
    """Test that the plugin delegates method calls to handler modules."""
    config = {"refresh_token": "test_token"}
    plugin = GoogleSearchConsolePlugin(config)

    # The plugin should have list_properties method via __getattr__
    assert hasattr(plugin, "list_properties")
    assert hasattr(plugin, "list_sitemaps")
    assert hasattr(plugin, "inspect_url")
    assert hasattr(plugin, "search_analytics")


def test_plugin_getattr_not_found():
    """Test that accessing a non-existent method raises AttributeError."""
    config = {"refresh_token": "test_token"}
    plugin = GoogleSearchConsolePlugin(config)

    with pytest.raises(AttributeError, match="has no attribute 'nonexistent_method'"):
        plugin.nonexistent_method  # noqa: B018
