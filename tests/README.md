# Testing Guide

## Integration Tests

### Quick Start

```bash
# In Docker container:
docker exec -it mcphub python tests/run_integration_tests.py

# Or local:
python tests/run_integration_tests.py
```

### What Gets Tested

1. **Module Imports** - All modules load correctly
2. **BasePlugin Architecture** - Plugin system compatibility
3. **WordPress Plugin** - Initialization and handlers
4. **Tool Specifications** - Format and completeness
5. **Handlers Structure** - All 14 handlers present
6. **Pydantic Schemas** - Validation working
7. **ToolGenerator Integration** - Dynamic tool generation ready

### Expected Output

```
Running Integration Tests for WordPress MCP Server
============================================================

Running: Imports... PASSED
Running: Base Plugin... PASSED
Running: WordPress Plugin Init... PASSED
Running: Tool Specifications... PASSED
Running: Handlers Structure... PASSED
Running: Pydantic Schemas... PASSED
Running: ToolGenerator Integration... PASSED

============================================================
Test Summary:
   Total: 7
   Passed: 7
   Failed: 0
   Skipped: 0
```

### Exit Codes

- `0` - All tests passed
- `1` - Some tests failed

### JSON Output

The script also outputs results as JSON for programmatic parsing:

```json
{
  "timestamp": "2025-11-16T10:30:00",
  "tests": [
    {
      "name": "imports",
      "status": "passed",
      "message": "All modules imported successfully",
      "details": {}
    }
  ],
  "summary": {
    "total": 7,
    "passed": 7,
    "failed": 0,
    "skipped": 0
  }
}
```

## Manual Testing with Real Sites

To test with real sites, use MCP Inspector or Claude Desktop:

```python
# Test health
wordpress_get_site_health(site="mysite")

# Test posts
wordpress_list_posts(site="mysite", per_page=5)

# Test products
wordpress_list_products(site="mysite", per_page=5)

# Test WP-CLI (requires container access)
wordpress_wp_cache_type(site="mysite")
```

## Troubleshooting

### Import Errors

```
Error: ModuleNotFoundError: No module named 'plugins'
```

**Fix**: Run from project root:
```bash
cd /app  # In Docker
python tests/run_integration_tests.py
```

### Handler Errors

```
Error: Can't instantiate abstract class WordPressPlugin
```

**Fix**: This means BasePlugin still has abstract get_tools().
This should be fixed in the latest version.
