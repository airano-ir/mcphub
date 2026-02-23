"""Tests for MCP client configuration snippet generation (core/config_snippets.py)."""

import json

import pytest

from core.config_snippets import generate_config, get_supported_clients

# ── Test Data ─────────────────────────────────────────────────

BASE_URL = "https://mcp.example.com"
USER_ID = "abc123-uuid"
ALIAS = "myblog"
API_KEY = "mhu_testapikey1234567890abcdefghijklmnopqr"
EXPECTED_ENDPOINT = f"{BASE_URL}/u/{USER_ID}/{ALIAS}/mcp"


# ── Supported Clients ────────────────────────────────────────


class TestSupportedClients:
    """Test get_supported_clients function."""

    @pytest.mark.unit
    def test_get_supported_clients(self):
        """Should return exactly 5 supported client types."""
        clients = get_supported_clients()
        assert len(clients) == 5
        client_ids = [c["id"] for c in clients]
        assert "claude_desktop" in client_ids
        assert "claude_code" in client_ids
        assert "cursor" in client_ids
        assert "vscode" in client_ids
        assert "chatgpt" in client_ids

    @pytest.mark.unit
    def test_supported_clients_have_labels(self):
        """Each client should have id, label, and description."""
        for client in get_supported_clients():
            assert "id" in client
            assert "label" in client
            assert "description" in client
            assert len(client["label"]) > 0
            assert len(client["description"]) > 0


# ── Claude Desktop / Claude Code Format ──────────────────────


class TestClaudeFormat:
    """Test Claude Desktop and Claude Code config generation."""

    @pytest.mark.unit
    def test_claude_desktop_format(self):
        """Claude Desktop config should be valid JSON with mcpServers."""
        snippet = generate_config(BASE_URL, USER_ID, ALIAS, API_KEY, "claude_desktop")
        config = json.loads(snippet)
        assert "mcpServers" in config
        server_name = f"mcphub-{ALIAS}"
        assert server_name in config["mcpServers"]
        server = config["mcpServers"][server_name]
        assert server["url"] == EXPECTED_ENDPOINT
        assert f"Bearer {API_KEY}" in server["headers"]["Authorization"]

    @pytest.mark.unit
    def test_claude_code_format(self):
        """Claude Code config should use the same mcpServers format."""
        snippet = generate_config(BASE_URL, USER_ID, ALIAS, API_KEY, "claude_code")
        config = json.loads(snippet)
        assert "mcpServers" in config
        server_name = f"mcphub-{ALIAS}"
        assert server_name in config["mcpServers"]


# ── Cursor / VS Code Format ─────────────────────────────────


class TestCursorVSCodeFormat:
    """Test Cursor and VS Code config generation."""

    @pytest.mark.unit
    def test_cursor_format(self):
        """Cursor config should be valid JSON with mcp.servers."""
        snippet = generate_config(BASE_URL, USER_ID, ALIAS, API_KEY, "cursor")
        config = json.loads(snippet)
        assert "mcp" in config
        assert "servers" in config["mcp"]
        server_name = f"mcphub-{ALIAS}"
        assert server_name in config["mcp"]["servers"]
        server = config["mcp"]["servers"][server_name]
        assert server["url"] == EXPECTED_ENDPOINT
        assert f"Bearer {API_KEY}" in server["headers"]["Authorization"]

    @pytest.mark.unit
    def test_vscode_format(self):
        """VS Code config should use the same mcp.servers format as Cursor."""
        snippet = generate_config(BASE_URL, USER_ID, ALIAS, API_KEY, "vscode")
        config = json.loads(snippet)
        assert "mcp" in config
        assert "servers" in config["mcp"]


# ── ChatGPT Format ───────────────────────────────────────────


class TestChatGPTFormat:
    """Test ChatGPT config generation."""

    @pytest.mark.unit
    def test_chatgpt_format(self):
        """ChatGPT config should return the raw endpoint URL only."""
        snippet = generate_config(BASE_URL, USER_ID, ALIAS, API_KEY, "chatgpt")
        assert snippet == EXPECTED_ENDPOINT
        # Should NOT be JSON
        with pytest.raises(json.JSONDecodeError):
            json.loads(snippet)


# ── Error Handling ───────────────────────────────────────────


class TestErrorHandling:
    """Test error conditions."""

    @pytest.mark.unit
    def test_invalid_client_type(self):
        """Unsupported client type should raise ValueError."""
        with pytest.raises(ValueError, match="Unsupported client type"):
            generate_config(BASE_URL, USER_ID, ALIAS, API_KEY, "unknown_client")


# ── URL Correctness ──────────────────────────────────────────


class TestURLCorrectness:
    """Test that generated configs contain the correct endpoint URL."""

    @pytest.mark.unit
    def test_config_contains_correct_url(self):
        """All config formats should contain /u/{user_id}/{alias}/mcp."""
        for client_type in ("claude_desktop", "claude_code", "cursor", "vscode", "chatgpt"):
            snippet = generate_config(BASE_URL, USER_ID, ALIAS, API_KEY, client_type)
            assert (
                f"/u/{USER_ID}/{ALIAS}/mcp" in snippet
            ), f"{client_type} config missing expected URL path"

    @pytest.mark.unit
    def test_trailing_slash_stripped(self):
        """Base URL with trailing slash should not produce double slashes."""
        snippet = generate_config(
            "https://mcp.example.com/", USER_ID, ALIAS, API_KEY, "claude_desktop"
        )
        assert "//u/" not in snippet
        assert f"/u/{USER_ID}/{ALIAS}/mcp" in snippet
