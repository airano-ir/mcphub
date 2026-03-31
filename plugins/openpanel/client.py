"""
OpenPanel API Client (Self-Hosted).

Handles all HTTP communication with OpenPanel Self-Hosted APIs.

Public APIs (client_id + client_secret auth):
- Track API (/track) - Event ingestion (POST)
- Export API (/export/events, /export/charts) - Data export (GET)
- Insights API (/insights/:projectId/*) - Analytics queries (GET)
- Manage API (/manage/projects, /manage/clients) - CRUD management
- Profile API (/profile) - Profile updates (POST)
- Health API (/healthcheck) - Instance health (GET)

All public API endpoints use openpanel-client-id + openpanel-client-secret headers.
The client must have appropriate mode: 'write' for tracking, 'read' for export, 'root' for manage.

Note: The tRPC API (/trpc/*) requires dashboard session cookies and is NOT used.
"""

import logging
from typing import Any

import aiohttp


class OpenPanelClient:
    """
    OpenPanel Self-Hosted API client.

    Uses the public REST APIs (Track, Export, Insights, Manage, Profile, Health).
    Authentication via openpanel-client-id and openpanel-client-secret headers.

    Client modes:
    - write: Can send events (Track API)
    - read: Can read data (Export API, Insights API)
    - root: Full access (all APIs including Manage)
    """

    def __init__(
        self,
        base_url: str,
        client_id: str,
        client_secret: str,
        project_id: str | None = None,
        organization_id: str | None = None,
    ):
        """
        Initialize OpenPanel API client.

        Args:
            base_url: OpenPanel instance URL (e.g., https://analytics.example.com)
            client_id: Client ID for authentication
            client_secret: Client Secret for authentication
            project_id: Default project ID for operations (optional)
            organization_id: Organization/Workspace ID (optional)
        """
        self.base_url = base_url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self.default_project_id = project_id
        self.default_organization_id = organization_id
        self.logger = logging.getLogger(f"OpenPanelClient.{base_url}")

    def _get_headers(
        self,
        client_ip: str | None = None,
        user_agent: str | None = None,
        additional_headers: dict | None = None,
    ) -> dict[str, str]:
        """Get request headers with authentication."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "openpanel-client-id": self.client_id,
            "openpanel-client-secret": self.client_secret,
        }
        if client_ip:
            headers["x-client-ip"] = client_ip
        if user_agent:
            headers["user-agent"] = user_agent
        if additional_headers:
            headers.update(additional_headers)
        return headers

    async def request(
        self,
        method: str,
        endpoint: str,
        params: dict | None = None,
        json_data: dict | None = None,
        headers_override: dict | None = None,
        client_ip: str | None = None,
        user_agent: str | None = None,
    ) -> Any:
        """
        Make authenticated request to OpenPanel API.

        Args:
            method: HTTP method
            endpoint: API endpoint (with leading /)
            params: Query parameters
            json_data: JSON body data
            headers_override: Override/add headers
            client_ip: Client IP for geo tracking
            user_agent: User agent for device info

        Returns:
            API response

        Raises:
            Exception: On API errors
        """
        url = f"{self.base_url}{endpoint}"
        headers = self._get_headers(client_ip, user_agent, headers_override)

        if params:
            params = {k: v for k, v in params.items() if v is not None}
        if json_data:
            json_data = {k: v for k, v in json_data.items() if v is not None}

        self.logger.debug(f"{method} {url}")

        async with aiohttp.ClientSession() as session:
            kwargs: dict[str, Any] = {
                "method": method,
                "url": url,
                "headers": headers,
            }
            if params:
                kwargs["params"] = params
            if json_data:
                kwargs["json"] = json_data

            async with session.request(**kwargs) as response:
                self.logger.debug(f"Response status: {response.status}")

                if response.status == 204:
                    return {"success": True}

                try:
                    response_data = await response.json()
                except Exception:
                    response_text = await response.text()
                    if response.status >= 400:
                        raise Exception(
                            f"OpenPanel API error (status {response.status}): {response_text}"
                        )
                    return {"success": True, "message": response_text}

                if response.status >= 400:
                    error_msg = self._extract_error_message(response_data, response.status)
                    raise Exception(f"OpenPanel API error (status {response.status}): {error_msg}")

                return response_data

    def _extract_error_message(self, response_data: Any, status_code: int = 0) -> str:
        """Extract error message from various response formats with helpful hints."""
        message = ""
        if isinstance(response_data, dict):
            if "message" in response_data:
                message = response_data["message"]
            elif "error" in response_data:
                message = response_data["error"]
            elif "msg" in response_data:
                message = response_data["msg"]
            else:
                message = str(response_data)
        else:
            message = str(response_data)

        hints = []
        if status_code == 401 or status_code == 403:
            hints.append("Verify client_id and client_secret are correct and have appropriate mode")
        elif status_code == 404:
            hints.append("Verify the project_id exists in OpenPanel")
        elif status_code == 429:
            hints.append("Rate limited (100 req/10s). Retry with backoff")

        if hints:
            return f"{message} (Hint: {'; '.join(hints)})"
        return message

    # =====================
    # TRACK API (/track)
    # =====================

    async def track(
        self,
        event_type: str,
        payload: dict[str, Any],
        client_ip: str | None = None,
        user_agent: str | None = None,
    ) -> dict[str, Any]:
        """
        Send tracking request to POST /track.

        Supported types: track, identify, increment, decrement, group, assign_group.

        Args:
            event_type: Type of tracking operation
            payload: Event payload
            client_ip: Client IP for geo tracking
            user_agent: User agent for device info
        """
        data = {"type": event_type, "payload": payload}
        return await self.request(
            "POST", "/track", json_data=data, client_ip=client_ip, user_agent=user_agent
        )

    async def track_event(
        self,
        name: str,
        properties: dict[str, Any] | None = None,
        profile_id: str | None = None,
        groups: list[str] | None = None,
        timestamp: str | None = None,
        client_ip: str | None = None,
        user_agent: str | None = None,
    ) -> dict[str, Any]:
        """Track a custom event."""
        payload: dict[str, Any] = {"name": name}
        if properties:
            payload["properties"] = properties
        if profile_id:
            payload["profileId"] = profile_id
        if groups:
            payload["groups"] = groups
        if timestamp:
            payload["timestamp"] = timestamp
        return await self.track("track", payload, client_ip, user_agent)

    async def identify_user(
        self,
        profile_id: str,
        properties: dict[str, Any] | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        email: str | None = None,
        client_ip: str | None = None,
        user_agent: str | None = None,
    ) -> dict[str, Any]:
        """Identify a user with profile data."""
        payload: dict[str, Any] = {"profileId": profile_id}
        if first_name:
            payload["firstName"] = first_name
        if last_name:
            payload["lastName"] = last_name
        if email:
            payload["email"] = email
        if properties:
            payload["properties"] = properties
        return await self.track("identify", payload, client_ip, user_agent)

    async def increment_property(
        self,
        profile_id: str,
        property_name: str,
        value: int = 1,
        client_ip: str | None = None,
        user_agent: str | None = None,
    ) -> dict[str, Any]:
        """Increment a numeric property on a profile."""
        payload = {"profileId": profile_id, "property": property_name, "value": value}
        return await self.track("increment", payload, client_ip, user_agent)

    async def decrement_property(
        self,
        profile_id: str,
        property_name: str,
        value: int = 1,
        client_ip: str | None = None,
        user_agent: str | None = None,
    ) -> dict[str, Any]:
        """Decrement a numeric property on a profile."""
        payload = {"profileId": profile_id, "property": property_name, "value": value}
        return await self.track("decrement", payload, client_ip, user_agent)

    async def track_group(
        self,
        group_id: str,
        group_type: str,
        name: str,
        properties: dict[str, Any] | None = None,
        client_ip: str | None = None,
        user_agent: str | None = None,
    ) -> dict[str, Any]:
        """Create or update a group (e.g., company, workspace)."""
        payload: dict[str, Any] = {"id": group_id, "type": group_type, "name": name}
        if properties:
            payload["properties"] = properties
        return await self.track("group", payload, client_ip, user_agent)

    async def assign_group(
        self,
        group_ids: list[str],
        profile_id: str | None = None,
        client_ip: str | None = None,
        user_agent: str | None = None,
    ) -> dict[str, Any]:
        """Assign a user to one or more groups."""
        payload: dict[str, Any] = {"groupIds": group_ids}
        if profile_id:
            payload["profileId"] = profile_id
        return await self.track("assign_group", payload, client_ip, user_agent)

    # =====================
    # EXPORT API (/export)
    # Requires 'read' or 'root' mode client
    # =====================

    async def export_events(
        self,
        project_id: str,
        event: str | list[str] | None = None,
        profile_id: str | None = None,
        start: str | None = None,
        end: str | None = None,
        page: int = 1,
        limit: int = 50,
        includes: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Export raw event data via GET /export/events.

        Args:
            project_id: Project ID to export from
            event: Event name(s) to filter
            profile_id: Filter by profile ID
            start: Start date (YYYY-MM-DD)
            end: End date (YYYY-MM-DD)
            page: Page number
            limit: Events per page (max 1000)
            includes: Additional data fields (profile, meta, properties, etc.)
        """
        params: dict[str, Any] = {"projectId": project_id, "page": page, "limit": limit}
        if event:
            params["event"] = event if isinstance(event, str) else ",".join(event)
        if profile_id:
            params["profileId"] = profile_id
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        if includes:
            params["includes"] = ",".join(includes)

        return await self.request("GET", "/export/events", params=params)

    async def export_charts(
        self,
        project_id: str,
        events: list[dict[str, Any]] | None = None,
        series: list[dict[str, Any]] | None = None,
        interval: str = "day",
        date_range: str = "30d",
        breakdowns: list[dict[str, Any]] | None = None,
        previous: bool = False,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        """
        Export aggregated chart data via GET /export/charts.

        Args:
            project_id: Project ID
            events: Legacy event configs (mapped to series internally)
            series: Series configurations with name, segment, filters
            interval: Time interval (minute, hour, day, week, month)
            date_range: Date range (30min, today, 7d, 30d, etc.)
            breakdowns: Breakdown dimensions [{name: "country"}, ...]
            previous: Include previous period for comparison
            start_date: Custom start date (YYYY-MM-DD)
            end_date: Custom end date (YYYY-MM-DD)
        """
        import json

        # Build series from events (backward compat) or use series directly
        series_data = series or []
        if not series_data and events:
            for idx, event in enumerate(events):
                item: dict[str, Any] = {
                    "id": str(idx),
                    "name": event.get("name", "*"),
                    "segment": event.get("segment", "event"),
                    "filters": event.get("filters", []),
                }
                if "property" in event:
                    item["property"] = event["property"]
                series_data.append(item)

        params: dict[str, Any] = {
            "projectId": project_id,
            "interval": interval,
            "range": date_range,
            "series": json.dumps(series_data),
            "previous": str(previous).lower(),
        }
        if breakdowns:
            params["breakdowns"] = json.dumps(breakdowns)
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date

        return await self.request("GET", "/export/charts", params=params)

    # =====================
    # INSIGHTS API (/insights/:projectId)
    # Requires 'read' or 'root' mode client
    # =====================

    async def get_overview_stats(
        self,
        project_id: str,
        date_range: str = "30d",
        start_date: str | None = None,
        end_date: str | None = None,
        filters: list[dict] | None = None,
    ) -> dict[str, Any]:
        """
        Get overview statistics via GET /insights/:projectId/metrics.

        Returns visitors, page views, sessions, bounce rate, etc.
        """
        import json

        params: dict[str, Any] = {"range": date_range}
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date
        if filters:
            params["filters"] = json.dumps(filters)

        return await self.request("GET", f"/insights/{project_id}/metrics", params=params)

    async def get_live_visitors(self, project_id: str) -> dict[str, Any]:
        """Get live/realtime visitor count via GET /insights/:projectId/live."""
        return await self.request("GET", f"/insights/{project_id}/live")

    async def get_top_pages(
        self,
        project_id: str,
        date_range: str = "30d",
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 10,
        cursor: int | None = None,
        filters: list[dict] | None = None,
    ) -> Any:
        """Get top pages via GET /insights/:projectId/pages."""
        import json

        params: dict[str, Any] = {"range": date_range, "limit": limit}
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date
        if cursor is not None:
            params["cursor"] = cursor
        if filters:
            params["filters"] = json.dumps(filters)

        return await self.request("GET", f"/insights/{project_id}/pages", params=params)

    async def get_insights_breakdown(
        self,
        project_id: str,
        column: str,
        date_range: str = "30d",
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 10,
        cursor: int | None = None,
        filters: list[dict] | None = None,
    ) -> Any:
        """
        Get breakdown data via GET /insights/:projectId/:column.

        Supported columns: referrer, referrer_name, referrer_type,
        utm_source, utm_medium, utm_campaign, utm_term, utm_content,
        device, browser, browser_version, os, os_version, brand, model,
        country, region, city.
        """
        import json

        params: dict[str, Any] = {"range": date_range, "limit": limit}
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date
        if cursor is not None:
            params["cursor"] = cursor
        if filters:
            params["filters"] = json.dumps(filters)

        return await self.request("GET", f"/insights/{project_id}/{column}", params=params)

    # Convenience wrappers for common breakdowns
    async def get_top_sources(
        self, project_id: str, date_range: str = "30d", limit: int = 10, **kwargs: Any
    ) -> Any:
        """Get top traffic sources/referrers."""
        return await self.get_insights_breakdown(
            project_id, "referrer_name", date_range, limit=limit, **kwargs
        )

    async def get_top_locations(
        self,
        project_id: str,
        date_range: str = "30d",
        breakdown: str = "country",
        limit: int = 10,
        **kwargs: Any,
    ) -> Any:
        """Get top locations (country, region, or city)."""
        return await self.get_insights_breakdown(
            project_id, breakdown, date_range, limit=limit, **kwargs
        )

    async def get_top_devices(
        self, project_id: str, date_range: str = "30d", limit: int = 10, **kwargs: Any
    ) -> Any:
        """Get top devices."""
        return await self.get_insights_breakdown(
            project_id, "device", date_range, limit=limit, **kwargs
        )

    async def get_top_browsers(
        self, project_id: str, date_range: str = "30d", limit: int = 10, **kwargs: Any
    ) -> Any:
        """Get top browsers."""
        return await self.get_insights_breakdown(
            project_id, "browser", date_range, limit=limit, **kwargs
        )

    async def get_top_os(
        self, project_id: str, date_range: str = "30d", limit: int = 10, **kwargs: Any
    ) -> Any:
        """Get top operating systems."""
        return await self.get_insights_breakdown(
            project_id, "os", date_range, limit=limit, **kwargs
        )

    # =====================
    # MANAGE API (/manage)
    # Requires 'root' mode client
    # =====================

    async def list_projects(self) -> Any:
        """List all projects via GET /manage/projects."""
        return await self.request("GET", "/manage/projects")

    async def get_project(self, project_id: str) -> Any:
        """Get project details via GET /manage/projects/:id."""
        return await self.request("GET", f"/manage/projects/{project_id}")

    async def create_project(self, data: dict[str, Any]) -> Any:
        """Create a new project via POST /manage/projects."""
        return await self.request("POST", "/manage/projects", json_data=data)

    async def update_project(self, project_id: str, data: dict[str, Any]) -> Any:
        """Update a project via PATCH /manage/projects/:id."""
        return await self.request("PATCH", f"/manage/projects/{project_id}", json_data=data)

    async def delete_project(self, project_id: str) -> Any:
        """Delete a project via DELETE /manage/projects/:id."""
        return await self.request("DELETE", f"/manage/projects/{project_id}")

    async def list_clients(self) -> Any:
        """List all API clients via GET /manage/clients."""
        return await self.request("GET", "/manage/clients")

    async def get_client(self, client_id: str) -> Any:
        """Get client details via GET /manage/clients/:id."""
        return await self.request("GET", f"/manage/clients/{client_id}")

    async def create_client(self, data: dict[str, Any]) -> Any:
        """Create a new API client via POST /manage/clients."""
        return await self.request("POST", "/manage/clients", json_data=data)

    async def update_client(self, client_id: str, data: dict[str, Any]) -> Any:
        """Update a client via PATCH /manage/clients/:id."""
        return await self.request("PATCH", f"/manage/clients/{client_id}", json_data=data)

    async def delete_client(self, client_id: str) -> Any:
        """Delete a client via DELETE /manage/clients/:id."""
        return await self.request("DELETE", f"/manage/clients/{client_id}")

    # =====================
    # HEALTH API
    # =====================

    async def health_check(self) -> dict[str, Any]:
        """Check OpenPanel instance health via GET /healthcheck."""
        results: dict[str, Any] = {"healthy": True, "services": {}}

        # Test health endpoint
        try:
            await self.request("GET", "/healthcheck")
            results["services"]["api"] = "ok"
        except Exception as e:
            error_str = str(e)
            if "200" in error_str or "ok" in error_str.lower():
                results["services"]["api"] = "ok"
            else:
                results["services"]["api"] = f"error: {error_str}"
                results["healthy"] = False

        # Test Track API
        try:
            await self.request(
                "POST",
                "/track",
                json_data={"type": "track", "payload": {"name": "__health_check__"}},
            )
            results["services"]["track_api"] = "ok"
        except Exception as e:
            error_str = str(e)
            if "400" in error_str or "invalid" in error_str.lower():
                results["services"]["track_api"] = "ok (responding)"
            else:
                results["services"]["track_api"] = f"error: {error_str}"
                results["healthy"] = False

        return results

    async def get_instance_info(self) -> dict[str, Any]:
        """Get OpenPanel instance information."""
        info: dict[str, Any] = {
            "url": self.base_url,
            "client_id": self.client_id[:8] + "..." if len(self.client_id) > 8 else self.client_id,
            "type": "openpanel",
            "version": "self-hosted",
        }
        if self.default_project_id:
            info["default_project_id"] = self.default_project_id
        if self.default_organization_id:
            info["default_organization_id"] = self.default_organization_id
        return info
