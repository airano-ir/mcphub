# 🦊 Gitea Plugin Guide

**Complete guide for Gitea integration in MCP Hub**

Version: 1.0.0 (Phase C)
Last Updated: 2025-11-19

---

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Installation](#installation)
- [Configuration](#configuration)
- [Tool Categories](#tool-categories)
- [Usage Examples](#usage-examples)
- [OAuth Integration](#oauth-integration)
- [API Reference](#api-reference)
- [Troubleshooting](#troubleshooting)
- [Best Practices](#best-practices)

---

## 🎯 Overview

The Gitea Plugin provides comprehensive Git repository management through Gitea's REST API. It enables AI assistants (like Claude) to manage repositories, issues, pull requests, and more directly from ChatGPT or other MCP-enabled clients.

### What is Gitea?

Gitea is a lightweight, self-hosted Git service similar to GitHub/GitLab. It provides:
- Git repository hosting
- Issue tracking
- Pull requests
- Code review
- Webhooks
- Organizations and teams

### Why This Plugin?

✅ **Git Workflow Automation** - Manage repositories from ChatGPT
✅ **CI/CD Integration** - Trigger deployments with PR merges
✅ **Issue Management** - AI-assisted issue triaging and responses
✅ **Code Review** - Automated PR reviews and suggestions
✅ **OAuth Support** - Seamless ChatGPT integration
✅ **Multi-Site** - Manage multiple Gitea instances

---

## ✨ Features

### 📦 Repository Management (15 Tools)

- **CRUD Operations**: Create, read, update, delete repositories
- **Branch Management**: List, create, delete branches
- **Tag Management**: Create and manage tags
- **File Operations**: Read, create, update files in repository

### 🐛 Issue Tracking (12 Tools)

- **Issue Management**: Create, update, close, reopen issues
- **Labels**: Create and manage issue labels
- **Milestones**: Track project milestones
- **Comments**: Add comments to issues

### 🔀 Pull Requests (15 Tools)

- **PR Operations**: Create, update, merge pull requests
- **Code Review**: Review PRs, request changes, approve
- **PR Details**: View commits, files, diff
- **Reviewers**: Request reviewers for PRs

### 👥 User & Organization (8 Tools)

- **User Management**: Get user info, list repositories
- **Organizations**: Manage organizations and teams
- **Teams**: List team members
- **Search**: Search for users

### 🔗 Webhooks (5 Tools)

- **Webhook Setup**: Create, list, delete webhooks
- **Event Configuration**: Configure webhook events
- **Testing**: Test webhook delivery

**Total: 55 Tools**

---

## 📦 Installation

### Prerequisites

- Gitea instance (self-hosted or managed)
- Gitea personal access token OR OAuth setup
- MCP Hub installed

### 1. Enable Gitea Plugin

The Gitea plugin is built-in. No additional installation needed.

### 2. Configure Environment

Edit `.env` file:

```bash
# Site 1 - Token Authentication
GITEA_SITE1_URL=https://gitea.mcphub.dev
GITEA_SITE1_TOKEN=your_personal_access_token_here
GITEA_SITE1_ALIAS=mygitea

# Site 2 - OAuth Authentication (for ChatGPT)
GITEA_SITE2_URL=https://git.company.com
GITEA_SITE2_OAUTH_ENABLED=true
GITEA_SITE2_ALIAS=workgit
```

### 3. Generate Personal Access Token

#### In Gitea:

1. Log in to your Gitea instance
2. Go to **Settings → Applications**
3. Click **Generate New Token**
4. Enter token name: `MCP Server`
5. Select permissions:
   - ✅ **repo** (all) - Full repository access
   - ✅ **write:org** - Manage organizations
   - ✅ **read:user** - Read user information
   - ✅ **write:issue** - Create/edit issues and PRs
6. Click **Generate Token**
7. **Copy the token** (shown only once!)
8. Add to `.env` as `GITEA_SITE1_TOKEN`

### 4. Restart Server

```bash
# If running locally
python server.py

# If running in Docker
docker-compose restart

# If deployed in Coolify
# Restart the service from Coolify dashboard
```

### 5. Verify Installation

Check server logs for:

```
✅ Gitea plugin loaded: gitea_site1 (mygitea)
```

Or use health check tool:

```
check_project_health(project_id="gitea_site1")
```

---

## ⚙️ Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GITEA_SITEX_URL` | ✅ Yes | - | Gitea instance URL |
| `GITEA_SITEX_TOKEN` | ⚠️ Conditional | - | Personal access token (required if not using OAuth) |
| `GITEA_SITEX_ALIAS` | ❌ No | - | Friendly site name |
| `GITEA_SITEX_OAUTH_ENABLED` | ❌ No | `false` | Enable OAuth instead of token |

### Multiple Sites

You can configure unlimited Gitea instances:

```bash
# Personal Gitea
GITEA_SITE1_URL=https://gitea.mcphub.dev
GITEA_SITE1_TOKEN=token1
GITEA_SITE1_ALIAS=personal

# Work Gitea
GITEA_SITE2_URL=https://git.company.com
GITEA_SITE2_TOKEN=token2
GITEA_SITE2_ALIAS=work

# Client Gitea
GITEA_SITE3_URL=https://git.client.com
GITEA_SITE3_TOKEN=token3
GITEA_SITE3_ALIAS=client
```

### OAuth vs Token Authentication

#### Token Authentication (Recommended for Scripts)

✅ **Pros:**
- Simple setup
- No user interaction needed
- Suitable for automation

❌ **Cons:**
- Tokens can expire
- Manual renewal needed
- Less secure if leaked

#### OAuth Authentication (Recommended for ChatGPT)

✅ **Pros:**
- User-approved access
- More secure
- Automatic token refresh
- Better for third-party apps

❌ **Cons:**
- Requires OAuth setup
- More complex configuration

---

## 🧰 Tool Categories

### 1. Repository Tools

#### List Repositories
```
gitea_list_repositories(site, owner?, type?, page?, limit?)
```

Example:
```
# List all my repositories
gitea_list_repositories(site="mygitea")

# List user's repositories
gitea_list_repositories(site="mygitea", owner="username")
```

#### Create Repository
```
gitea_create_repository(site, name, description?, private?, auto_init?)
```

Example:
```
gitea_create_repository(
    site="mygitea",
    name="awesome-project",
    description="My awesome project",
    private=False,
    auto_init=True
)
```

#### Manage Branches
```
gitea_list_branches(site, owner, repo)
gitea_create_branch(site, owner, repo, new_branch_name, old_branch_name?)
gitea_delete_branch(site, owner, repo, branch)
```

#### File Operations
```
gitea_get_file(site, owner, repo, path, ref?)
gitea_create_file(site, owner, repo, path, content, message)
gitea_update_file(site, owner, repo, path, content, sha, message)
```

#### Release Assets and Large Binary Uploads
```
gitea_upload_release_asset(site, owner, repo, release_id, filename, content_b64)
gitea_upload_start(site, kind="release_asset", owner, repo, release_id, filename, total_bytes, sha256?)
gitea_upload_chunk(site, session_id, index, data_b64, chunk_sha256?)
gitea_upload_status(site, session_id)
gitea_upload_abort(site, session_id)
gitea_upload_finish(site, session_id)
```

Use `gitea_create_file`, `gitea_update_file`, and `gitea_create_files` for small text or structured repository edits. Use `gitea_upload_release_asset` only for small base64 assets.

For generated artifacts, zips, images, and other large files, start a binary session with `gitea_upload_start`. On per-user MCP endpoints the response includes:

```json
{
  "handoff": "http_binary_put",
  "upload": {
    "method": "PUT",
    "url": "/u/{user_id}/{alias}/gitea-upload/{session_id}",
    "auth": "Use the same Authorization: Bearer token as this MCP endpoint."
  },
  "finish_tool": "gitea_upload_finish"
}
```

Upload bytes with the same Bearer token:

```bash
curl -X PUT   -H "Authorization: Bearer $MCPHUB_TOKEN"   --data-binary @artifact.zip   "https://your-mcphub.example.com/u/{user_id}/{alias}/gitea-upload/{session_id}"
```

When `ready_to_finish` is true, call `gitea_upload_finish(session_id)`. The finish step verifies the optional full-payload `sha256` and forwards the original bytes to Gitea as a release asset multipart upload.

`repo_file` binary handoff is intentionally not enabled yet. It needs explicit create/update overwrite semantics and current-file `sha` handling before it is safe to expose.

### 2. Issue Tools

#### Manage Issues
```
gitea_list_issues(site, owner, repo, state?, labels?, q?)
gitea_create_issue(site, owner, repo, title, body?, labels?)
gitea_update_issue(site, owner, repo, issue_number, ...)
gitea_close_issue(site, owner, repo, issue_number)
```

#### Labels & Milestones
```
gitea_list_labels(site, owner, repo)
gitea_create_label(site, owner, repo, name, color, description?)
gitea_list_milestones(site, owner, repo, state?)
gitea_create_milestone(site, owner, repo, title, due_on?)
```

### 3. Pull Request Tools

#### Manage PRs
```
gitea_create_pull_request(site, owner, repo, title, head, base, body?)
gitea_merge_pull_request(site, owner, repo, pr_number, method?)
gitea_list_pr_commits(site, owner, repo, pr_number)
gitea_list_pr_files(site, owner, repo, pr_number)
```

#### Code Review
```
gitea_create_pr_review(site, owner, repo, pr_number, event, body?)
gitea_request_pr_reviewers(site, owner, repo, pr_number, reviewers)
```

### 4. User & Organization Tools

```
gitea_get_user(site, username)
gitea_list_user_repos(site, username)
gitea_list_organizations(site)
gitea_list_org_teams(site, org)
```

### 5. Webhook Tools

```
gitea_list_webhooks(site, owner, repo)
gitea_create_webhook(site, owner, repo, url, events)
gitea_test_webhook(site, owner, repo, webhook_id)
```

---

## 💡 Usage Examples

### Example 1: Create a Repository

```
# Create a new repository with README
gitea_create_repository(
    site="mygitea",
    name="my-new-project",
    description="A new project for testing",
    private=False,
    auto_init=True,
    license="MIT"
)
```

### Example 2: Create an Issue

```
# Create an issue
gitea_create_issue(
    site="mygitea",
    owner="myuser",
    repo="my-project",
    title="Bug: Login not working",
    body="## Description\n\nUsers cannot log in after the latest update.\n\n## Steps to Reproduce\n1. Go to login page\n2. Enter credentials\n3. Click login\n\n## Expected\nShould log in successfully\n\n## Actual\nError message displayed",
    labels=[1, 3]  # bug, high-priority
)
```

### Example 3: Create a Pull Request

```
# Create feature branch
gitea_create_branch(
    site="mygitea",
    owner="myuser",
    repo="my-project",
    new_branch_name="feature/user-authentication",
    old_branch_name="main"
)

# Make changes to files
gitea_update_file(
    site="mygitea",
    owner="myuser",
    repo="my-project",
    path="src/auth.js",
    content="// Updated authentication code\n...",
    sha="abc123",
    message="Add OAuth support",
    branch="feature/user-authentication"
)

# Create pull request
gitea_create_pull_request(
    site="mygitea",
    owner="myuser",
    repo="my-project",
    title="Add OAuth Authentication",
    head="feature/user-authentication",
    base="main",
    body="This PR adds OAuth support for Google and GitHub authentication."
)
```

### Example 4: Review and Merge PR

```
# List open PRs
gitea_list_pull_requests(
    site="mygitea",
    owner="myuser",
    repo="my-project",
    state="open"
)

# Review the PR
gitea_create_pr_review(
    site="mygitea",
    owner="myuser",
    repo="my-project",
    pr_number=5,
    event="APPROVED",
    body="LGTM! Great work on the OAuth implementation."
)

# Merge the PR
gitea_merge_pull_request(
    site="mygitea",
    owner="myuser",
    repo="my-project",
    pr_number=5,
    method="squash",
    delete_branch_after_merge=True
)
```

### Example 5: Setup Webhook for CI/CD

```
# Create webhook for Coolify deployment
gitea_create_webhook(
    site="mygitea",
    owner="myuser",
    repo="my-project",
    url="https://coolify.example.com/webhooks/deploy",
    events=["push", "pull_request"],
    content_type="json",
    secret="webhook_secret_here"
)
```

---

## 🔐 OAuth Integration

### Setup OAuth for ChatGPT

#### 1. Configure Server

In `.env`:
```bash
# Enable OAuth for Gitea site
GITEA_SITE1_URL=https://gitea.mcphub.dev
GITEA_SITE1_OAUTH_ENABLED=true
GITEA_SITE1_ALIAS=mygitea

# OAuth settings (if not already set)
OAUTH_JWT_SECRET_KEY=your_jwt_secret_here
OAUTH_AUTH_MODE=trusted_domains
OAUTH_TRUSTED_DOMAINS=chatgpt.com,chat.openai.com,openai.com
```

#### 2. Create GPT Action

In ChatGPT GPTs:

1. Go to **Configure → Actions**
2. Click **Create new action**
3. Import OpenAPI schema from: `https://your-server.com/.well-known/oauth-authorization-server`
4. Set OAuth:
   - **Client ID**: Auto-registered via dynamic registration
   - **Authorization URL**: `https://your-server.com/oauth/authorize`
   - **Token URL**: `https://your-server.com/oauth/token`

#### 3. Use from ChatGPT

```
User: "Create a new repository called 'test-repo' in my Gitea"

Claude: Sure! I'll create a new repository.
[Calls gitea_create_repository with OAuth token]
```

### API Key with OAuth

For additional security, you can require API Keys even with OAuth:

```bash
OAUTH_AUTH_MODE=required
```

Then users must provide API Key in authorization URL:
```
/oauth/authorize?client_id=xxx&...&api_key=cmp_your_key_here
```

---

## 📚 API Reference

### Tool Naming Convention

All Gitea tools follow this pattern:
```
gitea_<action>_<resource>(site, ...params)
```

Examples:
- `gitea_create_repository`
- `gitea_list_issues`
- `gitea_merge_pull_request`

### Common Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `site` | string | ✅ | Site ID or alias (e.g., "mygitea") |
| `owner` | string | ✅ | Repository owner username/org |
| `repo` | string | ✅ | Repository name |
| `page` | integer | ❌ | Page number (default: 1) |
| `limit` | integer | ❌ | Items per page (default: 30, max: 100) |

### Response Format

All tools return consistent response format:

**Success:**
```json
{
  "success": true,
  "message": "Operation completed",
  "data": { ... }
}
```

**Error:**
```json
{
  "error": true,
  "message": "Error description",
  "code": "ERROR_CODE"
}
```

---

## 🔧 Troubleshooting

### Common Issues

#### 1. "Authentication failed"

**Cause**: Invalid or expired token

**Solution**:
- Regenerate personal access token in Gitea
- Update `GITEA_SITEX_TOKEN` in `.env`
- Restart server

#### 2. "Repository not found"

**Cause**: Incorrect owner or repo name

**Solution**:
- Verify repository exists in Gitea
- Check spelling of owner/repo
- Ensure user has access to repository

#### 3. "Permission denied"

**Cause**: Token lacks required permissions

**Solution**:
- Regenerate token with correct permissions:
  - `repo` (all)
  - `write:org`
  - `read:user`
  - `write:issue`

#### 4. "Webhook creation failed"

**Cause**: Invalid webhook URL or insufficient permissions

**Solution**:
- Verify webhook URL is accessible
- Ensure user has admin access to repository
- Check webhook events are valid

### Debug Mode

Enable debug logging:

```bash
LOG_LEVEL=DEBUG
```

Check logs:
```bash
tail -f logs/audit.log | jq
```

### Health Check

Test Gitea connectivity:

```
check_project_health(project_id="gitea_site1")
```

Expected response:
```json
{
  "healthy": true,
  "message": "Gitea instance is accessible"
}
```

---

## ✅ Best Practices

### 1. Security

- ✅ Use **personal access tokens** with minimal required permissions
- ✅ Enable **OAuth** for third-party access (ChatGPT)
- ✅ Rotate tokens regularly
- ✅ Use **private repositories** for sensitive code
- ✅ Enable **webhook secrets** for webhook security
- ✅ Use **per-project API keys** instead of master key

### 2. Git Workflow

- ✅ Create **feature branches** for new features
- ✅ Use **pull requests** for code review
- ✅ Add **meaningful commit messages**
- ✅ Use **labels** for issue categorization
- ✅ Set **milestones** for project planning
- ✅ **Squash merge** to keep history clean

### 3. Automation

- ✅ Setup **webhooks** for CI/CD integration
- ✅ Auto-close issues when PR is merged
- ✅ Use **labels** to trigger automation
- ✅ Create **templates** for issues and PRs

### 4. Performance

- ✅ Use **pagination** for large result sets
- ✅ Cache repository information when possible
- ✅ Use **search** instead of listing all items
- ✅ Batch operations when possible

---

## 🎯 Use Cases

### 1. Automated Issue Triage

```
# AI assistant automatically:
1. Lists open issues
2. Analyzes issue content
3. Adds appropriate labels
4. Assigns to team members
5. Sets milestone
```

### 2. AI Code Review

```
# AI assistant reviews PRs:
1. Lists open PRs
2. Gets PR diff
3. Analyzes code changes
4. Adds review comments
5. Approves or requests changes
```

### 3. Automated Releases

```
# Create release workflow:
1. Create release branch
2. Update version numbers
3. Generate changelog
4. Create pull request
5. After merge: create tag and release
```

### 4. Documentation Updates

```
# Keep docs in sync:
1. Detect code changes
2. Update corresponding documentation
3. Create PR for doc updates
4. Request review from maintainers
```

---

## 📖 Related Documentation

- [OAuth Guide](OAUTH_GUIDE.md) - Complete OAuth 2.1 setup
- [API Keys Guide](API_KEYS_USAGE.md) - API key management
- [Gitea API Docs](https://docs.gitea.io/en-us/api-usage/) - Official Gitea API

---

## 🆘 Support

### Need Help?

- 📧 **Email**: hello@mcphub.dev
- 🐛 **Issues**: [GitHub Issues](https://github.com/airano-ir/mcphub/issues)
- 📚 **Docs**: [Full Documentation](../README.md)

### Contributing

Contributions welcome! See [CONTRIBUTING.md](../CONTRIBUTING.md)

---

**Version**: 3.0.0
