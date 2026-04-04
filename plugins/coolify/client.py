"""
Coolify REST API Client

Handles all HTTP communication with Coolify REST API.
Separates API communication from business logic.
"""

import logging
from typing import Any

import aiohttp


class CoolifyClient:
    """
    Coolify REST API client for HTTP communication.

    Handles Bearer token authentication, request formatting,
    and error handling for all Coolify API v1 endpoints.
    """

    def __init__(self, site_url: str, token: str):
        """
        Initialize Coolify API client.

        Args:
            site_url: Coolify instance URL (e.g., https://coolify.example.com)
            token: API token for Bearer authentication
        """
        self.site_url = site_url.rstrip("/")
        self.api_base = f"{self.site_url}/api/v1"
        self.token = token
        self.logger = logging.getLogger(f"CoolifyClient.{site_url}")

    def _get_headers(self) -> dict[str, str]:
        """Get request headers with Bearer authentication."""
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def request(
        self,
        method: str,
        endpoint: str,
        params: dict | None = None,
        json_data: dict | None = None,
    ) -> Any:
        """
        Make authenticated request to Coolify REST API.

        Args:
            method: HTTP method (GET, POST, PATCH, DELETE)
            endpoint: API endpoint (without base URL)
            params: Query parameters
            json_data: JSON body data

        Returns:
            API response (dict, list, or None)

        Raises:
            Exception: On API errors with status code and message
        """
        url = f"{self.api_base}/{endpoint.lstrip('/')}"

        if params:
            params = {k: v for k, v in params.items() if v is not None}

        if json_data:
            json_data = {k: v for k, v in json_data.items() if v is not None}

        self.logger.debug(f"{method} {url}")

        async with (
            aiohttp.ClientSession() as session,
            session.request(
                method=method,
                url=url,
                params=params,
                json=json_data,
                headers=self._get_headers(),
            ) as response,
        ):
            self.logger.debug(f"Response status: {response.status}")

            if response.status == 204:
                return {"success": True, "message": "Operation completed successfully"}

            try:
                response_data = await response.json()
            except Exception:
                response_text = await response.text()
                if response.status >= 400:
                    raise Exception(
                        f"Coolify API error (status {response.status}): {response_text}"
                    )
                return {"success": True, "message": response_text}

            if response.status >= 400:
                error_msg = response_data.get("message", "Unknown error")
                raise Exception(f"Coolify API error (status {response.status}): {error_msg}")

            return response_data

    # --- Applications ---

    async def list_applications(self, tag: str | None = None) -> list[dict]:
        """List all applications."""
        params = {"tag": tag} if tag else {}
        return await self.request("GET", "applications", params=params)

    async def get_application(self, uuid: str) -> dict:
        """Get application by UUID."""
        return await self.request("GET", f"applications/{uuid}")

    async def create_application_public(self, data: dict) -> dict:
        """Create application from public repository."""
        return await self.request("POST", "applications/public", json_data=data)

    async def create_application_dockerfile(self, data: dict) -> dict:
        """Create application from Dockerfile."""
        return await self.request("POST", "applications/dockerfile", json_data=data)

    async def create_application_docker_image(self, data: dict) -> dict:
        """Create application from Docker image."""
        return await self.request("POST", "applications/dockerimage", json_data=data)

    async def create_application_docker_compose(self, data: dict) -> dict:
        """Create application from Docker Compose."""
        return await self.request("POST", "applications/dockercompose", json_data=data)

    async def update_application(self, uuid: str, data: dict) -> dict:
        """Update application by UUID."""
        return await self.request("PATCH", f"applications/{uuid}", json_data=data)

    async def delete_application(
        self,
        uuid: str,
        delete_configurations: bool = True,
        delete_volumes: bool = True,
        docker_cleanup: bool = True,
        delete_connected_networks: bool = True,
    ) -> dict:
        """Delete application by UUID."""
        params = {
            "delete_configurations": str(delete_configurations).lower(),
            "delete_volumes": str(delete_volumes).lower(),
            "docker_cleanup": str(docker_cleanup).lower(),
            "delete_connected_networks": str(delete_connected_networks).lower(),
        }
        return await self.request("DELETE", f"applications/{uuid}", params=params)

    async def start_application(
        self, uuid: str, force: bool = False, instant_deploy: bool = False
    ) -> dict:
        """Deploy/start application."""
        params = {}
        if force:
            params["force"] = "true"
        if instant_deploy:
            params["instant_deploy"] = "true"
        return await self.request("GET", f"applications/{uuid}/start", params=params)

    async def stop_application(self, uuid: str, docker_cleanup: bool = True) -> dict:
        """Stop application."""
        params = {"docker_cleanup": str(docker_cleanup).lower()}
        return await self.request("GET", f"applications/{uuid}/stop", params=params)

    async def restart_application(self, uuid: str) -> dict:
        """Restart application."""
        return await self.request("GET", f"applications/{uuid}/restart")

    async def get_application_logs(self, uuid: str, lines: int = 100) -> dict:
        """Get application logs."""
        return await self.request("GET", f"applications/{uuid}/logs", params={"lines": lines})

    # --- Application Environment Variables ---

    async def list_application_envs(self, uuid: str) -> list[dict]:
        """List application environment variables."""
        return await self.request("GET", f"applications/{uuid}/envs")

    async def create_application_env(self, uuid: str, data: dict) -> dict:
        """Create application environment variable."""
        return await self.request("POST", f"applications/{uuid}/envs", json_data=data)

    async def update_application_env(self, uuid: str, data: dict) -> dict:
        """Update application environment variable."""
        return await self.request("PATCH", f"applications/{uuid}/envs", json_data=data)

    async def update_application_envs_bulk(self, uuid: str, data: list[dict]) -> dict:
        """Bulk update application environment variables."""
        return await self.request(
            "PATCH", f"applications/{uuid}/envs/bulk", json_data={"data": data}
        )

    async def delete_application_env(self, uuid: str, env_uuid: str) -> dict:
        """Delete application environment variable."""
        return await self.request("DELETE", f"applications/{uuid}/envs/{env_uuid}")

    # --- Deployments ---

    async def list_deployments(self) -> list[dict]:
        """List running deployments."""
        return await self.request("GET", "deployments")

    async def get_deployment(self, uuid: str) -> dict:
        """Get deployment by UUID."""
        return await self.request("GET", f"deployments/{uuid}")

    async def cancel_deployment(self, uuid: str) -> dict:
        """Cancel a deployment."""
        return await self.request("POST", f"deployments/{uuid}/cancel")

    async def deploy(
        self,
        tag: str | None = None,
        uuid: str | None = None,
        force: bool = False,
    ) -> dict:
        """Deploy by tag or UUID."""
        params = {}
        if tag:
            params["tag"] = tag
        if uuid:
            params["uuid"] = uuid
        if force:
            params["force"] = "true"
        return await self.request("GET", "deploy", params=params)

    async def list_app_deployments(self, uuid: str, skip: int = 0, take: int = 10) -> list[dict]:
        """List deployments for a specific application."""
        params = {"skip": skip, "take": take}
        return await self.request("GET", f"deployments/applications/{uuid}", params=params)

    # --- Servers ---

    async def list_servers(self) -> list[dict]:
        """List all servers."""
        return await self.request("GET", "servers")

    async def get_server(self, uuid: str) -> dict:
        """Get server by UUID."""
        return await self.request("GET", f"servers/{uuid}")

    async def create_server(self, data: dict) -> dict:
        """Create a new server."""
        return await self.request("POST", "servers", json_data=data)

    async def update_server(self, uuid: str, data: dict) -> dict:
        """Update server by UUID."""
        return await self.request("PATCH", f"servers/{uuid}", json_data=data)

    async def delete_server(self, uuid: str) -> dict:
        """Delete server by UUID."""
        return await self.request("DELETE", f"servers/{uuid}")

    async def get_server_resources(self, uuid: str) -> list[dict]:
        """Get resources on a server."""
        return await self.request("GET", f"servers/{uuid}/resources")

    async def get_server_domains(self, uuid: str) -> list[dict]:
        """Get domains configured on a server."""
        return await self.request("GET", f"servers/{uuid}/domains")

    async def validate_server(self, uuid: str) -> dict:
        """Validate server connectivity and configuration."""
        return await self.request("GET", f"servers/{uuid}/validate")

    # --- Projects ---

    async def list_projects(self) -> list[dict]:
        """List all projects."""
        return await self.request("GET", "projects")

    async def get_project(self, uuid: str) -> dict:
        """Get project by UUID."""
        return await self.request("GET", f"projects/{uuid}")

    async def create_project(self, data: dict) -> dict:
        """Create a new project."""
        return await self.request("POST", "projects", json_data=data)

    async def update_project(self, uuid: str, data: dict) -> dict:
        """Update project by UUID."""
        return await self.request("PATCH", f"projects/{uuid}", json_data=data)

    async def delete_project(self, uuid: str) -> dict:
        """Delete project by UUID."""
        return await self.request("DELETE", f"projects/{uuid}")

    # --- Environments ---

    async def list_environments(self, project_uuid: str) -> list[dict]:
        """List environments in a project."""
        return await self.request("GET", f"projects/{project_uuid}/environments")

    async def get_environment(self, project_uuid: str, environment_name: str) -> dict:
        """Get environment by name."""
        return await self.request("GET", f"projects/{project_uuid}/environments/{environment_name}")

    async def create_environment(self, project_uuid: str, data: dict) -> dict:
        """Create environment in a project."""
        return await self.request("POST", f"projects/{project_uuid}/environments", json_data=data)

    # --- Databases ---

    async def list_databases(self) -> list[dict]:
        """List all databases."""
        return await self.request("GET", "databases")

    async def get_database(self, uuid: str) -> dict:
        """Get database by UUID."""
        return await self.request("GET", f"databases/{uuid}")

    async def update_database(self, uuid: str, data: dict) -> dict:
        """Update database by UUID."""
        return await self.request("PATCH", f"databases/{uuid}", json_data=data)

    async def delete_database(
        self,
        uuid: str,
        delete_configurations: bool = True,
        delete_volumes: bool = True,
        docker_cleanup: bool = True,
    ) -> dict:
        """Delete database by UUID."""
        params = {
            "delete_configurations": str(delete_configurations).lower(),
            "delete_volumes": str(delete_volumes).lower(),
            "docker_cleanup": str(docker_cleanup).lower(),
        }
        return await self.request("DELETE", f"databases/{uuid}", params=params)

    async def start_database(self, uuid: str) -> dict:
        """Start database."""
        return await self.request("GET", f"databases/{uuid}/start")

    async def stop_database(self, uuid: str) -> dict:
        """Stop database."""
        return await self.request("GET", f"databases/{uuid}/stop")

    async def restart_database(self, uuid: str) -> dict:
        """Restart database."""
        return await self.request("GET", f"databases/{uuid}/restart")

    async def create_database(self, db_type: str, data: dict) -> dict:
        """Create a database of given type (postgresql, mysql, mariadb, mongodb, redis, clickhouse)."""
        return await self.request("POST", f"databases/{db_type}", json_data=data)

    async def get_database_backups(self, uuid: str) -> dict:
        """Get database backups."""
        return await self.request("GET", f"databases/{uuid}/backups")

    async def create_database_backup(self, uuid: str) -> dict:
        """Create a manual database backup."""
        return await self.request("POST", f"databases/{uuid}/backups")

    async def list_backup_executions(self) -> list[dict]:
        """List all backup executions."""
        return await self.request("GET", "databases/backup-executions")

    # --- Services ---

    async def list_services(self) -> list[dict]:
        """List all services."""
        return await self.request("GET", "services")

    async def get_service(self, uuid: str) -> dict:
        """Get service by UUID."""
        return await self.request("GET", f"services/{uuid}")

    async def create_service(self, data: dict) -> dict:
        """Create a service from template."""
        return await self.request("POST", "services", json_data=data)

    async def update_service(self, uuid: str, data: dict) -> dict:
        """Update service by UUID."""
        return await self.request("PATCH", f"services/{uuid}", json_data=data)

    async def delete_service(
        self,
        uuid: str,
        delete_configurations: bool = True,
        delete_volumes: bool = True,
        docker_cleanup: bool = True,
    ) -> dict:
        """Delete service by UUID."""
        params = {
            "delete_configurations": str(delete_configurations).lower(),
            "delete_volumes": str(delete_volumes).lower(),
            "docker_cleanup": str(docker_cleanup).lower(),
        }
        return await self.request("DELETE", f"services/{uuid}", params=params)

    async def start_service(self, uuid: str) -> dict:
        """Start service."""
        return await self.request("GET", f"services/{uuid}/start")

    async def stop_service(self, uuid: str) -> dict:
        """Stop service."""
        return await self.request("GET", f"services/{uuid}/stop")

    async def restart_service(self, uuid: str) -> dict:
        """Restart service."""
        return await self.request("GET", f"services/{uuid}/restart")

    # --- Service Environment Variables ---

    async def list_service_envs(self, uuid: str) -> list[dict]:
        """List service environment variables."""
        return await self.request("GET", f"services/{uuid}/envs")

    async def create_service_env(self, uuid: str, data: dict) -> dict:
        """Create service environment variable."""
        return await self.request("POST", f"services/{uuid}/envs", json_data=data)

    async def update_service_env(self, uuid: str, data: dict) -> dict:
        """Update service environment variable."""
        return await self.request("PATCH", f"services/{uuid}/envs", json_data=data)

    async def update_service_envs_bulk(self, uuid: str, data: list[dict]) -> dict:
        """Bulk update service environment variables."""
        return await self.request("PATCH", f"services/{uuid}/envs/bulk", json_data={"data": data})

    async def delete_service_env(self, uuid: str, env_uuid: str) -> dict:
        """Delete service environment variable."""
        return await self.request("DELETE", f"services/{uuid}/envs/{env_uuid}")
