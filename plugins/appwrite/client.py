"""
Appwrite REST API Client (Self-Hosted)

Handles all HTTP communication with Appwrite Self-Hosted APIs.
Uses X-Appwrite-Project and X-Appwrite-Key headers for authentication.

APIs:
- Databases (/databases/) - Database, Collections, Documents
- Users (/users/) - User management
- Teams (/teams/) - Team management
- Storage (/storage/) - Buckets and Files
- Functions (/functions/) - Serverless Functions
- Messaging (/messaging/) - Email, SMS, Push
- Health (/health/) - Service health checks
- Avatars (/avatars/) - Avatar utilities
"""

import base64
import logging
from typing import Any

import aiohttp


class AppwriteClient:
    """
    Appwrite Self-Hosted API client.

    All requests include X-Appwrite-Project and X-Appwrite-Key headers.
    API key provides admin access and bypasses rate limits.
    """

    def __init__(self, base_url: str, project_id: str, api_key: str):
        """
        Initialize Appwrite API client.

        Args:
            base_url: Appwrite instance URL (e.g., https://appwrite.example.com/v1)
            project_id: Appwrite project ID
            api_key: API key with required scopes
        """
        self.base_url = base_url.rstrip("/")
        self.project_id = project_id
        self.api_key = api_key

        # Initialize logger
        self.logger = logging.getLogger(f"AppwriteClient.{base_url}")

    def _get_headers(self, additional_headers: dict | None = None) -> dict[str, str]:
        """
        Get request headers with API key authentication.

        Args:
            additional_headers: Additional headers to include

        Returns:
            Dict: Headers with authentication
        """
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Appwrite-Project": self.project_id,
            "X-Appwrite-Key": self.api_key,
        }

        if additional_headers:
            headers.update(additional_headers)

        return headers

    async def request(
        self,
        method: str,
        endpoint: str,
        params: dict | list | None = None,
        json_data: dict | list | None = None,
        data: bytes | None = None,
        headers_override: dict | None = None,
    ) -> Any:
        """
        Make authenticated request to Appwrite API.

        Args:
            method: HTTP method
            endpoint: API endpoint (with leading /)
            params: Query parameters (dict or list of tuples for repeated keys)
            json_data: JSON body data
            data: Raw binary data (for file uploads)
            headers_override: Override/add headers

        Returns:
            API response

        Raises:
            Exception: On API errors
        """
        url = f"{self.base_url}{endpoint}"

        headers = self._get_headers(headers_override)

        # Remove Content-Type for binary data (multipart)
        if data is not None:
            headers.pop("Content-Type", None)

        # Process params: convert dict to list of tuples, handle lists and booleans
        if params:
            if isinstance(params, dict):
                clean_params = []
                for k, v in params.items():
                    if v is None:
                        continue
                    # Handle list values - create multiple tuples with same key
                    if isinstance(v, list):
                        for item in v:
                            clean_params.append((k, item))
                    # Convert booleans to lowercase strings for URL params
                    elif isinstance(v, bool):
                        clean_params.append((k, "true" if v else "false"))
                    else:
                        clean_params.append((k, v))
                params = clean_params
            # If already a list, just filter None values
            elif isinstance(params, list):
                params = [(k, v) for k, v in params if v is not None]

        # Process JSON body: filter None values and coerce string types back to native
        if isinstance(json_data, dict):
            json_data = self._coerce_json_types(json_data)

        async with aiohttp.ClientSession() as session:
            kwargs = {
                "method": method,
                "url": url,
                "headers": headers,
            }

            if params:
                kwargs["params"] = params
            if json_data is not None:
                kwargs["json"] = json_data
            if data:
                kwargs["data"] = data

            async with session.request(**kwargs) as response:
                self.logger.debug(f"Response status: {response.status}")

                # Handle 204 No Content
                if response.status == 204:
                    return {"success": True}

                # Handle binary responses (file downloads)
                content_type = response.headers.get("Content-Type", "")
                if "application/json" not in content_type and response.status < 400:
                    # Return binary data as base64
                    binary_data = await response.read()
                    return {
                        "data": base64.b64encode(binary_data).decode(),
                        "content_type": content_type,
                        "size": len(binary_data),
                    }

                # Parse JSON response
                try:
                    response_data = await response.json()
                except Exception:
                    response_text = await response.text()
                    if response.status >= 400:
                        raise Exception(
                            f"Appwrite API error (status {response.status}): {response_text}"
                        )
                    return {"success": True, "message": response_text}

                # Check for errors
                if response.status >= 400:
                    error_msg = self._extract_error_message(response_data)
                    raise Exception(f"Appwrite API error (status {response.status}): {error_msg}")

                return response_data

    def _extract_error_message(self, response_data: Any) -> str:
        """Extract error message from Appwrite error response."""
        if isinstance(response_data, dict):
            if "message" in response_data:
                return response_data["message"]
            if "error" in response_data:
                return response_data["error"]
            if "type" in response_data:
                return (
                    f"{response_data.get('type')}: {response_data.get('message', 'Unknown error')}"
                )
        return str(response_data)

    def _coerce_json_types(self, data: dict) -> dict:
        """
        Coerce string representations back to native JSON types.

        MCP clients may send "true"/"false" strings instead of boolean,
        or "123" strings instead of integers. This method converts them
        back to native types for proper Appwrite API compatibility.

        Args:
            data: Dictionary with potential string-encoded values

        Returns:
            Dictionary with properly typed values
        """
        result = {}
        for k, v in data.items():
            if v is None:
                continue  # Filter out None values

            # Handle nested dictionaries
            if isinstance(v, dict):
                result[k] = self._coerce_json_types(v)
            # Handle lists
            elif isinstance(v, list):
                result[k] = [
                    (
                        self._coerce_json_types(item)
                        if isinstance(item, dict)
                        else self._coerce_value(item)
                    )
                    for item in v
                ]
            else:
                result[k] = self._coerce_value(v)

        return result

    def _coerce_value(self, value: Any) -> Any:
        """
        Coerce a single value to its native type.

        Converts:
        - "true"/"false" strings to boolean
        - Numeric strings to int/float
        - Preserves other values as-is
        """
        if isinstance(value, str):
            # Boolean conversion
            if value.lower() == "true":
                return True
            if value.lower() == "false":
                return False

            # Integer conversion (only for pure numeric strings)
            if value.lstrip("-").isdigit():
                try:
                    return int(value)
                except ValueError:
                    pass

            # Float conversion
            try:
                if "." in value and value.replace(".", "", 1).lstrip("-").isdigit():
                    return float(value)
            except ValueError:
                pass

        return value

    # =====================
    # DATABASES
    # =====================

    async def list_databases(
        self, queries: list[str] | None = None, search: str | None = None
    ) -> dict[str, Any]:
        """List all databases."""
        params = {}
        if queries:
            params["queries[]"] = queries
        if search:
            params["search"] = search

        return await self.request("GET", "/databases", params=params)

    async def get_database(self, database_id: str) -> dict[str, Any]:
        """Get database by ID."""
        return await self.request("GET", f"/databases/{database_id}")

    async def create_database(
        self, database_id: str, name: str, enabled: bool = True
    ) -> dict[str, Any]:
        """Create a new database."""
        data = {"databaseId": database_id, "name": name, "enabled": enabled}
        return await self.request("POST", "/databases", json_data=data)

    async def update_database(
        self, database_id: str, name: str, enabled: bool | None = None
    ) -> dict[str, Any]:
        """Update database."""
        data = {"name": name}
        if enabled is not None:
            data["enabled"] = enabled
        return await self.request("PUT", f"/databases/{database_id}", json_data=data)

    async def delete_database(self, database_id: str) -> dict[str, Any]:
        """Delete database."""
        return await self.request("DELETE", f"/databases/{database_id}")

    # =====================
    # COLLECTIONS
    # =====================

    async def list_collections(
        self, database_id: str, queries: list[str] | None = None, search: str | None = None
    ) -> dict[str, Any]:
        """List collections in a database."""
        params = {}
        if queries:
            params["queries[]"] = queries
        if search:
            params["search"] = search

        return await self.request("GET", f"/databases/{database_id}/collections", params=params)

    async def get_collection(self, database_id: str, collection_id: str) -> dict[str, Any]:
        """Get collection by ID."""
        return await self.request("GET", f"/databases/{database_id}/collections/{collection_id}")

    async def create_collection(
        self,
        database_id: str,
        collection_id: str,
        name: str,
        permissions: list[str] | None = None,
        document_security: bool = True,
        enabled: bool = True,
    ) -> dict[str, Any]:
        """Create a new collection."""
        data = {
            "collectionId": collection_id,
            "name": name,
            "documentSecurity": document_security,
            "enabled": enabled,
        }
        if permissions:
            data["permissions"] = permissions

        return await self.request("POST", f"/databases/{database_id}/collections", json_data=data)

    async def update_collection(
        self,
        database_id: str,
        collection_id: str,
        name: str,
        permissions: list[str] | None = None,
        document_security: bool | None = None,
        enabled: bool | None = None,
    ) -> dict[str, Any]:
        """Update collection."""
        data = {"name": name}
        if permissions is not None:
            data["permissions"] = permissions
        if document_security is not None:
            data["documentSecurity"] = document_security
        if enabled is not None:
            data["enabled"] = enabled

        return await self.request(
            "PUT", f"/databases/{database_id}/collections/{collection_id}", json_data=data
        )

    async def delete_collection(self, database_id: str, collection_id: str) -> dict[str, Any]:
        """Delete collection."""
        return await self.request("DELETE", f"/databases/{database_id}/collections/{collection_id}")

    # =====================
    # ATTRIBUTES
    # =====================

    async def list_attributes(
        self, database_id: str, collection_id: str, queries: list[str] | None = None
    ) -> dict[str, Any]:
        """List attributes of a collection."""
        params = {}
        if queries:
            params["queries[]"] = queries

        return await self.request(
            "GET", f"/databases/{database_id}/collections/{collection_id}/attributes", params=params
        )

    async def create_string_attribute(
        self,
        database_id: str,
        collection_id: str,
        key: str,
        size: int,
        required: bool = False,
        default: str | None = None,
        array: bool = False,
        encrypt: bool = False,
    ) -> dict[str, Any]:
        """Create a string attribute."""
        data = {"key": key, "size": size, "required": required, "array": array, "encrypt": encrypt}
        if default is not None:
            data["default"] = default

        return await self.request(
            "POST",
            f"/databases/{database_id}/collections/{collection_id}/attributes/string",
            json_data=data,
        )

    async def create_integer_attribute(
        self,
        database_id: str,
        collection_id: str,
        key: str,
        required: bool = False,
        min: int | None = None,
        max: int | None = None,
        default: int | None = None,
        array: bool = False,
    ) -> dict[str, Any]:
        """Create an integer attribute."""
        data = {"key": key, "required": required, "array": array}
        if min is not None:
            data["min"] = min
        if max is not None:
            data["max"] = max
        if default is not None:
            data["default"] = default

        return await self.request(
            "POST",
            f"/databases/{database_id}/collections/{collection_id}/attributes/integer",
            json_data=data,
        )

    async def create_float_attribute(
        self,
        database_id: str,
        collection_id: str,
        key: str,
        required: bool = False,
        min: float | None = None,
        max: float | None = None,
        default: float | None = None,
        array: bool = False,
    ) -> dict[str, Any]:
        """Create a float attribute."""
        data = {"key": key, "required": required, "array": array}
        if min is not None:
            data["min"] = min
        if max is not None:
            data["max"] = max
        if default is not None:
            data["default"] = default

        return await self.request(
            "POST",
            f"/databases/{database_id}/collections/{collection_id}/attributes/float",
            json_data=data,
        )

    async def create_boolean_attribute(
        self,
        database_id: str,
        collection_id: str,
        key: str,
        required: bool = False,
        default: bool | None = None,
        array: bool = False,
    ) -> dict[str, Any]:
        """Create a boolean attribute."""
        data = {"key": key, "required": required, "array": array}
        if default is not None:
            data["default"] = default

        return await self.request(
            "POST",
            f"/databases/{database_id}/collections/{collection_id}/attributes/boolean",
            json_data=data,
        )

    async def create_datetime_attribute(
        self,
        database_id: str,
        collection_id: str,
        key: str,
        required: bool = False,
        default: str | None = None,
        array: bool = False,
    ) -> dict[str, Any]:
        """Create a datetime attribute."""
        data = {"key": key, "required": required, "array": array}
        if default is not None:
            data["default"] = default

        return await self.request(
            "POST",
            f"/databases/{database_id}/collections/{collection_id}/attributes/datetime",
            json_data=data,
        )

    async def create_email_attribute(
        self,
        database_id: str,
        collection_id: str,
        key: str,
        required: bool = False,
        default: str | None = None,
        array: bool = False,
    ) -> dict[str, Any]:
        """Create an email attribute."""
        data = {"key": key, "required": required, "array": array}
        if default is not None:
            data["default"] = default

        return await self.request(
            "POST",
            f"/databases/{database_id}/collections/{collection_id}/attributes/email",
            json_data=data,
        )

    async def create_url_attribute(
        self,
        database_id: str,
        collection_id: str,
        key: str,
        required: bool = False,
        default: str | None = None,
        array: bool = False,
    ) -> dict[str, Any]:
        """Create a URL attribute."""
        data = {"key": key, "required": required, "array": array}
        if default is not None:
            data["default"] = default

        return await self.request(
            "POST",
            f"/databases/{database_id}/collections/{collection_id}/attributes/url",
            json_data=data,
        )

    async def create_ip_attribute(
        self,
        database_id: str,
        collection_id: str,
        key: str,
        required: bool = False,
        default: str | None = None,
        array: bool = False,
    ) -> dict[str, Any]:
        """Create an IP address attribute."""
        data = {"key": key, "required": required, "array": array}
        if default is not None:
            data["default"] = default

        return await self.request(
            "POST",
            f"/databases/{database_id}/collections/{collection_id}/attributes/ip",
            json_data=data,
        )

    async def create_enum_attribute(
        self,
        database_id: str,
        collection_id: str,
        key: str,
        elements: list[str],
        required: bool = False,
        default: str | None = None,
        array: bool = False,
    ) -> dict[str, Any]:
        """Create an enum attribute."""
        data = {"key": key, "elements": elements, "required": required, "array": array}
        if default is not None:
            data["default"] = default

        return await self.request(
            "POST",
            f"/databases/{database_id}/collections/{collection_id}/attributes/enum",
            json_data=data,
        )

    async def create_relationship_attribute(
        self,
        database_id: str,
        collection_id: str,
        related_collection_id: str,
        type: str,
        two_way: bool = False,
        key: str | None = None,
        two_way_key: str | None = None,
        on_delete: str = "setNull",
    ) -> dict[str, Any]:
        """Create a relationship attribute."""
        data = {
            "relatedCollectionId": related_collection_id,
            "type": type,  # oneToOne, oneToMany, manyToOne, manyToMany
            "twoWay": two_way,
            "onDelete": on_delete,  # setNull, cascade, restrict
        }
        if key:
            data["key"] = key
        if two_way_key:
            data["twoWayKey"] = two_way_key

        return await self.request(
            "POST",
            f"/databases/{database_id}/collections/{collection_id}/attributes/relationship",
            json_data=data,
        )

    async def get_attribute(self, database_id: str, collection_id: str, key: str) -> dict[str, Any]:
        """Get attribute by key."""
        return await self.request(
            "GET", f"/databases/{database_id}/collections/{collection_id}/attributes/{key}"
        )

    async def delete_attribute(
        self, database_id: str, collection_id: str, key: str
    ) -> dict[str, Any]:
        """Delete attribute."""
        return await self.request(
            "DELETE", f"/databases/{database_id}/collections/{collection_id}/attributes/{key}"
        )

    # =====================
    # INDEXES
    # =====================

    async def list_indexes(
        self, database_id: str, collection_id: str, queries: list[str] | None = None
    ) -> dict[str, Any]:
        """List indexes of a collection."""
        params = {}
        if queries:
            params["queries[]"] = queries

        return await self.request(
            "GET", f"/databases/{database_id}/collections/{collection_id}/indexes", params=params
        )

    async def create_index(
        self,
        database_id: str,
        collection_id: str,
        key: str,
        type: str,
        attributes: list[str],
        orders: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create an index."""
        data = {"key": key, "type": type, "attributes": attributes}  # key, unique, fulltext
        if orders:
            data["orders"] = orders

        return await self.request(
            "POST", f"/databases/{database_id}/collections/{collection_id}/indexes", json_data=data
        )

    async def get_index(self, database_id: str, collection_id: str, key: str) -> dict[str, Any]:
        """Get index by key."""
        return await self.request(
            "GET", f"/databases/{database_id}/collections/{collection_id}/indexes/{key}"
        )

    async def delete_index(self, database_id: str, collection_id: str, key: str) -> dict[str, Any]:
        """Delete index."""
        return await self.request(
            "DELETE", f"/databases/{database_id}/collections/{collection_id}/indexes/{key}"
        )

    # =====================
    # DOCUMENTS
    # =====================

    async def list_documents(
        self, database_id: str, collection_id: str, queries: list[str] | None = None
    ) -> dict[str, Any]:
        """List documents in a collection."""
        params = {}
        if queries:
            # Send each query as separate queries[] param - Appwrite REST API format
            params["queries[]"] = queries

        return await self.request(
            "GET", f"/databases/{database_id}/collections/{collection_id}/documents", params=params
        )

    async def get_document(
        self,
        database_id: str,
        collection_id: str,
        document_id: str,
        queries: list[str] | None = None,
    ) -> dict[str, Any]:
        """Get document by ID."""
        params = {}
        if queries:
            params["queries[]"] = queries

        return await self.request(
            "GET",
            f"/databases/{database_id}/collections/{collection_id}/documents/{document_id}",
            params=params,
        )

    async def create_document(
        self,
        database_id: str,
        collection_id: str,
        document_id: str,
        data: dict[str, Any],
        permissions: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a new document."""
        body = {"documentId": document_id, "data": data}
        if permissions:
            body["permissions"] = permissions

        return await self.request(
            "POST",
            f"/databases/{database_id}/collections/{collection_id}/documents",
            json_data=body,
        )

    async def update_document(
        self,
        database_id: str,
        collection_id: str,
        document_id: str,
        data: dict[str, Any] | None = None,
        permissions: list[str] | None = None,
    ) -> dict[str, Any]:
        """Update document."""
        body = {}
        if data:
            body["data"] = data
        if permissions is not None:
            body["permissions"] = permissions

        return await self.request(
            "PATCH",
            f"/databases/{database_id}/collections/{collection_id}/documents/{document_id}",
            json_data=body,
        )

    async def delete_document(
        self, database_id: str, collection_id: str, document_id: str
    ) -> dict[str, Any]:
        """Delete document."""
        return await self.request(
            "DELETE",
            f"/databases/{database_id}/collections/{collection_id}/documents/{document_id}",
        )

    # =====================
    # USERS
    # =====================

    async def list_users(
        self, queries: list[str] | None = None, search: str | None = None
    ) -> dict[str, Any]:
        """List users."""
        params = {}
        if queries:
            for i, q in enumerate(queries):
                params[f"queries[{i}]"] = q
        if search:
            params["search"] = search

        return await self.request("GET", "/users", params=params)

    async def get_user(self, user_id: str) -> dict[str, Any]:
        """Get user by ID."""
        return await self.request("GET", f"/users/{user_id}")

    async def create_user(
        self,
        user_id: str,
        email: str | None = None,
        phone: str | None = None,
        password: str | None = None,
        name: str | None = None,
    ) -> dict[str, Any]:
        """Create a new user."""
        data = {"userId": user_id}
        if email:
            data["email"] = email
        if phone:
            data["phone"] = phone
        if password:
            data["password"] = password
        if name:
            data["name"] = name

        return await self.request("POST", "/users", json_data=data)

    async def update_user_name(self, user_id: str, name: str) -> dict[str, Any]:
        """Update user name."""
        return await self.request("PATCH", f"/users/{user_id}/name", json_data={"name": name})

    async def update_user_email(self, user_id: str, email: str) -> dict[str, Any]:
        """Update user email."""
        return await self.request("PATCH", f"/users/{user_id}/email", json_data={"email": email})

    async def update_user_phone(self, user_id: str, number: str) -> dict[str, Any]:
        """Update user phone."""
        return await self.request("PATCH", f"/users/{user_id}/phone", json_data={"number": number})

    async def update_user_password(self, user_id: str, password: str) -> dict[str, Any]:
        """Update user password."""
        return await self.request(
            "PATCH", f"/users/{user_id}/password", json_data={"password": password}
        )

    async def update_user_status(self, user_id: str, status: bool) -> dict[str, Any]:
        """Update user status (enable/disable)."""
        return await self.request("PATCH", f"/users/{user_id}/status", json_data={"status": status})

    async def update_user_labels(self, user_id: str, labels: list[str]) -> dict[str, Any]:
        """Update user labels."""
        return await self.request("PUT", f"/users/{user_id}/labels", json_data={"labels": labels})

    async def update_user_prefs(self, user_id: str, prefs: dict[str, Any]) -> dict[str, Any]:
        """Update user preferences."""
        return await self.request("PATCH", f"/users/{user_id}/prefs", json_data={"prefs": prefs})

    async def delete_user(self, user_id: str) -> dict[str, Any]:
        """Delete user."""
        return await self.request("DELETE", f"/users/{user_id}")

    async def list_user_sessions(self, user_id: str) -> dict[str, Any]:
        """List user sessions."""
        return await self.request("GET", f"/users/{user_id}/sessions")

    async def delete_user_sessions(self, user_id: str) -> dict[str, Any]:
        """Delete all user sessions."""
        return await self.request("DELETE", f"/users/{user_id}/sessions")

    async def delete_user_session(self, user_id: str, session_id: str) -> dict[str, Any]:
        """Delete a specific user session."""
        return await self.request("DELETE", f"/users/{user_id}/sessions/{session_id}")

    # =====================
    # TEAMS
    # =====================

    async def list_teams(
        self, queries: list[str] | None = None, search: str | None = None
    ) -> dict[str, Any]:
        """List teams."""
        params = {}
        if queries:
            for i, q in enumerate(queries):
                params[f"queries[{i}]"] = q
        if search:
            params["search"] = search

        return await self.request("GET", "/teams", params=params)

    async def get_team(self, team_id: str) -> dict[str, Any]:
        """Get team by ID."""
        return await self.request("GET", f"/teams/{team_id}")

    async def create_team(
        self, team_id: str, name: str, roles: list[str] | None = None
    ) -> dict[str, Any]:
        """Create a new team."""
        data = {"teamId": team_id, "name": name}
        if roles:
            data["roles"] = roles

        return await self.request("POST", "/teams", json_data=data)

    async def update_team(self, team_id: str, name: str) -> dict[str, Any]:
        """Update team name."""
        return await self.request("PUT", f"/teams/{team_id}", json_data={"name": name})

    async def delete_team(self, team_id: str) -> dict[str, Any]:
        """Delete team."""
        return await self.request("DELETE", f"/teams/{team_id}")

    async def list_team_memberships(
        self, team_id: str, queries: list[str] | None = None, search: str | None = None
    ) -> dict[str, Any]:
        """List team memberships."""
        params = {}
        if queries:
            for i, q in enumerate(queries):
                params[f"queries[{i}]"] = q
        if search:
            params["search"] = search

        return await self.request("GET", f"/teams/{team_id}/memberships", params=params)

    async def create_team_membership(
        self,
        team_id: str,
        roles: list[str],
        email: str | None = None,
        user_id: str | None = None,
        phone: str | None = None,
        url: str | None = None,
        name: str | None = None,
    ) -> dict[str, Any]:
        """Create team membership (invite)."""
        data = {"roles": roles}
        if email:
            data["email"] = email
        if user_id:
            data["userId"] = user_id
        if phone:
            data["phone"] = phone
        if url:
            data["url"] = url
        if name:
            data["name"] = name

        return await self.request("POST", f"/teams/{team_id}/memberships", json_data=data)

    async def update_membership(
        self, team_id: str, membership_id: str, roles: list[str]
    ) -> dict[str, Any]:
        """Update membership roles."""
        return await self.request(
            "PATCH", f"/teams/{team_id}/memberships/{membership_id}", json_data={"roles": roles}
        )

    async def delete_membership(self, team_id: str, membership_id: str) -> dict[str, Any]:
        """Delete team membership."""
        return await self.request("DELETE", f"/teams/{team_id}/memberships/{membership_id}")

    # =====================
    # STORAGE
    # =====================

    async def list_buckets(
        self, queries: list[str] | None = None, search: str | None = None
    ) -> dict[str, Any]:
        """List storage buckets."""
        params = {}
        if queries:
            for i, q in enumerate(queries):
                params[f"queries[{i}]"] = q
        if search:
            params["search"] = search

        return await self.request("GET", "/storage/buckets", params=params)

    async def get_bucket(self, bucket_id: str) -> dict[str, Any]:
        """Get bucket by ID."""
        return await self.request("GET", f"/storage/buckets/{bucket_id}")

    async def create_bucket(
        self,
        bucket_id: str,
        name: str,
        permissions: list[str] | None = None,
        file_security: bool = True,
        enabled: bool = True,
        maximum_file_size: int | None = None,
        allowed_file_extensions: list[str] | None = None,
        compression: str = "none",
        encryption: bool = True,
        antivirus: bool = True,
    ) -> dict[str, Any]:
        """Create a new bucket."""
        data = {
            "bucketId": bucket_id,
            "name": name,
            "fileSecurity": file_security,
            "enabled": enabled,
            "compression": compression,
            "encryption": encryption,
            "antivirus": antivirus,
        }
        if permissions:
            data["permissions"] = permissions
        if maximum_file_size:
            data["maximumFileSize"] = maximum_file_size
        if allowed_file_extensions:
            data["allowedFileExtensions"] = allowed_file_extensions

        return await self.request("POST", "/storage/buckets", json_data=data)

    async def update_bucket(
        self,
        bucket_id: str,
        name: str,
        permissions: list[str] | None = None,
        file_security: bool | None = None,
        enabled: bool | None = None,
        maximum_file_size: int | None = None,
        allowed_file_extensions: list[str] | None = None,
        compression: str | None = None,
        encryption: bool | None = None,
        antivirus: bool | None = None,
    ) -> dict[str, Any]:
        """Update bucket."""
        data = {"name": name}
        if permissions is not None:
            data["permissions"] = permissions
        if file_security is not None:
            data["fileSecurity"] = file_security
        if enabled is not None:
            data["enabled"] = enabled
        if maximum_file_size is not None:
            data["maximumFileSize"] = maximum_file_size
        if allowed_file_extensions is not None:
            data["allowedFileExtensions"] = allowed_file_extensions
        if compression is not None:
            data["compression"] = compression
        if encryption is not None:
            data["encryption"] = encryption
        if antivirus is not None:
            data["antivirus"] = antivirus

        return await self.request("PUT", f"/storage/buckets/{bucket_id}", json_data=data)

    async def delete_bucket(self, bucket_id: str) -> dict[str, Any]:
        """Delete bucket."""
        return await self.request("DELETE", f"/storage/buckets/{bucket_id}")

    async def list_files(
        self, bucket_id: str, queries: list[str] | None = None, search: str | None = None
    ) -> dict[str, Any]:
        """List files in a bucket."""
        params = {}
        if queries:
            for i, q in enumerate(queries):
                params[f"queries[{i}]"] = q
        if search:
            params["search"] = search

        return await self.request("GET", f"/storage/buckets/{bucket_id}/files", params=params)

    async def get_file(self, bucket_id: str, file_id: str) -> dict[str, Any]:
        """Get file metadata."""
        return await self.request("GET", f"/storage/buckets/{bucket_id}/files/{file_id}")

    async def delete_file(self, bucket_id: str, file_id: str) -> dict[str, Any]:
        """Delete file."""
        return await self.request("DELETE", f"/storage/buckets/{bucket_id}/files/{file_id}")

    async def get_file_download(self, bucket_id: str, file_id: str) -> dict[str, Any]:
        """Download file (returns base64 content)."""
        return await self.request("GET", f"/storage/buckets/{bucket_id}/files/{file_id}/download")

    async def get_file_preview(
        self,
        bucket_id: str,
        file_id: str,
        width: int | None = None,
        height: int | None = None,
        gravity: str | None = None,
        quality: int | None = None,
        border_width: int | None = None,
        border_color: str | None = None,
        border_radius: int | None = None,
        opacity: float | None = None,
        rotation: int | None = None,
        background: str | None = None,
        output: str | None = None,
    ) -> dict[str, Any]:
        """Get file preview (image transformation)."""
        params = {}
        if width:
            params["width"] = width
        if height:
            params["height"] = height
        if gravity:
            params["gravity"] = gravity
        if quality:
            params["quality"] = quality
        if border_width:
            params["borderWidth"] = border_width
        if border_color:
            params["borderColor"] = border_color
        if border_radius:
            params["borderRadius"] = border_radius
        if opacity:
            params["opacity"] = opacity
        if rotation:
            params["rotation"] = rotation
        if background:
            params["background"] = background
        if output:
            params["output"] = output

        return await self.request(
            "GET", f"/storage/buckets/{bucket_id}/files/{file_id}/preview", params=params
        )

    async def get_file_view(self, bucket_id: str, file_id: str) -> dict[str, Any]:
        """Get file for viewing in browser."""
        return await self.request("GET", f"/storage/buckets/{bucket_id}/files/{file_id}/view")

    # =====================
    # FUNCTIONS
    # =====================

    async def list_functions(
        self, queries: list[str] | None = None, search: str | None = None
    ) -> dict[str, Any]:
        """List functions."""
        params = {}
        if queries:
            for i, q in enumerate(queries):
                params[f"queries[{i}]"] = q
        if search:
            params["search"] = search

        return await self.request("GET", "/functions", params=params)

    async def get_function(self, function_id: str) -> dict[str, Any]:
        """Get function by ID."""
        return await self.request("GET", f"/functions/{function_id}")

    async def create_function(
        self,
        function_id: str,
        name: str,
        runtime: str,
        execute: list[str] | None = None,
        events: list[str] | None = None,
        schedule: str | None = None,
        timeout: int = 15,
        enabled: bool = True,
        logging: bool = True,
        entrypoint: str | None = None,
        commands: str | None = None,
        scopes: list[str] | None = None,
        installation_id: str | None = None,
        provider_repository_id: str | None = None,
        provider_branch: str | None = None,
        provider_silent_mode: bool = False,
        provider_root_directory: str | None = None,
    ) -> dict[str, Any]:
        """Create a new function."""
        data = {
            "functionId": function_id,
            "name": name,
            "runtime": runtime,
            "timeout": timeout,
            "enabled": enabled,
            "logging": logging,
            "providerSilentMode": provider_silent_mode,
        }
        if execute:
            data["execute"] = execute
        if events:
            data["events"] = events
        if schedule:
            data["schedule"] = schedule
        if entrypoint:
            data["entrypoint"] = entrypoint
        if commands:
            data["commands"] = commands
        if scopes:
            data["scopes"] = scopes
        if installation_id:
            data["installationId"] = installation_id
        if provider_repository_id:
            data["providerRepositoryId"] = provider_repository_id
        if provider_branch:
            data["providerBranch"] = provider_branch
        if provider_root_directory:
            data["providerRootDirectory"] = provider_root_directory

        return await self.request("POST", "/functions", json_data=data)

    async def update_function(
        self,
        function_id: str,
        name: str,
        runtime: str | None = None,
        execute: list[str] | None = None,
        events: list[str] | None = None,
        schedule: str | None = None,
        timeout: int | None = None,
        enabled: bool | None = None,
        logging: bool | None = None,
        entrypoint: str | None = None,
        commands: str | None = None,
        scopes: list[str] | None = None,
    ) -> dict[str, Any]:
        """Update function."""
        data = {"name": name}
        if runtime:
            data["runtime"] = runtime
        if execute is not None:
            data["execute"] = execute
        if events is not None:
            data["events"] = events
        if schedule is not None:
            data["schedule"] = schedule
        if timeout is not None:
            data["timeout"] = timeout
        if enabled is not None:
            data["enabled"] = enabled
        if logging is not None:
            data["logging"] = logging
        if entrypoint:
            data["entrypoint"] = entrypoint
        if commands:
            data["commands"] = commands
        if scopes is not None:
            data["scopes"] = scopes

        return await self.request("PUT", f"/functions/{function_id}", json_data=data)

    async def delete_function(self, function_id: str) -> dict[str, Any]:
        """Delete function."""
        return await self.request("DELETE", f"/functions/{function_id}")

    async def list_deployments(
        self, function_id: str, queries: list[str] | None = None, search: str | None = None
    ) -> dict[str, Any]:
        """List function deployments."""
        params = {}
        if queries:
            for i, q in enumerate(queries):
                params[f"queries[{i}]"] = q
        if search:
            params["search"] = search

        return await self.request("GET", f"/functions/{function_id}/deployments", params=params)

    async def get_deployment(self, function_id: str, deployment_id: str) -> dict[str, Any]:
        """Get deployment by ID."""
        return await self.request("GET", f"/functions/{function_id}/deployments/{deployment_id}")

    async def delete_deployment(self, function_id: str, deployment_id: str) -> dict[str, Any]:
        """Delete deployment."""
        return await self.request("DELETE", f"/functions/{function_id}/deployments/{deployment_id}")

    async def update_deployment(self, function_id: str, deployment_id: str) -> dict[str, Any]:
        """Activate deployment (set as active)."""
        return await self.request("PATCH", f"/functions/{function_id}/deployments/{deployment_id}")

    async def list_executions(
        self, function_id: str, queries: list[str] | None = None, search: str | None = None
    ) -> dict[str, Any]:
        """List function executions."""
        params = {}
        if queries:
            for i, q in enumerate(queries):
                params[f"queries[{i}]"] = q
        if search:
            params["search"] = search

        return await self.request("GET", f"/functions/{function_id}/executions", params=params)

    async def get_execution(self, function_id: str, execution_id: str) -> dict[str, Any]:
        """Get execution by ID."""
        return await self.request("GET", f"/functions/{function_id}/executions/{execution_id}")

    async def create_execution(
        self,
        function_id: str,
        body: str | None = None,
        async_execution: bool = False,
        path: str | None = None,
        method: str = "POST",
        headers: dict[str, str] | None = None,
        scheduled_at: str | None = None,
    ) -> dict[str, Any]:
        """Execute a function."""
        data = {"async": async_execution, "method": method}
        if body:
            data["body"] = body
        if path:
            data["path"] = path
        if headers:
            data["headers"] = headers
        if scheduled_at:
            data["scheduledAt"] = scheduled_at

        return await self.request("POST", f"/functions/{function_id}/executions", json_data=data)

    async def delete_execution(self, function_id: str, execution_id: str) -> dict[str, Any]:
        """Delete execution."""
        return await self.request("DELETE", f"/functions/{function_id}/executions/{execution_id}")

    # =====================
    # HEALTH
    # =====================

    async def health(self) -> dict[str, Any]:
        """Get general health status."""
        return await self.request("GET", "/health")

    async def health_db(self) -> dict[str, Any]:
        """Get database health status."""
        return await self.request("GET", "/health/db")

    async def health_cache(self) -> dict[str, Any]:
        """Get cache health status."""
        return await self.request("GET", "/health/cache")

    async def health_pubsub(self) -> dict[str, Any]:
        """Get pub/sub health status."""
        return await self.request("GET", "/health/pubsub")

    async def health_queue(self) -> dict[str, Any]:
        """Get queue health status."""
        return await self.request("GET", "/health/queue")

    async def health_storage_local(self) -> dict[str, Any]:
        """Get local storage health status."""
        return await self.request("GET", "/health/storage/local")

    async def health_time(self) -> dict[str, Any]:
        """Get time sync health status."""
        return await self.request("GET", "/health/time")

    async def health_certificate(self, domain: str | None = None) -> dict[str, Any]:
        """Get SSL certificate health status."""
        params = {}
        if domain:
            params["domain"] = domain
        return await self.request("GET", "/health/certificate", params=params)

    # =====================
    # AVATARS
    # =====================

    async def get_avatar_initials(
        self,
        name: str | None = None,
        width: int = 100,
        height: int = 100,
        background: str | None = None,
    ) -> dict[str, Any]:
        """Get avatar image from initials."""
        params = {"width": width, "height": height}
        if name:
            params["name"] = name
        if background:
            params["background"] = background

        return await self.request("GET", "/avatars/initials", params=params)

    async def get_avatar_image(
        self, url: str, width: int = 400, height: int = 400
    ) -> dict[str, Any]:
        """Get avatar from URL."""
        params = {"url": url, "width": width, "height": height}
        return await self.request("GET", "/avatars/image", params=params)

    async def get_favicon(self, url: str) -> dict[str, Any]:
        """Get website favicon."""
        return await self.request("GET", "/avatars/favicon", params={"url": url})

    async def get_qr_code(
        self, text: str, size: int = 400, margin: int = 1, download: bool = False
    ) -> dict[str, Any]:
        """Generate QR code."""
        params = {"text": text, "size": size, "margin": margin, "download": download}
        return await self.request("GET", "/avatars/qr", params=params)

    # =====================
    # MESSAGING (Server SDK)
    # =====================

    async def list_providers(
        self, queries: list[str] | None = None, search: str | None = None
    ) -> dict[str, Any]:
        """List messaging providers."""
        params = {}
        if queries:
            for i, q in enumerate(queries):
                params[f"queries[{i}]"] = q
        if search:
            params["search"] = search

        return await self.request("GET", "/messaging/providers", params=params)

    async def list_topics(
        self, queries: list[str] | None = None, search: str | None = None
    ) -> dict[str, Any]:
        """List messaging topics."""
        params = {}
        if queries:
            for i, q in enumerate(queries):
                params[f"queries[{i}]"] = q
        if search:
            params["search"] = search

        return await self.request("GET", "/messaging/topics", params=params)

    async def get_topic(self, topic_id: str) -> dict[str, Any]:
        """Get topic by ID."""
        return await self.request("GET", f"/messaging/topics/{topic_id}")

    async def create_topic(
        self, topic_id: str, name: str, subscribe: list[str] | None = None
    ) -> dict[str, Any]:
        """Create a messaging topic."""
        data = {"topicId": topic_id, "name": name}
        if subscribe:
            data["subscribe"] = subscribe

        return await self.request("POST", "/messaging/topics", json_data=data)

    async def update_topic(
        self, topic_id: str, name: str | None = None, subscribe: list[str] | None = None
    ) -> dict[str, Any]:
        """Update topic."""
        data = {}
        if name:
            data["name"] = name
        if subscribe is not None:
            data["subscribe"] = subscribe

        return await self.request("PATCH", f"/messaging/topics/{topic_id}", json_data=data)

    async def delete_topic(self, topic_id: str) -> dict[str, Any]:
        """Delete topic."""
        return await self.request("DELETE", f"/messaging/topics/{topic_id}")

    async def create_subscriber(
        self, topic_id: str, subscriber_id: str, target_id: str
    ) -> dict[str, Any]:
        """Add subscriber to topic."""
        data = {"subscriberId": subscriber_id, "targetId": target_id}
        return await self.request(
            "POST", f"/messaging/topics/{topic_id}/subscribers", json_data=data
        )

    async def delete_subscriber(self, topic_id: str, subscriber_id: str) -> dict[str, Any]:
        """Remove subscriber from topic."""
        return await self.request(
            "DELETE", f"/messaging/topics/{topic_id}/subscribers/{subscriber_id}"
        )

    async def list_messages(
        self, queries: list[str] | None = None, search: str | None = None
    ) -> dict[str, Any]:
        """List messages."""
        params = {}
        if queries:
            for i, q in enumerate(queries):
                params[f"queries[{i}]"] = q
        if search:
            params["search"] = search

        return await self.request("GET", "/messaging/messages", params=params)

    async def get_message(self, message_id: str) -> dict[str, Any]:
        """Get message by ID."""
        return await self.request("GET", f"/messaging/messages/{message_id}")

    async def create_email(
        self,
        message_id: str,
        subject: str,
        content: str,
        topics: list[str] | None = None,
        users: list[str] | None = None,
        targets: list[str] | None = None,
        cc: list[str] | None = None,
        bcc: list[str] | None = None,
        attachments: list[str] | None = None,
        draft: bool = False,
        html: bool = True,
        scheduled_at: str | None = None,
    ) -> dict[str, Any]:
        """Create/send email message."""
        data = {
            "messageId": message_id,
            "subject": subject,
            "content": content,
            "draft": draft,
            "html": html,
        }
        if topics:
            data["topics"] = topics
        if users:
            data["users"] = users
        if targets:
            data["targets"] = targets
        if cc:
            data["cc"] = cc
        if bcc:
            data["bcc"] = bcc
        if attachments:
            data["attachments"] = attachments
        if scheduled_at:
            data["scheduledAt"] = scheduled_at

        return await self.request("POST", "/messaging/messages/email", json_data=data)

    async def create_sms(
        self,
        message_id: str,
        content: str,
        topics: list[str] | None = None,
        users: list[str] | None = None,
        targets: list[str] | None = None,
        draft: bool = False,
        scheduled_at: str | None = None,
    ) -> dict[str, Any]:
        """Create/send SMS message."""
        data = {"messageId": message_id, "content": content, "draft": draft}
        if topics:
            data["topics"] = topics
        if users:
            data["users"] = users
        if targets:
            data["targets"] = targets
        if scheduled_at:
            data["scheduledAt"] = scheduled_at

        return await self.request("POST", "/messaging/messages/sms", json_data=data)

    async def create_push(
        self,
        message_id: str,
        title: str,
        body: str,
        topics: list[str] | None = None,
        users: list[str] | None = None,
        targets: list[str] | None = None,
        data_payload: dict[str, Any] | None = None,
        action: str | None = None,
        image: str | None = None,
        icon: str | None = None,
        sound: str | None = None,
        color: str | None = None,
        tag: str | None = None,
        badge: int | None = None,
        draft: bool = False,
        scheduled_at: str | None = None,
    ) -> dict[str, Any]:
        """Create/send push notification."""
        data = {"messageId": message_id, "title": title, "body": body, "draft": draft}
        if topics:
            data["topics"] = topics
        if users:
            data["users"] = users
        if targets:
            data["targets"] = targets
        if data_payload:
            data["data"] = data_payload
        if action:
            data["action"] = action
        if image:
            data["image"] = image
        if icon:
            data["icon"] = icon
        if sound:
            data["sound"] = sound
        if color:
            data["color"] = color
        if tag:
            data["tag"] = tag
        if badge is not None:
            data["badge"] = badge
        if scheduled_at:
            data["scheduledAt"] = scheduled_at

        return await self.request("POST", "/messaging/messages/push", json_data=data)

    async def delete_message(self, message_id: str) -> dict[str, Any]:
        """Delete message."""
        return await self.request("DELETE", f"/messaging/messages/{message_id}")

    # =====================
    # COMPREHENSIVE HEALTH CHECK
    # =====================

    async def health_check(self) -> dict[str, Any]:
        """
        Check Appwrite instance health.

        Returns comprehensive health status of all services.
        """
        results = {"healthy": True, "services": {}}

        # Check general health
        try:
            health = await self.health()
            results["services"]["general"] = health.get("status", "ok")
        except Exception as e:
            results["services"]["general"] = f"error: {str(e)}"
            results["healthy"] = False

        # Check database
        try:
            db_health = await self.health_db()
            results["services"]["database"] = db_health.get("status", "ok")
        except Exception as e:
            results["services"]["database"] = f"error: {str(e)}"
            results["healthy"] = False

        # Check cache
        try:
            cache_health = await self.health_cache()
            results["services"]["cache"] = cache_health.get("status", "ok")
        except Exception as e:
            results["services"]["cache"] = f"error: {str(e)}"
            # Cache error might not be critical
            if "error" not in str(e).lower():
                results["services"]["cache"] = "warning"

        # Check storage
        try:
            storage_health = await self.health_storage_local()
            results["services"]["storage"] = storage_health.get("status", "ok")
        except Exception as e:
            results["services"]["storage"] = f"error: {str(e)}"
            results["healthy"] = False

        return results
