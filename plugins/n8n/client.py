"""
n8n REST API Client

Handles all HTTP communication with n8n REST API.
Separates API communication from business logic.
"""

import logging
from typing import Any

import aiohttp


class N8nClient:
    """
    n8n REST API client for HTTP communication.

    Handles authentication, request formatting, and error handling
    for all n8n API endpoints.

    Authentication: API Key via X-N8N-API-KEY header
    """

    def __init__(self, site_url: str, api_key: str):
        """
        Initialize n8n API client.

        Args:
            site_url: n8n instance URL (e.g., https://n8n.example.com)
            api_key: n8n API key for authentication
        """
        self.site_url = site_url.rstrip("/")
        self.api_base = f"{self.site_url}/api/v1"
        self.api_key = api_key

        # Initialize logger
        self.logger = logging.getLogger(f"N8nClient.{site_url}")

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
            "X-N8N-API-KEY": self.api_key,
        }

        # Merge additional headers
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
    ) -> Any:
        """
        Make authenticated request to n8n REST API.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE, PATCH)
            endpoint: API endpoint (without base URL)
            params: Query parameters
            json_data: JSON body data
            headers_override: Override default headers

        Returns:
            API response (dict, list, or None)

        Raises:
            Exception: On API errors with status code and message
        """
        # Build full URL
        url = f"{self.api_base}/{endpoint.lstrip('/')}"

        # Setup headers
        headers = self._get_headers(headers_override)

        # Filter out None values from params
        if params:
            params = {k: v for k, v in params.items() if v is not None}

        # Filter None values from JSON data
        if json_data:
            json_data = {k: v for k, v in json_data.items() if v is not None}

        # Make request
        self.logger.debug(f"{method} {url}")
        self.logger.debug(f"Params: {params}")
        self.logger.debug(f"Data: {json_data}")

        async with (
            aiohttp.ClientSession() as session,
            session.request(
                method=method, url=url, params=params, json=json_data, headers=headers
            ) as response,
        ):
            # Log response
            self.logger.debug(f"Response status: {response.status}")

            # Handle empty responses (e.g., 204 No Content)
            if response.status == 204:
                return {"success": True, "message": "Operation completed successfully"}

            # Try to parse JSON response
            try:
                response_data = await response.json()
            except Exception:
                response_text = await response.text()
                if response.status >= 400:
                    raise Exception(f"n8n API error (status {response.status}): {response_text}")
                return {"success": True, "message": response_text}

            # Check for errors
            if response.status >= 400:
                error_msg = response_data.get("message", str(response_data))
                raise Exception(f"n8n API error (status {response.status}): {error_msg}")

            return response_data

    # =====================
    # WORKFLOW ENDPOINTS
    # =====================

    async def list_workflows(
        self,
        active: bool | None = None,
        tags: str | None = None,
        name: str | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        """List workflows with optional filters"""
        params = {"active": active, "tags": tags, "name": name, "limit": limit, "cursor": cursor}
        return await self.request("GET", "workflows", params=params)

    async def get_workflow(self, workflow_id: str) -> dict[str, Any]:
        """Get workflow by ID"""
        return await self.request("GET", f"workflows/{workflow_id}")

    async def create_workflow(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create a new workflow"""
        return await self.request("POST", "workflows", json_data=data)

    async def update_workflow(self, workflow_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """Update an existing workflow"""
        return await self.request("PUT", f"workflows/{workflow_id}", json_data=data)

    async def delete_workflow(self, workflow_id: str) -> dict[str, Any]:
        """Delete a workflow"""
        return await self.request("DELETE", f"workflows/{workflow_id}")

    async def activate_workflow(self, workflow_id: str) -> dict[str, Any]:
        """Activate a workflow"""
        return await self.request("POST", f"workflows/{workflow_id}/activate")

    async def deactivate_workflow(self, workflow_id: str) -> dict[str, Any]:
        """Deactivate a workflow"""
        return await self.request("POST", f"workflows/{workflow_id}/deactivate")

    async def execute_workflow(
        self, workflow_id: str, data: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Execute a workflow manually"""
        return await self.request("POST", f"workflows/{workflow_id}/run", json_data=data or {})

    async def get_workflow_tags(self, workflow_id: str) -> list[dict[str, Any]]:
        """Get tags assigned to a workflow"""
        workflow = await self.get_workflow(workflow_id)
        return workflow.get("tags", [])

    # =====================
    # EXECUTION ENDPOINTS
    # =====================

    async def list_executions(
        self,
        workflow_id: str | None = None,
        status: str | None = None,
        include_data: bool = False,
        limit: int = 20,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        """List workflow executions with filters"""
        params = {
            "workflowId": workflow_id,
            "status": status,
            "includeData": str(include_data).lower(),
            "limit": limit,
            "cursor": cursor,
        }
        return await self.request("GET", "executions", params=params)

    async def get_execution(self, execution_id: str, include_data: bool = True) -> dict[str, Any]:
        """Get execution details"""
        params = {"includeData": str(include_data).lower()}
        return await self.request("GET", f"executions/{execution_id}", params=params)

    async def delete_execution(self, execution_id: str) -> dict[str, Any]:
        """Delete a single execution"""
        return await self.request("DELETE", f"executions/{execution_id}")

    async def stop_execution(self, execution_id: str) -> dict[str, Any]:
        """Stop a running execution"""
        return await self.request("POST", f"executions/{execution_id}/stop")

    # =====================
    # CREDENTIAL ENDPOINTS
    # =====================

    async def list_credentials(self, limit: int = 100, cursor: str | None = None) -> dict[str, Any]:
        """List all credentials (metadata only)"""
        params = {"limit": limit, "cursor": cursor}
        return await self.request("GET", "credentials", params=params)

    async def get_credential(self, credential_id: str) -> dict[str, Any]:
        """Get credential metadata"""
        return await self.request("GET", f"credentials/{credential_id}")

    async def create_credential(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create a new credential"""
        return await self.request("POST", "credentials", json_data=data)

    async def delete_credential(self, credential_id: str) -> dict[str, Any]:
        """Delete a credential"""
        return await self.request("DELETE", f"credentials/{credential_id}")

    async def get_credential_schema(self, credential_type: str) -> dict[str, Any]:
        """Get schema for a credential type"""
        return await self.request("GET", f"credentials/schema/{credential_type}")

    async def transfer_credential(
        self, credential_id: str, destination_project_id: str
    ) -> dict[str, Any]:
        """Transfer credential to another project"""
        data = {"destinationProjectId": destination_project_id}
        return await self.request("POST", f"credentials/{credential_id}/transfer", json_data=data)

    # =====================
    # TAG ENDPOINTS
    # =====================

    async def list_tags(self, limit: int = 100, cursor: str | None = None) -> dict[str, Any]:
        """List all tags"""
        params = {"limit": limit, "cursor": cursor}
        return await self.request("GET", "tags", params=params)

    async def get_tag(self, tag_id: str) -> dict[str, Any]:
        """Get tag by ID"""
        return await self.request("GET", f"tags/{tag_id}")

    async def create_tag(self, name: str) -> dict[str, Any]:
        """Create a new tag"""
        return await self.request("POST", "tags", json_data={"name": name})

    async def update_tag(self, tag_id: str, name: str) -> dict[str, Any]:
        """Update tag name"""
        return await self.request("PUT", f"tags/{tag_id}", json_data={"name": name})

    async def delete_tag(self, tag_id: str) -> dict[str, Any]:
        """Delete a tag"""
        return await self.request("DELETE", f"tags/{tag_id}")

    # =====================
    # USER ENDPOINTS
    # =====================

    async def list_users(
        self, limit: int = 100, cursor: str | None = None, include_role: bool = True
    ) -> dict[str, Any]:
        """List all users"""
        params = {"limit": limit, "cursor": cursor, "includeRole": str(include_role).lower()}
        return await self.request("GET", "users", params=params)

    async def get_user(self, user_id: str, include_role: bool = True) -> dict[str, Any]:
        """Get user by ID or email"""
        params = {"includeRole": str(include_role).lower()}
        return await self.request("GET", f"users/{user_id}", params=params)

    async def create_user(self, users: list[dict[str, Any]]) -> dict[str, Any]:
        """Create/invite users"""
        return await self.request("POST", "users", json_data=users)

    async def delete_user(self, user_id: str) -> dict[str, Any]:
        """Delete a user"""
        return await self.request("DELETE", f"users/{user_id}")

    async def change_user_role(self, user_id: str, new_role: str) -> dict[str, Any]:
        """Change user's global role"""
        return await self.request(
            "PATCH", f"users/{user_id}/role", json_data={"newRoleName": new_role}
        )

    # =====================
    # PROJECT ENDPOINTS (Enterprise/Pro)
    # =====================

    async def list_projects(self, limit: int = 100, cursor: str | None = None) -> dict[str, Any]:
        """List all projects"""
        params = {"limit": limit, "cursor": cursor}
        return await self.request("GET", "projects", params=params)

    async def get_project(self, project_id: str) -> dict[str, Any]:
        """Get project by ID"""
        return await self.request("GET", f"projects/{project_id}")

    async def create_project(self, name: str) -> dict[str, Any]:
        """Create a new project"""
        return await self.request("POST", "projects", json_data={"name": name})

    async def update_project(self, project_id: str, name: str) -> dict[str, Any]:
        """Update project"""
        return await self.request("PUT", f"projects/{project_id}", json_data={"name": name})

    async def delete_project(self, project_id: str) -> dict[str, Any]:
        """Delete a project"""
        return await self.request("DELETE", f"projects/{project_id}")

    async def add_project_users(
        self, project_id: str, relations: list[dict[str, str]]
    ) -> dict[str, Any]:
        """Add users to project with roles"""
        return await self.request("POST", f"projects/{project_id}/users", json_data=relations)

    async def change_project_user_role(
        self, project_id: str, user_id: str, role: str
    ) -> dict[str, Any]:
        """Change user's role in project"""
        return await self.request(
            "PUT", f"projects/{project_id}/users/{user_id}", json_data={"role": role}
        )

    async def remove_project_user(self, project_id: str, user_id: str) -> dict[str, Any]:
        """Remove user from project"""
        return await self.request("DELETE", f"projects/{project_id}/users/{user_id}")

    # =====================
    # VARIABLE ENDPOINTS
    # =====================

    async def list_variables(self, limit: int = 100, cursor: str | None = None) -> dict[str, Any]:
        """List all variables"""
        params = {"limit": limit, "cursor": cursor}
        return await self.request("GET", "variables", params=params)

    async def get_variable(self, key: str) -> dict[str, Any]:
        """Get variable by key"""
        return await self.request("GET", f"variables/{key}")

    async def create_variable(self, key: str, value: str) -> dict[str, Any]:
        """Create a new variable"""
        return await self.request("POST", "variables", json_data={"key": key, "value": value})

    async def update_variable(self, key: str, value: str) -> dict[str, Any]:
        """Update variable value"""
        return await self.request("PUT", f"variables/{key}", json_data={"value": value})

    async def delete_variable(self, key: str) -> dict[str, Any]:
        """Delete a variable"""
        return await self.request("DELETE", f"variables/{key}")

    # =====================
    # SYSTEM ENDPOINTS
    # =====================

    async def run_audit(self, categories: list[str] | None = None) -> dict[str, Any]:
        """Run security audit"""
        data = {}
        if categories:
            data["additionalOptions"] = {"categories": categories}
        return await self.request("POST", "audit", json_data=data)

    async def source_control_pull(
        self, variables: dict[str, str] | None = None, force: bool = False
    ) -> dict[str, Any]:
        """Pull from source control"""
        data = {"force": force}
        if variables:
            data["variables"] = variables
        return await self.request("POST", "source-control/pull", json_data=data)

    async def health_check(self) -> dict[str, Any]:
        """Check n8n instance health"""
        # Use direct URL, not API base
        url = f"{self.site_url}/healthz"
        async with aiohttp.ClientSession() as session, session.get(url) as response:
            if response.status == 200:
                return {"healthy": True, "status": "ok"}
            else:
                return {"healthy": False, "status": f"unhealthy (status {response.status})"}
