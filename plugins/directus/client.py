"""
Directus REST API Client (Self-Hosted)

Handles all HTTP communication with Directus Self-Hosted APIs.
Uses static token authentication via Authorization: Bearer header.

APIs:
- Items (/items/) - CRUD for any collection
- Collections (/collections/) - Schema management
- Fields (/fields/) - Field definitions
- Relations (/relations/) - Relationships
- Files (/files/) - Asset management
- Folders (/folders/) - Folder management
- Users (/users/) - User management
- Roles (/roles/) - Role management
- Permissions (/permissions/) - Permission rules
- Policies (/policies/) - Access policies
- Flows (/flows/) - Automation flows
- Operations (/operations/) - Flow operations
- Webhooks (/webhooks/) - Webhook management
- Activity (/activity/) - Activity log
- Revisions (/revisions/) - Content revisions
- Versions (/versions/) - Content versions
- Comments (/comments/) - Item comments
- Dashboards (/dashboards/) - Insights dashboards
- Panels (/panels/) - Dashboard panels
- Settings (/settings/) - System settings
- Server (/server/) - Server info & health
- Schema (/schema/) - Schema management
- Presets (/presets/) - User presets
- Shares (/shares/) - Content shares
- Notifications (/notifications/) - User notifications
- Translations (/translations/) - Content translations
"""

import base64
import json
import logging
from typing import Any

import aiohttp

def _ensure_list(value: Any) -> list[str]:
    """Ensure value is a list. If string, wrap in list."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        return [value]
    return [str(value)]

class DirectusClient:
    """
    Directus Self-Hosted API client.

    Uses static token authentication for server-to-server communication.
    All requests include Authorization: Bearer {token} header.
    """

    def __init__(self, base_url: str, token: str):
        """
        Initialize Directus API client.

        Args:
            base_url: Directus instance URL (e.g., https://directus.example.com)
            token: Static admin token
        """
        self.base_url = base_url.rstrip("/")
        self.token = token

        # Initialize logger
        self.logger = logging.getLogger(f"DirectusClient.{base_url}")

    def _get_headers(self, additional_headers: dict | None = None) -> dict[str, str]:
        """
        Get request headers with token authentication.

        Args:
            additional_headers: Additional headers to include

        Returns:
            Dict: Headers with authentication
        """
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {self.token}",
        }

        if additional_headers:
            headers.update(additional_headers)

        return headers

    async def request(
        self,
        method: str,
        endpoint: str,
        params: dict | None = None,
        json_data: dict | list | None = None,
        data: bytes | None = None,
        headers_override: dict | None = None,
    ) -> Any:
        """
        Make authenticated request to Directus API.

        Args:
            method: HTTP method
            endpoint: API endpoint (with leading /)
            params: Query parameters
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

        # Clean params - remove None values
        if params:
            params = {k: v for k, v in params.items() if v is not None}

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
                            f"Directus API error (status {response.status}): {response_text}"
                        )
                    return {"success": True, "message": response_text}

                # Check for errors
                if response.status >= 400:
                    error_msg = self._extract_error_message(response_data)
                    raise Exception(f"Directus API error (status {response.status}): {error_msg}")

                return response_data

    def _extract_error_message(self, response_data: Any) -> str:
        """Extract error message from Directus error response."""
        if isinstance(response_data, dict):
            errors = response_data.get("errors", [])
            if errors and isinstance(errors, list) and len(errors) > 0:
                first_error = errors[0]
                if isinstance(first_error, dict):
                    return first_error.get("message", str(first_error))
            if "message" in response_data:
                return response_data["message"]
            if "error" in response_data:
                return response_data["error"]
        return str(response_data)

    # =====================
    # ITEMS
    # =====================

    async def list_items(
        self,
        collection: str,
        fields: list[str] | None = None,
        filter: dict | None = None,
        sort: list[str] | None = None,
        limit: int = 100,
        offset: int = 0,
        search: str | None = None,
        deep: dict | None = None,
        aggregate: dict | None = None,
    ) -> dict[str, Any]:
        """List items from a collection."""
        params = {
            "limit": limit,
            "offset": offset,
        }
        if fields:
            params["fields"] = ",".join(_ensure_list(fields))
        if filter:
            params["filter"] = json.dumps(filter)
        if sort:
            params["sort"] = ",".join(_ensure_list(sort))
        if search:
            params["search"] = search
        if deep:
            params["deep"] = json.dumps(deep)
        if aggregate:
            params["aggregate"] = json.dumps(aggregate)

        return await self.request("GET", f"/items/{collection}", params=params)

    async def get_item(
        self, collection: str, id: str, fields: list[str] | None = None, deep: dict | None = None
    ) -> dict[str, Any]:
        """Get item by ID."""
        params = {}
        if fields:
            params["fields"] = ",".join(_ensure_list(fields))
        if deep:
            params["deep"] = json.dumps(deep)

        return await self.request("GET", f"/items/{collection}/{id}", params=params)

    async def create_item(
        self, collection: str, data: dict[str, Any], fields: list[str] | None = None
    ) -> dict[str, Any]:
        """Create a new item."""
        params = {}
        if fields:
            params["fields"] = ",".join(_ensure_list(fields))

        return await self.request("POST", f"/items/{collection}", params=params, json_data=data)

    async def create_items(
        self, collection: str, data: list[dict[str, Any]], fields: list[str] | None = None
    ) -> dict[str, Any]:
        """Create multiple items."""
        params = {}
        if fields:
            params["fields"] = ",".join(_ensure_list(fields))

        return await self.request("POST", f"/items/{collection}", params=params, json_data=data)

    async def update_item(
        self, collection: str, id: str, data: dict[str, Any], fields: list[str] | None = None
    ) -> dict[str, Any]:
        """Update an item."""
        params = {}
        if fields:
            params["fields"] = ",".join(_ensure_list(fields))

        return await self.request(
            "PATCH", f"/items/{collection}/{id}", params=params, json_data=data
        )

    async def update_items(
        self,
        collection: str,
        keys: list[str],
        data: dict[str, Any],
        fields: list[str] | None = None,
    ) -> dict[str, Any]:
        """Update multiple items."""
        params = {}
        if fields:
            params["fields"] = ",".join(_ensure_list(fields))

        body = {"keys": keys, "data": data}
        return await self.request("PATCH", f"/items/{collection}", params=params, json_data=body)

    async def delete_item(self, collection: str, id: str) -> dict[str, Any]:
        """Delete an item."""
        return await self.request("DELETE", f"/items/{collection}/{id}")

    async def delete_items(self, collection: str, keys: list[str]) -> dict[str, Any]:
        """Delete multiple items."""
        return await self.request("DELETE", f"/items/{collection}", json_data=keys)

    # =====================
    # COLLECTIONS
    # =====================

    async def list_collections(self) -> dict[str, Any]:
        """List all collections."""
        return await self.request("GET", "/collections")

    async def get_collection(self, collection: str) -> dict[str, Any]:
        """Get collection by name."""
        return await self.request("GET", f"/collections/{collection}")

    async def create_collection(
        self,
        collection: str,
        meta: dict | None = None,
        schema: dict | None = None,
        fields: list[dict] | None = None,
    ) -> dict[str, Any]:
        """Create a new collection."""
        data = {"collection": collection}
        if meta:
            data["meta"] = meta
        if schema:
            data["schema"] = schema
        if fields:
            data["fields"] = fields

        return await self.request("POST", "/collections", json_data=data)

    async def update_collection(self, collection: str, meta: dict) -> dict[str, Any]:
        """Update collection meta."""
        return await self.request("PATCH", f"/collections/{collection}", json_data={"meta": meta})

    async def delete_collection(self, collection: str) -> dict[str, Any]:
        """Delete a collection."""
        return await self.request("DELETE", f"/collections/{collection}")

    # =====================
    # FIELDS
    # =====================

    async def list_fields(self, collection: str | None = None) -> dict[str, Any]:
        """List fields, optionally filtered by collection."""
        if collection:
            return await self.request("GET", f"/fields/{collection}")
        return await self.request("GET", "/fields")

    async def get_field(self, collection: str, field: str) -> dict[str, Any]:
        """Get field by name."""
        return await self.request("GET", f"/fields/{collection}/{field}")

    async def create_field(
        self,
        collection: str,
        field: str,
        type: str,
        meta: dict | None = None,
        schema: dict | None = None,
    ) -> dict[str, Any]:
        """Create a new field."""
        data = {"field": field, "type": type}
        if meta:
            data["meta"] = meta
        if schema:
            data["schema"] = schema

        return await self.request("POST", f"/fields/{collection}", json_data=data)

    async def update_field(
        self, collection: str, field: str, meta: dict | None = None, schema: dict | None = None
    ) -> dict[str, Any]:
        """Update a field."""
        data = {}
        if meta:
            data["meta"] = meta
        if schema:
            data["schema"] = schema

        return await self.request("PATCH", f"/fields/{collection}/{field}", json_data=data)

    async def delete_field(self, collection: str, field: str) -> dict[str, Any]:
        """Delete a field."""
        return await self.request("DELETE", f"/fields/{collection}/{field}")

    # =====================
    # RELATIONS
    # =====================

    async def list_relations(self, collection: str | None = None) -> dict[str, Any]:
        """List relations."""
        if collection:
            return await self.request("GET", f"/relations/{collection}")
        return await self.request("GET", "/relations")

    async def get_relation(self, collection: str, field: str) -> dict[str, Any]:
        """Get relation by collection and field."""
        return await self.request("GET", f"/relations/{collection}/{field}")

    async def create_relation(
        self,
        collection: str,
        field: str,
        related_collection: str,
        meta: dict | None = None,
        schema: dict | None = None,
    ) -> dict[str, Any]:
        """Create a new relation."""
        data = {"collection": collection, "field": field, "related_collection": related_collection}
        if meta:
            data["meta"] = meta
        if schema:
            data["schema"] = schema

        return await self.request("POST", "/relations", json_data=data)

    async def update_relation(
        self, collection: str, field: str, meta: dict | None = None, schema: dict | None = None
    ) -> dict[str, Any]:
        """Update a relation."""
        data = {}
        if meta:
            data["meta"] = meta
        if schema:
            data["schema"] = schema

        return await self.request("PATCH", f"/relations/{collection}/{field}", json_data=data)

    async def delete_relation(self, collection: str, field: str) -> dict[str, Any]:
        """Delete a relation."""
        return await self.request("DELETE", f"/relations/{collection}/{field}")

    # =====================
    # FILES
    # =====================

    async def list_files(
        self,
        filter: dict | None = None,
        sort: list[str] | None = None,
        limit: int = 100,
        offset: int = 0,
        search: str | None = None,
    ) -> dict[str, Any]:
        """List files."""
        params = {"limit": limit, "offset": offset}
        if filter:
            params["filter"] = json.dumps(filter)
        if sort:
            params["sort"] = ",".join(_ensure_list(sort))
        if search:
            params["search"] = search

        return await self.request("GET", "/files", params=params)

    async def get_file(self, id: str) -> dict[str, Any]:
        """Get file by ID."""
        return await self.request("GET", f"/files/{id}")

    async def update_file(self, id: str, data: dict[str, Any]) -> dict[str, Any]:
        """Update file metadata."""
        return await self.request("PATCH", f"/files/{id}", json_data=data)

    async def delete_file(self, id: str) -> dict[str, Any]:
        """Delete a file."""
        return await self.request("DELETE", f"/files/{id}")

    async def delete_files(self, ids: list[str]) -> dict[str, Any]:
        """Delete multiple files."""
        return await self.request("DELETE", "/files", json_data=ids)

    async def import_file_url(self, url: str, data: dict | None = None) -> dict[str, Any]:
        """Import file from URL."""
        body = {"url": url}
        if data:
            body["data"] = data
        return await self.request("POST", "/files/import", json_data=body)

    # =====================
    # FOLDERS
    # =====================

    async def list_folders(
        self,
        filter: dict | None = None,
        sort: list[str] | None = None,
        limit: int = 100,
        offset: int = 0,
        search: str | None = None,
    ) -> dict[str, Any]:
        """List folders."""
        params = {"limit": limit, "offset": offset}
        if filter:
            params["filter"] = json.dumps(filter)
        if sort:
            params["sort"] = ",".join(_ensure_list(sort))
        if search:
            params["search"] = search

        return await self.request("GET", "/folders", params=params)

    async def get_folder(self, id: str) -> dict[str, Any]:
        """Get folder by ID."""
        return await self.request("GET", f"/folders/{id}")

    async def create_folder(self, name: str, parent: str | None = None) -> dict[str, Any]:
        """Create a folder."""
        data = {"name": name}
        if parent:
            data["parent"] = parent
        return await self.request("POST", "/folders", json_data=data)

    async def update_folder(self, id: str, data: dict[str, Any]) -> dict[str, Any]:
        """Update folder."""
        return await self.request("PATCH", f"/folders/{id}", json_data=data)

    async def delete_folder(self, id: str) -> dict[str, Any]:
        """Delete a folder."""
        return await self.request("DELETE", f"/folders/{id}")

    # =====================
    # USERS
    # =====================

    async def list_users(
        self,
        filter: dict | None = None,
        sort: list[str] | None = None,
        limit: int = 100,
        offset: int = 0,
        search: str | None = None,
    ) -> dict[str, Any]:
        """List users."""
        params = {"limit": limit, "offset": offset}
        if filter:
            params["filter"] = json.dumps(filter)
        if sort:
            params["sort"] = ",".join(_ensure_list(sort))
        if search:
            params["search"] = search

        return await self.request("GET", "/users", params=params)

    async def get_user(self, id: str) -> dict[str, Any]:
        """Get user by ID."""
        return await self.request("GET", f"/users/{id}")

    async def get_current_user(self) -> dict[str, Any]:
        """Get current authenticated user."""
        return await self.request("GET", "/users/me")

    async def create_user(
        self,
        email: str,
        password: str,
        role: str,
        first_name: str | None = None,
        last_name: str | None = None,
        status: str = "active",
        **kwargs,
    ) -> dict[str, Any]:
        """Create a new user."""
        data = {"email": email, "password": password, "role": role, "status": status}
        if first_name:
            data["first_name"] = first_name
        if last_name:
            data["last_name"] = last_name
        data.update(kwargs)

        return await self.request("POST", "/users", json_data=data)

    async def update_user(self, id: str, data: dict[str, Any]) -> dict[str, Any]:
        """Update a user."""
        return await self.request("PATCH", f"/users/{id}", json_data=data)

    async def delete_user(self, id: str) -> dict[str, Any]:
        """Delete a user."""
        return await self.request("DELETE", f"/users/{id}")

    async def delete_users(self, ids: list[str]) -> dict[str, Any]:
        """Delete multiple users."""
        return await self.request("DELETE", "/users", json_data=ids)

    async def invite_user(
        self, email: str, role: str, invite_url: str | None = None
    ) -> dict[str, Any]:
        """Invite a user."""
        data = {"email": email, "role": role}
        if invite_url:
            data["invite_url"] = invite_url

        return await self.request("POST", "/users/invite", json_data=data)

    # =====================
    # ROLES
    # =====================

    async def list_roles(
        self,
        filter: dict | None = None,
        sort: list[str] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List roles."""
        params = {"limit": limit, "offset": offset}
        if filter:
            params["filter"] = json.dumps(filter)
        if sort:
            params["sort"] = ",".join(_ensure_list(sort))

        return await self.request("GET", "/roles", params=params)

    async def get_role(self, id: str) -> dict[str, Any]:
        """Get role by ID."""
        return await self.request("GET", f"/roles/{id}")

    async def create_role(
        self,
        name: str,
        icon: str = "supervised_user_circle",
        description: str | None = None,
        admin_access: bool = False,
        app_access: bool = True,
        **kwargs,
    ) -> dict[str, Any]:
        """Create a new role."""
        data = {"name": name, "icon": icon, "admin_access": admin_access, "app_access": app_access}
        if description:
            data["description"] = description
        data.update(kwargs)

        return await self.request("POST", "/roles", json_data=data)

    async def update_role(self, id: str, data: dict[str, Any]) -> dict[str, Any]:
        """Update a role."""
        return await self.request("PATCH", f"/roles/{id}", json_data=data)

    async def delete_role(self, id: str) -> dict[str, Any]:
        """Delete a role."""
        return await self.request("DELETE", f"/roles/{id}")

    # =====================
    # PERMISSIONS
    # =====================

    async def list_permissions(
        self, filter: dict | None = None, limit: int = 100, offset: int = 0
    ) -> dict[str, Any]:
        """List permissions."""
        params = {"limit": limit, "offset": offset}
        if filter:
            params["filter"] = json.dumps(filter)

        return await self.request("GET", "/permissions", params=params)

    async def get_permission(self, id: str) -> dict[str, Any]:
        """Get permission by ID."""
        return await self.request("GET", f"/permissions/{id}")

    async def get_my_permissions(self) -> dict[str, Any]:
        """Get current user's permissions."""
        return await self.request("GET", "/permissions/me")

    async def create_permission(
        self,
        collection: str,
        action: str,
        policy: str,
        role: str | None = None,
        permissions: dict | None = None,
        validation: dict | None = None,
        presets: dict | None = None,
        fields: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a new permission. Requires 'policy' in Directus v10+."""
        data = {
            "collection": collection,
            "action": action,
            "policy": policy,  # Required in Directus v10+
        }
        if role:
            data["role"] = role
        if permissions:
            data["permissions"] = permissions
        if validation:
            data["validation"] = validation
        if presets:
            data["presets"] = presets
        if fields:
            data["fields"] = fields

        return await self.request("POST", "/permissions", json_data=data)

    async def update_permission(self, id: str, data: dict[str, Any]) -> dict[str, Any]:
        """Update a permission."""
        return await self.request("PATCH", f"/permissions/{id}", json_data=data)

    async def delete_permission(self, id: str) -> dict[str, Any]:
        """Delete a permission."""
        return await self.request("DELETE", f"/permissions/{id}")

    # =====================
    # POLICIES
    # =====================

    async def list_policies(
        self, filter: dict | None = None, limit: int = 100, offset: int = 0
    ) -> dict[str, Any]:
        """List policies."""
        params = {"limit": limit, "offset": offset}
        if filter:
            params["filter"] = json.dumps(filter)

        return await self.request("GET", "/policies", params=params)

    async def get_policy(self, id: str) -> dict[str, Any]:
        """Get policy by ID."""
        return await self.request("GET", f"/policies/{id}")

    # =====================
    # FLOWS
    # =====================

    async def list_flows(
        self,
        filter: dict | None = None,
        sort: list[str] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List flows."""
        params = {"limit": limit, "offset": offset}
        if filter:
            params["filter"] = json.dumps(filter)
        if sort:
            params["sort"] = ",".join(_ensure_list(sort))

        return await self.request("GET", "/flows", params=params)

    async def get_flow(self, id: str) -> dict[str, Any]:
        """Get flow by ID."""
        return await self.request("GET", f"/flows/{id}")

    async def create_flow(
        self,
        name: str,
        trigger: str,
        status: str = "active",
        icon: str = "bolt",
        options: dict | None = None,
        accountability: str | None = None,
        description: str | None = None,
    ) -> dict[str, Any]:
        """Create a new flow."""
        data = {"name": name, "trigger": trigger, "status": status, "icon": icon}
        if options:
            data["options"] = options
        if accountability:
            data["accountability"] = accountability
        if description:
            data["description"] = description

        return await self.request("POST", "/flows", json_data=data)

    async def update_flow(self, id: str, data: dict[str, Any]) -> dict[str, Any]:
        """Update a flow."""
        return await self.request("PATCH", f"/flows/{id}", json_data=data)

    async def delete_flow(self, id: str) -> dict[str, Any]:
        """Delete a flow."""
        return await self.request("DELETE", f"/flows/{id}")

    async def trigger_flow(self, id: str, data: dict | None = None) -> dict[str, Any]:
        """Trigger a manual flow."""
        return await self.request("POST", f"/flows/trigger/{id}", json_data=data or {})

    # =====================
    # OPERATIONS
    # =====================

    async def list_operations(
        self, filter: dict | None = None, limit: int = 100, offset: int = 0
    ) -> dict[str, Any]:
        """List operations."""
        params = {"limit": limit, "offset": offset}
        if filter:
            params["filter"] = json.dumps(filter)

        return await self.request("GET", "/operations", params=params)

    async def get_operation(self, id: str) -> dict[str, Any]:
        """Get operation by ID."""
        return await self.request("GET", f"/operations/{id}")

    async def create_operation(
        self,
        flow: str,
        type: str,
        name: str | None = None,
        key: str | None = None,
        options: dict | None = None,
        position_x: int = 0,
        position_y: int = 0,
        resolve: str | None = None,
        reject: str | None = None,
    ) -> dict[str, Any]:
        """Create a new operation."""
        data = {"flow": flow, "type": type, "position_x": position_x, "position_y": position_y}
        if name:
            data["name"] = name
        if key:
            data["key"] = key
        if options:
            data["options"] = options
        if resolve:
            data["resolve"] = resolve
        if reject:
            data["reject"] = reject

        return await self.request("POST", "/operations", json_data=data)

    async def update_operation(self, id: str, data: dict[str, Any]) -> dict[str, Any]:
        """Update an operation."""
        return await self.request("PATCH", f"/operations/{id}", json_data=data)

    async def delete_operation(self, id: str) -> dict[str, Any]:
        """Delete an operation."""
        return await self.request("DELETE", f"/operations/{id}")

    # =====================
    # WEBHOOKS
    # =====================

    async def list_webhooks(
        self, filter: dict | None = None, limit: int = 100, offset: int = 0
    ) -> dict[str, Any]:
        """List webhooks."""
        params = {"limit": limit, "offset": offset}
        if filter:
            params["filter"] = json.dumps(filter)

        return await self.request("GET", "/webhooks", params=params)

    async def get_webhook(self, id: str) -> dict[str, Any]:
        """Get webhook by ID."""
        return await self.request("GET", f"/webhooks/{id}")

    async def create_webhook(
        self,
        name: str,
        url: str,
        actions: list[str],
        collections: list[str],
        method: str = "POST",
        status: str = "active",
        headers: dict | None = None,
    ) -> dict[str, Any]:
        """Create a new webhook."""
        data = {
            "name": name,
            "url": url,
            "actions": _ensure_list(actions),
            "collections": _ensure_list(collections),
            "method": method,
            "status": status,
        }
        if headers:
            data["headers"] = headers

        return await self.request("POST", "/webhooks", json_data=data)

    async def update_webhook(self, id: str, data: dict[str, Any]) -> dict[str, Any]:
        """Update a webhook."""
        return await self.request("PATCH", f"/webhooks/{id}", json_data=data)

    async def delete_webhook(self, id: str) -> dict[str, Any]:
        """Delete a webhook."""
        return await self.request("DELETE", f"/webhooks/{id}")

    # =====================
    # ACTIVITY
    # =====================

    async def list_activity(
        self,
        filter: dict | None = None,
        sort: list[str] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List activity."""
        params = {"limit": limit, "offset": offset}
        if filter:
            params["filter"] = json.dumps(filter)
        if sort:
            params["sort"] = ",".join(_ensure_list(sort))

        return await self.request("GET", "/activity", params=params)

    async def get_activity(self, id: str) -> dict[str, Any]:
        """Get activity by ID."""
        return await self.request("GET", f"/activity/{id}")

    # =====================
    # REVISIONS
    # =====================

    async def list_revisions(
        self,
        filter: dict | None = None,
        sort: list[str] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List revisions."""
        params = {"limit": limit, "offset": offset}
        if filter:
            params["filter"] = json.dumps(filter)
        if sort:
            params["sort"] = ",".join(_ensure_list(sort))

        return await self.request("GET", "/revisions", params=params)

    async def get_revision(self, id: str) -> dict[str, Any]:
        """Get revision by ID."""
        return await self.request("GET", f"/revisions/{id}")

    # =====================
    # VERSIONS
    # =====================

    async def list_versions(
        self,
        filter: dict | None = None,
        sort: list[str] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List content versions."""
        params = {"limit": limit, "offset": offset}
        if filter:
            params["filter"] = json.dumps(filter)
        if sort:
            params["sort"] = ",".join(_ensure_list(sort))

        return await self.request("GET", "/versions", params=params)

    async def get_version(self, id: str) -> dict[str, Any]:
        """Get version by ID."""
        return await self.request("GET", f"/versions/{id}")

    async def create_version(
        self, name: str, collection: str, item: str, key: str
    ) -> dict[str, Any]:
        """Create a new version."""
        data = {"name": name, "collection": collection, "item": item, "key": key}

        return await self.request("POST", "/versions", json_data=data)

    async def update_version(self, id: str, data: dict[str, Any]) -> dict[str, Any]:
        """Update a version."""
        return await self.request("PATCH", f"/versions/{id}", json_data=data)

    async def delete_version(self, id: str) -> dict[str, Any]:
        """Delete a version."""
        return await self.request("DELETE", f"/versions/{id}")

    async def promote_version(self, id: str, mainHash: str | None = None) -> dict[str, Any]:
        """Promote a version to main."""
        data = {}
        if mainHash:
            data["mainHash"] = mainHash
        return await self.request("POST", f"/versions/{id}/promote", json_data=data)

    # =====================
    # COMMENTS
    # =====================

    async def list_comments(
        self,
        filter: dict | None = None,
        sort: list[str] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List comments."""
        params = {"limit": limit, "offset": offset}
        if filter:
            params["filter"] = json.dumps(filter)
        if sort:
            params["sort"] = ",".join(_ensure_list(sort))

        return await self.request("GET", "/comments", params=params)

    async def get_comment(self, id: str) -> dict[str, Any]:
        """Get comment by ID."""
        return await self.request("GET", f"/comments/{id}")

    async def create_comment(self, collection: str, item: str, comment: str) -> dict[str, Any]:
        """Create a new comment."""
        data = {"collection": collection, "item": item, "comment": comment}
        return await self.request("POST", "/comments", json_data=data)

    async def update_comment(self, id: str, comment: str) -> dict[str, Any]:
        """Update a comment."""
        return await self.request("PATCH", f"/comments/{id}", json_data={"comment": comment})

    async def delete_comment(self, id: str) -> dict[str, Any]:
        """Delete a comment."""
        return await self.request("DELETE", f"/comments/{id}")

    # =====================
    # DASHBOARDS
    # =====================

    async def list_dashboards(
        self,
        filter: dict | None = None,
        sort: list[str] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List dashboards."""
        params = {"limit": limit, "offset": offset}
        if filter:
            params["filter"] = json.dumps(filter)
        if sort:
            params["sort"] = ",".join(_ensure_list(sort))

        return await self.request("GET", "/dashboards", params=params)

    async def get_dashboard(self, id: str) -> dict[str, Any]:
        """Get dashboard by ID."""
        return await self.request("GET", f"/dashboards/{id}")

    async def create_dashboard(
        self, name: str, icon: str = "dashboard", note: str | None = None, color: str | None = None
    ) -> dict[str, Any]:
        """Create a new dashboard."""
        data = {"name": name, "icon": icon}
        if note:
            data["note"] = note
        if color:
            data["color"] = color

        return await self.request("POST", "/dashboards", json_data=data)

    async def update_dashboard(self, id: str, data: dict[str, Any]) -> dict[str, Any]:
        """Update a dashboard."""
        return await self.request("PATCH", f"/dashboards/{id}", json_data=data)

    async def delete_dashboard(self, id: str) -> dict[str, Any]:
        """Delete a dashboard."""
        return await self.request("DELETE", f"/dashboards/{id}")

    # =====================
    # PANELS
    # =====================

    async def list_panels(
        self, filter: dict | None = None, limit: int = 100, offset: int = 0
    ) -> dict[str, Any]:
        """List panels."""
        params = {"limit": limit, "offset": offset}
        if filter:
            params["filter"] = json.dumps(filter)

        return await self.request("GET", "/panels", params=params)

    async def get_panel(self, id: str) -> dict[str, Any]:
        """Get panel by ID."""
        return await self.request("GET", f"/panels/{id}")

    async def create_panel(
        self,
        dashboard: str,
        type: str,
        name: str | None = None,
        icon: str | None = None,
        color: str | None = None,
        note: str | None = None,
        width: int = 12,
        height: int = 6,
        position_x: int = 0,
        position_y: int = 0,
        options: dict | None = None,
    ) -> dict[str, Any]:
        """Create a new panel."""
        data = {
            "dashboard": dashboard,
            "type": type,
            "width": width,
            "height": height,
            "position_x": position_x,
            "position_y": position_y,
        }
        if name:
            data["name"] = name
        if icon:
            data["icon"] = icon
        if color:
            data["color"] = color
        if note:
            data["note"] = note
        if options:
            data["options"] = options

        return await self.request("POST", "/panels", json_data=data)

    async def update_panel(self, id: str, data: dict[str, Any]) -> dict[str, Any]:
        """Update a panel."""
        return await self.request("PATCH", f"/panels/{id}", json_data=data)

    async def delete_panel(self, id: str) -> dict[str, Any]:
        """Delete a panel."""
        return await self.request("DELETE", f"/panels/{id}")

    # =====================
    # SETTINGS
    # =====================

    async def get_settings(self) -> dict[str, Any]:
        """Get system settings."""
        return await self.request("GET", "/settings")

    async def update_settings(self, data: dict[str, Any]) -> dict[str, Any]:
        """Update system settings."""
        return await self.request("PATCH", "/settings", json_data=data)

    # =====================
    # SERVER
    # =====================

    async def get_server_info(self) -> dict[str, Any]:
        """Get server info."""
        return await self.request("GET", "/server/info")

    async def health_check(self) -> dict[str, Any]:
        """Check server health."""
        return await self.request("GET", "/server/health")

    async def get_graphql_sdl(self) -> dict[str, Any]:
        """Get GraphQL SDL schema."""
        return await self.request("GET", "/server/specs/graphql")

    async def get_openapi_spec(self) -> dict[str, Any]:
        """Get OpenAPI specification."""
        return await self.request("GET", "/server/specs/oas")

    # =====================
    # SCHEMA
    # =====================

    async def get_schema_snapshot(self) -> dict[str, Any]:
        """Get schema snapshot."""
        return await self.request("GET", "/schema/snapshot")

    async def schema_diff(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        """Get diff between current schema and snapshot."""
        return await self.request("POST", "/schema/diff", json_data=snapshot)

    async def schema_apply(self, diff: dict[str, Any]) -> dict[str, Any]:
        """Apply schema diff."""
        return await self.request("POST", "/schema/apply", json_data=diff)

    # =====================
    # PRESETS
    # =====================

    async def list_presets(
        self, filter: dict | None = None, limit: int = 100, offset: int = 0
    ) -> dict[str, Any]:
        """List presets."""
        params = {"limit": limit, "offset": offset}
        if filter:
            params["filter"] = json.dumps(filter)

        return await self.request("GET", "/presets", params=params)

    async def get_preset(self, id: str) -> dict[str, Any]:
        """Get preset by ID."""
        return await self.request("GET", f"/presets/{id}")

    async def create_preset(
        self,
        collection: str,
        layout: str | None = None,
        layout_query: dict | None = None,
        layout_options: dict | None = None,
        filter: dict | None = None,
        search: str | None = None,
        bookmark: str | None = None,
        user: str | None = None,
        role: str | None = None,
    ) -> dict[str, Any]:
        """Create a new preset."""
        data = {"collection": collection}
        if layout:
            data["layout"] = layout
        if layout_query:
            data["layout_query"] = layout_query
        if layout_options:
            data["layout_options"] = layout_options
        if filter:
            data["filter"] = filter
        if search:
            data["search"] = search
        if bookmark:
            data["bookmark"] = bookmark
        if user:
            data["user"] = user
        if role:
            data["role"] = role

        return await self.request("POST", "/presets", json_data=data)

    async def update_preset(self, id: str, data: dict[str, Any]) -> dict[str, Any]:
        """Update a preset."""
        return await self.request("PATCH", f"/presets/{id}", json_data=data)

    async def delete_preset(self, id: str) -> dict[str, Any]:
        """Delete a preset."""
        return await self.request("DELETE", f"/presets/{id}")

    # =====================
    # SHARES
    # =====================

    async def list_shares(
        self, filter: dict | None = None, limit: int = 100, offset: int = 0
    ) -> dict[str, Any]:
        """List shares."""
        params = {"limit": limit, "offset": offset}
        if filter:
            params["filter"] = json.dumps(filter)

        return await self.request("GET", "/shares", params=params)

    async def get_share(self, id: str) -> dict[str, Any]:
        """Get share by ID."""
        return await self.request("GET", f"/shares/{id}")

    async def create_share(
        self,
        collection: str,
        item: str,
        name: str | None = None,
        role: str | None = None,
        password: str | None = None,
        date_start: str | None = None,
        date_end: str | None = None,
        max_uses: int | None = None,
    ) -> dict[str, Any]:
        """Create a new share."""
        data = {"collection": collection, "item": item}
        if name:
            data["name"] = name
        if role:
            data["role"] = role
        if password:
            data["password"] = password
        if date_start:
            data["date_start"] = date_start
        if date_end:
            data["date_end"] = date_end
        if max_uses:
            data["max_uses"] = max_uses

        return await self.request("POST", "/shares", json_data=data)

    async def update_share(self, id: str, data: dict[str, Any]) -> dict[str, Any]:
        """Update a share."""
        return await self.request("PATCH", f"/shares/{id}", json_data=data)

    async def delete_share(self, id: str) -> dict[str, Any]:
        """Delete a share."""
        return await self.request("DELETE", f"/shares/{id}")

    # =====================
    # NOTIFICATIONS
    # =====================

    async def list_notifications(
        self, filter: dict | None = None, limit: int = 100, offset: int = 0
    ) -> dict[str, Any]:
        """List notifications."""
        params = {"limit": limit, "offset": offset}
        if filter:
            params["filter"] = json.dumps(filter)

        return await self.request("GET", "/notifications", params=params)

    async def get_notification(self, id: str) -> dict[str, Any]:
        """Get notification by ID."""
        return await self.request("GET", f"/notifications/{id}")

    async def update_notification(self, id: str, status: str) -> dict[str, Any]:
        """Update notification (mark as read/archived)."""
        return await self.request("PATCH", f"/notifications/{id}", json_data={"status": status})

    async def delete_notification(self, id: str) -> dict[str, Any]:
        """Delete a notification."""
        return await self.request("DELETE", f"/notifications/{id}")

    # =====================
    # TRANSLATIONS
    # =====================

    async def list_translations(
        self, filter: dict | None = None, limit: int = 100, offset: int = 0
    ) -> dict[str, Any]:
        """List translations."""
        params = {"limit": limit, "offset": offset}
        if filter:
            params["filter"] = json.dumps(filter)

        return await self.request("GET", "/translations", params=params)

    async def get_translation(self, id: str) -> dict[str, Any]:
        """Get translation by ID."""
        return await self.request("GET", f"/translations/{id}")

    async def create_translation(self, key: str, language: str, value: str) -> dict[str, Any]:
        """Create a new translation."""
        data = {"key": key, "language": language, "value": value}
        return await self.request("POST", "/translations", json_data=data)

    async def update_translation(self, id: str, data: dict[str, Any]) -> dict[str, Any]:
        """Update a translation."""
        return await self.request("PATCH", f"/translations/{id}", json_data=data)

    async def delete_translation(self, id: str) -> dict[str, Any]:
        """Delete a translation."""
        return await self.request("DELETE", f"/translations/{id}")
