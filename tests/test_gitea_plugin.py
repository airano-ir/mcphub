"""Tests for Gitea Plugin (plugins/gitea/).

Unit tests covering client initialization, tool specifications,
handler delegation, API request building, and health checks.
"""

import json
from unittest.mock import AsyncMock

import pytest

from plugins.gitea.client import GiteaClient
from plugins.gitea.plugin import GiteaPlugin

# --- GiteaClient Tests ---


class TestGiteaClientInit:
    """Test GiteaClient initialization."""

    def test_valid_initialization(self):
        """Should initialize with valid credentials."""
        client = GiteaClient(site_url="https://gitea.example.com", token="test-token")
        assert client.site_url == "https://gitea.example.com"
        assert client.api_base == "https://gitea.example.com/api/v1"
        assert client.token == "test-token"
        assert client.oauth_enabled is False

    def test_trailing_slash_stripped(self):
        """Should strip trailing slash from site URL."""
        client = GiteaClient(site_url="https://gitea.example.com/", token="tk")
        assert client.site_url == "https://gitea.example.com"
        assert client.api_base == "https://gitea.example.com/api/v1"

    def test_no_token(self):
        """Should allow initialization without token."""
        client = GiteaClient(site_url="https://gitea.example.com")
        assert client.token is None

    def test_oauth_enabled(self):
        """Should store oauth_enabled flag."""
        client = GiteaClient(site_url="https://gitea.example.com", token="tk", oauth_enabled=True)
        assert client.oauth_enabled is True

    def test_logger_created(self):
        """Should create a logger with site URL."""
        client = GiteaClient(site_url="https://gitea.example.com", token="tk")
        assert client.logger is not None
        assert "gitea.example.com" in client.logger.name


class TestGiteaClientHeaders:
    """Test request header generation."""

    def test_default_headers_with_token(self):
        """Should include Authorization header when token is set."""
        client = GiteaClient(site_url="https://g.com", token="my-token")
        headers = client._get_headers()
        assert headers["Authorization"] == "token my-token"
        assert headers["Content-Type"] == "application/json"
        assert headers["accept"] == "application/json"

    def test_default_headers_without_token(self):
        """Should not include Authorization header when no token."""
        client = GiteaClient(site_url="https://g.com")
        headers = client._get_headers()
        assert "Authorization" not in headers
        assert headers["Content-Type"] == "application/json"

    def test_additional_headers_merged(self):
        """Should merge additional headers."""
        client = GiteaClient(site_url="https://g.com", token="tk")
        headers = client._get_headers(additional_headers={"X-Custom": "val"})
        assert headers["X-Custom"] == "val"
        assert headers["Authorization"] == "token tk"

    def test_additional_headers_override(self):
        """Should allow overriding default headers."""
        client = GiteaClient(site_url="https://g.com", token="tk")
        headers = client._get_headers(additional_headers={"Content-Type": "text/plain"})
        assert headers["Content-Type"] == "text/plain"


# --- GiteaPlugin Tests ---


class TestGiteaPluginInit:
    """Test GiteaPlugin initialization."""

    def test_valid_initialization(self):
        """Should initialize with URL config."""
        plugin = GiteaPlugin(config={"url": "https://gitea.example.com", "token": "tk"})
        assert plugin.client.site_url == "https://gitea.example.com"
        assert plugin.client.token == "tk"

    def test_plugin_name(self):
        """Should return 'gitea' as plugin name."""
        assert GiteaPlugin.get_plugin_name() == "gitea"

    def test_required_config_keys(self):
        """Should require 'url' key."""
        assert GiteaPlugin.get_required_config_keys() == ["url"]

    def test_oauth_config(self):
        """Should pass oauth_enabled to client."""
        plugin = GiteaPlugin(config={"url": "https://gitea.example.com", "oauth_enabled": True})
        assert plugin.client.oauth_enabled is True

    def test_getattr_raises_for_unknown(self):
        """Should raise AttributeError for unknown method."""
        plugin = GiteaPlugin(config={"url": "https://gitea.example.com"})
        with pytest.raises(AttributeError, match="has no attribute 'nonexistent_method'"):
            plugin.nonexistent_method  # noqa: B018


# --- Tool Specification Tests ---


class TestGiteaToolSpecifications:
    """Test tool specifications from all handlers."""

    @pytest.fixture()
    def specs(self):
        """Get all tool specifications."""
        return GiteaPlugin.get_tool_specifications()

    def test_total_tool_count(self, specs):
        """Should have 58 tools total (16 repo + 13 issue + 15 PR + 8 user + 6 webhook)."""
        assert len(specs) == 58

    def test_all_specs_have_required_keys(self, specs):
        """Every spec must have name, method_name, description, schema, scope."""
        required_keys = {"name", "method_name", "description", "schema", "scope"}
        for spec in specs:
            missing = required_keys - set(spec.keys())
            assert not missing, f"Tool '{spec.get('name', '?')}' missing keys: {missing}"

    def test_all_specs_have_unique_names(self, specs):
        """All tool names must be unique."""
        names = [s["name"] for s in specs]
        assert len(names) == len(
            set(names)
        ), f"Duplicate names: {[n for n in names if names.count(n) > 1]}"

    def test_all_scopes_are_valid(self, specs):
        """All scopes must be read, write, or admin."""
        valid_scopes = {"read", "write", "admin"}
        for spec in specs:
            assert (
                spec["scope"] in valid_scopes
            ), f"Tool '{spec['name']}' has invalid scope: {spec['scope']}"

    def test_all_schemas_have_type_object(self, specs):
        """All schemas must be type: object."""
        for spec in specs:
            assert spec["schema"]["type"] == "object", f"Tool '{spec['name']}' schema not object"

    def test_repository_tools_present(self, specs):
        """Should have all 16 repository tools."""
        repo_tools = {
            "list_repositories",
            "get_repository",
            "create_repository",
            "update_repository",
            "delete_repository",
            "list_branches",
            "get_branch",
            "create_branch",
            "delete_branch",
            "list_tags",
            "create_tag",
            "delete_tag",
            "get_file",
            "create_file",
            "update_file",
            "delete_file",
        }
        names = {s["name"] for s in specs}
        assert repo_tools.issubset(names), f"Missing repo tools: {repo_tools - names}"

    def test_issue_tools_present(self, specs):
        """Should have all 13 issue tools."""
        issue_tools = {
            "list_issues",
            "get_issue",
            "create_issue",
            "update_issue",
            "close_issue",
            "reopen_issue",
            "list_issue_comments",
            "create_issue_comment",
            "list_labels",
            "create_label",
            "delete_label",
            "list_milestones",
            "create_milestone",
        }
        names = {s["name"] for s in specs}
        assert issue_tools.issubset(names), f"Missing issue tools: {issue_tools - names}"

    def test_pull_request_tools_present(self, specs):
        """Should have all 15 pull request tools."""
        pr_tools = {
            "list_pull_requests",
            "get_pull_request",
            "create_pull_request",
            "update_pull_request",
            "merge_pull_request",
            "close_pull_request",
            "reopen_pull_request",
            "list_pr_commits",
            "list_pr_files",
            "get_pr_diff",
            "list_pr_comments",
            "create_pr_comment",
            "list_pr_reviews",
            "create_pr_review",
            "request_pr_reviewers",
        }
        names = {s["name"] for s in specs}
        assert pr_tools.issubset(names), f"Missing PR tools: {pr_tools - names}"

    def test_user_tools_present(self, specs):
        """Should have all 8 user tools."""
        user_tools = {
            "get_user",
            "list_user_repos",
            "search_users",
            "list_organizations",
            "get_organization",
            "list_org_repos",
            "list_org_teams",
            "list_team_members",
        }
        names = {s["name"] for s in specs}
        assert user_tools.issubset(names), f"Missing user tools: {user_tools - names}"

    def test_webhook_tools_present(self, specs):
        """Should have all 6 webhook tools."""
        webhook_tools = {
            "list_webhooks",
            "create_webhook",
            "get_webhook",
            "update_webhook",
            "delete_webhook",
            "test_webhook",
        }
        names = {s["name"] for s in specs}
        assert webhook_tools.issubset(names), f"Missing webhook tools: {webhook_tools - names}"

    def test_delete_repository_is_admin_scope(self, specs):
        """delete_repository should be admin scope."""
        spec = next(s for s in specs if s["name"] == "delete_repository")
        assert spec["scope"] == "admin"

    def test_list_issues_is_read_scope(self, specs):
        """list_issues should be read scope."""
        spec = next(s for s in specs if s["name"] == "list_issues")
        assert spec["scope"] == "read"

    def test_create_issue_is_write_scope(self, specs):
        """create_issue should be write scope."""
        spec = next(s for s in specs if s["name"] == "create_issue")
        assert spec["scope"] == "write"

    def test_create_webhook_is_admin_scope(self, specs):
        """create_webhook should be admin scope."""
        spec = next(s for s in specs if s["name"] == "create_webhook")
        assert spec["scope"] == "admin"

    def test_update_webhook_is_admin_scope(self, specs):
        """update_webhook should be admin scope."""
        spec = next(s for s in specs if s["name"] == "update_webhook")
        assert spec["scope"] == "admin"

    def test_merge_pr_schema_has_method_enum(self, specs):
        """merge_pull_request should have method enum."""
        spec = next(s for s in specs if s["name"] == "merge_pull_request")
        method_prop = spec["schema"]["properties"]["method"]
        assert method_prop["enum"] == ["merge", "rebase", "rebase-merge", "squash"]

    def test_create_issue_required_fields(self, specs):
        """create_issue should require owner, repo, title."""
        spec = next(s for s in specs if s["name"] == "create_issue")
        assert set(spec["schema"]["required"]) == {"owner", "repo", "title"}

    def test_create_pr_required_fields(self, specs):
        """create_pull_request should require owner, repo, title, head, base."""
        spec = next(s for s in specs if s["name"] == "create_pull_request")
        assert set(spec["schema"]["required"]) == {"owner", "repo", "title", "head", "base"}


# --- Repository Handler Tests ---


class TestRepositoryHandlers:
    """Test repository handler functions via mocked client."""

    @pytest.mark.asyncio
    async def test_list_repositories(self):
        """Should return list of repositories."""
        from plugins.gitea.handlers.repositories import list_repositories

        client = GiteaClient(site_url="https://g.com", token="tk")
        client.list_repositories = AsyncMock(return_value=[{"name": "repo1"}, {"name": "repo2"}])

        result = json.loads(await list_repositories(client, owner="user1"))
        assert result["success"] is True
        assert result["count"] == 2
        assert len(result["repositories"]) == 2

    @pytest.mark.asyncio
    async def test_get_repository(self):
        """Should return repository details."""
        from plugins.gitea.handlers.repositories import get_repository

        client = GiteaClient(site_url="https://g.com", token="tk")
        client.get_repository = AsyncMock(return_value={"name": "repo1", "full_name": "user/repo1"})

        result = json.loads(await get_repository(client, owner="user", repo="repo1"))
        assert result["success"] is True
        assert result["repository"]["name"] == "repo1"

    @pytest.mark.asyncio
    async def test_create_repository(self):
        """Should create and return repository."""
        from plugins.gitea.handlers.repositories import create_repository

        client = GiteaClient(site_url="https://g.com", token="tk")
        client.create_repository = AsyncMock(return_value={"name": "new-repo", "id": 42})

        result = json.loads(await create_repository(client, name="new-repo", private=True))
        assert result["success"] is True
        assert "new-repo" in result["message"]
        client.create_repository.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_repository_in_org(self):
        """Should create repo under organization."""
        from plugins.gitea.handlers.repositories import create_repository

        client = GiteaClient(site_url="https://g.com", token="tk")
        client.create_repository = AsyncMock(return_value={"name": "org-repo"})

        await create_repository(client, name="org-repo", org="myorg")
        call_kwargs = client.create_repository.call_args
        assert call_kwargs.kwargs.get("org") == "myorg" or call_kwargs[1].get("org") == "myorg"

    @pytest.mark.asyncio
    async def test_delete_repository(self):
        """Should delete repository."""
        from plugins.gitea.handlers.repositories import delete_repository

        client = GiteaClient(site_url="https://g.com", token="tk")
        client.delete_repository = AsyncMock(return_value=None)

        result = json.loads(await delete_repository(client, owner="user", repo="old-repo"))
        assert result["success"] is True
        assert "deleted" in result["message"]

    @pytest.mark.asyncio
    async def test_list_branches(self):
        """Should return branches."""
        from plugins.gitea.handlers.repositories import list_branches

        client = GiteaClient(site_url="https://g.com", token="tk")
        client.list_branches = AsyncMock(return_value=[{"name": "main"}, {"name": "dev"}])

        result = json.loads(await list_branches(client, owner="u", repo="r"))
        assert result["count"] == 2

    @pytest.mark.asyncio
    async def test_create_branch(self):
        """Should create branch."""
        from plugins.gitea.handlers.repositories import create_branch

        client = GiteaClient(site_url="https://g.com", token="tk")
        client.create_branch = AsyncMock(return_value={"name": "feature"})

        result = json.loads(
            await create_branch(client, owner="u", repo="r", new_branch_name="feature")
        )
        assert result["success"] is True
        assert "feature" in result["message"]

    @pytest.mark.asyncio
    async def test_delete_branch(self):
        """Should delete branch."""
        from plugins.gitea.handlers.repositories import delete_branch

        client = GiteaClient(site_url="https://g.com", token="tk")
        client.delete_branch = AsyncMock(return_value=None)

        result = json.loads(await delete_branch(client, owner="u", repo="r", branch="old"))
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_list_tags(self):
        """Should return tags."""
        from plugins.gitea.handlers.repositories import list_tags

        client = GiteaClient(site_url="https://g.com", token="tk")
        client.list_tags = AsyncMock(return_value=[{"name": "v1.0"}])

        result = json.loads(await list_tags(client, owner="u", repo="r"))
        assert result["count"] == 1

    @pytest.mark.asyncio
    async def test_create_tag(self):
        """Should create tag."""
        from plugins.gitea.handlers.repositories import create_tag

        client = GiteaClient(site_url="https://g.com", token="tk")
        client.create_tag = AsyncMock(return_value={"name": "v2.0"})

        result = json.loads(await create_tag(client, owner="u", repo="r", tag_name="v2.0"))
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_get_file(self):
        """Should return file contents."""
        from plugins.gitea.handlers.repositories import get_file

        client = GiteaClient(site_url="https://g.com", token="tk")
        client.get_file = AsyncMock(return_value={"content": "SGVsbG8=", "name": "README.md"})

        result = json.loads(await get_file(client, owner="u", repo="r", path="README.md"))
        assert result["success"] is True
        assert result["file"]["name"] == "README.md"

    @pytest.mark.asyncio
    async def test_create_file(self):
        """Should create file."""
        from plugins.gitea.handlers.repositories import create_file

        client = GiteaClient(site_url="https://g.com", token="tk")
        client.create_file = AsyncMock(return_value={"content": {"name": "test.txt"}})

        result = json.loads(
            await create_file(
                client, owner="u", repo="r", path="test.txt", content="Hello", message="add"
            )
        )
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_update_file(self):
        """Should update file."""
        from plugins.gitea.handlers.repositories import update_file

        client = GiteaClient(site_url="https://g.com", token="tk")
        client.update_file = AsyncMock(return_value={"content": {"name": "test.txt"}})

        result = json.loads(
            await update_file(
                client,
                owner="u",
                repo="r",
                path="test.txt",
                content="Updated",
                sha="abc123",
                message="update",
            )
        )
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_delete_file(self):
        """Should delete file."""
        from plugins.gitea.handlers.repositories import delete_file

        client = GiteaClient(site_url="https://g.com", token="tk")
        client.delete_file = AsyncMock(return_value=None)

        result = json.loads(
            await delete_file(client, owner="u", repo="r", path="old.txt", sha="abc", message="rm")
        )
        assert result["success"] is True


# --- Issue Handler Tests ---


class TestIssueHandlers:
    """Test issue handler functions via mocked client."""

    @pytest.mark.asyncio
    async def test_list_issues(self):
        """Should return issues list."""
        from plugins.gitea.handlers.issues import list_issues

        client = GiteaClient(site_url="https://g.com", token="tk")
        client.list_issues = AsyncMock(return_value=[{"number": 1}, {"number": 2}])

        result = json.loads(await list_issues(client, owner="u", repo="r"))
        assert result["count"] == 2

    @pytest.mark.asyncio
    async def test_get_issue(self):
        """Should return issue details."""
        from plugins.gitea.handlers.issues import get_issue

        client = GiteaClient(site_url="https://g.com", token="tk")
        client.get_issue = AsyncMock(return_value={"number": 5, "title": "Bug"})

        result = json.loads(await get_issue(client, owner="u", repo="r", issue_number=5))
        assert result["issue"]["title"] == "Bug"

    @pytest.mark.asyncio
    async def test_create_issue(self):
        """Should create issue."""
        from plugins.gitea.handlers.issues import create_issue

        client = GiteaClient(site_url="https://g.com", token="tk")
        client.create_issue = AsyncMock(return_value={"number": 10, "title": "New bug"})

        result = json.loads(await create_issue(client, owner="u", repo="r", title="New bug"))
        assert result["success"] is True
        assert "#10" in result["message"]

    @pytest.mark.asyncio
    async def test_close_issue(self):
        """Should close issue."""
        from plugins.gitea.handlers.issues import close_issue

        client = GiteaClient(site_url="https://g.com", token="tk")
        client.update_issue = AsyncMock(return_value={"number": 5, "state": "closed"})

        result = json.loads(await close_issue(client, owner="u", repo="r", issue_number=5))
        assert "closed" in result["message"]
        client.update_issue.assert_called_once_with("u", "r", 5, {"state": "closed"})

    @pytest.mark.asyncio
    async def test_reopen_issue(self):
        """Should reopen issue."""
        from plugins.gitea.handlers.issues import reopen_issue

        client = GiteaClient(site_url="https://g.com", token="tk")
        client.update_issue = AsyncMock(return_value={"number": 5, "state": "open"})

        result = json.loads(await reopen_issue(client, owner="u", repo="r", issue_number=5))
        assert "reopened" in result["message"]
        client.update_issue.assert_called_once_with("u", "r", 5, {"state": "open"})

    @pytest.mark.asyncio
    async def test_list_issue_comments(self):
        """Should return comments."""
        from plugins.gitea.handlers.issues import list_issue_comments

        client = GiteaClient(site_url="https://g.com", token="tk")
        client.list_issue_comments = AsyncMock(return_value=[{"id": 1, "body": "hi"}])

        result = json.loads(await list_issue_comments(client, owner="u", repo="r", issue_number=1))
        assert result["count"] == 1

    @pytest.mark.asyncio
    async def test_create_issue_comment(self):
        """Should create comment."""
        from plugins.gitea.handlers.issues import create_issue_comment

        client = GiteaClient(site_url="https://g.com", token="tk")
        client.create_issue_comment = AsyncMock(return_value={"id": 2, "body": "Thanks"})

        result = json.loads(
            await create_issue_comment(client, owner="u", repo="r", issue_number=1, body="Thanks")
        )
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_list_labels(self):
        """Should return labels."""
        from plugins.gitea.handlers.issues import list_labels

        client = GiteaClient(site_url="https://g.com", token="tk")
        client.list_labels = AsyncMock(return_value=[{"id": 1, "name": "bug"}])

        result = json.loads(await list_labels(client, owner="u", repo="r"))
        assert result["count"] == 1

    @pytest.mark.asyncio
    async def test_create_label(self):
        """Should create label."""
        from plugins.gitea.handlers.issues import create_label

        client = GiteaClient(site_url="https://g.com", token="tk")
        client.create_label = AsyncMock(return_value={"id": 2, "name": "feature"})

        result = json.loads(
            await create_label(client, owner="u", repo="r", name="feature", color="00ff00")
        )
        assert result["success"] is True
        assert "feature" in result["message"]

    @pytest.mark.asyncio
    async def test_delete_label(self):
        """Should delete label."""
        from plugins.gitea.handlers.issues import delete_label

        client = GiteaClient(site_url="https://g.com", token="tk")
        client.delete_label = AsyncMock(return_value=None)

        result = json.loads(await delete_label(client, owner="u", repo="r", label_id=1))
        assert result["success"] is True
        assert "deleted" in result["message"]

    @pytest.mark.asyncio
    async def test_list_milestones(self):
        """Should return milestones."""
        from plugins.gitea.handlers.issues import list_milestones

        client = GiteaClient(site_url="https://g.com", token="tk")
        client.list_milestones = AsyncMock(return_value=[{"id": 1, "title": "v1.0"}])

        result = json.loads(await list_milestones(client, owner="u", repo="r"))
        assert result["count"] == 1

    @pytest.mark.asyncio
    async def test_create_milestone(self):
        """Should create milestone."""
        from plugins.gitea.handlers.issues import create_milestone

        client = GiteaClient(site_url="https://g.com", token="tk")
        client.create_milestone = AsyncMock(return_value={"id": 2, "title": "v2.0"})

        result = json.loads(await create_milestone(client, owner="u", repo="r", title="v2.0"))
        assert result["success"] is True


# --- Pull Request Handler Tests ---


class TestPullRequestHandlers:
    """Test pull request handler functions via mocked client."""

    @pytest.mark.asyncio
    async def test_list_pull_requests(self):
        """Should return pull requests."""
        from plugins.gitea.handlers.pull_requests import list_pull_requests

        client = GiteaClient(site_url="https://g.com", token="tk")
        client.list_pull_requests = AsyncMock(return_value=[{"number": 1}])

        result = json.loads(await list_pull_requests(client, owner="u", repo="r"))
        assert result["count"] == 1

    @pytest.mark.asyncio
    async def test_get_pull_request(self):
        """Should return PR details."""
        from plugins.gitea.handlers.pull_requests import get_pull_request

        client = GiteaClient(site_url="https://g.com", token="tk")
        client.get_pull_request = AsyncMock(return_value={"number": 3, "title": "Fix"})

        result = json.loads(await get_pull_request(client, owner="u", repo="r", pr_number=3))
        assert result["pull_request"]["title"] == "Fix"

    @pytest.mark.asyncio
    async def test_create_pull_request(self):
        """Should create PR."""
        from plugins.gitea.handlers.pull_requests import create_pull_request

        client = GiteaClient(site_url="https://g.com", token="tk")
        client.create_pull_request = AsyncMock(return_value={"number": 7, "title": "New feature"})

        result = json.loads(
            await create_pull_request(
                client, owner="u", repo="r", title="New feature", head="feat", base="main"
            )
        )
        assert result["success"] is True
        assert "#7" in result["message"]

    @pytest.mark.asyncio
    async def test_merge_pull_request(self):
        """Should merge PR with specified method."""
        from plugins.gitea.handlers.pull_requests import merge_pull_request

        client = GiteaClient(site_url="https://g.com", token="tk")
        client.merge_pull_request = AsyncMock(return_value={"merged": True})

        result = json.loads(
            await merge_pull_request(client, owner="u", repo="r", pr_number=3, method="squash")
        )
        assert result["success"] is True
        assert "squash" in result["message"]

    @pytest.mark.asyncio
    async def test_close_pull_request(self):
        """Should close PR."""
        from plugins.gitea.handlers.pull_requests import close_pull_request

        client = GiteaClient(site_url="https://g.com", token="tk")
        client.update_pull_request = AsyncMock(return_value={"number": 3, "state": "closed"})

        result = json.loads(await close_pull_request(client, owner="u", repo="r", pr_number=3))
        assert "closed" in result["message"]

    @pytest.mark.asyncio
    async def test_reopen_pull_request(self):
        """Should reopen PR."""
        from plugins.gitea.handlers.pull_requests import reopen_pull_request

        client = GiteaClient(site_url="https://g.com", token="tk")
        client.update_pull_request = AsyncMock(return_value={"number": 3, "state": "open"})

        result = json.loads(await reopen_pull_request(client, owner="u", repo="r", pr_number=3))
        assert "reopened" in result["message"]

    @pytest.mark.asyncio
    async def test_list_pr_commits(self):
        """Should return PR commits."""
        from plugins.gitea.handlers.pull_requests import list_pr_commits

        client = GiteaClient(site_url="https://g.com", token="tk")
        client.list_pr_commits = AsyncMock(return_value=[{"sha": "abc"}])

        result = json.loads(await list_pr_commits(client, owner="u", repo="r", pr_number=1))
        assert result["count"] == 1

    @pytest.mark.asyncio
    async def test_list_pr_files(self):
        """Should return PR files."""
        from plugins.gitea.handlers.pull_requests import list_pr_files

        client = GiteaClient(site_url="https://g.com", token="tk")
        client.list_pr_files = AsyncMock(return_value=[{"filename": "a.py"}])

        result = json.loads(await list_pr_files(client, owner="u", repo="r", pr_number=1))
        assert result["count"] == 1

    @pytest.mark.asyncio
    async def test_get_pr_diff(self):
        """Should return PR diff."""
        from plugins.gitea.handlers.pull_requests import get_pr_diff

        client = GiteaClient(site_url="https://g.com", token="tk")
        client.get_pr_diff = AsyncMock(return_value="--- a/file\n+++ b/file")

        result = json.loads(await get_pr_diff(client, owner="u", repo="r", pr_number=1))
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_create_pr_comment(self):
        """Should create PR comment."""
        from plugins.gitea.handlers.pull_requests import create_pr_comment

        client = GiteaClient(site_url="https://g.com", token="tk")
        client.create_issue_comment = AsyncMock(return_value={"id": 5, "body": "LGTM"})

        result = json.loads(
            await create_pr_comment(client, owner="u", repo="r", pr_number=1, body="LGTM")
        )
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_list_pr_reviews(self):
        """Should return PR reviews."""
        from plugins.gitea.handlers.pull_requests import list_pr_reviews

        client = GiteaClient(site_url="https://g.com", token="tk")
        client.list_pr_reviews = AsyncMock(return_value=[{"id": 1, "state": "APPROVED"}])

        result = json.loads(await list_pr_reviews(client, owner="u", repo="r", pr_number=1))
        assert result["count"] == 1

    @pytest.mark.asyncio
    async def test_create_pr_review(self):
        """Should create PR review."""
        from plugins.gitea.handlers.pull_requests import create_pr_review

        client = GiteaClient(site_url="https://g.com", token="tk")
        client.create_pr_review = AsyncMock(return_value={"id": 2, "state": "APPROVED"})

        result = json.loads(
            await create_pr_review(client, owner="u", repo="r", pr_number=1, event="APPROVED")
        )
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_request_pr_reviewers(self):
        """Should request reviewers."""
        from plugins.gitea.handlers.pull_requests import request_pr_reviewers

        client = GiteaClient(site_url="https://g.com", token="tk")
        client.request_pr_reviewers = AsyncMock(return_value={"ok": True})

        result = json.loads(
            await request_pr_reviewers(
                client, owner="u", repo="r", pr_number=1, reviewers=["alice"]
            )
        )
        assert result["success"] is True


# --- User Handler Tests ---


class TestUserHandlers:
    """Test user handler functions via mocked client."""

    @pytest.mark.asyncio
    async def test_get_user(self):
        """Should return user info."""
        from plugins.gitea.handlers.users import get_user

        client = GiteaClient(site_url="https://g.com", token="tk")
        client.get_user = AsyncMock(return_value={"login": "alice", "id": 1})

        result = json.loads(await get_user(client, username="alice"))
        assert result["user"]["login"] == "alice"

    @pytest.mark.asyncio
    async def test_list_user_repos(self):
        """Should return user repos."""
        from plugins.gitea.handlers.users import list_user_repos

        client = GiteaClient(site_url="https://g.com", token="tk")
        client.list_user_repos = AsyncMock(return_value=[{"name": "r1"}])

        result = json.loads(await list_user_repos(client, username="alice"))
        assert result["count"] == 1

    @pytest.mark.asyncio
    async def test_search_users(self):
        """Should search users."""
        from plugins.gitea.handlers.users import search_users

        client = GiteaClient(site_url="https://g.com", token="tk")
        client.search_users = AsyncMock(return_value=[{"login": "bob"}])

        result = json.loads(await search_users(client, q="bob"))
        assert result["count"] == 1

    @pytest.mark.asyncio
    async def test_list_organizations(self):
        """Should return orgs."""
        from plugins.gitea.handlers.users import list_organizations

        client = GiteaClient(site_url="https://g.com", token="tk")
        client.list_organizations = AsyncMock(return_value=[{"username": "myorg"}])

        result = json.loads(await list_organizations(client))
        assert result["count"] == 1

    @pytest.mark.asyncio
    async def test_get_organization(self):
        """Should return org info."""
        from plugins.gitea.handlers.users import get_organization

        client = GiteaClient(site_url="https://g.com", token="tk")
        client.get_organization = AsyncMock(return_value={"username": "myorg"})

        result = json.loads(await get_organization(client, org="myorg"))
        assert result["organization"]["username"] == "myorg"

    @pytest.mark.asyncio
    async def test_list_org_repos(self):
        """Should return org repos."""
        from plugins.gitea.handlers.users import list_org_repos

        client = GiteaClient(site_url="https://g.com", token="tk")
        client.list_org_repos = AsyncMock(return_value=[{"name": "proj1"}])

        result = json.loads(await list_org_repos(client, org="myorg"))
        assert result["count"] == 1

    @pytest.mark.asyncio
    async def test_list_org_teams(self):
        """Should return org teams."""
        from plugins.gitea.handlers.users import list_org_teams

        client = GiteaClient(site_url="https://g.com", token="tk")
        client.list_org_teams = AsyncMock(return_value=[{"id": 1, "name": "devs"}])

        result = json.loads(await list_org_teams(client, org="myorg"))
        assert result["count"] == 1

    @pytest.mark.asyncio
    async def test_list_team_members(self):
        """Should return team members."""
        from plugins.gitea.handlers.users import list_team_members

        client = GiteaClient(site_url="https://g.com", token="tk")
        client.list_team_members = AsyncMock(return_value=[{"login": "alice"}])

        result = json.loads(await list_team_members(client, team_id=1))
        assert result["count"] == 1


# --- Webhook Handler Tests ---


class TestWebhookHandlers:
    """Test webhook handler functions via mocked client."""

    @pytest.mark.asyncio
    async def test_list_webhooks(self):
        """Should return webhooks list."""
        from plugins.gitea.handlers.webhooks import list_webhooks

        client = GiteaClient(site_url="https://g.com", token="tk")
        client.list_webhooks = AsyncMock(
            return_value=[{"id": 1, "url": "https://hook.example.com"}]
        )

        result = json.loads(await list_webhooks(client, owner="u", repo="r"))
        assert result["count"] == 1

    @pytest.mark.asyncio
    async def test_create_webhook(self):
        """Should create webhook."""
        from plugins.gitea.handlers.webhooks import create_webhook

        client = GiteaClient(site_url="https://g.com", token="tk")
        client.create_webhook = AsyncMock(return_value={"id": 2})

        result = json.loads(
            await create_webhook(
                client, owner="u", repo="r", url="https://hook.example.com", events=["push"]
            )
        )
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_create_webhook_builds_config(self):
        """Should build correct webhook config."""
        from plugins.gitea.handlers.webhooks import create_webhook

        client = GiteaClient(site_url="https://g.com", token="tk")
        client.create_webhook = AsyncMock(return_value={"id": 3})

        await create_webhook(
            client,
            owner="u",
            repo="r",
            url="https://hook.example.com",
            events=["push", "issues"],
            content_type="form",
            secret="s3cret",
            active=False,
            type="slack",
        )

        call_data = client.create_webhook.call_args[0][2]  # data arg
        assert call_data["config"]["url"] == "https://hook.example.com"
        assert call_data["config"]["content_type"] == "form"
        assert call_data["config"]["secret"] == "s3cret"
        assert call_data["events"] == ["push", "issues"]
        assert call_data["active"] is False
        assert call_data["type"] == "slack"

    @pytest.mark.asyncio
    async def test_get_webhook(self):
        """Should return webhook details."""
        from plugins.gitea.handlers.webhooks import get_webhook

        client = GiteaClient(site_url="https://g.com", token="tk")
        client.get_webhook = AsyncMock(return_value={"id": 1, "active": True})

        result = json.loads(await get_webhook(client, owner="u", repo="r", webhook_id=1))
        assert result["webhook"]["active"] is True

    @pytest.mark.asyncio
    async def test_update_webhook(self):
        """Should update webhook."""
        from plugins.gitea.handlers.webhooks import update_webhook

        client = GiteaClient(site_url="https://g.com", token="tk")
        client.update_webhook = AsyncMock(return_value={"id": 1, "active": False})

        result = json.loads(
            await update_webhook(client, owner="u", repo="r", webhook_id=1, active=False)
        )
        assert result["success"] is True
        assert "updated" in result["message"]

    @pytest.mark.asyncio
    async def test_update_webhook_builds_data(self):
        """Should build correct update data with config."""
        from plugins.gitea.handlers.webhooks import update_webhook

        client = GiteaClient(site_url="https://g.com", token="tk")
        client.update_webhook = AsyncMock(return_value={"id": 1})

        await update_webhook(
            client,
            owner="u",
            repo="r",
            webhook_id=1,
            url="https://new-hook.com",
            events=["push"],
            content_type="json",
            active=True,
        )

        call_data = client.update_webhook.call_args[0][3]  # data arg
        assert call_data["config"]["url"] == "https://new-hook.com"
        assert call_data["config"]["content_type"] == "json"
        assert call_data["events"] == ["push"]
        assert call_data["active"] is True

    @pytest.mark.asyncio
    async def test_update_webhook_minimal(self):
        """Should send minimal data when only active is changed."""
        from plugins.gitea.handlers.webhooks import update_webhook

        client = GiteaClient(site_url="https://g.com", token="tk")
        client.update_webhook = AsyncMock(return_value={"id": 1})

        await update_webhook(client, owner="u", repo="r", webhook_id=1, active=False)

        call_data = client.update_webhook.call_args[0][3]
        assert call_data == {"active": False}
        assert "config" not in call_data

    @pytest.mark.asyncio
    async def test_delete_webhook(self):
        """Should delete webhook."""
        from plugins.gitea.handlers.webhooks import delete_webhook

        client = GiteaClient(site_url="https://g.com", token="tk")
        client.delete_webhook = AsyncMock(return_value=None)

        result = json.loads(await delete_webhook(client, owner="u", repo="r", webhook_id=1))
        assert result["success"] is True
        assert "deleted" in result["message"]

    @pytest.mark.asyncio
    async def test_test_webhook(self):
        """Should test webhook."""
        from plugins.gitea.handlers.webhooks import test_webhook

        client = GiteaClient(site_url="https://g.com", token="tk")
        client.test_webhook = AsyncMock(return_value={"status": 200})

        result = json.loads(await test_webhook(client, owner="u", repo="r", webhook_id=1))
        assert result["success"] is True


# --- Health Check Tests ---


class TestGiteaHealthCheck:
    """Test plugin health check."""

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """Should return healthy when API is accessible."""
        plugin = GiteaPlugin(config={"url": "https://gitea.example.com", "token": "tk"})
        plugin.client.request = AsyncMock(return_value={"login": "admin"})

        result = await plugin.health_check()
        assert result["healthy"] is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        """Should return unhealthy on API error."""
        plugin = GiteaPlugin(config={"url": "https://gitea.example.com", "token": "tk"})
        plugin.client.request = AsyncMock(side_effect=Exception("Connection refused"))

        result = await plugin.health_check()
        assert result["healthy"] is False
        assert "Connection refused" in result["message"]


# --- Plugin Delegation Tests ---


class TestGiteaPluginDelegation:
    """Test that plugin delegates methods to correct handlers."""

    @pytest.mark.asyncio
    async def test_delegates_to_repositories(self):
        """Should delegate list_repositories to repos handler."""
        plugin = GiteaPlugin(config={"url": "https://g.com", "token": "tk"})
        plugin.client.list_repositories = AsyncMock(return_value=[])

        result = json.loads(await plugin.list_repositories())
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_delegates_to_issues(self):
        """Should delegate list_issues to issues handler."""
        plugin = GiteaPlugin(config={"url": "https://g.com", "token": "tk"})
        plugin.client.list_issues = AsyncMock(return_value=[])

        result = json.loads(await plugin.list_issues(owner="u", repo="r"))
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_delegates_to_pull_requests(self):
        """Should delegate list_pull_requests to PR handler."""
        plugin = GiteaPlugin(config={"url": "https://g.com", "token": "tk"})
        plugin.client.list_pull_requests = AsyncMock(return_value=[])

        result = json.loads(await plugin.list_pull_requests(owner="u", repo="r"))
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_delegates_to_users(self):
        """Should delegate get_user to users handler."""
        plugin = GiteaPlugin(config={"url": "https://g.com", "token": "tk"})
        plugin.client.get_user = AsyncMock(return_value={"login": "test"})

        result = json.loads(await plugin.get_user(username="test"))
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_delegates_to_webhooks(self):
        """Should delegate list_webhooks to webhooks handler."""
        plugin = GiteaPlugin(config={"url": "https://g.com", "token": "tk"})
        plugin.client.list_webhooks = AsyncMock(return_value=[])

        result = json.loads(await plugin.list_webhooks(owner="u", repo="r"))
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_delegates_update_webhook(self):
        """Should delegate update_webhook to webhooks handler."""
        plugin = GiteaPlugin(config={"url": "https://g.com", "token": "tk"})
        plugin.client.update_webhook = AsyncMock(return_value={"id": 1})

        result = json.loads(
            await plugin.update_webhook(owner="u", repo="r", webhook_id=1, active=False)
        )
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_delegates_delete_label(self):
        """Should delegate delete_label to issues handler."""
        plugin = GiteaPlugin(config={"url": "https://g.com", "token": "tk"})
        plugin.client.delete_label = AsyncMock(return_value=None)

        result = json.loads(await plugin.delete_label(owner="u", repo="r", label_id=1))
        assert result["success"] is True
