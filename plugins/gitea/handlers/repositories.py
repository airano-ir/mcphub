"""Repository Handler - manages Gitea repositories, branches, tags, and files"""

import json
from typing import Any

from plugins.gitea.client import GiteaClient


def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator"""
    return [
        # === REPOSITORIES ===
        {
            "name": "list_repositories",
            "method_name": "list_repositories",
            "description": "List Gitea repositories for a user/organization or current user. Returns repository list with metadata.",
            "schema": {
                "type": "object",
                "properties": {
                    "owner": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Repository owner username/org (null for current user repos)",
                    },
                    "type": {
                        "type": "string",
                        "description": "Filter by repository type",
                        "enum": ["all", "owner", "collaborative", "member"],
                        "default": "all",
                    },
                    "page": {
                        "type": "integer",
                        "description": "Page number",
                        "default": 1,
                        "minimum": 1,
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Items per page (1-100)",
                        "default": 30,
                        "minimum": 1,
                        "maximum": 100,
                    },
                },
            },
            "scope": "read",
        },
        {
            "name": "get_repository",
            "method_name": "get_repository",
            "description": "Get details of a specific Gitea repository. Returns complete repository information.",
            "schema": {
                "type": "object",
                "properties": {
                    "owner": {
                        "type": "string",
                        "description": "Repository owner username/org",
                        "minLength": 1,
                    },
                    "repo": {"type": "string", "description": "Repository name", "minLength": 1},
                },
                "required": ["owner", "repo"],
            },
            "scope": "read",
        },
        {
            "name": "create_repository",
            "method_name": "create_repository",
            "description": "Create a new Gitea repository. Can create user or organization repository with optional auto-initialization.",
            "schema": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Repository name",
                        "minLength": 1,
                        "maxLength": 100,
                    },
                    "description": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Repository description",
                        "maxLength": 500,
                    },
                    "private": {
                        "type": "boolean",
                        "description": "Make repository private",
                        "default": False,
                    },
                    "auto_init": {
                        "type": "boolean",
                        "description": "Initialize with README",
                        "default": False,
                    },
                    "gitignores": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Gitignore template name",
                    },
                    "license": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "License template name",
                    },
                    "readme": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Readme template",
                    },
                    "default_branch": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Default branch name",
                    },
                    "org": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Create under organization (null for user repo)",
                    },
                },
                "required": ["name"],
            },
            "scope": "write",
        },
        {
            "name": "update_repository",
            "method_name": "update_repository",
            "description": "Update Gitea repository settings like name, description, visibility, and features.",
            "schema": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "Repository owner", "minLength": 1},
                    "repo": {"type": "string", "description": "Repository name", "minLength": 1},
                    "name": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "New repository name",
                    },
                    "description": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Repository description",
                    },
                    "website": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Repository website",
                    },
                    "private": {
                        "anyOf": [{"type": "boolean"}, {"type": "null"}],
                        "description": "Make repository private",
                    },
                    "archived": {
                        "anyOf": [{"type": "boolean"}, {"type": "null"}],
                        "description": "Archive repository",
                    },
                    "has_issues": {
                        "anyOf": [{"type": "boolean"}, {"type": "null"}],
                        "description": "Enable issues",
                    },
                    "has_wiki": {
                        "anyOf": [{"type": "boolean"}, {"type": "null"}],
                        "description": "Enable wiki",
                    },
                    "default_branch": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Default branch",
                    },
                    "allow_merge_commits": {
                        "anyOf": [{"type": "boolean"}, {"type": "null"}],
                        "description": "Allow merge commits",
                    },
                    "allow_rebase": {
                        "anyOf": [{"type": "boolean"}, {"type": "null"}],
                        "description": "Allow rebase",
                    },
                    "allow_squash_merge": {
                        "anyOf": [{"type": "boolean"}, {"type": "null"}],
                        "description": "Allow squash merge",
                    },
                },
                "required": ["owner", "repo"],
            },
            "scope": "write",
        },
        {
            "name": "delete_repository",
            "method_name": "delete_repository",
            "description": "Delete a Gitea repository permanently. This action cannot be undone!",
            "schema": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "Repository owner", "minLength": 1},
                    "repo": {"type": "string", "description": "Repository name", "minLength": 1},
                },
                "required": ["owner", "repo"],
            },
            "scope": "admin",
        },
        # === BRANCHES ===
        {
            "name": "list_branches",
            "method_name": "list_branches",
            "description": "List all branches in a Gitea repository with commit information and protection status.",
            "schema": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "Repository owner", "minLength": 1},
                    "repo": {"type": "string", "description": "Repository name", "minLength": 1},
                    "page": {
                        "type": "integer",
                        "description": "Page number",
                        "default": 1,
                        "minimum": 1,
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Items per page (1-100)",
                        "default": 30,
                        "minimum": 1,
                        "maximum": 100,
                    },
                },
                "required": ["owner", "repo"],
            },
            "scope": "read",
        },
        {
            "name": "get_branch",
            "method_name": "get_branch",
            "description": "Get details of a specific branch including latest commit and protection settings.",
            "schema": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "Repository owner", "minLength": 1},
                    "repo": {"type": "string", "description": "Repository name", "minLength": 1},
                    "branch": {"type": "string", "description": "Branch name", "minLength": 1},
                },
                "required": ["owner", "repo", "branch"],
            },
            "scope": "read",
        },
        {
            "name": "create_branch",
            "method_name": "create_branch",
            "description": "Create a new branch in a Gitea repository from existing branch or commit.",
            "schema": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "Repository owner", "minLength": 1},
                    "repo": {"type": "string", "description": "Repository name", "minLength": 1},
                    "new_branch_name": {
                        "type": "string",
                        "description": "New branch name",
                        "minLength": 1,
                    },
                    "old_branch_name": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Source branch (default: default branch)",
                    },
                    "old_ref_name": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Source commit SHA or ref",
                    },
                },
                "required": ["owner", "repo", "new_branch_name"],
            },
            "scope": "write",
        },
        {
            "name": "delete_branch",
            "method_name": "delete_branch",
            "description": "Delete a branch from a Gitea repository. Cannot delete default branch.",
            "schema": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "Repository owner", "minLength": 1},
                    "repo": {"type": "string", "description": "Repository name", "minLength": 1},
                    "branch": {
                        "type": "string",
                        "description": "Branch name to delete",
                        "minLength": 1,
                    },
                },
                "required": ["owner", "repo", "branch"],
            },
            "scope": "write",
        },
        # === TAGS ===
        {
            "name": "list_tags",
            "method_name": "list_tags",
            "description": "List all tags in a Gitea repository with commit information.",
            "schema": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "Repository owner", "minLength": 1},
                    "repo": {"type": "string", "description": "Repository name", "minLength": 1},
                    "page": {
                        "type": "integer",
                        "description": "Page number",
                        "default": 1,
                        "minimum": 1,
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Items per page (1-100)",
                        "default": 30,
                        "minimum": 1,
                        "maximum": 100,
                    },
                },
                "required": ["owner", "repo"],
            },
            "scope": "read",
        },
        {
            "name": "create_tag",
            "method_name": "create_tag",
            "description": "Create a new tag in a Gitea repository at specific commit.",
            "schema": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "Repository owner", "minLength": 1},
                    "repo": {"type": "string", "description": "Repository name", "minLength": 1},
                    "tag_name": {"type": "string", "description": "Tag name", "minLength": 1},
                    "message": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Tag message (annotated tag)",
                    },
                    "target": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Target commit SHA (default: latest)",
                    },
                },
                "required": ["owner", "repo", "tag_name"],
            },
            "scope": "write",
        },
        {
            "name": "delete_tag",
            "method_name": "delete_tag",
            "description": "Delete a tag from a Gitea repository.",
            "schema": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "Repository owner", "minLength": 1},
                    "repo": {"type": "string", "description": "Repository name", "minLength": 1},
                    "tag": {"type": "string", "description": "Tag name to delete", "minLength": 1},
                },
                "required": ["owner", "repo", "tag"],
            },
            "scope": "write",
        },
        # === FILES ===
        {
            "name": "get_file",
            "method_name": "get_file",
            "description": "Get file contents from a Gitea repository. Returns file content (Base64 encoded) and metadata.",
            "schema": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "Repository owner", "minLength": 1},
                    "repo": {"type": "string", "description": "Repository name", "minLength": 1},
                    "path": {
                        "type": "string",
                        "description": "File path in repository",
                        "minLength": 1,
                    },
                    "ref": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Branch/tag/commit (default: default branch)",
                    },
                },
                "required": ["owner", "repo", "path"],
            },
            "scope": "read",
        },
        {
            "name": "create_file",
            "method_name": "create_file",
            "description": "Create a new file in a Gitea repository with commit message.",
            "schema": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "Repository owner", "minLength": 1},
                    "repo": {"type": "string", "description": "Repository name", "minLength": 1},
                    "path": {
                        "type": "string",
                        "description": "File path to create",
                        "minLength": 1,
                    },
                    "content": {
                        "type": "string",
                        "description": "File content (will be Base64 encoded automatically unless content_is_base64=true)",
                    },
                    "message": {"type": "string", "description": "Commit message", "minLength": 1},
                    "branch": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Target branch (default: default branch)",
                    },
                    "new_branch": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Create new branch for this commit",
                    },
                    "author_name": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Author name",
                    },
                    "author_email": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Author email",
                    },
                    "content_is_base64": {
                        "type": "boolean",
                        "description": "Set to true if content is already Base64 encoded (skip automatic encoding)",
                        "default": False,
                    },
                },
                "required": ["owner", "repo", "path", "content", "message"],
            },
            "scope": "write",
        },
        {
            "name": "update_file",
            "method_name": "update_file",
            "description": "Update an existing file in a Gitea repository. Requires current file SHA for conflict detection.",
            "schema": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "Repository owner", "minLength": 1},
                    "repo": {"type": "string", "description": "Repository name", "minLength": 1},
                    "path": {
                        "type": "string",
                        "description": "File path to update",
                        "minLength": 1,
                    },
                    "content": {
                        "type": "string",
                        "description": "New file content (will be Base64 encoded automatically)",
                    },
                    "sha": {
                        "type": "string",
                        "description": "Current file SHA (for conflict detection)",
                        "minLength": 1,
                    },
                    "message": {"type": "string", "description": "Commit message", "minLength": 1},
                    "branch": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Target branch (default: default branch)",
                    },
                    "new_branch": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Create new branch for this commit",
                    },
                    "content_is_base64": {
                        "type": "boolean",
                        "description": "Set to true if content is already Base64 encoded (skip automatic encoding)",
                        "default": False,
                    },
                },
                "required": ["owner", "repo", "path", "content", "sha", "message"],
            },
            "scope": "write",
        },
        {
            "name": "delete_file",
            "method_name": "delete_file",
            "description": "Delete a file from a Gitea repository. Requires current file SHA for conflict detection.",
            "schema": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "Repository owner", "minLength": 1},
                    "repo": {"type": "string", "description": "Repository name", "minLength": 1},
                    "path": {
                        "type": "string",
                        "description": "File path to delete",
                        "minLength": 1,
                    },
                    "sha": {
                        "type": "string",
                        "description": "Current file SHA (for conflict detection)",
                        "minLength": 1,
                    },
                    "message": {"type": "string", "description": "Commit message", "minLength": 1},
                    "branch": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Target branch (default: default branch)",
                    },
                },
                "required": ["owner", "repo", "path", "sha", "message"],
            },
            "scope": "write",
        },
        # === F.17 ergonomics: batch files, tree, search, compare, releases, fork ===
        {
            "name": "create_files",
            "method_name": "create_files",
            "description": (
                "Create or update multiple files in a single commit. Uses Gitea's "
                "``/repos/{owner}/{repo}/contents`` batch endpoint. Per-file operations: "
                "``create`` | ``update`` | ``delete``. For create/update, pass raw UTF-8 "
                "``content`` (default) or a base64 string with ``content_is_base64=true`` "
                "per file. Delete requires each file's current ``sha``."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "minLength": 1},
                    "repo": {"type": "string", "minLength": 1},
                    "message": {
                        "type": "string",
                        "description": "Single commit message for the whole batch.",
                        "minLength": 1,
                    },
                    "branch": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                    "new_branch": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "If set, commit on a new branch created from ``branch``.",
                    },
                    "files": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 100,
                        "items": {
                            "type": "object",
                            "properties": {
                                "operation": {
                                    "type": "string",
                                    "enum": ["create", "update", "delete"],
                                },
                                "path": {"type": "string", "minLength": 1},
                                "content": {
                                    "anyOf": [{"type": "string"}, {"type": "null"}],
                                    "description": "Required for create/update.",
                                },
                                "sha": {
                                    "anyOf": [{"type": "string"}, {"type": "null"}],
                                    "description": "Required for update/delete.",
                                },
                                "content_is_base64": {"type": "boolean", "default": False},
                            },
                            "required": ["operation", "path"],
                        },
                    },
                },
                "required": ["owner", "repo", "files", "message"],
            },
            "scope": "write",
        },
        {
            "name": "get_tree",
            "method_name": "get_tree",
            "description": (
                "List the file tree of a Gitea repository. ``sha`` may be a branch "
                "name, tag, or commit (default: HEAD). ``recursive=true`` returns "
                "the entire tree in one payload. Use this instead of issuing many "
                "``get_file`` calls when you don't know the paths ahead of time."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "minLength": 1},
                    "repo": {"type": "string", "minLength": 1},
                    "sha": {"type": "string", "default": "HEAD"},
                    "recursive": {"type": "boolean", "default": False},
                    "page": {"type": "integer", "minimum": 1, "default": 1},
                    "per_page": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100,
                        "default": 100,
                    },
                },
                "required": ["owner", "repo"],
            },
            "scope": "read",
        },
        {
            "name": "search_code",
            "method_name": "search_code",
            "description": (
                "Search code inside Gitea. When ``owner`` and ``repo`` are set, the "
                "search scopes to that repository; otherwise it's an instance-wide "
                "code search. Returns Gitea's raw ``{ok, data: [...]}`` shape."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "minLength": 1},
                    "owner": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                    "repo": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                    "page": {"type": "integer", "minimum": 1, "default": 1},
                    "per_page": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 50,
                        "default": 30,
                    },
                },
                "required": ["keyword"],
            },
            "scope": "read",
        },
        {
            "name": "compare",
            "method_name": "compare",
            "description": (
                "Compare two commits / branches / tags in a Gitea repository. Returns "
                "commits + file diffs between ``base`` and ``head`` (the Gitea "
                "``compare`` endpoint)."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "minLength": 1},
                    "repo": {"type": "string", "minLength": 1},
                    "base": {"type": "string", "minLength": 1},
                    "head": {"type": "string", "minLength": 1},
                },
                "required": ["owner", "repo", "base", "head"],
            },
            "scope": "read",
        },
        {
            "name": "list_releases",
            "method_name": "list_releases",
            "description": "List releases of a Gitea repository (paginated).",
            "schema": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "minLength": 1},
                    "repo": {"type": "string", "minLength": 1},
                    "page": {"type": "integer", "minimum": 1, "default": 1},
                    "per_page": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 50,
                        "default": 30,
                    },
                },
                "required": ["owner", "repo"],
            },
            "scope": "read",
        },
        {
            "name": "create_release",
            "method_name": "create_release",
            "description": (
                "Create a release (tag + release metadata) on a Gitea repository. "
                "Set ``draft`` to hide it from users until published."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "minLength": 1},
                    "repo": {"type": "string", "minLength": 1},
                    "tag_name": {"type": "string", "minLength": 1},
                    "name": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                    "body": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                    "target_commitish": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Branch or commit to tag (default: default branch).",
                    },
                    "draft": {"type": "boolean", "default": False},
                    "prerelease": {"type": "boolean", "default": False},
                },
                "required": ["owner", "repo", "tag_name"],
            },
            "scope": "write",
        },
        {
            "name": "fork_repository",
            "method_name": "fork_repository",
            "description": (
                "Fork a Gitea repository. Without ``organization``, forks under the "
                "calling user. ``name`` optionally renames the fork."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "minLength": 1},
                    "repo": {"type": "string", "minLength": 1},
                    "organization": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                    "name": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                },
                "required": ["owner", "repo"],
            },
            "scope": "write",
        },
    ]


async def list_repositories(
    client: GiteaClient, owner: str | None = None, type: str = "all", page: int = 1, limit: int = 30
) -> str:
    """List Gitea repositories"""
    repos = await client.list_repositories(owner=owner, page=page, limit=limit)
    result = {"success": True, "count": len(repos), "repositories": repos}
    return json.dumps(result, indent=2)


async def get_repository(client: GiteaClient, owner: str, repo: str) -> str:
    """Get repository details"""
    repository = await client.get_repository(owner, repo)
    result = {"success": True, "repository": repository}
    return json.dumps(result, indent=2)


async def create_repository(
    client: GiteaClient,
    name: str,
    description: str | None = None,
    private: bool = False,
    auto_init: bool = False,
    gitignores: str | None = None,
    license: str | None = None,
    readme: str | None = None,
    default_branch: str | None = None,
    org: str | None = None,
) -> str:
    """Create a new repository"""
    data = {
        "name": name,
        "description": description,
        "private": private,
        "auto_init": auto_init,
        "gitignores": gitignores,
        "license": license,
        "readme": readme,
        "default_branch": default_branch,
    }
    repository = await client.create_repository(data, org=org)
    result = {
        "success": True,
        "message": f"Repository '{name}' created successfully",
        "repository": repository,
    }
    return json.dumps(result, indent=2)


async def update_repository(client: GiteaClient, owner: str, repo: str, **kwargs) -> str:
    """Update repository settings"""
    # Build update data from kwargs
    data = {k: v for k, v in kwargs.items() if v is not None and k not in ["owner", "repo"]}

    repository = await client.update_repository(owner, repo, data)
    result = {
        "success": True,
        "message": f"Repository '{owner}/{repo}' updated successfully",
        "repository": repository,
    }
    return json.dumps(result, indent=2)


async def delete_repository(client: GiteaClient, owner: str, repo: str) -> str:
    """Delete a repository"""
    await client.delete_repository(owner, repo)
    result = {"success": True, "message": f"Repository '{owner}/{repo}' deleted successfully"}
    return json.dumps(result, indent=2)


# Branch operations
async def list_branches(
    client: GiteaClient, owner: str, repo: str, page: int = 1, limit: int = 30
) -> str:
    """List repository branches"""
    branches = await client.list_branches(owner, repo, page=page, limit=limit)
    result = {"success": True, "count": len(branches), "branches": branches}
    return json.dumps(result, indent=2)


async def get_branch(client: GiteaClient, owner: str, repo: str, branch: str) -> str:
    """Get branch details"""
    branch_info = await client.get_branch(owner, repo, branch)
    result = {"success": True, "branch": branch_info}
    return json.dumps(result, indent=2)


async def create_branch(
    client: GiteaClient,
    owner: str,
    repo: str,
    new_branch_name: str,
    old_branch_name: str | None = None,
    old_ref_name: str | None = None,
) -> str:
    """Create a new branch"""
    data = {
        "new_branch_name": new_branch_name,
        "old_branch_name": old_branch_name,
        "old_ref_name": old_ref_name,
    }
    branch = await client.create_branch(owner, repo, data)
    result = {
        "success": True,
        "message": f"Branch '{new_branch_name}' created successfully",
        "branch": branch,
    }
    return json.dumps(result, indent=2)


async def delete_branch(client: GiteaClient, owner: str, repo: str, branch: str) -> str:
    """Delete a branch"""
    await client.delete_branch(owner, repo, branch)
    result = {"success": True, "message": f"Branch '{branch}' deleted successfully"}
    return json.dumps(result, indent=2)


# Tag operations
async def list_tags(
    client: GiteaClient, owner: str, repo: str, page: int = 1, limit: int = 30
) -> str:
    """List repository tags"""
    tags = await client.list_tags(owner, repo, page=page, limit=limit)
    result = {"success": True, "count": len(tags), "tags": tags}
    return json.dumps(result, indent=2)


async def create_tag(
    client: GiteaClient,
    owner: str,
    repo: str,
    tag_name: str,
    message: str | None = None,
    target: str | None = None,
) -> str:
    """Create a new tag"""
    data = {"tag_name": tag_name, "message": message, "target": target}
    tag = await client.create_tag(owner, repo, data)
    result = {"success": True, "message": f"Tag '{tag_name}' created successfully", "tag": tag}
    return json.dumps(result, indent=2)


async def delete_tag(client: GiteaClient, owner: str, repo: str, tag: str) -> str:
    """Delete a tag"""
    await client.delete_tag(owner, repo, tag)
    result = {"success": True, "message": f"Tag '{tag}' deleted successfully"}
    return json.dumps(result, indent=2)


# File operations
async def get_file(
    client: GiteaClient, owner: str, repo: str, path: str, ref: str | None = None
) -> str:
    """Get file contents"""
    file_data = await client.get_file(owner, repo, path, ref=ref)
    result = {"success": True, "file": file_data}
    return json.dumps(result, indent=2)


async def create_file(
    client: GiteaClient,
    owner: str,
    repo: str,
    path: str,
    content: str,
    message: str,
    branch: str | None = None,
    new_branch: str | None = None,
    author_name: str | None = None,
    author_email: str | None = None,
    content_is_base64: bool = False,
) -> str:
    """Create a new file"""
    data = {
        "content": content,
        "message": message,
        "branch": branch,
        "new_branch": new_branch,
        "content_is_base64": content_is_base64,
        "author": {},
    }

    if author_name:
        data["author"]["name"] = author_name
    if author_email:
        data["author"]["email"] = author_email

    file_result = await client.create_file(owner, repo, path, data)
    result = {
        "success": True,
        "message": f"File '{path}' created successfully",
        "file": file_result,
    }
    return json.dumps(result, indent=2)


async def update_file(
    client: GiteaClient,
    owner: str,
    repo: str,
    path: str,
    content: str,
    sha: str,
    message: str,
    branch: str | None = None,
    new_branch: str | None = None,
    content_is_base64: bool = False,
) -> str:
    """Update an existing file"""
    data = {
        "content": content,
        "sha": sha,
        "message": message,
        "branch": branch,
        "new_branch": new_branch,
        "content_is_base64": content_is_base64,
    }

    file_result = await client.update_file(owner, repo, path, data)
    result = {
        "success": True,
        "message": f"File '{path}' updated successfully",
        "file": file_result,
    }
    return json.dumps(result, indent=2)


async def delete_file(
    client: GiteaClient,
    owner: str,
    repo: str,
    path: str,
    sha: str,
    message: str,
    branch: str | None = None,
) -> str:
    """Delete a file from repository"""
    await client.delete_file(owner, repo, path, sha, message, branch)
    result = {"success": True, "message": f"File '{path}' deleted successfully"}
    return json.dumps(result, indent=2)


# ---------------------------------------------------------------------------
# F.17 ergonomics: batch files, tree, search, compare, releases, fork
# ---------------------------------------------------------------------------


async def create_files(
    client: GiteaClient,
    owner: str,
    repo: str,
    files: list[dict[str, Any]],
    message: str,
    branch: str | None = None,
    new_branch: str | None = None,
) -> str:
    """Apply a batch of create / update / delete file operations in a single commit.

    Each entry in ``files`` is normalised so Gitea's batch endpoint
    receives base64-encoded content with the ``content_is_base64`` flag
    stripped (the server expects base64). Validation:

    * ``operation`` is ``create`` / ``update`` / ``delete``.
    * ``path`` required on every entry.
    * ``content`` required on create / update.
    * ``sha`` required on update / delete (current file SHA).
    """
    prepared: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for idx, f in enumerate(files or []):
        op = (f.get("operation") or "").strip().lower()
        path = f.get("path")
        if op not in {"create", "update", "delete"}:
            errors.append({"index": idx, "path": path, "error": f"invalid_operation:{op!r}"})
            continue
        if not path:
            errors.append({"index": idx, "error": "missing_path"})
            continue
        if op in {"update", "delete"} and not f.get("sha"):
            errors.append({"index": idx, "path": path, "error": f"missing_sha_for_{op}"})
            continue

        entry: dict[str, Any] = {"operation": op, "path": path}
        if op in {"create", "update"}:
            content = f.get("content")
            if content is None:
                errors.append({"index": idx, "path": path, "error": "missing_content"})
                continue
            try:
                entry["content"] = client._normalise_file_content(
                    content, bool(f.get("content_is_base64", False))
                )
            except ValueError as exc:
                errors.append({"index": idx, "path": path, "error": str(exc)})
                continue
        if f.get("sha"):
            entry["sha"] = f["sha"]
        if f.get("from_path"):  # Gitea also supports rename via from_path
            entry["from_path"] = f["from_path"]
        prepared.append(entry)

    if errors:
        return json.dumps(
            {
                "success": False,
                "error": "validation_failed",
                "errors": errors,
                "total": len(files or []),
                "prepared": len(prepared),
            },
            indent=2,
        )

    payload: dict[str, Any] = {"message": message, "files": prepared}
    if branch:
        payload["branch"] = branch
    if new_branch:
        payload["new_branch"] = new_branch

    result = await client.change_files(owner, repo, payload)
    return json.dumps(
        {
            "success": True,
            "message": f"Batched {len(prepared)} file operation(s) into one commit",
            "result": result,
        },
        indent=2,
    )


async def get_tree(
    client: GiteaClient,
    owner: str,
    repo: str,
    sha: str = "HEAD",
    recursive: bool = False,
    page: int = 1,
    per_page: int = 100,
) -> str:
    tree = await client.get_tree(
        owner, repo, sha, recursive=recursive, page=page, per_page=per_page
    )
    return json.dumps({"success": True, "tree": tree}, indent=2)


async def search_code(
    client: GiteaClient,
    keyword: str,
    owner: str | None = None,
    repo: str | None = None,
    page: int = 1,
    per_page: int = 30,
) -> str:
    result = await client.search_code(
        keyword=keyword, owner=owner, repo=repo, page=page, per_page=per_page
    )
    return json.dumps({"success": True, "result": result}, indent=2)


async def compare(
    client: GiteaClient,
    owner: str,
    repo: str,
    base: str,
    head: str,
) -> str:
    diff = await client.compare(owner, repo, base, head)
    return json.dumps({"success": True, "compare": diff}, indent=2)


async def list_releases(
    client: GiteaClient,
    owner: str,
    repo: str,
    page: int = 1,
    per_page: int = 30,
) -> str:
    releases = await client.list_releases(owner, repo, page=page, per_page=per_page)
    return json.dumps({"success": True, "releases": releases}, indent=2)


async def create_release(
    client: GiteaClient,
    owner: str,
    repo: str,
    tag_name: str,
    name: str | None = None,
    body: str | None = None,
    target_commitish: str | None = None,
    draft: bool = False,
    prerelease: bool = False,
) -> str:
    data: dict[str, Any] = {
        "tag_name": tag_name,
        "draft": draft,
        "prerelease": prerelease,
    }
    if name is not None:
        data["name"] = name
    if body is not None:
        data["body"] = body
    if target_commitish is not None:
        data["target_commitish"] = target_commitish
    release = await client.create_release(owner, repo, data)
    return json.dumps({"success": True, "release": release}, indent=2)


async def fork_repository(
    client: GiteaClient,
    owner: str,
    repo: str,
    organization: str | None = None,
    name: str | None = None,
) -> str:
    fork = await client.fork_repository(owner, repo, organization=organization, name=name)
    return json.dumps({"success": True, "fork": fork}, indent=2)
