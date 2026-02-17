# WordPress Advanced Plugin

> **Advanced WordPress management features requiring elevated permissions**

## Overview

The WordPress Advanced plugin provides 22 powerful tools for advanced WordPress management, separated from the core WordPress plugin for better security and tool visibility.

### Why Separated?

**Phase D (WordPress Advanced Split)** separates advanced management features into their own plugin for:

1. **Better Security** 🔒
   - Separate API keys for basic vs advanced operations
   - Advanced operations require explicit permission
   - Reduces risk of accidental database modifications

2. **Better Tool Visibility** 👁️
   - Basic users see only 95 WordPress tools (not 117)
   - Advanced users explicitly enable advanced features
   - Cleaner tool list for most users

3. **Granular Access Control** 🎯
   - Per-project API keys can grant access to:
     - WordPress Core only (95 tools)
     - WordPress Advanced only (22 tools)
     - Both (117 tools total)

## Features

### 22 Advanced Tools

#### Database Operations (7 tools)
- `wp_db_export` - Export WordPress database to SQL file
- `wp_db_import` - Import SQL file to WordPress database
- `wp_db_size` - Get database size and table information
- `wp_db_tables` - List all database tables with sizes
- `wp_db_search` - Search database for specific content
- `wp_db_query` - Execute read-only SQL queries
- `wp_db_repair` - Repair and optimize database tables

#### Bulk Operations (8 tools)
- `bulk_update_posts` - Update multiple posts in parallel (max 100)
- `bulk_delete_posts` - Delete multiple posts in parallel (max 100)
- `bulk_update_products` - Update multiple products in parallel (max 100)
- `bulk_delete_products` - Delete multiple products in parallel (max 100)
- `bulk_delete_media` - Delete multiple media files in parallel (max 100)
- `bulk_assign_categories` - Assign categories to multiple posts
- `bulk_assign_tags` - Assign tags to multiple posts
- `bulk_trash_posts` - Move multiple posts to trash

#### System Operations (7 tools)
- `system_info` - Get WordPress system information (PHP, MySQL, server)
- `system_phpinfo` - Get detailed PHP configuration
- `system_disk_usage` - Get disk usage for WordPress installation
- `system_clear_all_caches` - Clear all WordPress caches
- `cron_list` - List all WordPress cron jobs
- `cron_run` - Run specific cron job immediately
- `error_log` - Get WordPress error log

## Requirements

### Core Requirements
- WordPress site with REST API enabled
- WordPress application password
- **Docker container name** (for WP-CLI access) - REQUIRED!

### WP-CLI Access
All WordPress Advanced features require WP-CLI access through Docker:

```bash
# The MCP server must have access to:
/var/run/docker.sock  # Docker socket

# And the WordPress container must be accessible:
docker exec <container_name> wp --version
```

## Configuration

### Environment Variables

```bash
# WordPress Advanced Site 1
WORDPRESS_ADVANCED_SITE1_URL=https://example.com
WORDPRESS_ADVANCED_SITE1_USERNAME=admin
WORDPRESS_ADVANCED_SITE1_APP_PASSWORD=xxxx xxxx xxxx xxxx xxxx xxxx
WORDPRESS_ADVANCED_SITE1_ALIAS=myblog           # Optional: friendly name
WORDPRESS_ADVANCED_SITE1_CONTAINER=coolify-wp1  # REQUIRED: Docker container name
```

### Finding Container Name

```bash
# List all WordPress containers:
docker ps --filter "name=wordpress" --format "{{.Names}}"

# Test WP-CLI access:
docker exec <container_name> wp --info
```

## Usage Examples

### Database Operations

```python
# Export database
result = await mcp.call_tool("wordpress_advanced_wp_db_export", {
    "site": "myblog",
    "output_file": "/backup/db-backup.sql"
})

# Get database size
result = await mcp.call_tool("wordpress_advanced_wp_db_size", {
    "site": "myblog"
})

# Search database
result = await mcp.call_tool("wordpress_advanced_wp_db_search", {
    "site": "myblog",
    "search_term": "old-domain.com",
    "tables": ["wp_posts", "wp_options"]
})

# Execute read-only query
result = await mcp.call_tool("wordpress_advanced_wp_db_query", {
    "site": "myblog",
    "query": "SELECT COUNT(*) as total FROM wp_posts WHERE post_status='publish'"
})
```

### Bulk Operations

```python
# Bulk update posts
result = await mcp.call_tool("wordpress_advanced_bulk_update_posts", {
    "site": "myblog",
    "post_ids": [1, 2, 3, 4, 5],
    "updates": {
        "status": "draft",
        "author": 2
    }
})

# Bulk delete products
result = await mcp.call_tool("wordpress_advanced_bulk_delete_products", {
    "site": "mystore",
    "product_ids": [100, 101, 102],
    "force": False  # Move to trash instead of permanent delete
})

# Bulk assign categories
result = await mcp.call_tool("wordpress_advanced_bulk_assign_categories", {
    "site": "myblog",
    "post_ids": [10, 11, 12],
    "category_ids": [5, 6]
})
```

### System Operations

```python
# Get system information
result = await mcp.call_tool("wordpress_advanced_system_info", {
    "site": "myblog"
})

# Clear all caches
result = await mcp.call_tool("wordpress_advanced_system_clear_all_caches", {
    "site": "myblog"
})

# List cron jobs
result = await mcp.call_tool("wordpress_advanced_cron_list", {
    "site": "myblog"
})

# Get error log
result = await mcp.call_tool("wordpress_advanced_error_log", {
    "site": "myblog",
    "lines": 100
})
```

## Tool Count

```
WordPress Core Plugin:        95 tools  ✅ (basic features)
WordPress Advanced Plugin:    22 tools  🔒 (advanced features)
─────────────────────────────────────────────────
Total (if both enabled):     117 tools
```

## API Key Configuration

### Option 1: WordPress Core Only (Basic Users)
```bash
# Create API key with wordpress scope only
# User gets: 95 WordPress tools
# User does NOT see: WordPress Advanced tools
```

### Option 2: WordPress Advanced Only (Power Users)
```bash
# Create API key with wordpress_advanced scope only
# User gets: 22 WordPress Advanced tools
# User does NOT see: WordPress Core tools
```

### Option 3: Both Plugins (Admin Users)
```bash
# Create API key with both scopes
# User gets: 117 total tools (95 + 22)
```

## Security Considerations

### Database Operations
- **wp_db_export**: Exports contain sensitive data - secure storage required
- **wp_db_import**: Can overwrite entire database - use with extreme caution
- **wp_db_query**: Read-only enforced - write queries are rejected
- **wp_db_search**: May expose sensitive information in results

### Bulk Operations
- **Parallel Execution**: Max 10 concurrent operations (controlled by semaphore)
- **Batch Limits**: Maximum 100 items per bulk operation
- **Error Handling**: Returns success/failure status for each item
- **Reversibility**: Most operations support trash (soft delete) before permanent deletion

### System Operations
- **system_clear_all_caches**: May cause temporary performance impact
- **cron_run**: Can trigger resource-intensive operations
- **error_log**: May contain sensitive information (paths, credentials)

## Troubleshooting

### "WP-CLI not available" Error

**Cause**: Container not configured or Docker socket not mounted

**Solution**:
```bash
# 1. Check container name
docker ps | grep wordpress

# 2. Test WP-CLI access
docker exec <container_name> wp --info

# 3. Verify Docker socket in docker-compose.yaml
volumes:
  - /var/run/docker.sock:/var/run/docker.sock:ro
```

### "Database handler not available" Error

**Cause**: WP-CLI not configured (container name missing)

**Solution**:
```bash
# Ensure CONTAINER is set in environment variables
WORDPRESS_ADVANCED_SITE1_CONTAINER=your-container-name
```

### "Bulk operation failed" Error

**Cause**: Too many items or invalid IDs

**Solution**:
- Reduce batch size (max 100 items)
- Verify all IDs exist
- Check error details in response for specific failures

## Architecture

```
plugins/wordpress_advanced/
├── __init__.py                  # Plugin exports
├── plugin.py                    # WordPressAdvancedPlugin class
├── README.md                    # This file
│
├── schemas/                     # Pydantic validation models
│   ├── __init__.py
│   ├── database.py             # Database operation schemas
│   ├── bulk.py                 # Bulk operation schemas
│   └── system.py               # System operation schemas
│
└── handlers/                    # Tool implementations
    ├── __init__.py
    ├── database.py             # Database operations (7 tools)
    ├── bulk.py                 # Bulk operations (8 tools)
    └── system.py               # System operations (7 tools)
```

## Migration from WordPress Core

If you previously used WordPress Phase 5 features (database, bulk, system operations):

### Before (Phase 5 - Single Plugin)
```bash
# All features in one plugin
WORDPRESS_SITE1_CONTAINER=coolify-wp1

# All 117 tools visible to everyone
```

### After (Phase D - Split Plugins)
```bash
# Basic WordPress (95 tools)
WORDPRESS_SITE1_URL=...
WORDPRESS_SITE1_USERNAME=...
WORDPRESS_SITE1_APP_PASSWORD=...

# Advanced WordPress (22 tools) - separate configuration
WORDPRESS_ADVANCED_SITE1_URL=...
WORDPRESS_ADVANCED_SITE1_USERNAME=...
WORDPRESS_ADVANCED_SITE1_APP_PASSWORD=...
WORDPRESS_ADVANCED_SITE1_CONTAINER=coolify-wp1  # REQUIRED

# API Keys can now control access separately
```

### Tool Name Changes

Tool names now include `wordpress_advanced_` prefix:

| Before (Phase 5)      | After (Phase D)                       |
|-----------------------|---------------------------------------|
| `wp_db_export`        | `wordpress_advanced_wp_db_export`     |
| `bulk_update_posts`   | `wordpress_advanced_bulk_update_posts`|
| `system_info`         | `wordpress_advanced_system_info`      |

## Performance

### Bulk Operations
- **Parallel Execution**: Up to 10 concurrent operations
- **Semaphore Control**: Prevents server overload
- **Progress Tracking**: Per-item success/failure status
- **Recommended Batch Size**: 10-50 items for optimal performance

### Database Operations
- **Export**: Time depends on database size (1GB ≈ 30-60 seconds)
- **Import**: Slightly slower than export due to indexing
- **Search**: Full-text search across specified tables
- **Query**: Fast read-only queries with result limits

### System Operations
- **Cache Clear**: 1-5 seconds depending on cache size
- **Cron Jobs**: Immediate execution, duration depends on job
- **System Info**: Near-instant (<1 second)

## Best Practices

1. **Use Separate API Keys**: Create different keys for basic and advanced operations
2. **Batch Size**: Keep bulk operations under 50 items for optimal performance
3. **Database Backups**: Always backup before using wp_db_import
4. **Cron Jobs**: Test cron jobs in staging environment first
5. **Error Logs**: Regularly check error logs for security issues
6. **Disk Usage**: Monitor disk usage before large export operations

## Support

For issues, feature requests, or contributions:
- GitHub Issues: [mcphub/issues](https://github.com/airano-ir/mcphub/issues)
- Documentation: [docs/](../../docs/)
- Main README: [../../README.md](../../README.md)

## License

Same as main project license.

---

**Part of MCP Hub** - Phase D (WordPress Advanced Split)
**Version**: 1.0.0
**Last Updated**: 2025-11-18
