# n8n Automation Plugin Design

> **Phase I: n8n Automation Plugin**
> **Priority**: High (Upgraded from Medium)
> **Estimated Tools**: 55-60

---

## Overview

The n8n plugin provides comprehensive automation workflow management through n8n's REST API. This enables AI assistants to create, manage, execute, and monitor automation workflows programmatically.

### Key Capabilities
- Complete workflow lifecycle management (CRUD + activate/deactivate/execute)
- Execution monitoring and history
- Credential management for third-party integrations
- Project and user management (Enterprise/Pro features)
- Environment variables management
- Security audit and source control integration

---

## Architecture

### Plugin Structure

```
plugins/n8n/
├── __init__.py
├── plugin.py              # N8nPlugin class
├── client.py              # N8nClient (REST API communication)
└── handlers/
    ├── __init__.py
    ├── workflows.py       # Workflow management (14 tools)
    ├── executions.py      # Execution monitoring (8 tools)
    ├── credentials.py     # Credential management (8 tools)
    ├── tags.py            # Tag management (6 tools)
    ├── users.py           # User management (6 tools)
    ├── projects.py        # Project management (8 tools)
    ├── variables.py       # Variable management (6 tools)
    └── system.py          # Audit & Source Control (4 tools)
```

### Authentication

n8n uses API Key authentication via `X-N8N-API-KEY` header.

```python
# Environment Variables
N8N_SITE1_URL=https://n8n.example.com
N8N_SITE1_API_KEY=your-api-key
N8N_SITE1_ALIAS=myautomation  # Optional friendly name
```

---

## Tool Specifications (55-60 Tools)

### 1. Workflows Handler (14 tools)

| Tool | Method | Scope | Description |
|------|--------|-------|-------------|
| `list_workflows` | GET | read | List all workflows with filters (active, tags, name) |
| `get_workflow` | GET | read | Get workflow details by ID |
| `create_workflow` | POST | write | Create new workflow from JSON definition |
| `update_workflow` | PUT | write | Update existing workflow |
| `delete_workflow` | DELETE | admin | Delete a workflow |
| `activate_workflow` | POST | write | Activate a workflow |
| `deactivate_workflow` | POST | write | Deactivate a workflow |
| `execute_workflow` | POST | write | Manually execute a workflow |
| `execute_workflow_with_data` | POST | write | Execute with custom input data |
| `duplicate_workflow` | POST | write | Duplicate an existing workflow |
| `export_workflow` | GET | read | Export workflow as JSON |
| `import_workflow` | POST | write | Import workflow from JSON |
| `get_workflow_tags` | GET | read | Get tags assigned to a workflow |
| `set_workflow_tags` | PUT | write | Assign tags to a workflow |

#### Tool Specification Example

```python
{
    "name": "list_workflows",
    "method_name": "list_workflows",
    "description": "List all n8n workflows with optional filters. Returns workflow ID, name, active status, and metadata.",
    "schema": {
        "type": "object",
        "properties": {
            "active": {
                "type": "boolean",
                "description": "Filter by active/inactive status"
            },
            "tags": {
                "anyOf": [{"type": "string"}, {"type": "null"}],
                "description": "Filter by tag name(s), comma-separated"
            },
            "name": {
                "anyOf": [{"type": "string"}, {"type": "null"}],
                "description": "Filter by workflow name (partial match)"
            },
            "limit": {
                "type": "integer",
                "description": "Maximum workflows to return",
                "default": 50,
                "minimum": 1,
                "maximum": 250
            },
            "cursor": {
                "anyOf": [{"type": "string"}, {"type": "null"}],
                "description": "Pagination cursor for next page"
            }
        }
    },
    "scope": "read"
}
```

```python
{
    "name": "execute_workflow",
    "method_name": "execute_workflow",
    "description": "Manually execute a workflow and return execution ID. Use get_execution to check status.",
    "schema": {
        "type": "object",
        "properties": {
            "workflow_id": {
                "type": "string",
                "description": "Workflow ID to execute",
                "minLength": 1
            },
            "wait": {
                "type": "boolean",
                "description": "Wait for execution to complete (max 5 minutes)",
                "default": False
            }
        },
        "required": ["workflow_id"]
    },
    "scope": "write"
}
```

```python
{
    "name": "execute_workflow_with_data",
    "method_name": "execute_workflow_with_data",
    "description": "Execute workflow with custom input data. Useful for workflows with webhook/manual triggers.",
    "schema": {
        "type": "object",
        "properties": {
            "workflow_id": {
                "type": "string",
                "description": "Workflow ID to execute",
                "minLength": 1
            },
            "data": {
                "type": "object",
                "description": "Input data to pass to workflow trigger node"
            },
            "wait": {
                "type": "boolean",
                "description": "Wait for execution to complete",
                "default": False
            }
        },
        "required": ["workflow_id", "data"]
    },
    "scope": "write"
}
```

---

### 2. Executions Handler (8 tools)

| Tool | Method | Scope | Description |
|------|--------|-------|-------------|
| `list_executions` | GET | read | List workflow executions with filters |
| `get_execution` | GET | read | Get execution details and data |
| `delete_execution` | DELETE | write | Delete a single execution |
| `delete_executions` | DELETE | write | Bulk delete executions |
| `stop_execution` | POST | write | Stop a running execution |
| `retry_execution` | POST | write | Retry a failed execution |
| `get_execution_data` | GET | read | Get full execution data including node outputs |
| `wait_for_execution` | GET | read | Poll until execution completes |

#### Tool Specification Examples

```python
{
    "name": "list_executions",
    "method_name": "list_executions",
    "description": "List workflow executions with filters by status, workflow, date range. Returns execution history.",
    "schema": {
        "type": "object",
        "properties": {
            "workflow_id": {
                "anyOf": [{"type": "string"}, {"type": "null"}],
                "description": "Filter by workflow ID"
            },
            "status": {
                "anyOf": [{"type": "string", "enum": ["success", "error", "waiting", "running", "new"]}, {"type": "null"}],
                "description": "Filter by execution status"
            },
            "include_data": {
                "type": "boolean",
                "description": "Include full execution data",
                "default": False
            },
            "limit": {
                "type": "integer",
                "description": "Maximum results",
                "default": 20,
                "minimum": 1,
                "maximum": 250
            },
            "cursor": {
                "anyOf": [{"type": "string"}, {"type": "null"}],
                "description": "Pagination cursor"
            }
        }
    },
    "scope": "read"
}
```

```python
{
    "name": "get_execution",
    "method_name": "get_execution",
    "description": "Get detailed information about a specific execution including status, timing, and optionally full data.",
    "schema": {
        "type": "object",
        "properties": {
            "execution_id": {
                "type": "string",
                "description": "Execution ID",
                "minLength": 1
            },
            "include_data": {
                "type": "boolean",
                "description": "Include full node execution data",
                "default": True
            }
        },
        "required": ["execution_id"]
    },
    "scope": "read"
}
```

---

### 3. Credentials Handler (8 tools)

| Tool | Method | Scope | Description |
|------|--------|-------|-------------|
| `list_credentials` | GET | read | List all credentials (without sensitive data) |
| `get_credential` | GET | read | Get credential metadata |
| `create_credential` | POST | admin | Create new credential |
| `update_credential` | PUT | admin | Update credential |
| `delete_credential` | DELETE | admin | Delete a credential |
| `get_credential_schema` | GET | read | Get schema for credential type |
| `list_credential_types` | GET | read | List available credential types |
| `transfer_credential` | POST | admin | Transfer credential to another project |

#### Tool Specification Examples

```python
{
    "name": "list_credentials",
    "method_name": "list_credentials",
    "description": "List all stored credentials. Returns metadata only (no sensitive values).",
    "schema": {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "Maximum results",
                "default": 100,
                "minimum": 1,
                "maximum": 250
            },
            "cursor": {
                "anyOf": [{"type": "string"}, {"type": "null"}],
                "description": "Pagination cursor"
            }
        }
    },
    "scope": "read"
}
```

```python
{
    "name": "create_credential",
    "method_name": "create_credential",
    "description": "Create a new credential for use in workflows. Use get_credential_schema to see required fields.",
    "schema": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Credential display name",
                "minLength": 1
            },
            "type": {
                "type": "string",
                "description": "Credential type (e.g., 'githubApi', 'slackApi')",
                "minLength": 1
            },
            "data": {
                "type": "object",
                "description": "Credential data matching the schema for this type"
            }
        },
        "required": ["name", "type", "data"]
    },
    "scope": "admin"
}
```

---

### 4. Tags Handler (6 tools)

| Tool | Method | Scope | Description |
|------|--------|-------|-------------|
| `list_tags` | GET | read | List all tags |
| `get_tag` | GET | read | Get tag details |
| `create_tag` | POST | write | Create a new tag |
| `update_tag` | PUT | write | Update tag name |
| `delete_tag` | DELETE | write | Delete a tag |
| `delete_tags` | DELETE | write | Bulk delete tags |

---

### 5. Users Handler (6 tools)

| Tool | Method | Scope | Description |
|------|--------|-------|-------------|
| `list_users` | GET | admin | List all users |
| `get_user` | GET | admin | Get user details |
| `create_user` | POST | admin | Invite/create new user |
| `delete_user` | DELETE | admin | Delete a user |
| `change_user_role` | PUT | admin | Change user's global role |
| `get_current_user` | GET | read | Get current authenticated user |

---

### 6. Projects Handler (8 tools) - Enterprise/Pro

| Tool | Method | Scope | Description |
|------|--------|-------|-------------|
| `list_projects` | GET | read | List all projects |
| `get_project` | GET | read | Get project details |
| `create_project` | POST | admin | Create a new project |
| `update_project` | PUT | admin | Update project metadata |
| `delete_project` | DELETE | admin | Delete a project |
| `add_project_users` | POST | admin | Add users to project with roles |
| `change_project_user_role` | PUT | admin | Change user's role in project |
| `remove_project_user` | DELETE | admin | Remove user from project |

---

### 7. Variables Handler (6 tools)

| Tool | Method | Scope | Description |
|------|--------|-------|-------------|
| `list_variables` | GET | read | List all environment variables |
| `get_variable` | GET | read | Get variable value by key |
| `create_variable` | POST | admin | Create new variable |
| `update_variable` | PUT | admin | Update variable value |
| `delete_variable` | DELETE | admin | Delete a variable |
| `set_variables` | POST | admin | Bulk set multiple variables |

---

### 8. System Handler (4 tools)

| Tool | Method | Scope | Description |
|------|--------|-------|-------------|
| `run_security_audit` | POST | admin | Run security audit on instance |
| `source_control_pull` | POST | admin | Pull workflows from Git repository |
| `get_instance_info` | GET | read | Get n8n instance version and status |
| `health_check` | GET | read | Check n8n instance health |

---

## API Client Design

### N8nClient Class

```python
class N8nClient:
    """
    n8n REST API client for HTTP communication.

    Handles authentication, request formatting, and error handling
    for all n8n API endpoints.
    """

    def __init__(self, site_url: str, api_key: str):
        """
        Initialize n8n API client.

        Args:
            site_url: n8n instance URL (e.g., https://n8n.example.com)
            api_key: n8n API key for authentication
        """
        self.site_url = site_url.rstrip('/')
        self.api_base = f"{self.site_url}/api/v1"
        self.api_key = api_key

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with API key authentication."""
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-N8N-API-KEY": self.api_key
        }

    async def request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        json_data: Optional[Dict] = None
    ) -> Any:
        """Make authenticated request to n8n REST API."""
        # Implementation similar to GiteaClient
```

---

## Endpoint Reference

### Base URL
```
{N8N_URL}/api/v1
```

### Workflows
```
GET    /workflows                    - List workflows
POST   /workflows                    - Create workflow
GET    /workflows/{id}               - Get workflow
PUT    /workflows/{id}               - Update workflow
DELETE /workflows/{id}               - Delete workflow
POST   /workflows/{id}/activate      - Activate workflow
POST   /workflows/{id}/deactivate    - Deactivate workflow
POST   /workflows/{id}/run           - Execute workflow
```

### Executions
```
GET    /executions                   - List executions
GET    /executions/{id}              - Get execution
DELETE /executions/{id}              - Delete execution
```

### Credentials
```
GET    /credentials                  - List credentials
POST   /credentials                  - Create credential
GET    /credentials/{id}             - Get credential
DELETE /credentials/{id}             - Delete credential
GET    /credentials/schema/{type}    - Get credential schema
POST   /credentials/{id}/transfer    - Transfer credential
```

### Tags
```
GET    /tags                         - List tags
POST   /tags                         - Create tag
GET    /tags/{id}                    - Get tag
PUT    /tags/{id}                    - Update tag
DELETE /tags/{id}                    - Delete tag
```

### Users
```
GET    /users                        - List users
POST   /users                        - Create/invite user
GET    /users/{id}                   - Get user
DELETE /users/{id}                   - Delete user
PATCH  /users/{id}/role              - Change user role
```

### Projects (Enterprise/Pro)
```
GET    /projects                     - List projects
POST   /projects                     - Create project
GET    /projects/{id}                - Get project
PUT    /projects/{id}                - Update project
DELETE /projects/{id}                - Delete project
POST   /projects/{id}/users          - Add users to project
```

### Variables
```
GET    /variables                    - List variables
POST   /variables                    - Create variable
GET    /variables/{key}              - Get variable
PUT    /variables/{key}              - Update variable
DELETE /variables/{key}              - Delete variable
```

### System
```
POST   /audit                        - Run security audit
POST   /source-control/pull          - Pull from Git
GET    /health                       - Health check
```

---

## Multi-Endpoint Integration

### Endpoint Configuration

```python
# core/endpoints/config.py
ENDPOINT_CONFIGS = {
    # ... existing configs ...

    "n8n": EndpointConfig(
        path="/n8n/mcp",
        name="n8n Automation",
        plugin_types=["n8n"],
        description="Workflow automation management",
        tools_count=55
    )
}
```

### Per-Project Endpoint

```
/project/{alias}/mcp    - Site-specific n8n endpoint
/project/myautomation/mcp
```

---

## Environment Configuration

```bash
# Single n8n instance
N8N_SITE1_URL=https://n8n.example.com
N8N_SITE1_API_KEY=your-api-key-here
N8N_SITE1_ALIAS=automation

# Multiple instances
N8N_SITE2_URL=https://n8n-staging.example.com
N8N_SITE2_API_KEY=staging-api-key
N8N_SITE2_ALIAS=automation-staging
```

---

## Use Cases

### 1. Workflow Management
```
User: "Create a new workflow that sends Slack notifications when a GitHub issue is created"

AI Assistant:
1. create_workflow with workflow JSON definition
2. activate_workflow to enable it
3. list_credentials to verify Slack/GitHub credentials exist
```

### 2. Execution Monitoring
```
User: "Show me failed executions from the last 24 hours"

AI Assistant:
1. list_executions with status="error" filter
2. get_execution for each to see error details
3. Provide summary and suggestions
```

### 3. Credential Management
```
User: "Set up new API credentials for OpenAI"

AI Assistant:
1. get_credential_schema for "openAiApi" type
2. create_credential with required fields
3. Confirm credential is ready for use
```

### 4. Security Audit
```
User: "Run a security audit on our n8n instance"

AI Assistant:
1. run_security_audit
2. Parse and summarize findings
3. Provide recommendations
```

---

## Implementation Priority

### Phase 1 (Core - Must Have)
1. Workflows handler (14 tools)
2. Executions handler (8 tools)
3. Client implementation
4. Plugin class

### Phase 2 (Extended - Should Have)
1. Credentials handler (8 tools)
2. Tags handler (6 tools)
3. Variables handler (6 tools)

### Phase 3 (Advanced - Nice to Have)
1. Users handler (6 tools)
2. Projects handler (8 tools)
3. System handler (4 tools)

---

## Security Considerations

1. **API Key Protection**: Store API keys securely, never log them
2. **Credential Handling**: Never expose credential values in responses
3. **Scope Enforcement**: Admin-level tools require admin scope
4. **Rate Limiting**: Respect n8n API rate limits
5. **Audit Logging**: Log all write/admin operations

---

## Testing Strategy

1. **Unit Tests**: Test each handler function independently
2. **Integration Tests**: Test against a local n8n instance
3. **Mock Tests**: Use mocked API responses for CI/CD

---

## Documentation Links

- [n8n Public REST API](https://docs.n8n.io/api/)
- [n8n API Reference](https://docs.n8n.io/api/api-reference/)
- [n8n Authentication](https://docs.n8n.io/api/authentication/)

---

## Summary

| Category | Tools | Priority |
|----------|-------|----------|
| Workflows | 14 | Phase 1 |
| Executions | 8 | Phase 1 |
| Credentials | 8 | Phase 2 |
| Tags | 6 | Phase 2 |
| Variables | 6 | Phase 2 |
| Users | 6 | Phase 3 |
| Projects | 8 | Phase 3 |
| System | 4 | Phase 3 |
| **Total** | **60** | - |

---

**Created**: 2025-11-27
**Author**: AI Assistant
**Status**: Design Document - Awaiting Implementation
