# Multi-Endpoint Architecture Guide

> Solving the Tool Visibility Problem

---

## The Problem

### Before (Single Endpoint)
```
Client connects to /mcp
    ↓
Sees ALL 188 tools
    ↓
API key for site4 can see:
  - ✅ WordPress tools (but for all sites!)
  - ❌ Gitea tools (shouldn't see)
  - ❌ System tools (shouldn't see)
  - ❌ API key management (security risk!)
```

### Issue
- Users saw tools they couldn't use
- Wasted AI context on irrelevant tools
- Security concern: tool enumeration
- Confusing UX

---

## The Solution

### After (Multi-Endpoint)
```
Client connects to /mcp/wordpress
    ↓
Sees ONLY 92 WordPress tools
    ↓
Clean, focused, secure
```

---

## Endpoint Overview

| Endpoint | Tools | Requires | Use Case |
|----------|-------|----------|----------|
| `/mcp` | 188 | Master Key | Admin operations |
| `/mcp/wordpress` | 92 | API Key | WordPress management |
| `/mcp/wordpress-advanced` | 22 | Admin Key | DB/Bulk/System ops |
| `/mcp/gitea` | 55 | API Key | Git management |
| `/mcp/project/{id}` | Varies | Project Key | Single project |

---

## Migration Guide

### For Existing Users

**Before (v1.x)**
```json
{
  "mcpServers": {
    "coolify": {
      "url": "https://mcp.example.com/mcp",
      "headers": {
        "Authorization": "Bearer cmp_xxx"
      }
    }
  }
}
```

**After (v2.0)**
```json
{
  "mcpServers": {
    "wordpress": {
      "url": "https://mcp.example.com/mcp/wordpress",
      "headers": {
        "Authorization": "Bearer cmp_xxx"
      }
    },
    "gitea": {
      "url": "https://mcp.example.com/mcp/gitea",
      "headers": {
        "Authorization": "Bearer cmp_yyy"
      }
    }
  }
}
```

### Benefits After Migration
- Faster tool discovery
- Less AI context used
- Better security
- Clearer access control

---

## API Key Configuration

### Creating WordPress-Only Key
```bash
# Using admin endpoint with Master Key
curl -X POST https://mcp.example.com/mcp \
  -H "Authorization: Bearer sk-master-key" \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "manage_api_keys_create",
    "arguments": {
      "project_id": "wordpress_site1",
      "scope": "write",
      "name": "Site1 Editor"
    }
  }'
```

### Key Scopes

| Scope | Permissions |
|-------|-------------|
| `read` | Read-only operations |
| `write` | Read + create/update |
| `admin` | Full access + system tools |

---

## Endpoint Details

### `/mcp` - Admin Endpoint

**Access**: Master API Key (`sk-*`) only

**Tools**: All 188 tools including:
- WordPress Core (92)
- WordPress Advanced (22)
- Gitea (55)
- System tools (19)
- API key management
- OAuth management

**Use Cases**:
- Initial setup
- Creating API keys
- System monitoring
- OAuth client management

---

### `/mcp/wordpress` - WordPress Endpoint

**Access**: Any valid API key

**Tools**: 92 WordPress tools
- Posts & Pages
- Media
- Taxonomy
- Comments
- Users
- WooCommerce
- SEO

**Blacklisted Tools**:
- `manage_api_keys_*`
- `oauth_*`
- System tools

**Use Cases**:
- Content management
- WooCommerce operations
- SEO management

---

### `/mcp/wordpress-advanced` - Advanced WordPress Endpoint

**Access**: Admin scope required

**Tools**: 22 advanced tools
- Database operations
- Bulk operations
- System operations

**Use Cases**:
- Database backup/restore
- Bulk content updates
- System maintenance

---

### `/mcp/gitea` - Gitea Endpoint

**Access**: Any valid API key (with gitea project)

**Tools**: 55 Gitea tools
- Repository management
- Issue tracking
- Pull requests
- Webhooks

**Use Cases**:
- Git operations
- Issue management
- PR reviews

---

### `/mcp/project/{id}` - Project Endpoint

**Access**: API key matching project_id

**Tools**: Plugin tools filtered to single project

**Example**: `/mcp/project/wordpress_site1`
- Only WordPress tools
- Site parameter auto-set to `site1`

**Use Cases**:
- Single-site management
- Restricted access per client

---

## Security Considerations

### Tool Blacklisting

System and admin tools are blacklisted from non-admin endpoints:
```python
tool_blacklist = {
    "manage_api_keys_create",
    "manage_api_keys_delete",
    "manage_api_keys_rotate",
    "oauth_register_client",
    "oauth_revoke_client",
}
```

### API Key Validation

Each endpoint validates:
1. Token format and validity
2. Scope requirements
3. Plugin type matching
4. Tool-level access

### Audit Logging

All tool calls are logged with:
- Endpoint path
- Tool name
- API key ID
- Timestamp
- Success/failure

---

## Running the Server

### Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run multi-endpoint server
python server_multi.py --port 8000
```

### Production (Docker)
```bash
# Build
docker-compose build

# Run
docker-compose up -d
```

### Environment Variables
```bash
# Required
MASTER_API_KEY=sk-your-secure-key

# WordPress
WORDPRESS_SITE1_URL=https://example.com
WORDPRESS_SITE1_USERNAME=admin
WORDPRESS_SITE1_PASSWORD=app_password

# Gitea
GITEA_SITE1_URL=https://gitea.example.com
GITEA_SITE1_TOKEN=your-token
```

---

## Testing Endpoints

### Check Available Endpoints
```bash
curl http://localhost:8000/endpoints
```

### Check Health
```bash
curl http://localhost:8000/health
```

### Test WordPress Endpoint
```bash
curl -X POST http://localhost:8000/mcp/wordpress \
  -H "Authorization: Bearer cmp_xxx" \
  -H "Content-Type: application/json" \
  -d '{"tool": "wordpress_list_posts", "arguments": {"site": "site1"}}'
```

---

## Troubleshooting

### "Endpoint requires master API key"
- Use `/mcp` endpoint with Master Key for admin operations
- Or use appropriate plugin endpoint with project API key

### "API key cannot access this endpoint"
- API key project_id must match endpoint plugin type
- Example: `wordpress_site1` key works on `/mcp/wordpress`, not `/mcp/gitea`

### "Access denied to tool"
- Tool may be blacklisted for this endpoint
- Check if admin scope is required

---

## Future Improvements

- [ ] Per-project endpoints (`/mcp/project/{id}`)
- [ ] Dynamic endpoint creation
- [ ] Custom tool whitelists
- [ ] Endpoint-level rate limiting
- [ ] Endpoint usage analytics

---

**Last Updated**: 2025-11-24
