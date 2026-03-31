"""Tests for OpenPanel Plugin (plugins/openpanel/).

Unit tests covering client initialization, tool specifications,
handler delegation, API request building, and health checks.
"""

import json
from unittest.mock import AsyncMock

import pytest

from plugins.openpanel.client import OpenPanelClient
from plugins.openpanel.plugin import OpenPanelPlugin

# --- OpenPanelClient Tests ---


class TestOpenPanelClientInit:
    """Test OpenPanelClient initialization."""

    def test_valid_initialization(self):
        """Should initialize with valid credentials."""
        client = OpenPanelClient(
            base_url="https://analytics.example.com",
            client_id="test-client-id",
            client_secret="test-client-secret",
        )
        assert client.base_url == "https://analytics.example.com"
        assert client.client_id == "test-client-id"
        assert client.client_secret == "test-client-secret"
        assert client.default_project_id is None

    def test_trailing_slash_stripped(self):
        """Should strip trailing slash from base URL."""
        client = OpenPanelClient(
            base_url="https://analytics.example.com/",
            client_id="cid",
            client_secret="csec",
        )
        assert client.base_url == "https://analytics.example.com"

    def test_project_id_stored(self):
        """Should store optional project_id."""
        client = OpenPanelClient(
            base_url="https://analytics.example.com",
            client_id="cid",
            client_secret="csec",
            project_id="proj123",
        )
        assert client.default_project_id == "proj123"

    def test_organization_id_stored(self):
        """Should store optional organization_id."""
        client = OpenPanelClient(
            base_url="https://analytics.example.com",
            client_id="cid",
            client_secret="csec",
            organization_id="org456",
        )
        assert client.default_organization_id == "org456"


class TestOpenPanelClientHeaders:
    """Test request header generation."""

    def test_auth_headers(self):
        """Should include client_id and client_secret in headers."""
        client = OpenPanelClient(
            base_url="https://a.com", client_id="my-id", client_secret="my-secret"
        )
        headers = client._get_headers()
        assert headers["openpanel-client-id"] == "my-id"
        assert headers["openpanel-client-secret"] == "my-secret"
        assert headers["Content-Type"] == "application/json"

    def test_client_ip_header(self):
        """Should include x-client-ip when provided."""
        client = OpenPanelClient(base_url="https://a.com", client_id="cid", client_secret="csec")
        headers = client._get_headers(client_ip="1.2.3.4")
        assert headers["x-client-ip"] == "1.2.3.4"

    def test_user_agent_header(self):
        """Should include user-agent when provided."""
        client = OpenPanelClient(base_url="https://a.com", client_id="cid", client_secret="csec")
        headers = client._get_headers(user_agent="Mozilla/5.0")
        assert headers["user-agent"] == "Mozilla/5.0"

    def test_additional_headers(self):
        """Should merge additional headers."""
        client = OpenPanelClient(base_url="https://a.com", client_id="cid", client_secret="csec")
        headers = client._get_headers(additional_headers={"X-Custom": "val"})
        assert headers["X-Custom"] == "val"


class TestOpenPanelClientTrack:
    """Test Track API methods."""

    @pytest.mark.asyncio
    async def test_track_event_builds_correct_payload(self):
        """Should build correct track payload."""
        client = OpenPanelClient(base_url="https://a.com", client_id="cid", client_secret="csec")
        client.request = AsyncMock(return_value={"success": True})

        await client.track_event(name="purchase", properties={"amount": 99}, profile_id="user1")

        client.request.assert_called_once()
        call_args = client.request.call_args
        json_data = call_args.kwargs.get("json_data") or call_args[1].get("json_data")
        assert json_data["type"] == "track"
        assert json_data["payload"]["name"] == "purchase"
        assert json_data["payload"]["properties"]["amount"] == 99
        assert json_data["payload"]["profileId"] == "user1"

    @pytest.mark.asyncio
    async def test_identify_user_builds_correct_payload(self):
        """Should build correct identify payload."""
        client = OpenPanelClient(base_url="https://a.com", client_id="cid", client_secret="csec")
        client.request = AsyncMock(return_value={"success": True})

        await client.identify_user(profile_id="user1", first_name="John", email="john@test.com")

        json_data = client.request.call_args.kwargs.get("json_data")
        assert json_data["type"] == "identify"
        assert json_data["payload"]["profileId"] == "user1"
        assert json_data["payload"]["firstName"] == "John"
        assert json_data["payload"]["email"] == "john@test.com"

    @pytest.mark.asyncio
    async def test_increment_property(self):
        """Should build correct increment payload."""
        client = OpenPanelClient(base_url="https://a.com", client_id="cid", client_secret="csec")
        client.request = AsyncMock(return_value={"success": True})

        await client.increment_property(profile_id="user1", property_name="visits", value=5)

        json_data = client.request.call_args.kwargs.get("json_data")
        assert json_data["type"] == "increment"
        assert json_data["payload"]["property"] == "visits"
        assert json_data["payload"]["value"] == 5

    @pytest.mark.asyncio
    async def test_decrement_property(self):
        """Should build correct decrement payload."""
        client = OpenPanelClient(base_url="https://a.com", client_id="cid", client_secret="csec")
        client.request = AsyncMock(return_value={"success": True})

        await client.decrement_property(profile_id="user1", property_name="credits", value=3)

        json_data = client.request.call_args.kwargs.get("json_data")
        assert json_data["type"] == "decrement"
        assert json_data["payload"]["value"] == 3

    @pytest.mark.asyncio
    async def test_track_group(self):
        """Should build correct group payload."""
        client = OpenPanelClient(base_url="https://a.com", client_id="cid", client_secret="csec")
        client.request = AsyncMock(return_value={"success": True})

        await client.track_group(
            group_id="g1", group_type="company", name="Acme", properties={"plan": "pro"}
        )

        json_data = client.request.call_args.kwargs.get("json_data")
        assert json_data["type"] == "group"
        assert json_data["payload"]["id"] == "g1"
        assert json_data["payload"]["type"] == "company"
        assert json_data["payload"]["name"] == "Acme"
        assert json_data["payload"]["properties"]["plan"] == "pro"

    @pytest.mark.asyncio
    async def test_assign_group(self):
        """Should build correct assign_group payload."""
        client = OpenPanelClient(base_url="https://a.com", client_id="cid", client_secret="csec")
        client.request = AsyncMock(return_value={"success": True})

        await client.assign_group(group_ids=["g1", "g2"], profile_id="user1")

        json_data = client.request.call_args.kwargs.get("json_data")
        assert json_data["type"] == "assign_group"
        assert json_data["payload"]["groupIds"] == ["g1", "g2"]
        assert json_data["payload"]["profileId"] == "user1"


class TestOpenPanelClientExport:
    """Test Export API methods."""

    @pytest.mark.asyncio
    async def test_export_events_params(self):
        """Should build correct export_events query params."""
        client = OpenPanelClient(base_url="https://a.com", client_id="cid", client_secret="csec")
        client.request = AsyncMock(return_value={"meta": {}, "data": []})

        await client.export_events(
            project_id="proj1", event="purchase", start="2024-01-01", limit=100
        )

        call_args = client.request.call_args
        assert call_args[0][0] == "GET"
        assert call_args[0][1] == "/export/events"
        params = call_args.kwargs.get("params")
        assert params["projectId"] == "proj1"
        assert params["event"] == "purchase"
        assert params["start"] == "2024-01-01"
        assert params["limit"] == 100

    @pytest.mark.asyncio
    async def test_export_events_array_event_filter(self):
        """Should join array event filters."""
        client = OpenPanelClient(base_url="https://a.com", client_id="cid", client_secret="csec")
        client.request = AsyncMock(return_value={"meta": {}, "data": []})

        await client.export_events(project_id="proj1", event=["click", "view"])

        params = client.request.call_args.kwargs.get("params")
        assert params["event"] == "click,view"

    @pytest.mark.asyncio
    async def test_export_charts_params(self):
        """Should build correct export_charts query params."""
        client = OpenPanelClient(base_url="https://a.com", client_id="cid", client_secret="csec")
        client.request = AsyncMock(return_value={})

        await client.export_charts(
            project_id="proj1",
            events=[{"name": "page_view", "segment": "user"}],
            interval="day",
            date_range="7d",
        )

        call_args = client.request.call_args
        assert call_args[0][0] == "GET"
        assert call_args[0][1] == "/export/charts"
        params = call_args.kwargs.get("params")
        assert params["projectId"] == "proj1"
        assert params["interval"] == "day"
        assert params["range"] == "7d"


class TestOpenPanelClientInsights:
    """Test Insights API methods."""

    @pytest.mark.asyncio
    async def test_get_overview_stats(self):
        """Should call correct insights endpoint."""
        client = OpenPanelClient(base_url="https://a.com", client_id="cid", client_secret="csec")
        client.request = AsyncMock(return_value={"visitors": 100})

        result = await client.get_overview_stats(project_id="proj1", date_range="7d")

        call_args = client.request.call_args
        assert call_args[0][0] == "GET"
        assert call_args[0][1] == "/insights/proj1/metrics"
        assert result["visitors"] == 100

    @pytest.mark.asyncio
    async def test_get_live_visitors(self):
        """Should call live endpoint."""
        client = OpenPanelClient(base_url="https://a.com", client_id="cid", client_secret="csec")
        client.request = AsyncMock(return_value={"count": 5})

        result = await client.get_live_visitors(project_id="proj1")

        assert client.request.call_args[0][1] == "/insights/proj1/live"
        assert result["count"] == 5

    @pytest.mark.asyncio
    async def test_get_top_pages(self):
        """Should call pages endpoint with params."""
        client = OpenPanelClient(base_url="https://a.com", client_id="cid", client_secret="csec")
        client.request = AsyncMock(return_value=[])

        await client.get_top_pages(project_id="proj1", date_range="30d", limit=20)

        assert client.request.call_args[0][1] == "/insights/proj1/pages"
        params = client.request.call_args.kwargs.get("params")
        assert params["limit"] == 20

    @pytest.mark.asyncio
    async def test_get_insights_breakdown(self):
        """Should call breakdown endpoint with correct column."""
        client = OpenPanelClient(base_url="https://a.com", client_id="cid", client_secret="csec")
        client.request = AsyncMock(return_value=[])

        await client.get_insights_breakdown(project_id="proj1", column="country")

        assert client.request.call_args[0][1] == "/insights/proj1/country"

    @pytest.mark.asyncio
    async def test_get_top_sources_uses_referrer_name(self):
        """Should use referrer_name breakdown."""
        client = OpenPanelClient(base_url="https://a.com", client_id="cid", client_secret="csec")
        client.get_insights_breakdown = AsyncMock(return_value=[])

        await client.get_top_sources(project_id="proj1")

        client.get_insights_breakdown.assert_called_once()
        assert client.get_insights_breakdown.call_args[0][1] == "referrer_name"


class TestOpenPanelClientManage:
    """Test Manage API methods."""

    @pytest.mark.asyncio
    async def test_list_projects(self):
        """Should call GET /manage/projects."""
        client = OpenPanelClient(base_url="https://a.com", client_id="cid", client_secret="csec")
        client.request = AsyncMock(return_value=[{"id": "p1", "name": "Test"}])

        result = await client.list_projects()

        assert client.request.call_args[0] == ("GET", "/manage/projects")
        assert result[0]["id"] == "p1"

    @pytest.mark.asyncio
    async def test_create_project(self):
        """Should call POST /manage/projects."""
        client = OpenPanelClient(base_url="https://a.com", client_id="cid", client_secret="csec")
        client.request = AsyncMock(return_value={"id": "new", "name": "New"})

        await client.create_project({"name": "New", "domain": "new.com"})

        assert client.request.call_args[0] == ("POST", "/manage/projects")
        assert client.request.call_args.kwargs["json_data"]["name"] == "New"

    @pytest.mark.asyncio
    async def test_delete_project(self):
        """Should call DELETE /manage/projects/:id."""
        client = OpenPanelClient(base_url="https://a.com", client_id="cid", client_secret="csec")
        client.request = AsyncMock(return_value={"success": True})

        await client.delete_project("proj1")

        assert client.request.call_args[0] == ("DELETE", "/manage/projects/proj1")

    @pytest.mark.asyncio
    async def test_list_clients(self):
        """Should call GET /manage/clients."""
        client = OpenPanelClient(base_url="https://a.com", client_id="cid", client_secret="csec")
        client.request = AsyncMock(return_value=[])

        await client.list_clients()

        assert client.request.call_args[0] == ("GET", "/manage/clients")

    @pytest.mark.asyncio
    async def test_create_client(self):
        """Should call POST /manage/clients."""
        client = OpenPanelClient(base_url="https://a.com", client_id="cid", client_secret="csec")
        client.request = AsyncMock(return_value={"id": "c1"})

        await client.create_client({"name": "test", "projectId": "p1", "mode": "read"})

        assert client.request.call_args[0] == ("POST", "/manage/clients")


class TestOpenPanelClientHealth:
    """Test health check methods."""

    @pytest.mark.asyncio
    async def test_health_check_healthy(self):
        """Should report healthy when both endpoints respond."""
        client = OpenPanelClient(base_url="https://a.com", client_id="cid", client_secret="csec")
        client.request = AsyncMock(return_value={"success": True})

        result = await client.health_check()

        assert result["healthy"] is True
        assert "api" in result["services"]
        assert "track_api" in result["services"]

    @pytest.mark.asyncio
    async def test_get_instance_info(self):
        """Should return instance details."""
        client = OpenPanelClient(
            base_url="https://analytics.example.com",
            client_id="long-client-id-12345",
            client_secret="csec",
            project_id="proj1",
        )

        info = await client.get_instance_info()

        assert info["url"] == "https://analytics.example.com"
        assert info["client_id"] == "long-cli..."
        assert info["default_project_id"] == "proj1"
        assert info["type"] == "openpanel"


class TestOpenPanelClientErrors:
    """Test error handling."""

    def test_extract_error_message_dict(self):
        """Should extract message from dict."""
        client = OpenPanelClient(base_url="https://a.com", client_id="cid", client_secret="csec")
        msg = client._extract_error_message({"message": "Not found"}, 404)
        assert "Not found" in msg
        assert "Hint" in msg

    def test_extract_error_auth_hint(self):
        """Should add auth hint for 401/403."""
        client = OpenPanelClient(base_url="https://a.com", client_id="cid", client_secret="csec")
        msg = client._extract_error_message({"error": "Unauthorized"}, 401)
        assert "Verify client_id" in msg

    def test_extract_error_rate_limit_hint(self):
        """Should add rate limit hint for 429."""
        client = OpenPanelClient(base_url="https://a.com", client_id="cid", client_secret="csec")
        msg = client._extract_error_message({"message": "Too many"}, 429)
        assert "Rate limited" in msg


# --- OpenPanelPlugin Tests ---


class TestOpenPanelPluginInit:
    """Test OpenPanelPlugin initialization."""

    def test_valid_initialization(self):
        """Should initialize with valid config."""
        plugin = OpenPanelPlugin(
            config={
                "url": "https://analytics.example.com",
                "client_id": "cid",
                "client_secret": "csec",
            }
        )
        assert isinstance(plugin.client, OpenPanelClient)
        assert plugin.client.base_url == "https://analytics.example.com"

    def test_project_id_passed_to_client(self):
        """Should pass project_id to client."""
        plugin = OpenPanelPlugin(
            config={
                "url": "https://a.com",
                "client_id": "cid",
                "client_secret": "csec",
                "project_id": "proj123",
            }
        )
        assert plugin.client.default_project_id == "proj123"
        assert plugin.openpanel_project_id == "proj123"

    def test_plugin_name(self):
        """Should return correct plugin name."""
        assert OpenPanelPlugin.get_plugin_name() == "openpanel"

    def test_required_config_keys(self):
        """Should require url, client_id, client_secret."""
        keys = OpenPanelPlugin.get_required_config_keys()
        assert "url" in keys
        assert "client_id" in keys
        assert "client_secret" in keys


class TestOpenPanelPluginToolSpecs:
    """Test tool specifications."""

    def test_tool_count(self):
        """Should return 42 tools."""
        specs = OpenPanelPlugin.get_tool_specifications()
        assert len(specs) == 42

    def test_all_specs_have_required_fields(self):
        """All specs should have name, method_name, description, schema."""
        specs = OpenPanelPlugin.get_tool_specifications()
        for spec in specs:
            assert "name" in spec, "Missing name in spec"
            assert "method_name" in spec, f"Missing method_name in {spec.get('name')}"
            assert "description" in spec, f"Missing description in {spec.get('name')}"
            assert "schema" in spec, f"Missing schema in {spec.get('name')}"

    def test_unique_tool_names(self):
        """All tool names should be unique."""
        specs = OpenPanelPlugin.get_tool_specifications()
        names = [s["name"] for s in specs]
        assert len(names) == len(
            set(names)
        ), f"Duplicate names: {[n for n in names if names.count(n) > 1]}"

    def test_event_tools_present(self):
        """Should include core event tracking tools."""
        specs = OpenPanelPlugin.get_tool_specifications()
        names = {s["name"] for s in specs}
        assert "track_event" in names
        assert "identify_user" in names
        assert "track_page_view" in names
        assert "track_revenue" in names
        assert "track_batch" in names
        assert "create_group" in names
        assert "assign_group" in names

    def test_export_tools_present(self):
        """Should include export tools."""
        specs = OpenPanelPlugin.get_tool_specifications()
        names = {s["name"] for s in specs}
        assert "export_events" in names
        assert "export_chart_data" in names
        assert "get_top_pages" in names
        assert "get_top_referrers" in names
        assert "get_geo_data" in names

    def test_manage_tools_present(self):
        """Should include project and client management tools."""
        specs = OpenPanelPlugin.get_tool_specifications()
        names = {s["name"] for s in specs}
        assert "list_projects" in names
        assert "create_project" in names
        assert "delete_project" in names
        assert "list_clients" in names
        assert "create_client" in names

    def test_no_alias_tool(self):
        """Should NOT include alias_user (not supported by OpenPanel)."""
        specs = OpenPanelPlugin.get_tool_specifications()
        names = {s["name"] for s in specs}
        assert "alias_user" not in names

    def test_no_dashboard_tools(self):
        """Should NOT include dashboard tools (no public API)."""
        specs = OpenPanelPlugin.get_tool_specifications()
        names = {s["name"] for s in specs}
        assert "list_dashboards" not in names
        assert "create_dashboard" not in names
        assert "add_chart" not in names

    def test_no_funnel_tools(self):
        """Should NOT include funnel tools (no public API)."""
        specs = OpenPanelPlugin.get_tool_specifications()
        names = {s["name"] for s in specs}
        assert "list_funnels" not in names
        assert "create_funnel" not in names


class TestOpenPanelPluginDelegation:
    """Test handler method delegation."""

    def test_track_event_delegated(self):
        """Should delegate track_event to events handler."""
        plugin = OpenPanelPlugin(
            config={"url": "https://a.com", "client_id": "cid", "client_secret": "csec"}
        )
        # __getattr__ should find track_event in events handler
        assert callable(plugin.track_event)

    def test_export_events_delegated(self):
        """Should delegate export_events to export handler."""
        plugin = OpenPanelPlugin(
            config={"url": "https://a.com", "client_id": "cid", "client_secret": "csec"}
        )
        assert callable(plugin.export_events)

    def test_list_projects_delegated(self):
        """Should delegate list_projects to projects handler."""
        plugin = OpenPanelPlugin(
            config={"url": "https://a.com", "client_id": "cid", "client_secret": "csec"}
        )
        assert callable(plugin.list_projects)

    def test_nonexistent_method_raises(self):
        """Should raise AttributeError for unknown methods."""
        plugin = OpenPanelPlugin(
            config={"url": "https://a.com", "client_id": "cid", "client_secret": "csec"}
        )
        with pytest.raises(AttributeError):
            plugin.nonexistent_method()


# --- Handler Integration Tests ---


class TestEventHandlers:
    """Test event handler functions."""

    @pytest.mark.asyncio
    async def test_track_event_handler(self):
        """Should return success JSON on track."""
        from plugins.openpanel.handlers.events import track_event

        client = OpenPanelClient(base_url="https://a.com", client_id="cid", client_secret="csec")
        client.track_event = AsyncMock(return_value={"success": True})

        result = await track_event(client, name="test_event")
        data = json.loads(result)

        assert data["success"] is True
        assert data["event"] == "test_event"

    @pytest.mark.asyncio
    async def test_track_event_error(self):
        """Should return error JSON on failure."""
        from plugins.openpanel.handlers.events import track_event

        client = OpenPanelClient(base_url="https://a.com", client_id="cid", client_secret="csec")
        client.track_event = AsyncMock(side_effect=Exception("Connection refused"))

        result = await track_event(client, name="test_event")
        data = json.loads(result)

        assert data["success"] is False
        assert "Connection refused" in data["error"]

    @pytest.mark.asyncio
    async def test_create_group_handler(self):
        """Should return success JSON on group creation."""
        from plugins.openpanel.handlers.events import create_group

        client = OpenPanelClient(base_url="https://a.com", client_id="cid", client_secret="csec")
        client.track_group = AsyncMock(return_value={"success": True})

        result = await create_group(client, group_id="g1", group_type="company", name="Acme")
        data = json.loads(result)

        assert data["success"] is True
        assert data["group_id"] == "g1"

    @pytest.mark.asyncio
    async def test_track_batch_handler(self):
        """Should track multiple events."""
        from plugins.openpanel.handlers.events import track_batch

        client = OpenPanelClient(base_url="https://a.com", client_id="cid", client_secret="csec")
        client.track_event = AsyncMock(return_value={"success": True})

        events = [{"name": "event1"}, {"name": "event2"}, {"name": "event3"}]
        result = await track_batch(client, events=events)
        data = json.loads(result)

        assert data["success"] is True
        assert data["tracked"] == 3
        assert data["total"] == 3


class TestExportHandlers:
    """Test export handler functions."""

    @pytest.mark.asyncio
    async def test_export_events_handler(self):
        """Should return formatted export data."""
        from plugins.openpanel.handlers.export import export_events

        client = OpenPanelClient(
            base_url="https://a.com", client_id="cid", client_secret="csec", project_id="proj1"
        )
        client.export_events = AsyncMock(
            return_value={
                "meta": {"totalCount": 2, "current": 1, "pages": 1},
                "data": [{"name": "ev1"}, {"name": "ev2"}],
            }
        )

        result = await export_events(client)
        data = json.loads(result)

        assert data["success"] is True
        assert data["count"] == 2
        assert data["total"] == 2

    @pytest.mark.asyncio
    async def test_get_top_pages_handler(self):
        """Should return top pages data."""
        from plugins.openpanel.handlers.export import get_top_pages

        client = OpenPanelClient(
            base_url="https://a.com", client_id="cid", client_secret="csec", project_id="proj1"
        )
        client.get_top_pages = AsyncMock(return_value=[{"path": "/home", "count": 100}])

        result = await get_top_pages(client)
        data = json.loads(result)

        assert data["success"] is True


class TestProjectHandlers:
    """Test project management handler functions."""

    @pytest.mark.asyncio
    async def test_list_projects_handler(self):
        """Should return projects list."""
        from plugins.openpanel.handlers.projects import list_projects

        client = OpenPanelClient(base_url="https://a.com", client_id="cid", client_secret="csec")
        client.list_projects = AsyncMock(return_value=[{"id": "p1", "name": "Test"}])

        result = await list_projects(client)
        data = json.loads(result)

        assert data["success"] is True
        assert data["count"] == 1

    @pytest.mark.asyncio
    async def test_create_project_handler(self):
        """Should create and return project."""
        from plugins.openpanel.handlers.projects import create_project

        client = OpenPanelClient(base_url="https://a.com", client_id="cid", client_secret="csec")
        client.create_project = AsyncMock(return_value={"id": "new", "name": "New"})

        result = await create_project(client, name="New", domain="new.com")
        data = json.loads(result)

        assert data["success"] is True
        assert "New" in data["message"]


class TestSystemHandlers:
    """Test system handler functions."""

    @pytest.mark.asyncio
    async def test_health_check_handler(self):
        """Should return health status."""
        from plugins.openpanel.handlers.system import health_check

        client = OpenPanelClient(base_url="https://a.com", client_id="cid", client_secret="csec")
        client.health_check = AsyncMock(
            return_value={"healthy": True, "services": {"api": "ok", "track_api": "ok"}}
        )

        result = await health_check(client)
        data = json.loads(result)

        assert data["success"] is True
        assert data["healthy"] is True

    @pytest.mark.asyncio
    async def test_test_connection_handler(self):
        """Should return connection status."""
        from plugins.openpanel.handlers.system import test_connection

        client = OpenPanelClient(base_url="https://a.com", client_id="cid", client_secret="csec")
        client.health_check = AsyncMock(return_value={"healthy": True})

        result = await test_connection(client)
        data = json.loads(result)

        assert data["success"] is True
        assert data["connection"] == "ok"


class TestUtilsModule:
    """Test utility functions."""

    def test_get_project_id_explicit(self):
        """Should use explicit project_id."""
        from plugins.openpanel.handlers.utils import get_project_id

        client = OpenPanelClient(
            base_url="https://a.com", client_id="cid", client_secret="csec", project_id="default"
        )
        assert get_project_id(client, "explicit") == "explicit"

    def test_get_project_id_default(self):
        """Should fall back to client default."""
        from plugins.openpanel.handlers.utils import get_project_id

        client = OpenPanelClient(
            base_url="https://a.com", client_id="cid", client_secret="csec", project_id="default"
        )
        assert get_project_id(client, None) == "default"

    def test_get_project_id_missing_raises(self):
        """Should raise ValueError when no project_id available."""
        from plugins.openpanel.handlers.utils import get_project_id

        client = OpenPanelClient(base_url="https://a.com", client_id="cid", client_secret="csec")
        with pytest.raises(ValueError, match="project_id"):
            get_project_id(client, None)
