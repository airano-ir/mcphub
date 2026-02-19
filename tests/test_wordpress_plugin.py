"""Tests for WordPress Plugin (plugins/wordpress/).

Integration tests covering plugin initialization, configuration validation,
tool specifications, handler delegation, client behavior, and health checks.
"""

import asyncio
import base64
import json
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from plugins.base import BasePlugin, PluginRegistry
from plugins.wordpress.client import (
    AuthenticationError,
    ConfigurationError,
    ConnectionError,
    WordPressClient,
)
from plugins.wordpress.plugin import WordPressPlugin

# --- WordPressClient Tests ---


class TestWordPressClientInit:
    """Test WordPressClient initialization and validation."""

    def test_valid_initialization(self):
        """Should initialize with valid credentials."""
        client = WordPressClient(
            site_url="https://example.com",
            username="admin",
            app_password="xxxx xxxx xxxx xxxx",
        )
        assert client.site_url == "https://example.com"
        assert client.api_base == "https://example.com/wp-json/wp/v2"
        assert client.wc_api_base == "https://example.com/wp-json/wc/v3"
        assert client.username == "admin"

    def test_trailing_slash_stripped(self):
        """Should strip trailing slash from site URL."""
        client = WordPressClient(
            site_url="https://example.com/",
            username="admin",
            app_password="xxxx",
        )
        assert client.site_url == "https://example.com"
        assert client.api_base == "https://example.com/wp-json/wp/v2"

    def test_auth_header_created(self):
        """Should create proper Basic auth header."""
        client = WordPressClient(
            site_url="https://example.com",
            username="admin",
            app_password="secret123",
        )
        expected_token = base64.b64encode(b"admin:secret123").decode()
        assert client.auth_header == f"Basic {expected_token}"

    def test_missing_url_raises(self):
        """Should raise ConfigurationError for empty URL."""
        with pytest.raises(ConfigurationError, match="Site URL is not configured"):
            WordPressClient(site_url="", username="admin", app_password="xxxx")

    def test_missing_username_raises(self):
        """Should raise ConfigurationError for empty username."""
        with pytest.raises(ConfigurationError, match="Username is not configured"):
            WordPressClient(site_url="https://example.com", username="", app_password="xxxx")

    def test_missing_password_raises(self):
        """Should raise ConfigurationError for empty app password."""
        with pytest.raises(ConfigurationError, match="App password is not configured"):
            WordPressClient(site_url="https://example.com", username="admin", app_password="")

    def test_none_url_raises(self):
        """Should raise ConfigurationError for None URL."""
        with pytest.raises(ConfigurationError):
            WordPressClient(site_url=None, username="admin", app_password="xxxx")


class TestWordPressClientErrorParsing:
    """Test error response parsing."""

    @pytest.fixture
    def client(self):
        return WordPressClient(
            site_url="https://example.com",
            username="admin",
            app_password="xxxx",
        )

    def test_parse_json_error(self, client):
        """Should parse JSON error responses."""
        error_text = json.dumps(
            {"code": "rest_forbidden", "message": "Sorry, you are not allowed."}
        )
        result = client._parse_error_response(403, error_text)
        assert result["error_code"] == "ACCESS_DENIED"
        assert result["status_code"] == 403
        assert result["wp_error_code"] == "rest_forbidden"

    def test_parse_non_json_error(self, client):
        """Should handle non-JSON error responses."""
        result = client._parse_error_response(500, "Internal Server Error")
        assert result["error_code"] == "SERVER_ERROR"
        assert result["wp_error_code"] == "unknown_error"

    def test_parse_auth_error(self, client):
        """Should provide auth-specific error messages."""
        error_text = json.dumps({"code": "invalid_auth", "message": "Bad credentials"})
        result = client._parse_error_response(401, error_text)
        assert result["error_code"] == "AUTH_FAILED"
        assert "Authentication failed" in result["message"]
        assert "Application Password" in result["message"]

    def test_parse_woocommerce_auth_error(self, client):
        """Should provide WooCommerce-specific auth error."""
        error_text = json.dumps({"code": "wc_auth", "message": "No permission"})
        result = client._parse_error_response(401, error_text, use_woocommerce=True)
        assert "WooCommerce" in result["message"]
        assert "manage_woocommerce" in result["message"]

    def test_parse_404_error(self, client):
        """Should parse 404 errors correctly."""
        error_text = json.dumps({"code": "rest_no_route", "message": "No route found"})
        result = client._parse_error_response(404, error_text)
        assert result["error_code"] == "NOT_FOUND"
        assert "not found" in result["message"].lower()

    def test_parse_400_error_with_hints(self, client):
        """Should provide parameter hints for 400 errors."""
        error_text = json.dumps({"code": "rest_invalid_param", "message": "Invalid param"})
        result = client._parse_error_response(400, error_text)
        assert result["error_code"] == "BAD_REQUEST"
        assert "Hints" in result["message"]

    def test_raw_response_truncated(self, client):
        """Should truncate raw response to 500 chars."""
        error_text = "x" * 1000
        result = client._parse_error_response(500, error_text)
        assert len(result["raw_response"]) == 500

    def test_unknown_status_code(self, client):
        """Should handle unknown HTTP status codes."""
        result = client._parse_error_response(418, "I'm a teapot")
        assert result["error_code"] == "HTTP_418"


class TestWordPressClientRequest:
    """Test HTTP request methods."""

    @pytest.fixture
    def client(self):
        return WordPressClient(
            site_url="https://example.com",
            username="admin",
            app_password="xxxx",
        )

    @pytest.mark.asyncio
    async def test_request_filters_none_params(self, client):
        """Should filter None and empty values from params."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"id": 1})

        mock_session = AsyncMock()
        mock_session.request = MagicMock(
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_response),
                __aexit__=AsyncMock(return_value=False),
            )
        )

        with patch("aiohttp.ClientSession") as mock_cls:
            mock_cls.return_value = AsyncMock(
                __aenter__=AsyncMock(return_value=mock_session),
                __aexit__=AsyncMock(return_value=False),
            )

            result = await client.request(
                "GET",
                "posts",
                params={"status": "publish", "search": None, "tags": "", "ids": []},
            )
            assert result == {"id": 1}

            # Verify filtered params
            call_kwargs = mock_session.request.call_args
            filtered_params = call_kwargs.kwargs.get("params") or call_kwargs[1].get("params", {})
            if filtered_params:
                assert "search" not in filtered_params
                assert "tags" not in filtered_params
                assert "ids" not in filtered_params

    @pytest.mark.asyncio
    async def test_request_raises_on_401(self, client):
        """Should raise AuthenticationError on 401."""
        mock_response = AsyncMock()
        mock_response.status = 401
        mock_response.text = AsyncMock(
            return_value=json.dumps({"code": "invalid_auth", "message": "Bad creds"})
        )

        mock_session = AsyncMock()
        mock_session.request = MagicMock(
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_response),
                __aexit__=AsyncMock(return_value=False),
            )
        )

        with patch("aiohttp.ClientSession") as mock_cls:
            mock_cls.return_value = AsyncMock(
                __aenter__=AsyncMock(return_value=mock_session),
                __aexit__=AsyncMock(return_value=False),
            )

            with pytest.raises(AuthenticationError):
                await client.request("GET", "posts")

    @pytest.mark.asyncio
    async def test_request_raises_on_500(self, client):
        """Should raise Exception on 500."""
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.text = AsyncMock(return_value="Internal Server Error")

        mock_session = AsyncMock()
        mock_session.request = MagicMock(
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_response),
                __aexit__=AsyncMock(return_value=False),
            )
        )

        with patch("aiohttp.ClientSession") as mock_cls:
            mock_cls.return_value = AsyncMock(
                __aenter__=AsyncMock(return_value=mock_session),
                __aexit__=AsyncMock(return_value=False),
            )

            with pytest.raises(Exception, match="SERVER_ERROR"):
                await client.request("GET", "posts")

    @pytest.mark.asyncio
    async def test_get_convenience_method(self, client):
        """GET method should delegate to request."""
        client.request = AsyncMock(return_value={"posts": []})
        result = await client.get("posts", params={"per_page": 10})
        client.request.assert_called_once_with(
            "GET",
            "posts",
            params={"per_page": 10},
            use_custom_namespace=False,
            use_woocommerce=False,
        )
        assert result == {"posts": []}

    @pytest.mark.asyncio
    async def test_post_convenience_method(self, client):
        """POST method should delegate to request."""
        client.request = AsyncMock(return_value={"id": 1})
        result = await client.post("posts", json_data={"title": "Test"})
        client.request.assert_called_once()
        assert result == {"id": 1}

    @pytest.mark.asyncio
    async def test_delete_convenience_method(self, client):
        """DELETE method should delegate to request."""
        client.request = AsyncMock(return_value={"deleted": True})
        result = await client.delete("posts/1", params={"force": True})
        client.request.assert_called_once()
        assert result == {"deleted": True}

    @pytest.mark.asyncio
    async def test_woocommerce_url(self, client):
        """WooCommerce requests should use wc/v3 base."""
        client.request = AsyncMock(return_value={"available": True})
        await client.get("products", use_woocommerce=True)
        client.request.assert_called_once_with(
            "GET",
            "products",
            params=None,
            use_custom_namespace=False,
            use_woocommerce=True,
        )


# --- Connection Error Tests ---


class TestWordPressClientConnectionErrors:
    """Test network error differentiation and retry logic."""

    @pytest.fixture
    def client(self):
        return WordPressClient(
            site_url="https://example.com",
            username="admin",
            app_password="xxxx",
        )

    @pytest.mark.asyncio
    async def test_dns_error_raises_connection_error(self, client):
        """DNS failure should raise ConnectionError with helpful message."""
        dns_error = aiohttp.ClientConnectorDNSError(
            connection_key=MagicMock(), os_error=OSError("Name resolution failed")
        )
        with patch("aiohttp.ClientSession") as mock_cls:
            mock_session = AsyncMock()
            mock_session.request = MagicMock(side_effect=dns_error)
            mock_cls.return_value = AsyncMock(
                __aenter__=AsyncMock(return_value=mock_session),
                __aexit__=AsyncMock(return_value=False),
            )
            with pytest.raises(ConnectionError, match="DNS resolution failed"):
                await client.request("GET", "posts")

    @pytest.mark.asyncio
    async def test_ssl_error_raises_connection_error(self, client):
        """SSL certificate error should raise ConnectionError with helpful message."""
        ssl_error = aiohttp.ClientConnectorCertificateError(
            connection_key=MagicMock(), certificate_error=Exception("cert expired")
        )
        with patch("aiohttp.ClientSession") as mock_cls:
            mock_session = AsyncMock()
            mock_session.request = MagicMock(side_effect=ssl_error)
            mock_cls.return_value = AsyncMock(
                __aenter__=AsyncMock(return_value=mock_session),
                __aexit__=AsyncMock(return_value=False),
            )
            with pytest.raises(ConnectionError, match="SSL certificate error"):
                await client.request("GET", "posts")

    @pytest.mark.asyncio
    async def test_connection_refused_raises_connection_error(self, client):
        """Connection refused should raise ConnectionError with helpful message."""
        conn_error = aiohttp.ClientConnectorError(
            connection_key=MagicMock(), os_error=OSError("Connection refused")
        )
        with patch("aiohttp.ClientSession") as mock_cls:
            mock_session = AsyncMock()
            mock_session.request = MagicMock(side_effect=conn_error)
            mock_cls.return_value = AsyncMock(
                __aenter__=AsyncMock(return_value=mock_session),
                __aexit__=AsyncMock(return_value=False),
            )
            with pytest.raises(ConnectionError, match="Cannot connect"):
                await client.request("GET", "posts")

    @pytest.mark.asyncio
    async def test_timeout_retries_then_raises(self, client):
        """Timeout should retry then raise ConnectionError."""
        with patch("aiohttp.ClientSession") as mock_cls:
            mock_session = AsyncMock()
            mock_session.request = MagicMock(side_effect=TimeoutError())
            mock_cls.return_value = AsyncMock(
                __aenter__=AsyncMock(return_value=mock_session),
                __aexit__=AsyncMock(return_value=False),
            )
            with patch("asyncio.sleep", new_callable=AsyncMock):
                with pytest.raises(ConnectionError, match="timed out"):
                    await client.request("GET", "posts")

    @pytest.mark.asyncio
    async def test_invalid_url_raises_connection_error(self, client):
        """Invalid URL should raise ConnectionError."""
        with patch("aiohttp.ClientSession") as mock_cls:
            mock_session = AsyncMock()
            mock_session.request = MagicMock(side_effect=aiohttp.InvalidURL("bad url"))
            mock_cls.return_value = AsyncMock(
                __aenter__=AsyncMock(return_value=mock_session),
                __aexit__=AsyncMock(return_value=False),
            )
            with pytest.raises(ConnectionError, match="Invalid URL"):
                await client.request("GET", "posts")

    @pytest.mark.asyncio
    async def test_auth_error_not_retried(self, client):
        """Auth errors should NOT be retried."""
        mock_response = AsyncMock()
        mock_response.status = 401
        mock_response.text = AsyncMock(
            return_value=json.dumps({"code": "invalid_auth", "message": "Bad"})
        )

        mock_session = AsyncMock()
        mock_session.request = MagicMock(
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_response),
                __aexit__=AsyncMock(return_value=False),
            )
        )

        with patch("aiohttp.ClientSession") as mock_cls:
            mock_cls.return_value = AsyncMock(
                __aenter__=AsyncMock(return_value=mock_session),
                __aexit__=AsyncMock(return_value=False),
            )
            with pytest.raises(AuthenticationError):
                await client.request("GET", "posts")
            # Should be called only once (no retry)
            assert mock_session.request.call_count == 1

    @pytest.mark.asyncio
    async def test_502_retried_then_raises(self, client):
        """502 errors should be retried before raising."""
        mock_response = AsyncMock()
        mock_response.status = 502
        mock_response.text = AsyncMock(return_value="Bad Gateway")

        mock_session = AsyncMock()
        mock_session.request = MagicMock(
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_response),
                __aexit__=AsyncMock(return_value=False),
            )
        )

        with patch("aiohttp.ClientSession") as mock_cls:
            mock_cls.return_value = AsyncMock(
                __aenter__=AsyncMock(return_value=mock_session),
                __aexit__=AsyncMock(return_value=False),
            )
            with patch("asyncio.sleep", new_callable=AsyncMock):
                with pytest.raises(Exception, match="BAD_GATEWAY"):
                    await client.request("GET", "posts")
                # Should be called 3 times (1 + 2 retries)
                assert mock_session.request.call_count == 3


class TestWordPressClientHealthCheck:
    """Test site health check with error differentiation."""

    @pytest.fixture
    def client(self):
        return WordPressClient(
            site_url="https://example.com",
            username="admin",
            app_password="xxxx",
        )

    @pytest.mark.asyncio
    async def test_healthy_site(self, client):
        """Healthy site should return proper status."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "name": "My Blog",
                "description": "A blog",
                "url": "https://example.com",
                "routes": {"a": 1},
            }
        )

        with patch("aiohttp.ClientSession") as mock_cls:
            mock_session = AsyncMock()
            mock_session.get = MagicMock(
                return_value=AsyncMock(
                    __aenter__=AsyncMock(return_value=mock_response),
                    __aexit__=AsyncMock(return_value=False),
                )
            )
            mock_cls.return_value = AsyncMock(
                __aenter__=AsyncMock(return_value=mock_session),
                __aexit__=AsyncMock(return_value=False),
            )
            result = await client.check_site_health()
            assert result["healthy"] is True
            assert result["name"] == "My Blog"

    @pytest.mark.asyncio
    async def test_rest_api_disabled_detected(self, client):
        """403/404 on /wp-json should detect REST API disabled."""
        for status in (403, 404):
            mock_response = AsyncMock()
            mock_response.status = status

            with patch("aiohttp.ClientSession") as mock_cls:
                mock_session = AsyncMock()
                mock_session.get = MagicMock(
                    return_value=AsyncMock(
                        __aenter__=AsyncMock(return_value=mock_response),
                        __aexit__=AsyncMock(return_value=False),
                    )
                )
                mock_cls.return_value = AsyncMock(
                    __aenter__=AsyncMock(return_value=mock_session),
                    __aexit__=AsyncMock(return_value=False),
                )
                result = await client.check_site_health()
                assert result["healthy"] is False
                assert result["accessible"] is True
                assert result["error_type"] == "rest_api_disabled"
                assert "REST API" in result["message"]

    @pytest.mark.asyncio
    async def test_dns_failure_in_health_check(self, client):
        """DNS failure in health check should be detected."""
        dns_error = aiohttp.ClientConnectorDNSError(
            connection_key=MagicMock(), os_error=OSError("DNS failed")
        )
        with patch("aiohttp.ClientSession") as mock_cls:
            mock_session = AsyncMock()
            mock_session.get = MagicMock(side_effect=dns_error)
            mock_cls.return_value = AsyncMock(
                __aenter__=AsyncMock(return_value=mock_session),
                __aexit__=AsyncMock(return_value=False),
            )
            result = await client.check_site_health()
            assert result["healthy"] is False
            assert result["error_type"] == "dns_failure"
            assert "DNS" in result["message"]

    @pytest.mark.asyncio
    async def test_timeout_in_health_check(self, client):
        """Timeout in health check should be detected."""
        with patch("aiohttp.ClientSession") as mock_cls:
            mock_session = AsyncMock()
            mock_session.get = MagicMock(side_effect=TimeoutError())
            mock_cls.return_value = AsyncMock(
                __aenter__=AsyncMock(return_value=mock_session),
                __aexit__=AsyncMock(return_value=False),
            )
            result = await client.check_site_health()
            assert result["healthy"] is False
            assert result["error_type"] == "timeout"

    @pytest.mark.asyncio
    async def test_ssl_error_in_health_check(self, client):
        """SSL error in health check should be detected."""
        ssl_error = aiohttp.ClientConnectorCertificateError(
            connection_key=MagicMock(), certificate_error=Exception("expired")
        )
        with patch("aiohttp.ClientSession") as mock_cls:
            mock_session = AsyncMock()
            mock_session.get = MagicMock(side_effect=ssl_error)
            mock_cls.return_value = AsyncMock(
                __aenter__=AsyncMock(return_value=mock_session),
                __aexit__=AsyncMock(return_value=False),
            )
            result = await client.check_site_health()
            assert result["healthy"] is False
            assert result["error_type"] == "ssl_error"

    @pytest.mark.asyncio
    async def test_connection_refused_in_health_check(self, client):
        """Connection refused in health check should be detected."""
        conn_error = aiohttp.ClientConnectorError(
            connection_key=MagicMock(), os_error=OSError("Connection refused")
        )
        with patch("aiohttp.ClientSession") as mock_cls:
            mock_session = AsyncMock()
            mock_session.get = MagicMock(side_effect=conn_error)
            mock_cls.return_value = AsyncMock(
                __aenter__=AsyncMock(return_value=mock_session),
                __aexit__=AsyncMock(return_value=False),
            )
            result = await client.check_site_health()
            assert result["healthy"] is False
            assert result["error_type"] == "connection_refused"


# --- WordPressPlugin Tests ---


class TestWordPressPluginInit:
    """Test WordPress plugin initialization."""

    VALID_CONFIG = {
        "url": "https://example.com",
        "username": "admin",
        "app_password": "xxxx xxxx xxxx xxxx",
    }

    def test_create_with_valid_config(self):
        """Should initialize with all required config keys."""
        plugin = WordPressPlugin(self.VALID_CONFIG)
        assert plugin.project_id is not None
        assert plugin.client is not None
        assert isinstance(plugin, BasePlugin)

    def test_handlers_initialized(self):
        """Should initialize all core handlers."""
        plugin = WordPressPlugin(self.VALID_CONFIG)
        assert plugin.posts is not None
        assert plugin.media is not None
        assert plugin.taxonomy is not None
        assert plugin.comments is not None
        assert plugin.users is not None
        assert plugin.site is not None
        assert plugin.seo is not None
        assert plugin.menus is not None

    def test_wp_cli_none_without_container(self):
        """WP-CLI handler should be None without container config."""
        plugin = WordPressPlugin(self.VALID_CONFIG)
        assert plugin.wp_cli is None

    def test_missing_url_raises(self):
        """Should raise ValueError for missing URL."""
        config = {"username": "admin", "app_password": "xxxx"}
        with pytest.raises(ValueError, match="Missing required configuration"):
            WordPressPlugin(config)

    def test_missing_username_raises(self):
        """Should raise ValueError for missing username."""
        config = {"url": "https://example.com", "app_password": "xxxx"}
        with pytest.raises(ValueError, match="Missing required configuration"):
            WordPressPlugin(config)

    def test_missing_password_raises(self):
        """Should raise ValueError for missing app_password."""
        config = {"url": "https://example.com", "username": "admin"}
        with pytest.raises(ValueError, match="Missing required configuration"):
            WordPressPlugin(config)

    def test_custom_project_id(self):
        """Should accept custom project_id."""
        plugin = WordPressPlugin(self.VALID_CONFIG, project_id="wp_myblog")
        assert plugin.project_id == "wp_myblog"

    def test_auto_generated_project_id(self):
        """Should auto-generate project_id from config."""
        plugin = WordPressPlugin(self.VALID_CONFIG)
        assert plugin.project_id.startswith("wordpress")

    def test_plugin_name(self):
        """Should return 'wordpress' as plugin name."""
        assert WordPressPlugin.get_plugin_name() == "wordpress"

    def test_required_config_keys(self):
        """Should require url, username, app_password."""
        keys = WordPressPlugin.get_required_config_keys()
        assert "url" in keys
        assert "username" in keys
        assert "app_password" in keys


class TestWordPressToolSpecifications:
    """Test tool specification generation."""

    def test_specs_not_empty(self):
        """Should return non-empty tool specifications."""
        specs = WordPressPlugin.get_tool_specifications()
        assert len(specs) > 0

    def test_specs_count(self):
        """Should return at least 65 tool specs (65 documented + possible additions)."""
        specs = WordPressPlugin.get_tool_specifications()
        assert len(specs) >= 65

    def test_specs_have_required_fields(self):
        """Each spec should have name, method_name, description, schema, scope."""
        specs = WordPressPlugin.get_tool_specifications()
        for spec in specs:
            assert "name" in spec, "Missing 'name' in spec"
            assert "method_name" in spec, f"Missing 'method_name' in {spec.get('name')}"
            assert "description" in spec, f"Missing 'description' in {spec.get('name')}"
            assert "schema" in spec, f"Missing 'schema' in {spec.get('name')}"
            assert "scope" in spec, f"Missing 'scope' in {spec.get('name')}"

    def test_specs_scope_values(self):
        """All scopes should be valid (read, write, admin)."""
        specs = WordPressPlugin.get_tool_specifications()
        valid_scopes = {"read", "write", "admin"}
        for spec in specs:
            assert (
                spec["scope"] in valid_scopes
            ), f"Invalid scope '{spec['scope']}' in {spec['name']}"

    def test_specs_unique_names(self):
        """All tool names should be unique."""
        specs = WordPressPlugin.get_tool_specifications()
        names = [s["name"] for s in specs]
        assert len(names) == len(
            set(names)
        ), f"Duplicate tool names found: {[n for n in names if names.count(n) > 1]}"

    def test_core_tools_present(self):
        """Should include key WordPress tools."""
        specs = WordPressPlugin.get_tool_specifications()
        names = {s["name"] for s in specs}
        expected = {"list_posts", "create_post", "get_post", "update_post", "delete_post"}
        assert expected.issubset(names), f"Missing core tools: {expected - names}"

    def test_media_tools_present(self):
        """Should include media tools."""
        specs = WordPressPlugin.get_tool_specifications()
        names = {s["name"] for s in specs}
        assert "list_media" in names
        assert "upload_media_from_url" in names

    def test_taxonomy_tools_present(self):
        """Should include taxonomy tools."""
        specs = WordPressPlugin.get_tool_specifications()
        names = {s["name"] for s in specs}
        assert "list_categories" in names
        assert "list_tags" in names

    def test_wp_cli_tools_present(self):
        """Should include WP-CLI tools."""
        specs = WordPressPlugin.get_tool_specifications()
        names = {s["name"] for s in specs}
        assert "wp_cache_flush" in names
        assert "wp_db_check" in names


class TestWordPressHandlerDelegation:
    """Test that plugin methods delegate to handlers correctly."""

    VALID_CONFIG = {
        "url": "https://example.com",
        "username": "admin",
        "app_password": "xxxx xxxx xxxx xxxx",
    }

    @pytest.fixture
    def plugin(self):
        return WordPressPlugin(self.VALID_CONFIG)

    @pytest.mark.asyncio
    async def test_list_posts_delegates(self, plugin):
        """list_posts should delegate to posts handler."""
        plugin.posts.list_posts = AsyncMock(return_value={"posts": []})
        result = await plugin.list_posts(per_page=5)
        plugin.posts.list_posts.assert_called_once_with(per_page=5)
        assert result == {"posts": []}

    @pytest.mark.asyncio
    async def test_create_post_delegates(self, plugin):
        """create_post should delegate to posts handler."""
        plugin.posts.create_post = AsyncMock(return_value={"id": 42})
        result = await plugin.create_post(title="Test", content="Hello")
        plugin.posts.create_post.assert_called_once_with(title="Test", content="Hello")
        assert result == {"id": 42}

    @pytest.mark.asyncio
    async def test_list_media_delegates(self, plugin):
        """list_media should delegate to media handler."""
        plugin.media.list_media = AsyncMock(return_value=[])
        await plugin.list_media()
        plugin.media.list_media.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_categories_delegates(self, plugin):
        """list_categories should delegate to taxonomy handler."""
        plugin.taxonomy.list_categories = AsyncMock(return_value=[])
        await plugin.list_categories()
        plugin.taxonomy.list_categories.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_comments_delegates(self, plugin):
        """list_comments should delegate to comments handler."""
        plugin.comments.list_comments = AsyncMock(return_value=[])
        await plugin.list_comments()
        plugin.comments.list_comments.assert_called_once()

    @pytest.mark.asyncio
    async def test_wp_cli_not_available(self, plugin):
        """WP-CLI methods should return error when not configured."""
        result = await plugin.wp_cache_flush()
        assert "error" in result.lower() or "error" in json.loads(result)

    @pytest.mark.asyncio
    async def test_health_check_delegates(self, plugin):
        """health_check should delegate to site handler."""
        plugin.site.health_check = AsyncMock(return_value={"healthy": True})
        result = await plugin.health_check()
        assert result["healthy"] is True


class TestWordPressPluginInfo:
    """Test plugin info and metadata methods."""

    VALID_CONFIG = {
        "url": "https://example.com",
        "username": "admin",
        "app_password": "xxxx xxxx xxxx xxxx",
    }

    def test_get_project_info(self):
        """Should return structured project info."""
        plugin = WordPressPlugin(self.VALID_CONFIG, project_id="wp_test")
        info = plugin.get_project_info()
        assert info["project_id"] == "wp_test"
        assert info["plugin_type"] == "wordpress"
        assert "url" in info["config_keys"]

    def test_get_tools_returns_empty(self):
        """Legacy get_tools should return empty list (Option B architecture)."""
        plugin = WordPressPlugin(self.VALID_CONFIG)
        assert plugin.get_tools() == []


# --- PluginRegistry Tests ---


class TestPluginRegistryWithWordPress:
    """Test PluginRegistry with WordPress plugin."""

    def test_register_wordpress(self):
        """Should register WordPress plugin type."""
        reg = PluginRegistry()
        reg.register("wordpress", WordPressPlugin)
        assert reg.is_registered("wordpress")
        assert "wordpress" in reg.get_registered_types()

    def test_create_instance(self):
        """Should create WordPress plugin instance."""
        reg = PluginRegistry()
        reg.register("wordpress", WordPressPlugin)
        config = {
            "url": "https://example.com",
            "username": "admin",
            "app_password": "xxxx",
        }
        instance = reg.create_instance("wordpress", "wp_site1", config)
        assert isinstance(instance, WordPressPlugin)
        assert instance.project_id == "wp_site1"

    def test_register_non_baseplugin_raises(self):
        """Should reject classes not inheriting BasePlugin."""
        reg = PluginRegistry()
        with pytest.raises(TypeError, match="must inherit from BasePlugin"):
            reg.register("bad", dict)

    def test_unknown_type_raises(self):
        """Should raise KeyError for unknown plugin type."""
        reg = PluginRegistry()
        with pytest.raises(KeyError, match="Unknown plugin type"):
            reg.create_instance("nonexistent", "id1", {})
