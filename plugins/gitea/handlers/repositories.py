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
