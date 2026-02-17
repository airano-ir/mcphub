"""
OpenPanel API Client (Self-Hosted)

Handles all HTTP communication with OpenPanel Self-Hosted APIs.

APIs:
- Track API (/track) - Event ingestion (POST)
- tRPC API (/trpc/*) - Analytics data queries (GET with query string)

Note: The REST /export/* endpoints do NOT exist on self-hosted OpenPanel.
All analytics queries must use the tRPC API.

tRPC Routers Available:
- chart.chart - Main analytics endpoint for all chart data with breakdowns
  - Supports breakdowns: referrer, country, city, device, browser, os, path, etc.
  - Supports segments: session, user, event
  - Use chartType="bar" for breakdown data, chartType="histogram" for time series
- chart.events - Event list with counts
- overview.stats - Main statistics (visitors, page views, etc.)
- overview.topPages - Top pages

Note: overview.topSources, overview.topLocations, overview.topDevices, etc.
do NOT exist. Use chart.chart with appropriate breakdowns instead.
"""

import json
import logging
from typing import Any

import aiohttp

class OpenPanelClient:
    """
    OpenPanel Self-Hosted API client.

    Handles Track API (Fastify) and tRPC API for analytics operations.

    Authentication:
    - Track API: Uses Client ID and Client Secret headers
    - tRPC API: Requires session cookie (obtained from dashboard login)

    Note: The REST /export/* endpoints do NOT exist on self-hosted OpenPanel.
    All analytics queries use the tRPC API which requires session authentication.
    """

    def __init__(
        self,
        base_url: str,
        client_id: str,
        client_secret: str,
        project_id: str | None = None,
        organization_id: str | None = None,
        session_cookie: str | None = None,
    ):
        """
        Initialize OpenPanel API client.

        Args:
            base_url: OpenPanel instance URL (e.g., https://analytics.example.com)
            client_id: Client ID for authentication (Track API)
            client_secret: Client Secret for authentication (Track API)
            project_id: Default project ID for operations (optional)
            organization_id: Organization/Workspace ID for multi-tenant setups (optional)
            session_cookie: Session cookie for tRPC API access (optional, from dashboard login)
        """
        self.base_url = base_url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self.default_project_id = project_id
        self.default_organization_id = organization_id
        self.session_cookie = session_cookie

        # Initialize logger
        self.logger = logging.getLogger(f"OpenPanelClient.{base_url}")

    def _get_headers(
        self,
        client_ip: str | None = None,
        user_agent: str | None = None,
        additional_headers: dict | None = None,
    ) -> dict[str, str]:
        """
        Get request headers with authentication.

        Args:
            client_ip: Client IP for geolocation tracking
            user_agent: User agent for device detection
            additional_headers: Additional headers to include

        Returns:
            Dict: Headers with authentication
        """
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

        # Filter None values
        if params:
            params = {k: v for k, v in params.items() if v is not None}
        if json_data:
            json_data = {k: v for k, v in json_data.items() if v is not None}

        self.logger.debug(f"{method} {url}")

        async with aiohttp.ClientSession() as session:
            kwargs = {
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

                # Handle 204 No Content
                if response.status == 204:
                    return {"success": True}

                # Parse response
                try:
                    response_data = await response.json()
                except Exception:
                    response_text = await response.text()
                    if response.status >= 400:
                        raise Exception(
                            f"OpenPanel API error (status {response.status}): {response_text}"
                        )
                    return {"success": True, "message": response_text}

                # Check for errors
                if response.status >= 400:
                    error_msg = self._extract_error_message(response_data, response.status)
                    raise Exception(f"OpenPanel API error (status {response.status}): {error_msg}")

                return response_data

    async def trpc_request(
        self,
        procedure: str,
        input_data: dict[str, Any],
    ) -> Any:
        """
        Make a tRPC API request using GET method with query string.

        Note: OpenPanel tRPC API uses GET requests with input as query parameter,
        NOT POST requests. The dashboard uses session cookies for authentication,
        but we try with client credentials first.

        Args:
            procedure: tRPC procedure name (e.g., "chart.chart", "overview.stats")
            input_data: Input data for the procedure

        Returns:
            The result data from the tRPC response

        Raises:
            Exception: On API errors
        """
        import urllib.parse

        # tRPC format: wrap input in {"json": ...}
        wrapped_input = {"json": input_data}
        input_json = json.dumps(wrapped_input)
        encoded_input = urllib.parse.quote(input_json)

        # Build URL with query parameter (tRPC uses GET with input in query string)
        # Note: OpenPanel uses /trpc/ not /api/trpc/
        url = f"{self.base_url}/trpc/{procedure}?input={encoded_input}"

        headers = self._get_headers()
        # Add Origin header for CORS
        headers["Origin"] = self.base_url
        headers["Referer"] = f"{self.base_url}/"

        self.logger.debug(f"tRPC GET {url}")
        self.logger.debug(f"tRPC Input: {json.dumps(input_data, indent=2)}")

        # Build cookies dict for session authentication
        cookies = {}
        if self.session_cookie:
            cookies["session"] = self.session_cookie
            # Some OpenPanel instances also use a_session_console
            cookies["a_session_console"] = self.session_cookie
            self.logger.debug("Using session cookie for tRPC authentication")

        async with aiohttp.ClientSession(cookies=cookies if cookies else None) as session:
            # Use GET method (not POST) as OpenPanel tRPC expects
            async with session.get(url, headers=headers) as response:
                self.logger.debug(f"tRPC Response status: {response.status}")

                try:
                    response_data = await response.json()
                except Exception:
                    response_text = await response.text()
                    if response.status >= 400:
                        raise Exception(
                            f"OpenPanel tRPC error (status {response.status}): {response_text}"
                        )
                    return {"success": True, "message": response_text}

                # Check for errors
                if response.status >= 400:
                    error_msg = self._extract_trpc_error(response_data, response.status)
                    raise Exception(f"OpenPanel tRPC error (status {response.status}): {error_msg}")

                # Extract result from tRPC response format
                # tRPC response: {"result": {"data": {"json": {...}}}}
                if isinstance(response_data, dict):
                    result = response_data.get("result", {})
                    if isinstance(result, dict):
                        data = result.get("data", {})
                        if isinstance(data, dict) and "json" in data:
                            return data["json"]
                        return data
                    return result

                return response_data

    def _extract_trpc_error(self, response_data: Any, status_code: int = 0) -> str:
        """Extract error message from tRPC error response."""
        if isinstance(response_data, dict):
            # tRPC error format: {"error": {"json": {"message": "..."}}}
            error = response_data.get("error", {})
            if isinstance(error, dict):
                json_error = error.get("json", {})
                if isinstance(json_error, dict):
                    return json_error.get("message", str(error))
                return str(error)
            # Alternative format: {"message": "..."}
            if "message" in response_data:
                return response_data["message"]
        return str(response_data)

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

        # Add helpful hints for common errors
        hints = []
        if status_code == 404:
            if "track" in message.lower():
                hints.append("Check if the tracking endpoint is enabled on your OpenPanel instance")
            elif "not found" in message.lower():
                hints.append("Verify the project_id exists in OpenPanel")
        elif status_code == 400:
            if "invalid" in message.lower() or "query" in message.lower():
                hints.append("Check parameter formats: date_range should be '7d', '30d', etc.")
        elif status_code == 401 or status_code == 403:
            hints.append("Verify client_id and client_secret are correct")

        if hints:
            return f"{message} (Hint: {'; '.join(hints)})"
        return message

    # =====================
    # TRACK API
    # =====================

    async def track(
        self,
        event_type: str,
        payload: dict[str, Any],
        client_ip: str | None = None,
        user_agent: str | None = None,
    ) -> dict[str, Any]:
        """
        Send tracking request to /track endpoint.

        Args:
            event_type: Type of tracking (track, identify, increment, decrement, alias)
            payload: Event payload
            client_ip: Client IP for geo tracking
            user_agent: User agent for device info

        Returns:
            API response
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
        timestamp: str | None = None,
        client_ip: str | None = None,
        user_agent: str | None = None,
    ) -> dict[str, Any]:
        """Track a custom event."""
        payload = {
            "name": name,
        }
        if properties:
            payload["properties"] = properties
        if profile_id:
            payload["profileId"] = profile_id
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
        payload = {
            "profileId": profile_id,
        }
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

    async def alias_user(
        self,
        profile_id: str,
        alias: str,
        client_ip: str | None = None,
        user_agent: str | None = None,
    ) -> dict[str, Any]:
        """Create an alias for a profile ID."""
        payload = {"profileId": profile_id, "alias": alias}
        return await self.track("alias", payload, client_ip, user_agent)

    # =====================
    # tRPC ANALYTICS API
    # =====================

    def _get_interval_from_range(self, date_range: str) -> str:
        """
        Map range to appropriate interval for tRPC API.

        Args:
            date_range: Date range string (e.g., "30min", "7d", "30d")

        Returns:
            Interval string: "minute", "hour", "day", "week", or "month"
        """
        if "min" in date_range:
            return "minute"
        elif date_range in ["1d", "today", "yesterday"]:
            return "hour"
        elif date_range in ["7d", "14d"] or date_range in ["30d", "60d", "90d", "monthToDate"]:
            return "day"
        elif date_range in ["6m", "12m", "yearToDate", "all"]:
            return "month"
        else:
            return "day"  # default

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
        Export raw event data using tRPC chart.events endpoint.

        Note: The REST /export/events endpoint does NOT exist on self-hosted OpenPanel.
        This uses the tRPC API instead.

        Args:
            project_id: Project ID to export from
            event: Event name(s) to filter (not fully supported via tRPC)
            profile_id: Filter by profile ID (not fully supported via tRPC)
            start: Start date (YYYY-MM-DD) - maps to range
            end: End date (YYYY-MM-DD) - maps to range
            page: Page number (pagination limited in tRPC)
            limit: Events per page (pagination limited in tRPC)
            includes: Additional data to include (not supported via tRPC)

        Returns:
            Event data
        """
        # Use chart.events tRPC endpoint to get event list
        input_data = {
            "projectId": project_id,
        }

        try:
            result = await self.trpc_request("chart.events", input_data)
            # Transform result to match expected format
            events_list = result if isinstance(result, list) else []

            # Filter by event name if specified
            if event:
                event_names = event if isinstance(event, list) else [event]
                events_list = [e for e in events_list if e.get("name") in event_names]

            return {"data": events_list, "total": len(events_list), "page": page, "limit": limit}
        except Exception as e:
            self.logger.warning(f"tRPC chart.events failed: {e}, returning empty result")
            return {"data": [], "total": 0, "page": page, "limit": limit}

    async def export_charts(
        self,
        project_id: str,
        events: list[dict[str, Any]],
        interval: str = "day",
        date_range: str = "30d",
        breakdowns: list[str] | None = None,
        previous: bool = False,
    ) -> dict[str, Any]:
        """
        Export aggregated chart data using tRPC chart.chart endpoint.

        Note: The REST /export/charts endpoint does NOT exist on self-hosted OpenPanel.
        This uses the tRPC API instead.

        Args:
            project_id: Project ID
            events: List of event configurations with name, segment, filters
            interval: Time interval (minute, hour, day, week, month)
            date_range: Date range (30min, today, 7d, 30d, etc.)
            breakdowns: Breakdown dimensions (country, device, browser, etc.)
            previous: Include previous period for comparison

        Returns:
            Chart data
        """
        # Build series from events for tRPC chart.chart
        series = []
        for idx, event in enumerate(events):
            series_item = {
                "id": str(idx),
                "name": event.get("name", "*"),
                "segment": event.get("segment", "event"),
                "filters": event.get("filters", []),
            }
            if "property" in event:
                series_item["property"] = event["property"]
            series.append(series_item)

        # Build breakdowns for tRPC
        breakdown_list = []
        if breakdowns:
            for b in breakdowns:
                breakdown_list.append({"name": b})

        input_data = {
            "projectId": project_id,
            "range": date_range,
            "interval": interval,
            "series": series,
            "previous": previous,
        }

        if breakdown_list:
            input_data["breakdowns"] = breakdown_list

        try:
            result = await self.trpc_request("chart.chart", input_data)

            # Transform tRPC response to match expected format
            if isinstance(result, dict):
                # tRPC returns {series: [...], metrics: {...}}
                data_points = []
                if "series" in result:
                    for series_data in result.get("series", []):
                        if "data" in series_data:
                            for point in series_data["data"]:
                                data_points.append(
                                    {
                                        "date": point.get("date"),
                                        "count": point.get("count", 0),
                                        "label": series_data.get("name", ""),
                                    }
                                )

                # Handle breakdowns
                breakdown_data = {}
                if breakdowns and "series" in result:
                    for series_data in result.get("series", []):
                        if "breakdowns" in series_data:
                            for bd in breakdowns:
                                bd_values = series_data.get("breakdowns", {}).get(bd, [])
                                breakdown_data[bd] = bd_values

                return {
                    "data": data_points,
                    "breakdowns": breakdown_data,
                    "metrics": result.get("metrics", {}),
                    "raw": result,
                }
            return {"data": [], "breakdowns": {}, "raw": result}
        except Exception as e:
            self.logger.warning(f"tRPC chart.chart failed: {e}, returning empty result")
            return {"data": [], "breakdowns": {}}

    async def get_overview_stats(
        self,
        project_id: str,
        date_range: str = "30d",
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        """
        Get overview statistics using tRPC overview.stats endpoint.

        Args:
            project_id: Project ID
            date_range: Date range (today, 7d, 30d, etc.)
            start_date: Custom start date (YYYY-MM-DD)
            end_date: Custom end date (YYYY-MM-DD)

        Returns:
            Overview stats including visitors, page views, sessions, etc.
        """
        # Map range to appropriate interval
        interval = self._get_interval_from_range(date_range)

        input_data = {
            "projectId": project_id,
            "range": date_range,
            "interval": interval,
            "filters": [],
            "startDate": start_date,
            "endDate": end_date,
        }

        try:
            result = await self.trpc_request("overview.stats", input_data)
            return result if isinstance(result, dict) else {"error": "Invalid response"}
        except Exception as e:
            self.logger.warning(f"tRPC overview.stats failed: {e}")
            return {"error": str(e)}

    async def get_top_pages(
        self,
        project_id: str,
        date_range: str = "30d",
        mode: str = "page",
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        """
        Get top pages using tRPC overview.topPages endpoint.

        Args:
            project_id: Project ID
            date_range: Date range (today, 7d, 30d, etc.)
            mode: Page mode (page, entry, exit, bot)
            start_date: Custom start date (YYYY-MM-DD)
            end_date: Custom end date (YYYY-MM-DD)

        Returns:
            List of top pages with view counts
        """
        # Map range to appropriate interval
        interval = self._get_interval_from_range(date_range)

        input_data = {
            "projectId": project_id,
            "range": date_range,
            "interval": interval,
            "filters": [],
            "mode": mode,
            "startDate": start_date,
            "endDate": end_date,
        }

        try:
            result = await self.trpc_request("overview.topPages", input_data)
            return result if isinstance(result, (dict, list)) else {"error": "Invalid response"}
        except Exception as e:
            self.logger.warning(f"tRPC overview.topPages failed: {e}")
            return {"error": str(e)}

    async def get_live_visitors(self, project_id: str) -> dict[str, Any]:
        """
        Get live/realtime visitor count using chart.chart with 30min range.

        Args:
            project_id: Project ID

        Returns:
            Live visitor count
        """
        input_data = {
            "projectId": project_id,
            "range": "30min",
            "interval": "minute",
            "chartType": "histogram",
            "metric": "sum",
            "events": [
                {
                    "id": "A",
                    "segment": "user",
                    "name": "*",
                    "displayName": "Active users",
                    "filters": [
                        {
                            "id": "1",
                            "name": "name",
                            "operator": "is",
                            "value": ["screen_view", "session_start"],
                        }
                    ],
                }
            ],
            "breakdowns": [],
            "filters": [],
        }

        try:
            result = await self.trpc_request("chart.chart", input_data)

            # Calculate active users from the time series data
            active_users = 0
            if isinstance(result, dict):
                # Sum up recent activity from series data
                series = result.get("series", [])
                if series:
                    for serie in series:
                        data_points = serie.get("data", [])
                        for point in data_points:
                            active_users += point.get("count", 0)
                # Also check metrics for current count
                metrics = result.get("metrics", {})
                if metrics.get("current", {}).get("value"):
                    active_users = metrics["current"]["value"]

            return {"count": active_users, "raw": result}
        except Exception as e:
            self.logger.warning(f"tRPC chart.chart for live visitors failed: {e}")
            return {"count": 0, "error": str(e)}

    async def get_top_generic(
        self,
        project_id: str,
        date_range: str = "30d",
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        """
        Get generic top items using tRPC overview.topGeneric endpoint.

        Args:
            project_id: Project ID
            date_range: Date range (today, 7d, 30d, etc.)
            start_date: Custom start date (YYYY-MM-DD)
            end_date: Custom end date (YYYY-MM-DD)

        Returns:
            Generic top items data
        """
        # Map range to appropriate interval
        interval = self._get_interval_from_range(date_range)

        input_data = {
            "projectId": project_id,
            "range": date_range,
            "interval": interval,
            "filters": [],
            "startDate": start_date,
            "endDate": end_date,
        }

        try:
            result = await self.trpc_request("overview.topGeneric", input_data)
            return result if isinstance(result, (dict, list)) else {"error": "Invalid response"}
        except Exception as e:
            self.logger.warning(f"tRPC overview.topGeneric failed: {e}")
            return {"error": str(e)}

    async def get_top_sources(
        self,
        project_id: str,
        date_range: str = "30d",
        limit: int = 10,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> Any:
        """
        Get top traffic sources/referrers using chart.chart with referrer breakdown.

        Args:
            project_id: Project ID
            date_range: Date range (today, 7d, 30d, etc.)
            limit: Number of results to return
            start_date: Custom start date (YYYY-MM-DD)
            end_date: Custom end date (YYYY-MM-DD)

        Returns:
            List of top sources with view counts
        """
        return await self.get_chart_data(
            project_id=project_id,
            date_range=date_range,
            breakdown="referrer",
            segment="session",
            limit=limit,
        )

    async def get_top_locations(
        self,
        project_id: str,
        date_range: str = "30d",
        breakdown: str = "country",
        limit: int = 10,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> Any:
        """
        Get top locations (geo data) using chart.chart with country/city/region breakdown.

        Args:
            project_id: Project ID
            date_range: Date range (today, 7d, 30d, etc.)
            breakdown: Geographic breakdown (country, city, region)
            limit: Number of results to return
            start_date: Custom start date (YYYY-MM-DD)
            end_date: Custom end date (YYYY-MM-DD)

        Returns:
            List of top locations with visitor counts
        """
        return await self.get_chart_data(
            project_id=project_id,
            date_range=date_range,
            breakdown=breakdown,
            segment="session",
            limit=limit,
        )

    async def get_top_devices(
        self,
        project_id: str,
        date_range: str = "30d",
        limit: int = 10,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> Any:
        """
        Get top devices using chart.chart with device breakdown.

        Args:
            project_id: Project ID
            date_range: Date range (today, 7d, 30d, etc.)
            limit: Number of results to return
            start_date: Custom start date (YYYY-MM-DD)
            end_date: Custom end date (YYYY-MM-DD)

        Returns:
            List of top devices with counts
        """
        return await self.get_chart_data(
            project_id=project_id,
            date_range=date_range,
            breakdown="device",
            segment="session",
            limit=limit,
        )

    async def get_top_browsers(
        self,
        project_id: str,
        date_range: str = "30d",
        limit: int = 10,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> Any:
        """
        Get top browsers using chart.chart with browser breakdown.

        Args:
            project_id: Project ID
            date_range: Date range (today, 7d, 30d, etc.)
            limit: Number of results to return
            start_date: Custom start date (YYYY-MM-DD)
            end_date: Custom end date (YYYY-MM-DD)

        Returns:
            List of top browsers with counts
        """
        return await self.get_chart_data(
            project_id=project_id,
            date_range=date_range,
            breakdown="browser",
            segment="session",
            limit=limit,
        )

    async def get_top_os(
        self,
        project_id: str,
        date_range: str = "30d",
        limit: int = 10,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> Any:
        """
        Get top operating systems using chart.chart with os breakdown.

        Args:
            project_id: Project ID
            date_range: Date range (today, 7d, 30d, etc.)
            limit: Number of results to return
            start_date: Custom start date (YYYY-MM-DD)
            end_date: Custom end date (YYYY-MM-DD)

        Returns:
            List of top OS with counts
        """
        return await self.get_chart_data(
            project_id=project_id,
            date_range=date_range,
            breakdown="os",
            segment="session",
            limit=limit,
        )

    async def get_chart_data(
        self,
        project_id: str,
        date_range: str,
        breakdown: str,
        segment: str = "session",
        event_name: str = "*",
        limit: int = 10,
    ) -> Any:
        """
        Generic chart data method using chart.chart tRPC endpoint.
        Can be used for any breakdown type.

        Args:
            project_id: Project ID
            date_range: Date range (today, 7d, 30d, etc.)
            breakdown: Breakdown type (referrer, country, city, device, browser, os, etc.)
            segment: Segment type (session, user, event)
            event_name: Event name filter (* for all)
            limit: Number of results to return

        Returns:
            Chart data with breakdown results
        """
        interval = self._get_interval_from_range(date_range)

        input_data = {
            "projectId": project_id,
            "range": date_range,
            "interval": interval,
            "chartType": "bar",
            "metric": "sum",
            "events": [{"id": "A", "segment": segment, "name": event_name}],
            "breakdowns": [{"id": "A", "name": breakdown}],
            "limit": limit,
            "filters": [],
        }

        try:
            result = await self.trpc_request("chart.chart", input_data)
            return result if isinstance(result, (dict, list)) else {"error": "Invalid response"}
        except Exception as e:
            self.logger.warning(f"tRPC chart.chart with breakdown '{breakdown}' failed: {e}")
            return {"error": str(e)}

    # =====================
    # HEALTH CHECK
    # =====================

    async def health_check(self) -> dict[str, Any]:
        """Check OpenPanel instance health by testing API connectivity."""
        results = {"healthy": True, "services": {}}

        # Test Track API (POST /track)
        try:
            await self.request(
                "POST",
                "/track",
                json_data={"type": "track", "payload": {"name": "__health_check__"}},
            )
            results["services"]["track_api"] = "ok"
        except Exception as e:
            error_str = str(e)
            # Any response from the endpoint means it's reachable
            if "400" in error_str or "invalid" in error_str.lower():
                results["services"]["track_api"] = "ok (responding)"
            else:
                results["services"]["track_api"] = f"error: {error_str}"
                results["healthy"] = False

        # Test tRPC API (POST /api/trpc/*)
        # Use a simple procedure to test tRPC connectivity
        try:
            # Try to call overview.liveVisitors with a test project
            # Even if the project doesn't exist, a valid tRPC response indicates the API is working
            await self.trpc_request("overview.liveVisitors", {"projectId": "test"})
            results["services"]["trpc_api"] = "ok"
        except Exception as e:
            error_str = str(e)
            # tRPC errors that indicate the API is responding
            if any(
                x in error_str.lower()
                for x in ["not found", "unauthorized", "forbidden", "invalid", "project"]
            ):
                results["services"]["trpc_api"] = "ok (auth required or project not found)"
            elif "400" in error_str or "401" in error_str or "403" in error_str:
                results["services"]["trpc_api"] = "ok (responding)"
            else:
                results["services"]["trpc_api"] = f"error: {error_str}"
                # Don't mark as completely unhealthy if track works
                if not results["services"].get("track_api", "").startswith("ok"):
                    results["healthy"] = False

        return results

    async def get_instance_info(self) -> dict[str, Any]:
        """Get OpenPanel instance information."""
        info = {
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
