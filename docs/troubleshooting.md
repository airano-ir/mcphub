# 🔧 Troubleshooting Guide

---

## Table of Contents

1. [Common Errors](#common-errors)
2. [Connection Issues](#connection-issues)
3. [Authentication Problems](#authentication-problems)
4. [Rate Limiting Issues](#rate-limiting-issues)
5. [Docker Problems](#docker-problems)
6. [Performance Issues](#performance-issues)
7. [Tool Registration Issues](#tool-registration-issues)
8. [Logging and Debugging](#logging-and-debugging)
9. [Getting Help](#getting-help)

---

## Common Errors

### Error: "No module named 'fastmcp'"

**Cause**: Dependencies not installed or virtual environment not activated.

**Solution**:
```bash
# Activate virtual environment
source venv/bin/activate  # Linux/Mac
.\venv\Scripts\Activate.ps1  # Windows

# Install dependencies
pip install -r requirements.txt
```

### Error: "KeyError: 'WORDPRESS_SITE1_URL'"

**Cause**: Environment variables not configured.

**Solution**:
```bash
# Check if .env file exists
ls -la .env

# If not, create from template
cp .env.example .env

# Edit with your credentials
nano .env  # Linux/Mac
notepad .env  # Windows
```

### Error: "ModuleNotFoundError: No module named 'core'"

**Cause**: Running from wrong directory or Python path issue.

**Solution**:
```bash
# Make sure you're in project root
cd /path/to/mcphub

# Run the server directly
python server.py

# Or add to .env
echo "PYTHONPATH=." >> .env
```

---

## Connection Issues

### WordPress Site Not Accessible

**Symptoms**: `Connection timeout`, `Connection refused`, `Name or service not known`

**Diagnosis**:
```bash
# Test site accessibility
curl -I https://your-wordpress-site.com

# Check DNS resolution
nslocalhost your-wordpress-site.com

# Test with timeout
timeout 5 curl https://your-wordpress-site.com
```

**Solutions**:

1. **Check URL format**:
   ```bash
   # Correct
   WORDPRESS_SITE1_URL=https://example.com

   # Incorrect
   WORDPRESS_SITE1_URL=example.com  # Missing https://
   WORDPRESS_SITE1_URL=https://example.com/  # Extra trailing slash
   ```

2. **Verify HTTPS certificate**:
   ```bash
   curl -v https://your-site.com 2>&1 | grep SSL
   ```

3. **Check firewall rules**:
   - Ensure port 443 (HTTPS) is open
   - Check if IP is whitelisted (if using server firewall)

4. **Test from different network**:
   - Try from different IP address
   - Check if WordPress site blocks data center IPs

### WordPress REST API Not Available

**Symptoms**: `404 Not Found` on `/wp-json/`

**Diagnosis**:
```bash
curl https://your-site.com/wp-json/
```

**Solutions**:

1. **Check permalink settings**:
   - Go to: WordPress Admin → Settings → Permalinks
   - Select any option except "Plain"
   - Click "Save Changes"

2. **Check .htaccess**:
   ```apache
   # Must have these rules
   RewriteEngine On
   RewriteRule ^index\.php$ - [L]
   RewriteCond %{REQUEST_FILENAME} !-f
   RewriteCond %{REQUEST_FILENAME} !-d
   RewriteRule . /index.php [L]
   ```

3. **Check nginx configuration** (if using nginx):
   ```nginx
   location / {
       try_files $uri $uri/ /index.php?$args;
   }
   ```

---

## Authentication Problems

### Error: "Invalid username or password"

**Cause**: Application Password not configured correctly.

**Solution**:

1. **Verify Application Password is enabled**:
   - WordPress 5.6+ only
   - Go to: Users → Your Profile
   - Look for "Application Passwords" section

2. **Generate new Application Password**:
   ```
   Name: MCP Server
   Click: Add New Application Password
   Copy password (format: xxxx xxxx xxxx xxxx xxxx xxxx)
   ```

3. **Update .env file**:
   ```bash
   WORDPRESS_SITE1_APP_PASSWORD=xxxx xxxx xxxx xxxx xxxx xxxx
   ```

4. **Important notes**:
   - Include spaces in password
   - Password is one-time display only
   - Each application needs unique password

### Error: "Application Passwords not available"

**Cause**: WordPress version < 5.6 or disabled by plugin/filter.

**Solutions**:

1. **Update WordPress**:
   ```bash
   # Via WP-CLI
   wp core update
   ```

2. **Check if disabled by plugin/filter**:
   - Some security plugins disable Application Passwords
   - Check: Security Plugins → Settings → Application Passwords

3. **Enable via code** (add to `functions.php`):
   ```php
   // Remove filter that may disable it
   add_filter('wp_is_application_passwords_available', '__return_true');
   ```

### WooCommerce Authentication Failed

**Cause**: Invalid Consumer Key/Secret.

**Solution**:

1. **Regenerate API keys**:
   - WooCommerce → Settings → Advanced → REST API
   - Add Key
   - Permissions: Read/Write
   - Copy both Consumer Key and Consumer Secret

2. **Verify format in .env**:
   ```bash
   WORDPRESS_SITE1_WC_CONSUMER_KEY=ck_xxxxxxxxxxxxxxxxxxxx
   WORDPRESS_SITE1_WC_CONSUMER_SECRET=cs_xxxxxxxxxxxxxxxxxxxx
   ```

3. **Check permissions**:
   - User must have `manage_woocommerce` capability
   - Keys must be for admin user

---

## Rate Limiting Issues

### Error: "Rate limit exceeded"

**Symptoms**: HTTP 429, "Too many requests"

**Diagnosis**:
```bash
# Check rate limit stats
python -c "
from src.core.rate_limiter import RateLimiter
limiter = RateLimiter()
print(limiter.get_stats())
"
```

**Solutions**:

1. **Adjust rate limits** in `.env`:
   ```bash
   RATE_LIMIT_PER_MINUTE=120  # Increase from 60
   RATE_LIMIT_PER_HOUR=2000   # Increase from 1000
   RATE_LIMIT_PER_DAY=20000   # Increase from 10000
   ```

2. **Reset rate limiter**:
   ```bash
   # Via MCP tool
   reset_rate_limit()

   # Or restart server
   docker compose restart  # If using Docker
   ```

3. **Distribute requests**:
   - Add delays between bulk operations
   - Use batching for large operations

### Rate Limit Not Working

**Symptoms**: No rate limiting being applied.

**Solution**:

Check rate limiter initialization in logs:
```bash
grep "Rate limiter" logs/audit.log
```

Ensure rate limiter is enabled:
```python
# In .env
RATE_LIMITING_ENABLED=true
```

---

## Docker Problems

### Container Won't Start

**Symptoms**: `docker compose up` fails, container exits immediately.

**Diagnosis**:
```bash
# Check container logs
docker compose logs

# Check container exit code
docker compose ps -a
```

**Common Solutions**:

1. **Port already in use**:
   ```bash
   # Check what's using port 8000
   lsof -i :8000  # Linux/Mac
   netstat -ano | findstr :8000  # Windows

   # Change port in docker-compose.yml
   ports:
     - "8080:8000"  # Use 8080 instead
   ```

2. **Invalid environment variables**:
   ```bash
   # Validate .env file
   docker compose config
   ```

3. **Permission issues**:
   ```bash
   # Fix permissions
   sudo chown -R 1000:1000 logs/
   ```

### Container Running but Not Accessible

**Symptoms**: Container status shows "Up" but health check fails.

**Diagnosis**:
```bash
# Check container health
docker compose ps

# Test from inside container
docker compose exec mcp-server curl localhost:8000/health

# Check container network
docker compose exec mcp-server cat /etc/hosts
```

**Solutions**:

1. **Check binding address**:
   - Should bind to `0.0.0.0`, not `127.0.0.1`
   - Update `server.py` if needed

2. **Check firewall**:
   ```bash
   # Allow Docker network
   sudo ufw allow from 172.0.0.0/8
   ```

### High Memory Usage

**Symptoms**: Container using excessive RAM.

**Solutions**:

1. **Set memory limits** in `docker-compose.yml`:
   ```yaml
   services:
     mcp-server:
       deploy:
         resources:
           limits:
             memory: 512M
   ```

2. **Optimize logging**:
   ```bash
   # Reduce log level
   LOG_LEVEL=WARNING
   ```

3. **Clear cache**:
   ```bash
   docker system prune -a
   ```

---

## Performance Issues

### Slow Response Times

**Symptoms**: Tools taking > 5 seconds to respond.

**Diagnosis**:
```bash
# Check health metrics
python -c "
from core.health import HealthMonitor
monitor = HealthMonitor()
print(monitor.get_all_health())
"
```

**Solutions**:

1. **Check WordPress site performance**:
   ```bash
   # Test direct WordPress API
   time curl https://your-site.com/wp-json/wp/v2/posts
   ```

2. **Enable caching** on WordPress:
   - Install caching plugin (WP Super Cache, W3 Total Cache)
   - Enable object caching (Redis/Memcached)

3. **Optimize database**:
   ```bash
   # Use WP-CLI tool
   wordpress_wp_db_optimize(site="site1")
   ```

4. **Reduce payload size**:
   ```python
   # Request fewer items
   wordpress_list_posts(site="site1", per_page=10)  # Instead of 100
   ```

### High CPU Usage

**Symptoms**: Server using 100% CPU.

**Solutions**:

1. **Check for infinite loops** in logs:
   ```bash
   tail -f logs/audit.log | grep ERROR
   ```

2. **Limit concurrent requests**:
   ```bash
   # In .env
   MAX_CONCURRENT_REQUESTS=5
   ```

3. **Optimize queries**:
   - Use pagination
   - Filter results
   - Cache responses

---

## Tool Registration Issues

### Error: "Tool not found"

**Symptoms**: MCP reports tool doesn't exist.

**Diagnosis**:
```bash
# List all registered tools
python -c "
from server import mcp
tools = app.list_tools()
for tool in tools:
    print(tool['name'])
"
```

**Solutions**:

1. **Check site configuration**:
   ```bash
   # Ensure site is configured in .env
   grep "WORDPRESS_SITE1" .env
   ```

2. **Verify plugin loaded**:
   ```bash
   # Check logs for plugin initialization
   grep "plugin loaded" logs/audit.log
   ```

3. **Restart server**:
   ```bash
   # Tools are registered at startup
   docker compose restart
   ```

### Duplicate Tools

**Symptoms**: Same tool name registered multiple times.

**Cause**: Multiple plugins or sites with same alias.

**Solution**:

1. **Check for duplicate aliases**:
   ```bash
   grep "ALIAS" .env | sort
   ```

2. **Ensure unique aliases**:
   ```bash
   WORDPRESS_SITE1_ALIAS=mainsite
   WORDPRESS_SITE2_ALIAS=shop  # Not mainsite
   ```

---

## Logging and Debugging

### Enable Debug Logging

```bash
# In .env
LOG_LEVEL=DEBUG

# Restart server
docker compose restart
```

### View Real-time Logs

```bash
# Audit logs
tail -f logs/audit.log

# Application logs
docker compose logs -f

# Filter for errors
grep ERROR logs/audit.log

# Filter for specific site
grep "site1" logs/audit.log
```

### Common Log Patterns

**Successful request**:
```json
{
  "timestamp": "2025-11-11T10:30:00Z",
  "event_type": "tool_execution",
  "level": "INFO",
  "event": "wordpress_list_posts",
  "details": {
    "site": "site1",
    "status": "success"
  }
}
```

**Failed request**:
```json
{
  "timestamp": "2025-11-11T10:30:00Z",
  "event_type": "tool_execution",
  "level": "ERROR",
  "event": "wordpress_list_posts",
  "details": {
    "site": "site1",
    "error": "Connection timeout",
    "status": "failed"
  }
}
```

### Debugging Tips

1. **Test with curl**:
   ```bash
   # Test WordPress directly
   curl -u "admin:xxxx xxxx xxxx xxxx xxxx xxxx" \
     https://your-site.com/wp-json/wp/v2/posts
   ```

2. **Check environment loading**:
   ```python
   python -c "
   from dotenv import load_dotenv
   import os
   load_dotenv()
   print(os.getenv('WORDPRESS_SITE1_URL'))
   "
   ```

3. **Test individual components**:
   ```bash
   # Test WordPress plugin
   pytest tests/test_wordpress_plugin.py -v

   # Test rate limiter
   pytest tests/test_rate_limiter.py -v
   ```

---

## Getting Help

### Before Asking for Help

1. **Check logs**:
   ```bash
   tail -50 logs/audit.log
   ```

2. **Run health check**:
   ```bash
   python -c "
   from core.health import HealthMonitor
   monitor = HealthMonitor()
   print(monitor.check_all_projects())
   "
   ```

3. **Verify configuration**:
   ```bash
   # Mask sensitive data
   grep -v "PASSWORD\|KEY\|SECRET" .env
   ```

4. **Test connectivity**:
   ```bash
   curl -I https://your-wordpress-site.com
   ```

### What to Include in Bug Reports

1. **Environment information**:
   - Python version: `python --version`
   - Docker version: `docker --version`
   - OS: `uname -a` (Linux/Mac) or `systeminfo` (Windows)

2. **Error messages**:
   - Full error output
   - Stack trace if available
   - Relevant log entries

3. **Configuration** (mask sensitive data):
   - Relevant .env variables
   - docker-compose.yml modifications
   - WordPress/WooCommerce versions

4. **Steps to reproduce**:
   - Exact commands run
   - Expected vs actual behavior
   - Frequency (always, sometimes, once)

### Contact Information

**Email**: hello@mcphub.dev

**Subject format**: `[BUG] Brief description`

**Example**:
```
Subject: [BUG] wordpress_list_posts returns 403 error

Environment:
- Python 3.11.5
- Docker 24.0.6
- WordPress 6.4
- Ubuntu 22.04

Issue:
wordpress_list_posts(site="site1") returns 403 Forbidden

Steps to reproduce:
1. Configure WORDPRESS_SITE1_* in .env
2. Run python server.py
3. Call wordpress_list_posts(site="site1", per_page=10)
4. Receive 403 error

Logs:
[Include relevant log entries]

Configuration:
WORDPRESS_SITE1_URL=https://example.com
WORDPRESS_SITE1_USERNAME=admin
[Application password masked]
```

---

---
