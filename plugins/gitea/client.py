"""
Gitea REST API Client

Handles all HTTP communication with Gitea REST API.
Separates API communication from business logic.
"""

import base64
import logging
from typing import Any

import aiohttp


class GiteaClient:
    """
    Gitea REST API client for HTTP communication.

    Handles authentication, request formatting, and error handling
    for all Gitea API endpoints.
    """

    def __init__(self, site_url: str, token: str | None = None, oauth_enabled: bool = False):
        """
        Initialize Gitea API client.

        Args:
            site_url: Gitea instance URL (e.g., https://gitea.example.com)
            token: Personal access token for authentication
            oauth_enabled: Whether OAuth is enabled for this site
        """
        self.site_url = site_url.rstrip("/")
        self.api_base = f"{self.site_url}/api/v1"
        self.token = token
        self.oauth_enabled = oauth_enabled

        # Initialize logger
        self.logger = logging.getLogger(f"GiteaClient.{site_url}")

    def _get_headers(self, additional_headers: dict | None = None) -> dict[str, str]:
        """
        Get request headers with authentication.

        Args:
            additional_headers: Additional headers to include

        Returns:
            Dict: Headers with authentication
        """
        headers = {"Content-Type": "application/json", "accept": "application/json"}

        # Add token authentication if available
        if self.token:
            headers["Authorization"] = f"token {self.token}"

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
        Make authenticated request to Gitea REST API.

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
                    raise Exception(f"Gitea API error (status {response.status}): {response_text}")
                return {"success": True, "message": response_text}

            # Check for errors
            if response.status >= 400:
                error_msg = response_data.get("message", "Unknown error")
                raise Exception(f"Gitea API error (status {response.status}): {error_msg}")

            return response_data

    # Repository endpoints
    async def list_repositories(
        self, owner: str | None = None, page: int = 1, limit: int = 30
    ) -> list[dict]:
        """List repositories for a user/org or current user"""
        if owner:
            endpoint = f"users/{owner}/repos"
        else:
            endpoint = "user/repos"

        params = {"page": page, "limit": limit}
        return await self.request("GET", endpoint, params=params)

    async def get_repository(self, owner: str, repo: str) -> dict:
        """Get repository details"""
        return await self.request("GET", f"repos/{owner}/{repo}")

    async def create_repository(self, data: dict, org: str | None = None) -> dict:
        """Create a new repository"""
        if org:
            endpoint = f"orgs/{org}/repos"
        else:
            endpoint = "user/repos"
        return await self.request("POST", endpoint, json_data=data)

    async def update_repository(self, owner: str, repo: str, data: dict) -> dict:
        """Update repository settings"""
        return await self.request("PATCH", f"repos/{owner}/{repo}", json_data=data)

    async def delete_repository(self, owner: str, repo: str) -> dict:
        """Delete a repository"""
        return await self.request("DELETE", f"repos/{owner}/{repo}")

    # Branch endpoints
    async def list_branches(
        self, owner: str, repo: str, page: int = 1, limit: int = 30
    ) -> list[dict]:
        """List repository branches"""
        params = {"page": page, "limit": limit}
        return await self.request("GET", f"repos/{owner}/{repo}/branches", params=params)

    async def get_branch(self, owner: str, repo: str, branch: str) -> dict:
        """Get branch details"""
        return await self.request("GET", f"repos/{owner}/{repo}/branches/{branch}")

    async def create_branch(self, owner: str, repo: str, data: dict) -> dict:
        """Create a new branch"""
        return await self.request("POST", f"repos/{owner}/{repo}/branches", json_data=data)

    async def delete_branch(self, owner: str, repo: str, branch: str) -> dict:
        """Delete a branch"""
        return await self.request("DELETE", f"repos/{owner}/{repo}/branches/{branch}")

    # Tag endpoints
    async def list_tags(self, owner: str, repo: str, page: int = 1, limit: int = 30) -> list[dict]:
        """List repository tags"""
        params = {"page": page, "limit": limit}
        return await self.request("GET", f"repos/{owner}/{repo}/tags", params=params)

    async def create_tag(self, owner: str, repo: str, data: dict) -> dict:
        """Create a new tag"""
        return await self.request("POST", f"repos/{owner}/{repo}/tags", json_data=data)

    async def delete_tag(self, owner: str, repo: str, tag: str) -> dict:
        """Delete a tag"""
        return await self.request("DELETE", f"repos/{owner}/{repo}/tags/{tag}")

    # File endpoints
    async def get_file(self, owner: str, repo: str, filepath: str, ref: str | None = None) -> dict:
        """Get file contents"""
        params = {"ref": ref} if ref else {}
        return await self.request("GET", f"repos/{owner}/{repo}/contents/{filepath}", params=params)

    async def create_file(self, owner: str, repo: str, filepath: str, data: dict) -> dict:
        """Create a file"""
        # Encode content to base64 if not already encoded
        if "content" in data:
            content = data["content"]

            # Check if content is already base64 encoded
            is_already_base64 = data.get("content_is_base64", False)

            if not is_already_base64:
                # Plain text content - encode to base64
                try:
                    data["content"] = base64.b64encode(content.encode()).decode()
                except (AttributeError, UnicodeDecodeError):
                    # If content is already bytes or has encoding issues, try direct encoding
                    if isinstance(content, bytes):
                        data["content"] = base64.b64encode(content).decode()
                    else:
                        raise ValueError("Content must be a string or bytes")

            # Remove the flag before sending to API
            data.pop("content_is_base64", None)

        return await self.request(
            "POST", f"repos/{owner}/{repo}/contents/{filepath}", json_data=data
        )

    async def update_file(self, owner: str, repo: str, filepath: str, data: dict) -> dict:
        """Update a file"""
        # Encode content to base64 if not already encoded
        if "content" in data:
            content = data["content"]

            # Check if content is already base64 encoded
            is_already_base64 = data.get("content_is_base64", False)

            if not is_already_base64:
                # Plain text content - encode to base64
                try:
                    data["content"] = base64.b64encode(content.encode()).decode()
                except (AttributeError, UnicodeDecodeError):
                    # If content is already bytes or has encoding issues, try direct encoding
                    if isinstance(content, bytes):
                        data["content"] = base64.b64encode(content).decode()
                    else:
                        raise ValueError("Content must be a string or bytes")

            # Remove the flag before sending to API
            data.pop("content_is_base64", None)

        return await self.request(
            "PUT", f"repos/{owner}/{repo}/contents/{filepath}", json_data=data
        )

    async def delete_file(
        self,
        owner: str,
        repo: str,
        filepath: str,
        sha: str,
        message: str,
        branch: str | None = None,
    ) -> dict:
        """Delete a file"""
        data = {"sha": sha, "message": message}
        if branch:
            data["branch"] = branch
        return await self.request(
            "DELETE", f"repos/{owner}/{repo}/contents/{filepath}", json_data=data
        )

    # Issue endpoints
    async def list_issues(self, owner: str, repo: str, params: dict) -> list[dict]:
        """List repository issues"""
        return await self.request("GET", f"repos/{owner}/{repo}/issues", params=params)

    async def get_issue(self, owner: str, repo: str, index: int) -> dict:
        """Get issue details"""
        return await self.request("GET", f"repos/{owner}/{repo}/issues/{index}")

    async def create_issue(self, owner: str, repo: str, data: dict) -> dict:
        """Create a new issue"""
        return await self.request("POST", f"repos/{owner}/{repo}/issues", json_data=data)

    async def update_issue(self, owner: str, repo: str, index: int, data: dict) -> dict:
        """Update an issue"""
        return await self.request("PATCH", f"repos/{owner}/{repo}/issues/{index}", json_data=data)

    async def list_issue_comments(self, owner: str, repo: str, index: int) -> list[dict]:
        """List issue comments"""
        return await self.request("GET", f"repos/{owner}/{repo}/issues/{index}/comments")

    async def create_issue_comment(self, owner: str, repo: str, index: int, data: dict) -> dict:
        """Create issue comment"""
        return await self.request(
            "POST", f"repos/{owner}/{repo}/issues/{index}/comments", json_data=data
        )

    # Label endpoints
    async def list_labels(self, owner: str, repo: str) -> list[dict]:
        """List repository labels"""
        return await self.request("GET", f"repos/{owner}/{repo}/labels")

    async def create_label(self, owner: str, repo: str, data: dict) -> dict:
        """Create a label"""
        return await self.request("POST", f"repos/{owner}/{repo}/labels", json_data=data)

    async def delete_label(self, owner: str, repo: str, label_id: int) -> dict:
        """Delete a label"""
        return await self.request("DELETE", f"repos/{owner}/{repo}/labels/{label_id}")

    # Milestone endpoints
    async def list_milestones(self, owner: str, repo: str, state: str | None = None) -> list[dict]:
        """List repository milestones"""
        params = {"state": state} if state else {}
        return await self.request("GET", f"repos/{owner}/{repo}/milestones", params=params)

    async def create_milestone(self, owner: str, repo: str, data: dict) -> dict:
        """Create a milestone"""
        return await self.request("POST", f"repos/{owner}/{repo}/milestones", json_data=data)

    # Pull Request endpoints
    async def list_pull_requests(self, owner: str, repo: str, params: dict) -> list[dict]:
        """List repository pull requests"""
        return await self.request("GET", f"repos/{owner}/{repo}/pulls", params=params)

    async def get_pull_request(self, owner: str, repo: str, index: int) -> dict:
        """Get pull request details"""
        return await self.request("GET", f"repos/{owner}/{repo}/pulls/{index}")

    async def create_pull_request(self, owner: str, repo: str, data: dict) -> dict:
        """Create a new pull request"""
        return await self.request("POST", f"repos/{owner}/{repo}/pulls", json_data=data)

    async def update_pull_request(self, owner: str, repo: str, index: int, data: dict) -> dict:
        """Update a pull request"""
        return await self.request("PATCH", f"repos/{owner}/{repo}/pulls/{index}", json_data=data)

    async def merge_pull_request(self, owner: str, repo: str, index: int, data: dict) -> dict:
        """Merge a pull request"""
        return await self.request(
            "POST", f"repos/{owner}/{repo}/pulls/{index}/merge", json_data=data
        )

    async def list_pr_commits(self, owner: str, repo: str, index: int) -> list[dict]:
        """List pull request commits"""
        return await self.request("GET", f"repos/{owner}/{repo}/pulls/{index}/commits")

    async def list_pr_files(self, owner: str, repo: str, index: int) -> list[dict]:
        """List pull request files"""
        return await self.request("GET", f"repos/{owner}/{repo}/pulls/{index}/files")

    async def get_pr_diff(self, owner: str, repo: str, index: int) -> str:
        """Get pull request diff"""
        # Override accept header for diff
        headers = {"accept": "text/plain"}
        response = await self.request(
            "GET", f"repos/{owner}/{repo}/pulls/{index}.diff", headers_override=headers
        )
        return response

    async def list_pr_reviews(self, owner: str, repo: str, index: int) -> list[dict]:
        """List pull request reviews"""
        return await self.request("GET", f"repos/{owner}/{repo}/pulls/{index}/reviews")

    async def create_pr_review(self, owner: str, repo: str, index: int, data: dict) -> dict:
        """Create pull request review"""
        return await self.request(
            "POST", f"repos/{owner}/{repo}/pulls/{index}/reviews", json_data=data
        )

    async def request_pr_reviewers(self, owner: str, repo: str, index: int, data: dict) -> dict:
        """Request pull request reviewers"""
        return await self.request(
            "POST", f"repos/{owner}/{repo}/pulls/{index}/requested_reviewers", json_data=data
        )

    # User endpoints
    async def get_user(self, username: str) -> dict:
        """Get user information"""
        return await self.request("GET", f"users/{username}")

    async def list_user_repos(self, username: str, page: int = 1, limit: int = 30) -> list[dict]:
        """List user repositories"""
        params = {"page": page, "limit": limit}
        return await self.request("GET", f"users/{username}/repos", params=params)

    async def search_users(self, query: str | None = None, uid: int | None = None) -> list[dict]:
        """Search users"""
        params = {}
        if query:
            params["q"] = query
        if uid:
            params["uid"] = uid
        response = await self.request("GET", "users/search", params=params)
        return response.get("data", [])

    # Organization endpoints
    async def list_organizations(self, page: int = 1, limit: int = 30) -> list[dict]:
        """List current user's organizations"""
        params = {"page": page, "limit": limit}
        return await self.request("GET", "user/orgs", params=params)

    async def get_organization(self, org: str) -> dict:
        """Get organization information"""
        return await self.request("GET", f"orgs/{org}")

    async def list_org_repos(self, org: str, page: int = 1, limit: int = 30) -> list[dict]:
        """List organization repositories"""
        params = {"page": page, "limit": limit}
        return await self.request("GET", f"orgs/{org}/repos", params=params)

    async def list_org_teams(self, org: str, page: int = 1, limit: int = 30) -> list[dict]:
        """List organization teams"""
        params = {"page": page, "limit": limit}
        return await self.request("GET", f"orgs/{org}/teams", params=params)

    async def list_team_members(self, team_id: int, page: int = 1, limit: int = 30) -> list[dict]:
        """List team members"""
        params = {"page": page, "limit": limit}
        return await self.request("GET", f"teams/{team_id}/members", params=params)

    # Webhook endpoints
    async def list_webhooks(self, owner: str, repo: str) -> list[dict]:
        """List repository webhooks"""
        return await self.request("GET", f"repos/{owner}/{repo}/hooks")

    async def create_webhook(self, owner: str, repo: str, data: dict) -> dict:
        """Create a webhook"""
        return await self.request("POST", f"repos/{owner}/{repo}/hooks", json_data=data)

    async def get_webhook(self, owner: str, repo: str, hook_id: int) -> dict:
        """Get webhook details"""
        return await self.request("GET", f"repos/{owner}/{repo}/hooks/{hook_id}")

    async def update_webhook(self, owner: str, repo: str, hook_id: int, data: dict) -> dict:
        """Update a webhook"""
        return await self.request("PATCH", f"repos/{owner}/{repo}/hooks/{hook_id}", json_data=data)

    async def delete_webhook(self, owner: str, repo: str, hook_id: int) -> dict:
        """Delete a webhook"""
        return await self.request("DELETE", f"repos/{owner}/{repo}/hooks/{hook_id}")

    async def test_webhook(self, owner: str, repo: str, hook_id: int) -> dict:
        """Test a webhook"""
        return await self.request("POST", f"repos/{owner}/{repo}/hooks/{hook_id}/tests")
