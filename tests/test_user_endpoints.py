"""Tests for per-user MCP endpoint handler (core/user_endpoints.py)."""

import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.requests import Request

from core.settings import get_cached_rate_per_min
from core.user_endpoints import (
    _rate_limits,
    user_mcp_handler,
)

# ── Helpers ───────────────────────────────────────────────────


def _make_request(
    user_id: str = "user-uuid-001",
    alias: str = "myblog",
    method_name: str = "initialize",
    params: dict | None = None,
    api_key: str = "mhu_validkey1234567890abcdefghijklmnopqrst",
    req_id: int = 1,
) -> Request:
    """Build a mock Starlette Request for the user MCP endpoint."""
    body = {
        "jsonrpc": "2.0",
        "id": req_id,
        "method": method_name,
        "params": params or {},
    }
    body_bytes = json.dumps(body).encode()

    scope = {
        "type": "http",
        "method": "POST",
        "path": f"/u/{user_id}/{alias}/mcp",
        "path_params": {"user_id": user_id, "alias": alias},
        "headers": [],
        "query_string": b"",
    }

    if api_key:
        scope["headers"].append((b"authorization", f"Bearer {api_key}".encode()))

    async def receive():
        return {"type": "http.request", "body": body_bytes}

    return Request(scope, receive)


def _make_request_no_auth(
    user_id: str = "user-uuid-001",
    alias: str = "myblog",
) -> Request:
    """Build a mock Request without an Authorization header."""
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize"}).encode()
    scope = {
        "type": "http",
        "method": "POST",
        "path": f"/u/{user_id}/{alias}/mcp",
        "path_params": {"user_id": user_id, "alias": alias},
        "headers": [],
        "query_string": b"",
    }

    async def receive():
        return {"type": "http.request", "body": body}

    return Request(scope, receive)


# ── Fixtures ──────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _clear_rate_limits():
    """Clear the global rate limit tracking between tests."""
    _rate_limits.clear()
    yield
    _rate_limits.clear()


@pytest.fixture(autouse=True)
def _clear_tool_cache():
    """No-op: the per-plugin tool schema cache was removed in F.7.

    Retained so the rest of the test fixtures stay unchanged; the scope-filter
    pipeline runs on every ``tools/list`` call so there is nothing to clear.
    """
    yield


@pytest.fixture
def mock_key_mgr():
    """Patch get_user_key_manager to return a mock."""
    mgr = AsyncMock()
    mgr.validate_key = AsyncMock(
        return_value={
            "key_id": "key-uuid-001",
            "user_id": "user-uuid-001",
            "scopes": "read write",
        }
    )
    with patch("core.user_keys.get_user_key_manager", return_value=mgr):
        yield mgr


@pytest.fixture
def mock_db():
    """Patch get_database to return a mock."""
    db = AsyncMock()
    db.get_site_tool_scope = AsyncMock(return_value="admin")
    db.get_site_tool_toggles = AsyncMock(return_value={})
    db.get_site_by_alias = AsyncMock(
        return_value={
            "id": "site-uuid-001",
            "user_id": "user-uuid-001",
            "plugin_type": "wordpress",
            "alias": "myblog",
            "url": "https://myblog.example.com",
            "credentials": b"encrypted-blob",
            "status": "active",
            "status_msg": "OK",
        }
    )
    with patch("core.database.get_database", return_value=db):
        yield db


@pytest.fixture
def mock_encryption():
    """Patch get_credential_encryption to return a mock."""
    enc = MagicMock()
    enc.decrypt_credentials = MagicMock(
        return_value={
            "username": "admin",
            "app_password": "xxxx xxxx xxxx xxxx",
        }
    )
    with patch("core.encryption.get_credential_encryption", return_value=enc):
        yield enc


@pytest.fixture
def mock_tool_registry():
    """Patch get_tool_registry to return a registry with a sample tool."""
    tool_def = MagicMock()
    tool_def.name = "wordpress_list_posts"
    tool_def.description = "List WordPress posts"
    tool_def.plugin_type = "wordpress"
    tool_def.required_scope = "read"
    tool_def.category = "read"
    tool_def.sensitivity = "normal"
    tool_def.input_schema = {
        "type": "object",
        "properties": {
            "site": {"type": "string", "description": "Site identifier"},
            "status": {"type": "string", "description": "Post status"},
        },
        "required": ["site"],
    }

    registry = MagicMock()
    registry.get_by_plugin_type = MagicMock(return_value=[tool_def])
    # F.19.7.1: tools/call also looks up the tool by name — the universal
    # scope check then reads ``required_scope`` off the returned tool_def.
    # Without this wire-up ``get_by_name`` returns a fresh MagicMock and
    # ``required_scope`` becomes a MagicMock, which is never a member of
    # the allowed-scope set — the call is rejected with "Insufficient scope".
    registry.get_by_name = MagicMock(return_value=tool_def)

    with patch("core.tool_registry.get_tool_registry", return_value=registry):
        yield registry


@pytest.fixture
def mock_plugin_registry():
    """Patch plugins.plugin_registry to return a mock."""
    mock_reg = MagicMock()
    mock_reg.is_registered = MagicMock(return_value=True)

    mock_instance = MagicMock()
    mock_instance.list_posts = AsyncMock(
        return_value=[
            {"id": 1, "title": "Hello World"},
        ]
    )
    mock_reg.create_instance = MagicMock(return_value=mock_instance)

    with patch("plugins.plugin_registry", mock_reg, create=True):
        yield mock_reg


# ── Authentication Tests ─────────────────────────────────────


class TestAuthentication:
    """Test authentication checks in user_mcp_handler."""

    @pytest.mark.unit
    async def test_missing_auth_header(self, mock_key_mgr, mock_db):
        """Request without Authorization header should return 401."""
        request = _make_request_no_auth()
        response = await user_mcp_handler(request)
        assert response.status_code == 401
        body = json.loads(response.body)
        assert "error" in body

    @pytest.mark.unit
    async def test_invalid_api_key(self, mock_key_mgr, mock_db):
        """Invalid API key should return 401."""
        mock_key_mgr.validate_key.return_value = None
        request = _make_request(api_key="mhu_invalidkeyvalue")
        response = await user_mcp_handler(request)
        assert response.status_code == 401
        body = json.loads(response.body)
        assert "Invalid API key" in body["error"]["message"]

    @pytest.mark.unit
    async def test_user_id_mismatch(self, mock_key_mgr, mock_db):
        """API key user_id not matching URL user_id should return 403."""
        mock_key_mgr.validate_key.return_value = {
            "key_id": "key-uuid-001",
            "user_id": "different-user-id",
            "scopes": "read write",
        }
        request = _make_request(user_id="user-uuid-001")
        response = await user_mcp_handler(request)
        assert response.status_code == 403
        body = json.loads(response.body)
        assert "does not match" in body["error"]["message"]

    @pytest.mark.unit
    async def test_site_scoped_key_wrong_site(self, mock_key_mgr, mock_db):
        """Site-scoped key (site_id=A) used for site B should return 403."""
        # Key is scoped to site-A
        mock_key_mgr.validate_key.return_value = {
            "key_id": "key-uuid-001",
            "user_id": "user-uuid-001",
            "scopes": "read write",
            "site_id": "site-uuid-A",
        }
        # The site looked up by site_id (A) has alias "blog-a", but the request
        # is for alias "myblog" (which is site-B in get_site_by_alias).
        mock_db.get_site = AsyncMock(
            return_value={
                "id": "site-uuid-A",
                "alias": "blog-a",
                "user_id": "user-uuid-001",
                "plugin_type": "wordpress",
                "url": "https://blog-a.example.com",
                "credentials": b"x",
                "status": "active",
            }
        )
        request = _make_request(alias="myblog")
        response = await user_mcp_handler(request)
        assert response.status_code == 403
        body = json.loads(response.body)
        assert "scoped to a different site" in body["error"]["message"]

    @pytest.mark.unit
    async def test_site_scoped_key_matching_site(self, mock_key_mgr, mock_db, mock_tool_registry):
        """Site-scoped key used for the matching alias should pass auth."""
        mock_key_mgr.validate_key.return_value = {
            "key_id": "key-uuid-001",
            "user_id": "user-uuid-001",
            "scopes": "read write",
            "site_id": "site-uuid-001",
        }
        mock_db.get_site = AsyncMock(
            return_value={
                "id": "site-uuid-001",
                "alias": "myblog",
                "user_id": "user-uuid-001",
                "plugin_type": "wordpress",
                "url": "https://myblog.example.com",
                "credentials": b"x",
                "status": "active",
            }
        )
        request = _make_request(alias="myblog", method_name="tools/list")
        response = await user_mcp_handler(request)
        assert response.status_code == 200
        body = json.loads(response.body)
        assert "result" in body
        assert "tools" in body["result"]


# ── Site Lookup Tests ────────────────────────────────────────


class TestSiteLookup:
    """Test site lookup behavior."""

    @pytest.mark.unit
    async def test_site_not_found(self, mock_key_mgr, mock_db):
        """Non-existent alias should return 404."""
        mock_db.get_site_by_alias.return_value = None
        request = _make_request(alias="nonexistent")
        response = await user_mcp_handler(request)
        assert response.status_code == 404
        body = json.loads(response.body)
        assert "not found" in body["error"]["message"]

    @pytest.mark.unit
    async def test_disabled_site(self, mock_key_mgr, mock_db):
        """Disabled site should return 403."""
        mock_db.get_site_by_alias.return_value = {
            "id": "site-uuid-001",
            "user_id": "user-uuid-001",
            "plugin_type": "wordpress",
            "alias": "myblog",
            "url": "https://myblog.example.com",
            "credentials": b"encrypted-blob",
            "status": "disabled",
            "status_msg": "Disabled by admin",
        }
        request = _make_request()
        response = await user_mcp_handler(request)
        assert response.status_code == 403
        body = json.loads(response.body)
        assert "disabled" in body["error"]["message"].lower()


# ── MCP Protocol Methods ─────────────────────────────────────


class TestMCPMethods:
    """Test MCP JSON-RPC method handling."""

    @pytest.mark.unit
    async def test_initialize_method(self, mock_key_mgr, mock_db):
        """initialize should return protocolVersion and capabilities."""
        request = _make_request(method_name="initialize")
        response = await user_mcp_handler(request)
        assert response.status_code == 200
        body = json.loads(response.body)
        result = body["result"]
        assert "protocolVersion" in result
        assert "capabilities" in result
        assert "tools" in result["capabilities"]
        assert "serverInfo" in result
        assert "myblog" in result["serverInfo"]["name"]

    @pytest.mark.unit
    async def test_notifications_initialized(self, mock_key_mgr, mock_db):
        """notifications/initialized should return 204 with no body."""
        request = _make_request(method_name="notifications/initialized")
        response = await user_mcp_handler(request)
        assert response.status_code == 204

    @pytest.mark.unit
    async def test_tools_list(self, mock_key_mgr, mock_db, mock_tool_registry):
        """tools/list should return tools with site param removed."""
        request = _make_request(method_name="tools/list")
        response = await user_mcp_handler(request)
        assert response.status_code == 200
        body = json.loads(response.body)
        tools = body["result"]["tools"]
        assert len(tools) == 1
        assert tools[0]["name"] == "wordpress_list_posts"
        # 'site' should be removed from properties and required
        schema = tools[0]["inputSchema"]
        assert "site" not in schema.get("properties", {})
        if "required" in schema:
            assert "site" not in schema["required"]

    @pytest.mark.unit
    async def test_tools_call_invalid_tool(self, mock_key_mgr, mock_db):
        """Calling a tool with wrong plugin prefix should return error."""
        request = _make_request(
            method_name="tools/call",
            params={"name": "gitea_list_repos", "arguments": {}},
        )
        response = await user_mcp_handler(request)
        assert response.status_code == 200
        body = json.loads(response.body)
        assert "error" in body
        assert "not available" in body["error"]["message"]

    @pytest.mark.unit
    async def test_tools_call_success(
        self,
        mock_key_mgr,
        mock_db,
        mock_encryption,
        mock_tool_registry,
        mock_plugin_registry,
    ):
        """Calling a valid tool should return content result."""
        request = _make_request(
            method_name="tools/call",
            params={"name": "wordpress_list_posts", "arguments": {"status": "publish"}},
        )
        response = await user_mcp_handler(request)
        assert response.status_code == 200
        body = json.loads(response.body)
        assert "result" in body
        assert "content" in body["result"]

    @pytest.mark.unit
    async def test_unsupported_method(self, mock_key_mgr, mock_db):
        """Unknown MCP method should return -32601 error."""
        request = _make_request(method_name="resources/list")
        response = await user_mcp_handler(request)
        assert response.status_code == 200
        body = json.loads(response.body)
        assert "error" in body
        assert body["error"]["code"] == -32601
        assert "not supported" in body["error"]["message"]


# ── F.19.7.1 — Universal scope tier regression coverage ─────
#
# Pre-fix bug: when an mhu_ key was issued with scope ``editor`` (the
# tier introduced by F.19.5 + F.19.7), every tool call failed with
# ``Insufficient scope`` because:
#
#   1. The local ``scope_hierarchy`` map didn't know about ``editor``,
#      so the editor key collapsed to level 0 and was rejected for every
#      required_scope ≥ 1 (i.e. read/editor/write/admin).
#   2. The Coolify category whitelist was applied to every plugin. For
#      wordpress_specialist tools whose default category is ``"read"``
#      (one of Coolify's KNOWN_CATEGORIES), the whitelist rejected
#      anything an editor-scope key requested unless that key happened
#      to also include the ``read`` scope.
#
# These tests pin the post-fix behaviour: editor scope on a non-Coolify
# plugin admits both ``read`` and ``editor`` tools; Coolify still
# enforces its fine-grained category check.


class TestUniversalScopeTierRegression:
    """F.19.7.1 — editor scope tier must work on non-Coolify plugins."""

    @pytest.mark.unit
    async def test_editor_scope_admits_read_tool_on_wordpress_specialist(
        self,
        mock_key_mgr,
        mock_db,
        mock_encryption,
        mock_plugin_registry,
    ):
        """editor scope key should be allowed to call a read-scope wp_specialist tool."""
        # Key has only the editor scope.
        mock_key_mgr.validate_key.return_value = {
            "key_id": "key-uuid-001",
            "user_id": "user-uuid-001",
            "scopes": "editor",
        }
        # Site is wordpress_specialist with admin tier (so site-level
        # check is permissive).
        mock_db.get_site_by_alias = AsyncMock(
            return_value={
                "id": "site-uuid-001",
                "user_id": "user-uuid-001",
                "plugin_type": "wordpress_specialist",
                "alias": "myblog",
                "url": "https://myblog.example.com",
                "credentials": b"encrypted-blob",
                "status": "active",
                "tool_scope": "admin",
            }
        )

        # F.19.7 read tool: required_scope=read, plugin_type=wordpress_specialist.
        tool_def = MagicMock()
        tool_def.name = "wordpress_specialist_wp_theme_file_list"
        tool_def.plugin_type = "wordpress_specialist"
        tool_def.required_scope = "read"
        tool_def.category = "read"
        tool_def.input_schema = {"type": "object", "properties": {}}

        registry = MagicMock()
        registry.get_by_name = MagicMock(return_value=tool_def)
        registry.get_by_plugin_type = MagicMock(return_value=[tool_def])

        # Make the mocked plugin instance expose the method so the call
        # path doesn't error before the scope check completes.
        plugin_instance = MagicMock()
        plugin_instance.wp_theme_file_list = AsyncMock(return_value={"files": []})
        mock_plugin_registry.create_instance = MagicMock(return_value=plugin_instance)

        with (
            patch("core.tool_registry.get_tool_registry", return_value=registry),
            patch("core.plugin_visibility.is_plugin_public", return_value=True),
        ):
            request = _make_request(
                method_name="tools/call",
                params={
                    "name": "wordpress_specialist_wp_theme_file_list",
                    "arguments": {"theme_slug": "palebluedot"},
                },
            )
            response = await user_mcp_handler(request)
            body = json.loads(response.body)

        # Pre-fix: body["error"]["message"] starts with "Insufficient scope".
        assert "error" not in body or "Insufficient scope" not in body["error"].get(
            "message", ""
        ), f"editor scope was rejected for read-scope tool: {body}"

    @pytest.mark.unit
    async def test_editor_scope_admits_editor_tool_on_wordpress_specialist(
        self,
        mock_key_mgr,
        mock_db,
        mock_encryption,
        mock_plugin_registry,
    ):
        """editor scope key should be allowed to call an editor-scope wp_specialist tool."""
        mock_key_mgr.validate_key.return_value = {
            "key_id": "key-uuid-001",
            "user_id": "user-uuid-001",
            "scopes": "editor",
        }
        mock_db.get_site_by_alias = AsyncMock(
            return_value={
                "id": "site-uuid-001",
                "user_id": "user-uuid-001",
                "plugin_type": "wordpress_specialist",
                "alias": "myblog",
                "url": "https://myblog.example.com",
                "credentials": b"encrypted-blob",
                "status": "active",
                "tool_scope": "editor",
            }
        )

        tool_def = MagicMock()
        tool_def.name = "wordpress_specialist_wp_theme_activate"
        tool_def.plugin_type = "wordpress_specialist"
        tool_def.required_scope = "editor"
        tool_def.category = "read"  # default — same trap that triggered the bug
        tool_def.input_schema = {"type": "object", "properties": {}}

        registry = MagicMock()
        registry.get_by_name = MagicMock(return_value=tool_def)
        registry.get_by_plugin_type = MagicMock(return_value=[tool_def])

        plugin_instance = MagicMock()
        plugin_instance.wp_theme_activate = AsyncMock(return_value={"activated": True})
        mock_plugin_registry.create_instance = MagicMock(return_value=plugin_instance)

        with (
            patch("core.tool_registry.get_tool_registry", return_value=registry),
            patch("core.plugin_visibility.is_plugin_public", return_value=True),
        ):
            request = _make_request(
                method_name="tools/call",
                params={
                    "name": "wordpress_specialist_wp_theme_activate",
                    "arguments": {"slug": "palebluedot"},
                },
            )
            response = await user_mcp_handler(request)
            body = json.loads(response.body)

        assert "error" not in body or "Insufficient scope" not in body["error"].get(
            "message", ""
        ), f"editor scope was rejected for editor-scope tool: {body}"

    @pytest.mark.unit
    async def test_read_scope_still_rejects_editor_tool(
        self,
        mock_key_mgr,
        mock_db,
        mock_encryption,
        mock_plugin_registry,
    ):
        """A pure read-scope key must NOT be able to call editor-scope tools."""
        mock_key_mgr.validate_key.return_value = {
            "key_id": "key-uuid-001",
            "user_id": "user-uuid-001",
            "scopes": "read",
        }
        mock_db.get_site_by_alias = AsyncMock(
            return_value={
                "id": "site-uuid-001",
                "user_id": "user-uuid-001",
                "plugin_type": "wordpress_specialist",
                "alias": "myblog",
                "url": "https://myblog.example.com",
                "credentials": b"encrypted-blob",
                "status": "active",
                "tool_scope": "admin",
            }
        )

        tool_def = MagicMock()
        tool_def.name = "wordpress_specialist_wp_theme_file_write"
        tool_def.plugin_type = "wordpress_specialist"
        tool_def.required_scope = "editor"
        tool_def.category = "read"
        tool_def.input_schema = {"type": "object", "properties": {}}

        registry = MagicMock()
        registry.get_by_name = MagicMock(return_value=tool_def)
        registry.get_by_plugin_type = MagicMock(return_value=[tool_def])

        with (
            patch("core.tool_registry.get_tool_registry", return_value=registry),
            patch("core.plugin_visibility.is_plugin_public", return_value=True),
        ):
            request = _make_request(
                method_name="tools/call",
                params={
                    "name": "wordpress_specialist_wp_theme_file_write",
                    "arguments": {
                        "theme_slug": "palebluedot",
                        "path": "style.css",
                        "content_base64": "Lyo=",
                    },
                },
            )
            response = await user_mcp_handler(request)
            body = json.loads(response.body)

        assert "error" in body, "read scope must not be allowed to call an editor tool"
        assert "Insufficient scope" in body["error"]["message"]


# ── Rate Limiting ────────────────────────────────────────────


class TestRateLimiting:
    """Test per-user rate limiting."""

    @pytest.mark.unit
    async def test_rate_limit_exceeded(self, mock_key_mgr, mock_db):
        """Exceeding per-minute rate limit should return 429."""
        # Fill the rate limit bucket
        now = time.time()
        _rate_limits["user-uuid-001"] = [now - i for i in range(get_cached_rate_per_min())]

        request = _make_request(method_name="initialize")
        response = await user_mcp_handler(request)
        assert response.status_code == 429
        body = json.loads(response.body)
        assert "Rate limit" in body["error"]["message"]
