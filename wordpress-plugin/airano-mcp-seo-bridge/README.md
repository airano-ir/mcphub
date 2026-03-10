# SEO API Bridge - WordPress Plugin

**Version:** 1.3.0
**Requires:** WordPress 5.0+, PHP 7.4+
**License:** GPLv2 or later

## Description

SEO API Bridge is a comprehensive WordPress plugin that exposes Rank Math SEO and Yoast SEO meta fields via dedicated REST API endpoints. This enables MCP servers, AI agents, and other applications to read and write SEO metadata programmatically for posts, pages, and WooCommerce products.

## What's New in 1.3.0

- **Full REST API Endpoints** - GET and POST operations for all post types
- **Product SEO Support** - Complete WooCommerce product SEO management
- **Simplified Integration** - Direct API calls instead of meta field manipulation
- **Better Error Handling** - Proper validation and error responses

## Features

- **Rank Math SEO Support** - Full access to all Rank Math meta fields
- **Yoast SEO Support** - Full access to all Yoast SEO meta fields
- **WooCommerce Compatible** - Works with product post types
- **Secure** - Requires proper authentication and edit_posts capability
- **Auto-Detection** - Automatically detects which SEO plugin is active
- **Health Check Endpoint** - Dedicated API endpoint for plugin detection
- **Zero Configuration** - Works out of the box after activation

## Supported SEO Fields

### Rank Math SEO

| Category | Field | Description |
|----------|-------|-------------|
| Core | `rank_math_focus_keyword` | Focus keyword |
| Core | `rank_math_title` | Meta title |
| Core | `rank_math_description` | Meta description |
| Core | `rank_math_additional_keywords` | Additional keywords |
| Advanced | `rank_math_canonical_url` | Canonical URL |
| Advanced | `rank_math_robots` | Robots meta directives |
| Advanced | `rank_math_breadcrumb_title` | Breadcrumb title |
| Open Graph | `rank_math_facebook_title` | OG title |
| Open Graph | `rank_math_facebook_description` | OG description |
| Open Graph | `rank_math_facebook_image` | OG image URL |
| Open Graph | `rank_math_facebook_image_id` | OG image ID |
| Twitter | `rank_math_twitter_title` | Twitter title |
| Twitter | `rank_math_twitter_description` | Twitter description |
| Twitter | `rank_math_twitter_image` | Twitter image URL |
| Twitter | `rank_math_twitter_image_id` | Twitter image ID |
| Twitter | `rank_math_twitter_card_type` | Card type (summary, summary_large_image) |

### Yoast SEO

| Category | Field | Description |
|----------|-------|-------------|
| Core | `_yoast_wpseo_focuskw` | Focus keyword |
| Core | `_yoast_wpseo_title` | Meta title |
| Core | `_yoast_wpseo_metadesc` | Meta description |
| Advanced | `_yoast_wpseo_canonical` | Canonical URL |
| Advanced | `_yoast_wpseo_meta-robots-noindex` | Noindex setting |
| Advanced | `_yoast_wpseo_meta-robots-nofollow` | Nofollow setting |
| Advanced | `_yoast_wpseo_bctitle` | Breadcrumb title |
| Open Graph | `_yoast_wpseo_opengraph-title` | OG title |
| Open Graph | `_yoast_wpseo_opengraph-description` | OG description |
| Open Graph | `_yoast_wpseo_opengraph-image` | OG image URL |
| Open Graph | `_yoast_wpseo_opengraph-image-id` | OG image ID |
| Twitter | `_yoast_wpseo_twitter-title` | Twitter title |
| Twitter | `_yoast_wpseo_twitter-description` | Twitter description |
| Twitter | `_yoast_wpseo_twitter-image` | Twitter image URL |
| Twitter | `_yoast_wpseo_twitter-image-id` | Twitter image ID |

## Installation

### Method 1: Upload via WordPress Admin

1. Download `seo-api-bridge.zip` from [Releases](https://github.com/airano-ir/mcphub)
2. Go to WordPress Admin > Plugins > Add New > Upload Plugin
3. Upload the ZIP file and click "Install Now"
4. Click "Activate Plugin"

### Method 2: FTP/SSH Upload

1. Upload the `seo-api-bridge` folder to `/wp-content/plugins/`
2. Go to WordPress Admin > Plugins
3. Find "SEO API Bridge" and click "Activate"

### Method 3: WP-CLI

```bash
cd /var/www/html/wp-content/plugins/
# Copy the plugin folder here
wp plugin activate seo-api-bridge
```

## REST API Endpoints

All endpoints require **WordPress Application Password** authentication.

### Status Endpoint

**GET** `/wp-json/seo-api-bridge/v1/status`

```bash
curl -X GET "https://yoursite.com/wp-json/seo-api-bridge/v1/status" \
  -u "username:application_password"
```

**Response:**
```json
{
  "plugin": "SEO API Bridge",
  "version": "1.3.0",
  "active": true,
  "seo_plugins": {
    "rank_math": { "active": true, "version": "1.0.257" },
    "yoast": { "active": false, "version": null }
  },
  "supported_post_types": ["post", "page", "product"],
  "message": "SEO API Bridge is active and working with Rank Math SEO."
}
```

### Post SEO Endpoints

**GET** `/wp-json/seo-api-bridge/v1/posts/{id}/seo` — Get SEO metadata for a post

**POST** `/wp-json/seo-api-bridge/v1/posts/{id}/seo` — Update SEO metadata for a post

```bash
# Get post SEO
curl -X GET "https://yoursite.com/wp-json/seo-api-bridge/v1/posts/123/seo" \
  -u "username:application_password"

# Update post SEO
curl -X POST "https://yoursite.com/wp-json/seo-api-bridge/v1/posts/123/seo" \
  -u "username:application_password" \
  -H "Content-Type: application/json" \
  -d '{"focus_keyword": "wordpress", "seo_title": "My Title"}'
```

### Page SEO Endpoints

**GET** `/wp-json/seo-api-bridge/v1/pages/{id}/seo`

**POST** `/wp-json/seo-api-bridge/v1/pages/{id}/seo`

### Product SEO Endpoints (WooCommerce)

**GET** `/wp-json/seo-api-bridge/v1/products/{id}/seo`

**POST** `/wp-json/seo-api-bridge/v1/products/{id}/seo`

```bash
curl -X POST "https://yoursite.com/wp-json/seo-api-bridge/v1/products/1217/seo" \
  -u "username:application_password" \
  -H "Content-Type: application/json" \
  -d '{"focus_keyword": "product keyword", "seo_title": "Product Title"}'
```

### Alternative: Standard WordPress REST API

The plugin also registers all SEO meta fields on standard WordPress REST API endpoints. You can read/write SEO data directly via:

- `GET/POST /wp-json/wp/v2/posts/{id}` — SEO fields in the `meta` object
- `GET/POST /wp-json/wp/v2/pages/{id}`
- `GET/POST /wp-json/wp/v2/products/{id}` (WooCommerce)

```bash
# Read SEO fields via standard endpoint
curl -X GET "https://yoursite.com/wp-json/wp/v2/posts/123" \
  -u "username:application_password"

# Update SEO via standard endpoint
curl -X POST "https://yoursite.com/wp-json/wp/v2/posts/123" \
  -u "username:application_password" \
  -H "Content-Type: application/json" \
  -d '{"meta": {"rank_math_focus_keyword": "wordpress optimization"}}'
```

## Usage with MCP Hub

This plugin is designed to work with [MCP Hub](https://github.com/airano-ir/mcphub).

```javascript
// Get product SEO
const seo = await mcp.wordpress_get_product_seo({
  site: "yoursite",
  product_id: 1217
});

// Update product SEO
await mcp.wordpress_update_product_seo({
  site: "yoursite",
  product_id: 1217,
  focus_keyword: "keyword",
  seo_title: "Title",
  meta_description: "Description"
});
```

```python
# Get post SEO data
result = await mcp.call_tool(
    "wordpress_get_post_seo",
    {"site": "yoursite", "post_id": 123}
)

# Update post SEO
result = await mcp.call_tool(
    "wordpress_update_post_seo",
    {
        "site": "yoursite",
        "post_id": 123,
        "focus_keyword": "wordpress seo",
        "seo_title": "Complete SEO Guide",
        "meta_description": "Learn WordPress SEO..."
    }
)
```

## Verification

1. **Admin Notice:** After activation, visit the Plugins page to see a status notice indicating which SEO plugin was detected.

2. **Status Endpoint:**
```bash
curl -X GET "https://your-site.com/wp-json/seo-api-bridge/v1/status" \
  -u "username:application_password"
```

3. **REST API Test:**
```bash
curl -X GET "https://your-site.com/wp-json/wp/v2/posts/1" \
  -u "username:application_password"
```

4. **MCP Health Check:** The MCP server automatically detects the plugin using the status endpoint.

## Security

- All meta fields require authentication via Application Passwords
- Write access requires `edit_posts` capability
- Read access follows WordPress post visibility rules
- No sensitive data exposed without proper permissions

## Troubleshooting

### MCP Server Cannot Detect Plugin

1. Upgrade to v1.1.0+ (has dedicated health check endpoint)
2. Restart MCP server
3. Test endpoint: `curl "https://your-site.com/wp-json/seo-api-bridge/v1/status" -u "user:pass"`

### SEO Plugin Not Detected

1. Verify Rank Math or Yoast SEO is installed and activated
2. Deactivate and reactivate SEO API Bridge
3. Check PHP error logs for warnings

### Meta Fields Not Appearing in REST API

1. Ensure you're authenticated (use Application Password)
2. Check user has `edit_posts` permission
3. Verify the post type is supported (post, page, product)

## Compatibility

- WordPress 5.0+
- PHP 7.4+
- Rank Math SEO 1.0+
- Yoast SEO 14.0+
- WooCommerce 5.0+ (for product support)
- Classic Editor & Gutenberg
- Multisite compatible

## Changelog

### 1.3.0 (2025-02-18)
- Added REST API endpoints for posts, pages, and products (GET/POST operations)
- Added authentication requirement for all endpoints
- Fixed `rank_math_title` meta key registration
- Fixed output escaping for WordPress.org compliance

### 1.2.0 (2025-02-15)
- Enhanced WooCommerce product support
- Improved MariaDB compatibility for meta field queries

### 1.1.0 (2025-01-10)
- Added health check REST API endpoint `/seo-api-bridge/v1/status`
- Direct plugin detection without requiring posts/products
- Better compatibility with sites that have no content
- Returns SEO plugin versions in status endpoint

### 1.0.0 (2025-01-10)
- Initial release
- Rank Math SEO support (15 meta fields)
- Yoast SEO support (15 meta fields)
- WooCommerce product support
- Auto-detection of active SEO plugins

## Support

- **Plugin issues:** [GitHub Issues](https://github.com/airano-ir/mcphub/issues)
- **MCP Server:** [MCP Hub Documentation](https://github.com/airano-ir/mcphub)
- **Rank Math SEO:** [Rank Math Support](https://rankmath.com/support/)
- **Yoast SEO:** [Yoast Support](https://yoast.com/help/)

## License

GPLv2 or later - See [LICENSE](https://www.gnu.org/licenses/gpl-2.0.html) for details
