# 🔐 API Keys Management Guide

Complete guide for managing API keys in MCP Hub.

---

## Table of Contents

- [Overview](#overview)
- [Key Types](#key-types)
- [Scopes & Permissions](#scopes--permissions)
- [Creating Keys](#creating-keys)
- [Managing Keys](#managing-keys)
- [Best Practices](#best-practices)
- [Examples](#examples)
- [Troubleshooting](#troubleshooting)

---

## Overview

MCP Hub supports two types of API keys for authentication:

1. **Master API Key** - Full access to all operations and projects
2. **Per-Project API Keys** - Scoped access with granular permissions

Per-project keys provide:
- ✅ **Project-level isolation** - Limit access to specific projects
- ✅ **Scope-based permissions** - Control read/write/admin operations
- ✅ **Expiration support** - Automatic key rotation
- ✅ **Usage tracking** - Monitor key usage and last access
- ✅ **Audit trail** - All key operations are logged
- ✅ **Easy rotation** - Rotate all keys for a project with one command

---

## Key Types

### Master API Key

- **Source**: `MASTER_API_KEY` environment variable
- **Access Level**: Full admin access to all projects
- **Use Case**: Server administration, initial setup
- **Lifetime**: Permanent (until manually changed)
- **Format**: Any string (recommended: 32+ characters)

**Example**:
```bash
MASTER_API_KEY=your_secure_master_key_here
```

### Per-Project API Keys

- **Storage**: JSON file (`data/api_keys.json`)
- **Access Level**: Configurable per key (read/write/admin)
- **Use Case**: Application integration, team access, CI/CD
- **Lifetime**: Optional expiration (days)
- **Format**: `cmp_` prefix + random string

**Example**:
```
cmp_AQECAHhoZXJlIGlzIGEgcmFuZG9tIGtleQ
```

---

## Scopes & Permissions

### Read Scope

**Per-Project Keys** (`project_id` specific):
- ✅ List and get operations for assigned project
- ✅ Read WordPress content (posts, pages, comments, media)
- ✅ Read WooCommerce data (products, orders, customers)
- ✅ Read taxonomies, menus, and settings
- ❌ Cannot access system tools (requires global key)
- ❌ Cannot create, update, or delete

**Tools Allowed**:
- `wordpress_list_posts`, `wordpress_get_post`
- `wordpress_list_products`, `wordpress_get_product`
- `wordpress_list_orders`, `wordpress_get_order`
- All WordPress/WooCommerce `get_*` and `list_*` tools

**Global Keys** (`project_id="*"`):
- ✅ All per-project permissions for ALL projects
- ✅ System tools: `list_projects`, `get_project_info`
- ✅ Monitoring: `check_all_projects_health`, `get_system_metrics`
- ✅ Rate limits: `get_rate_limit_stats`
- ✅ API Keys: `manage_api_keys_list` (read-only)

**Use Cases**:
- **Per-Project**: Client access to their specific site
- **Global**: Admin dashboards, monitoring, analytics

### Write Scope

**Per-Project Keys**:
- ✅ All read operations for assigned project
- ✅ Create, update, delete content
- ✅ Upload and modify media
- ✅ Manage products, orders, customers
- ❌ Cannot access system tools (requires global key)
- ❌ Cannot manage API keys or system settings

**Tools Allowed**:
- All read scope tools for the project, plus:
- `wordpress_create_post`, `wordpress_update_post`, `wordpress_delete_post`
- `wordpress_create_product`, `wordpress_update_product`
- `wordpress_create_order`, `wordpress_update_order_status`
- `wordpress_upload_media_from_url`
- All `create_*`, `update_*`, `delete_*` tools for the project

**Global Keys** (`project_id="*"`):
- ✅ All per-project permissions for ALL projects
- ✅ System tools access (read-only)

**Use Cases**:
- **Per-Project**: Client content management for their site
- **Global**: Multi-site management, automated publishing

### Admin Scope

**Per-Project Keys**:
- ✅ All read and write operations for assigned project
- ✅ Advanced WordPress management (WP-CLI tools)
- ✅ Database operations (check, optimize, export)
- ❌ Cannot access system tools (requires global key)
- ❌ Cannot manage API keys (requires global key)

**Global Keys** (`project_id="*"`):
- ✅ All per-project permissions for ALL projects
- ✅ Full system access: `manage_api_keys_*`, `reset_rate_limit`
- ✅ System monitoring and administration
- ✅ Health metrics export

**Tools Allowed**:
- All read and write scope tools, plus:
- `manage_api_keys_*` tools (global keys only)
- `reset_rate_limit` (global keys only)
- `export_health_metrics`
- WP-CLI tools: `wp_cache_flush`, `wp_db_optimize`, etc.

**Use Cases**:
- **Per-Project**: Full site administration for specific client
- **Global**: Platform administration, multi-tenant management
- System maintenance

---

## Creating Keys

### Basic Key Creation

Create a read-only key for a specific project:

```python
result = manage_api_keys_create(
    project_id="wordpress_site1",
    scope="read"
)

# Save the key - it won't be shown again!
api_key = result["key"]  # cmp_...
key_id = result["key_id"]  # key_...
```

### Key with Description

Add a description for better organization:

```python
result = manage_api_keys_create(
    project_id="wordpress_site1",
    scope="write",
    description="CI/CD pipeline key for automated deployments"
)
```

### Expiring Key

Create a temporary key that expires after 30 days:

```python
result = manage_api_keys_create(
    project_id="wordpress_site2",
    scope="read",
    expires_in_days=30,
    description="Temporary access for contractor"
)
```

### Global Key

Create a key that works for all projects:

```python
result = manage_api_keys_create(
    project_id="*",  # All projects
    scope="admin",
    description="Backup admin key"
)
```

---

## Managing Keys

### List All Keys

```python
result = manage_api_keys_list()

print(f"Total keys: {result['total']}")
for key in result['keys']:
    print(f"- {key['key_id']}: {key['project_id']} ({key['scope']})")
```

### List Keys for Specific Project

```python
result = manage_api_keys_list(
    project_id="wordpress_site1"
)
```

### Include Revoked Keys

```python
result = manage_api_keys_list(
    include_revoked=True
)
```

### Get Key Information

```python
result = manage_api_keys_get_info(
    key_id="key_abc123"
)

if result['success']:
    key_info = result['key']
    print(f"Project: {key_info['project_id']}")
    print(f"Scope: {key_info['scope']}")
    print(f"Created: {key_info['created_at']}")
    print(f"Last used: {key_info['last_used_at']}")
    print(f"Usage count: {key_info['usage_count']}")
    print(f"Valid: {key_info['valid']}")
```

### Revoke a Key

Soft delete (can view in history):

```python
result = manage_api_keys_revoke(
    key_id="key_abc123"
)
```

### Delete a Key

Permanent deletion:

```python
result = manage_api_keys_delete(
    key_id="key_abc123"
)
```

### Rotate All Project Keys

Create new keys and revoke old ones:

```python
result = manage_api_keys_rotate(
    project_id="wordpress_site1"
)

# Save the new keys!
for new_key in result['new_keys']:
    print(f"New key: {new_key['key']}")
    print(f"Scope: {new_key['scope']}")
```

---

## Best Practices

### 1. Use Principle of Least Privilege

**❌ Don't**:
```python
# Giving admin access when read is enough
manage_api_keys_create("wordpress_site1", scope="admin")
```

**✅ Do**:
```python
# Use minimal required scope
manage_api_keys_create("wordpress_site1", scope="read")
```

### 2. Set Expiration for Temporary Access

**❌ Don't**:
```python
# Permanent key for temporary contractor
manage_api_keys_create("wordpress_site1", scope="write")
```

**✅ Do**:
```python
# Expiring key for contractor
manage_api_keys_create(
    "wordpress_site1",
    scope="write",
    expires_in_days=90,
    description="Q4 contractor access"
)
```

### 3. Use Descriptive Names

**❌ Don't**:
```python
manage_api_keys_create("wordpress_site1", "write")
```

**✅ Do**:
```python
manage_api_keys_create(
    "wordpress_site1",
    scope="write",
    description="Production deployment key for CI/CD pipeline"
)
```

### 4. Regular Key Rotation

Rotate keys quarterly or after team changes:

```python
# Every 3 months
result = manage_api_keys_rotate("wordpress_site1")

# Update all integrations with new keys
for key in result['new_keys']:
    # Update CI/CD, monitoring tools, etc.
    update_integration(key['key'])
```

### 5. Monitor Key Usage

```python
# Check if keys are being used
result = manage_api_keys_list()

for key in result['keys']:
    if key['usage_count'] == 0:
        print(f"Warning: Key {key['key_id']} has never been used")

    if key['last_used_at']:
        # Check if key hasn't been used in 30+ days
        # Consider revoking inactive keys
        pass
```

### 6. Revoke Compromised Keys Immediately

```python
# If a key is compromised
manage_api_keys_revoke("key_compromised")

# Create a new key
new_key = manage_api_keys_create(
    "wordpress_site1",
    scope="write",
    description="Replacement for compromised key"
)
```

---

## Examples

### Example 1: CI/CD Pipeline

```python
# 1. Create a write-scoped key for CI/CD
result = manage_api_keys_create(
    project_id="wordpress_site1",
    scope="write",
    description="GitHub Actions deployment key"
)

ci_key = result['key']

# 2. Add to GitHub Secrets as MCP_API_KEY

# 3. Use in workflow:
# headers = {"Authorization": f"Bearer {os.getenv('MCP_API_KEY')}"}
```

### Example 2: Monitoring Dashboard

```python
# Create read-only key for monitoring
result = manage_api_keys_create(
    project_id="*",  # All projects
    scope="read",
    description="Grafana monitoring dashboard"
)

monitoring_key = result['key']

# Use for health checks, metrics collection
```

### Example 3: Team Member Access

```python
# Create keys for team members
team_keys = {}

for member in ["alice", "bob", "charlie"]:
    result = manage_api_keys_create(
        project_id="wordpress_site1",
        scope="write",
        description=f"Key for {member}"
    )
    team_keys[member] = result['key']

# Distribute keys securely (1Password, etc.)
```

### Example 4: Temporary Contractor Access

```python
# 90-day expiring key for contractor
result = manage_api_keys_create(
    project_id="wordpress_site2",
    scope="read",
    expires_in_days=90,
    description="Contractor access - expires Q1 2026"
)

contractor_key = result['key']

# Key automatically becomes invalid after 90 days
```

### Example 5: Key Rotation Schedule

```python
# Quarterly rotation script
import schedule

def rotate_all_projects():
    projects = ["wordpress_site1", "wordpress_site2", "wordpress_site3"]

    for project in projects:
        result = manage_api_keys_rotate(project)
        print(f"Rotated {result['rotated_count']} keys for {project}")

        # Email new keys to team
        notify_team(project, result['new_keys'])

# Run every 90 days
schedule.every(90).days.do(rotate_all_projects)
```

---

## Troubleshooting

### Key Not Working

**Problem**: API key returns "Authentication failed"

**Solutions**:

1. Check if key is revoked:
```python
info = manage_api_keys_get_info("key_abc123")
if info['key']['revoked']:
    print("Key has been revoked")
```

2. Check if key expired:
```python
if info['key']['expired']:
    print("Key has expired")
```

3. Verify scope matches operation:
```python
# Read-only key cannot write
if info['key']['scope'] == 'read':
    print("Cannot use read key for write operations")
```

### Key Not Found

**Problem**: "Key not found: key_abc123"

**Solution**: List all keys to find correct ID:
```python
result = manage_api_keys_list(include_revoked=True)
for key in result['keys']:
    print(f"{key['key_id']}: {key['description']}")
```

### Permission Denied

**Problem**: "Insufficient scope"

**Solution**: Check required scope for operation:
```python
# Operation requires 'write' but key has 'read'
# Create new key with correct scope:
manage_api_keys_create(project_id="site1", scope="write")
```

### Storage File Issues

**Problem**: "Failed to load keys" or "Failed to save keys"

**Solutions**:

1. Check file permissions:
```bash
ls -l data/api_keys.json
chmod 600 data/api_keys.json  # Read/write for owner only
```

2. Check directory exists:
```bash
mkdir -p data
```

3. Validate JSON format:
```bash
python -m json.tool data/api_keys.json
```

---

## Security Considerations

### Storage Security

- API keys are stored as SHA256 hashes
- Only the key hash is saved, not the actual key
- Storage file should have restricted permissions (600)
- Consider encrypting the storage file at rest

### Network Security

- Always use HTTPS for API requests
- Never log API keys in plain text
- Use secure channels to distribute keys (1Password, Vault)

### Audit & Compliance

- All key operations are logged in audit.log
- Track key usage via `usage_count` and `last_used_at`
- Regular review of active keys
- Compliance with GDPR, SOC 2, ISO 27001

---

## Related Documentation

- [Authentication Guide](AUTH_GUIDE.md)
- [Security Policy](../SECURITY.md)
- [Audit Logging](AUDIT_LOGGING.md)
- [Rate Limiting](RATE_LIMITING.md)

---

**Version**: 1.0.0
**Last Updated**: 2025-11-11
**Maintained by**: Airano (https://mcphub.dev)
