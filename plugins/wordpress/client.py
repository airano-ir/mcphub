"""
WordPress REST API Client

Handles all HTTP communication with WordPress REST API.
Separates API communication from business logic.
"""

import base64
import json
import logging
from typing import Any

import aiohttp

class ConfigurationError(Exception):
    """Raised when site configuration is invalid or incomplete."""

    pass

class AuthenticationError(Exception):
    """Raised when authentication fails (401/403)."""

    pass

class WordPressClient:
    """
    WordPress REST API client for HTTP communication.

    Handles authentication, request formatting, and error handling
    for all WordPress and WooCommerce API endpoints.
    """

    def __init__(self, site_url: str, username: str, app_password: str):
        """
        Initialize WordPress API client.

        Args:
            site_url: WordPress site URL (e.g., https://example.com)
            username: WordPress username
            app_password: WordPress application password

        Raises:
            ConfigurationError: If required parameters are missing or invalid
        """
        # Validate required parameters
        if not site_url:
            raise ConfigurationError(
                "Site URL is not configured. "
                "Please set the URL environment variable (e.g., WORDPRESS_SITE1_URL)."
            )
        if not username:
            raise ConfigurationError(
                "Username is not configured. "
                "Please set the USERNAME environment variable (e.g., WORDPRESS_SITE1_USERNAME)."
            )
        if not app_password:
            raise ConfigurationError(
                "App password is not configured. "
                "Please set the APP_PASSWORD environment variable (e.g., WORDPRESS_SITE1_APP_PASSWORD)."
            )

        self.site_url = site_url.rstrip("/")
        self.api_base = f"{self.site_url}/wp-json/wp/v2"
        self.wc_api_base = f"{self.site_url}/wp-json/wc/v3"
        self.username = username
        self.app_password = app_password

        # Initialize logger
        self.logger = logging.getLogger(f"WordPressClient.{site_url}")

        # Create auth header
        credentials = f"{self.username}:{self.app_password}"
        token = base64.b64encode(credentials.encode()).decode()
        self.auth_header = f"Basic {token}"

    async def request(
        self,
        method: str,
        endpoint: str,
        params: dict | None = None,
        json_data: dict | None = None,
        data: Any | None = None,
        headers_override: dict | None = None,
        use_custom_namespace: bool = False,
        use_woocommerce: bool = False,
    ) -> dict[str, Any]:
        """
        Make authenticated request to WordPress REST API.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE, PATCH)
            endpoint: API endpoint (without base URL)
            params: Query parameters
            json_data: JSON body data
            data: Raw data or FormData for file uploads
            headers_override: Override default headers
            use_custom_namespace: If True, use wp-json root instead of wp/v2
            use_woocommerce: If True, use WooCommerce API base

        Returns:
            Dict: API response as JSON

        Raises:
            Exception: On API errors with status code and message
        """
        # Build URL based on endpoint type
        if use_custom_namespace:
            # For custom namespaces like seo-api-bridge/v1
            url = f"{self.site_url}/wp-json/{endpoint}"
        elif use_woocommerce:
            # For WooCommerce endpoints
            url = f"{self.wc_api_base}/{endpoint}"
        else:
            # Standard WordPress endpoints
            url = f"{self.api_base}/{endpoint}"

        # Setup headers
        headers = {"Authorization": self.auth_header}
        if headers_override:
            headers.update(headers_override)

        # Filter out None, empty strings, and empty lists from params
        # to avoid WordPress/WooCommerce API validation errors
        # Phase K.2.1: Enhanced parameter filtering
        def should_include(v):
            """Check if value should be included in request."""
            if v is None:
                return False
            if isinstance(v, str) and v.strip() == "":
                return False
            return not (isinstance(v, list) and len(v) == 0)

        if params:
            params = {k: v for k, v in params.items() if should_include(v)}

        # Filter None and empty values from JSON data for POST/PUT/PATCH requests
        if json_data:
            json_data = {k: v for k, v in json_data.items() if should_include(v)}

        # Make request
        async with (
            aiohttp.ClientSession() as session,
            session.request(
                method, url, params=params, json=json_data, data=data, headers=headers
            ) as response,
        ):
            # Handle errors with structured error messages
            if response.status >= 400:
                error_text = await response.text()

                # Parse structured error response
                error_info = self._parse_error_response(
                    response.status, error_text, use_woocommerce
                )

                # Log the error for debugging
                self.logger.error(
                    f"API error: {error_info['error_code']} - {error_info['message']}"
                )

                # Raise appropriate exception
                if response.status in (401, 403):
                    raise AuthenticationError(
                        f"[{error_info['error_code']}] {error_info['message']}"
                    )

                raise Exception(f"[{error_info['error_code']}] {error_info['message']}")

            # Return JSON response
            return await response.json()

    def _parse_error_response(
        self, status_code: int, error_text: str, use_woocommerce: bool = False
    ) -> dict[str, Any]:
        """
        Parse error response and return structured error info.

        Args:
            status_code: HTTP status code
            error_text: Raw error response text
            use_woocommerce: Whether this is a WooCommerce API call

        Returns:
            Dict with error_code, message, and details
        """
        # Try to parse as JSON
        try:
            error_json = json.loads(error_text)
            wp_error_code = error_json.get("code", "unknown_error")
            wp_message = error_json.get("message", error_text)
        except (json.JSONDecodeError, TypeError):
            wp_error_code = "unknown_error"
            wp_message = error_text

        # Map status codes to structured error codes
        error_codes = {
            400: "BAD_REQUEST",
            401: "AUTH_FAILED",
            403: "ACCESS_DENIED",
            404: "NOT_FOUND",
            405: "METHOD_NOT_ALLOWED",
            409: "CONFLICT",
            422: "VALIDATION_ERROR",
            429: "RATE_LIMITED",
            500: "SERVER_ERROR",
            502: "BAD_GATEWAY",
            503: "SERVICE_UNAVAILABLE",
        }

        error_code = error_codes.get(status_code, f"HTTP_{status_code}")

        # Create user-friendly messages for common errors
        # Phase K.2.1: Enhanced error messages with helpful hints
        friendly_messages = {
            400: (
                f"Invalid request parameters. {wp_message}. "
                "Hints: Check parameter types match the expected format. "
                'For categories/tags use IDs (e.g., [62] or "62,63"). '
                "For billing/shipping use JSON objects."
            ),
            401: (
                "Authentication failed. Please verify: "
                "1) Username is correct, "
                "2) Application Password is valid, "
                "3) User has required permissions. "
                f"Details: {wp_message}"
            ),
            403: (
                "Access denied. The user does not have permission for this action. "
                "Some operations (like coupons) require admin-level WooCommerce permissions. "
                f"Details: {wp_message}"
            ),
            404: (
                "Resource not found. The requested endpoint or item does not exist. "
                f"Details: {wp_message}"
            ),
        }

        # Add WooCommerce-specific hints
        if use_woocommerce and status_code == 401:
            friendly_messages[401] = (
                "WooCommerce authentication failed. Please verify: "
                "1) WooCommerce REST API is enabled, "
                "2) Application Password has WooCommerce permissions, "
                "3) User has 'manage_woocommerce' capability. "
                f"Details: {wp_message}"
            )

        message = friendly_messages.get(status_code, f"{wp_message}")

        return {
            "error_code": error_code,
            "status_code": status_code,
            "message": message,
            "wp_error_code": wp_error_code,
            "raw_response": error_text[:500],  # Limit raw response length
        }

    async def get(
        self,
        endpoint: str,
        params: dict | None = None,
        use_custom_namespace: bool = False,
        use_woocommerce: bool = False,
    ) -> dict[str, Any]:
        """
        Make GET request.

        Args:
            endpoint: API endpoint
            params: Query parameters
            use_custom_namespace: Use custom namespace instead of wp/v2
            use_woocommerce: Use WooCommerce API base

        Returns:
            Dict: API response
        """
        return await self.request(
            "GET",
            endpoint,
            params=params,
            use_custom_namespace=use_custom_namespace,
            use_woocommerce=use_woocommerce,
        )

    async def post(
        self,
        endpoint: str,
        json_data: dict | None = None,
        data: Any | None = None,
        headers_override: dict | None = None,
        use_custom_namespace: bool = False,
        use_woocommerce: bool = False,
    ) -> dict[str, Any]:
        """
        Make POST request.

        Args:
            endpoint: API endpoint
            json_data: JSON body data
            data: Raw data or FormData for file uploads
            headers_override: Override default headers
            use_custom_namespace: Use custom namespace instead of wp/v2
            use_woocommerce: Use WooCommerce API base

        Returns:
            Dict: API response
        """
        return await self.request(
            "POST",
            endpoint,
            json_data=json_data,
            data=data,
            headers_override=headers_override,
            use_custom_namespace=use_custom_namespace,
            use_woocommerce=use_woocommerce,
        )

    async def put(
        self,
        endpoint: str,
        json_data: dict,
        use_custom_namespace: bool = False,
        use_woocommerce: bool = False,
    ) -> dict[str, Any]:
        """
        Make PUT request.

        Args:
            endpoint: API endpoint
            json_data: JSON body data
            use_custom_namespace: Use custom namespace instead of wp/v2
            use_woocommerce: Use WooCommerce API base

        Returns:
            Dict: API response
        """
        return await self.request(
            "PUT",
            endpoint,
            json_data=json_data,
            use_custom_namespace=use_custom_namespace,
            use_woocommerce=use_woocommerce,
        )

    async def patch(
        self,
        endpoint: str,
        json_data: dict,
        use_custom_namespace: bool = False,
        use_woocommerce: bool = False,
    ) -> dict[str, Any]:
        """
        Make PATCH request.

        Args:
            endpoint: API endpoint
            json_data: JSON body data
            use_custom_namespace: Use custom namespace instead of wp/v2
            use_woocommerce: Use WooCommerce API base

        Returns:
            Dict: API response
        """
        return await self.request(
            "PATCH",
            endpoint,
            json_data=json_data,
            use_custom_namespace=use_custom_namespace,
            use_woocommerce=use_woocommerce,
        )

    async def delete(
        self,
        endpoint: str,
        params: dict | None = None,
        use_custom_namespace: bool = False,
        use_woocommerce: bool = False,
    ) -> dict[str, Any]:
        """
        Make DELETE request.

        Args:
            endpoint: API endpoint
            params: Query parameters
            use_custom_namespace: Use custom namespace instead of wp/v2
            use_woocommerce: Use WooCommerce API base

        Returns:
            Dict: API response
        """
        return await self.request(
            "DELETE",
            endpoint,
            params=params,
            use_custom_namespace=use_custom_namespace,
            use_woocommerce=use_woocommerce,
        )

    async def check_woocommerce(self) -> dict[str, Any]:
        """
        Check if WooCommerce is installed and accessible.

        Returns:
            Dict with 'available' bool and version info
        """
        try:
            # Try to access WooCommerce system status endpoint
            response = await self.get("system_status", use_woocommerce=True)
            return {
                "available": True,
                "version": response.get("environment", {}).get("version", "unknown"),
            }
        except Exception:
            return {"available": False, "version": None}

    async def check_site_health(self) -> dict[str, Any]:
        """
        Check WordPress site health and accessibility.

        Returns:
            Dict with health status information
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.site_url}/wp-json") as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            "healthy": True,
                            "accessible": True,
                            "name": data.get("name", "Unknown"),
                            "description": data.get("description", "Unknown"),
                            "url": data.get("url", self.site_url),
                            "routes": len(data.get("routes", {})),
                        }
                    else:
                        return {
                            "healthy": False,
                            "accessible": False,
                            "message": f"Site returned status {response.status}",
                        }
        except Exception as e:
            return {
                "healthy": False,
                "accessible": False,
                "message": f"Health check failed: {str(e)}",
            }
