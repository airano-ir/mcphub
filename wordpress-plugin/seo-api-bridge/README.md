# SEO API Bridge - WordPress Plugin

**Version:** 1.3.0
**Requires:** WordPress 5.0+, PHP 7.4+
**License:** GPLv2 or later

## Description

SEO API Bridge is a comprehensive WordPress plugin that exposes Rank Math SEO and Yoast SEO meta fields via dedicated REST API endpoints. This enables MCP servers, AI agents, and other applications to read and write SEO metadata programmatically for posts, pages, and WooCommerce products.

## What's New in 1.3.0

✨ **Full REST API Endpoints** - GET and POST operations for all post types
✨ **Product SEO Support** - Complete WooCommerce product SEO management
✨ **Simplified Integration** - Direct API calls instead of meta field manipulation
✨ **Better Error Handling** - Proper validation and error responses

## Features

- ✅ **Rank Math SEO Support** - Full access to all Rank Math meta fields
- ✅ **Yoast SEO Support** - Full access to all Yoast SEO meta fields
- ✅ **WooCommerce Compatible** - Works with product post types
- ✅ **Secure** - Requires proper authentication and edit_posts capability
- ✅ **Auto-Detection** - Automatically detects which SEO plugin is active
- ✅ **Health Check Endpoint** - NEW! Dedicated API endpoint for plugin detection
- ✅ **Zero Configuration** - Works out of the box after activation

## Supported SEO Fields

### Rank Math SEO

#### Core Fields
- `rank_math_focus_keyword` - Focus keyword
- `rank_math_title` - Meta title
- `rank_math_description` - Meta description
- `rank_math_additional_keywords` - Additional keywords

#### Advanced Fields
- `rank_math_canonical_url` - Canonical URL
- `rank_math_robots` - Robots meta directives
- `rank_math_breadcrumb_title` - Breadcrumb title

#### Open Graph (Facebook)
- `rank_math_facebook_title` - OG title
- `rank_math_facebook_description` - OG description
- `rank_math_facebook_image` - OG image URL
- `rank_math_facebook_image_id` - OG image ID

#### Twitter Card
- `rank_math_twitter_title` - Twitter title
- `rank_math_twitter_description` - Twitter description
- `rank_math_twitter_image` - Twitter image URL
- `rank_math_twitter_image_id` - Twitter image ID
- `rank_math_twitter_card_type` - Card type (summary, summary_large_image)

### Yoast SEO

#### Core Fields
- `_yoast_wpseo_focuskw` - Focus keyword
- `_yoast_wpseo_title` - Meta title
- `_yoast_wpseo_metadesc` - Meta description

#### Advanced Fields
- `_yoast_wpseo_canonical` - Canonical URL
- `_yoast_wpseo_meta-robots-noindex` - Noindex setting
- `_yoast_wpseo_meta-robots-nofollow` - Nofollow setting
- `_yoast_wpseo_bctitle` - Breadcrumb title

#### Open Graph
- `_yoast_wpseo_opengraph-title` - OG title
- `_yoast_wpseo_opengraph-description` - OG description
- `_yoast_wpseo_opengraph-image` - OG image URL
- `_yoast_wpseo_opengraph-image-id` - OG image ID

#### Twitter Card
- `_yoast_wpseo_twitter-title` - Twitter title
- `_yoast_wpseo_twitter-description` - Twitter description
- `_yoast_wpseo_twitter-image` - Twitter image URL
- `_yoast_wpseo_twitter-image-id` - Twitter image ID

## Installation

### Method 1: Manual Upload via WordPress Admin

1. Download the plugin folder
2. Create a ZIP file: `seo-api-bridge.zip`
3. Go to WordPress Admin → Plugins → Add New → Upload Plugin
4. Upload the ZIP file and click "Install Now"
5. Click "Activate Plugin"

### Method 2: FTP/SSH Upload

1. Upload the `seo-api-bridge` folder to `/wp-content/plugins/`
2. Go to WordPress Admin → Plugins
3. Find "SEO API Bridge" and click "Activate"

### Method 3: WP-CLI

```bash
# Via SSH to your WordPress container
cd /var/www/html/wp-content/plugins/
# Copy the plugin folder here
wp plugin activate seo-api-bridge
```

## REST API Endpoints

### Status Endpoint

**GET** `/wp-json/seo-api-bridge/v1/status`

Check plugin status and detected SEO plugins.

```bash
curl https://yoursite.com/wp-json/seo-api-bridge/v1/status
```

### Post SEO Endpoints

**GET** `/wp-json/seo-api-bridge/v1/posts/{id}/seo`

Get SEO metadata for a post.

**POST** `/wp-json/seo-api-bridge/v1/posts/{id}/seo`

Update SEO metadata for a post.

```bash
curl -X POST https://yoursite.com/wp-json/seo-api-bridge/v1/posts/123/seo \
  -H "Content-Type: application/json" \
  -d '{"focus_keyword": "wordpress", "seo_title": "My Title"}'
```

### Page SEO Endpoints

**GET** `/wp-json/seo-api-bridge/v1/pages/{id}/seo`

**POST** `/wp-json/seo-api-bridge/v1/pages/{id}/seo`

### Product SEO Endpoints (WooCommerce)

**GET** `/wp-json/seo-api-bridge/v1/products/{id}/seo`

Get SEO metadata for a WooCommerce product.

**POST** `/wp-json/seo-api-bridge/v1/products/{id}/seo`

Update SEO metadata for a WooCommerce product.

```bash
curl -X POST https://yoursite.com/wp-json/seo-api-bridge/v1/products/1217/seo \
  -H "Content-Type: application/json" \
  -d '{"focus_keyword": "product keyword", "seo_title": "Product Title"}'
```

## Usage with MCP Servers

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

**Benefits of this approach:**
1. ✅ **WordPress Best Practice** - Uses recommended core REST API functionality
2. ✅ **Zero Maintenance** - Leverages WordPress built-in features
3. ✅ **Universal Compatibility** - Works with all WordPress REST API clients
4. ✅ **Inherits Security** - Uses WordPress authentication and permissions
5. ✅ **Simpler Code** - No custom endpoints to maintain

**Standard Endpoints:**
- Posts/Pages: `/wp-json/wp/v2/posts/{id}` or `/wp-json/wp/v2/pages/{id}`
- Products: `/wp-json/wp/v2/products/{id}` (WooCommerce custom post type)

**SEO data is in the `meta` object:**
```json
{
  "id": 123,
  "title": {"rendered": "My Post"},
  "meta": {
    "rank_math_focus_keyword": "wordpress seo",
    "rank_math_title": "Complete SEO Guide",
    "rank_math_description": "Learn WordPress SEO best practices..."
  }
}
```

### Reading SEO Data

**Get Post with SEO Fields:**
```bash
GET /wp-json/wp/v2/posts/{id}
```

**Response includes:**
```json
{
  "id": 123,
  "title": {"rendered": "My Post"},
  "meta": {
    "rank_math_focus_keyword": "wordpress seo",
    "rank_math_title": "Complete WordPress SEO Guide",
    "rank_math_description": "Learn how to optimize your WordPress site...",
    "rank_math_facebook_title": "SEO Guide for Facebook",
    "rank_math_twitter_card_type": "summary_large_image"
  }
}
```

### Writing SEO Data

**Update Post SEO Fields:**
```bash
POST /wp-json/wp/v2/posts/{id}
Authorization: Basic [base64(username:application_password)]
Content-Type: application/json

{
  "meta": {
    "rank_math_focus_keyword": "wordpress optimization",
    "rank_math_title": "WordPress Optimization Tips",
    "rank_math_description": "Discover the best practices for WordPress optimization"
  }
}
```

### WooCommerce Products

**Get Product with SEO:**
```bash
GET /wp-json/wp/v2/products/{id}
```

**Update Product SEO:**
```bash
POST /wp-json/wp/v2/products/{id}
{
  "meta": {
    "rank_math_focus_keyword": "premium widget",
    "rank_math_description": "Buy the best premium widget online"
  }
}
```

## Usage with MCP Server

This plugin is designed to work with the [MCP Hub](https://github.com/airano-ir/mcphub).

### Example MCP Tool Usage

```python
# Get post SEO data
result = await mcp.call_tool(
    "wordpress_site1_get_post_seo",
    {"post_id": 123}
)

# Update post SEO
result = await mcp.call_tool(
    "wordpress_site1_update_post_seo",
    {
        "post_id": 123,
        "focus_keyword": "wordpress seo",
        "seo_title": "Complete SEO Guide",
        "meta_description": "Learn WordPress SEO..."
    }
)

# Update WooCommerce product SEO
result = await mcp.call_tool(
    "wordpress_site1_update_product_seo",
    {
        "product_id": 456,
        "focus_keyword": "premium widget",
        "meta_description": "Buy the best widget"
    }
)
```

## Verification

### Check if Plugin is Working

1. **Admin Notice:** After activation, you should see a success notice indicating which SEO plugin was detected

2. **Health Check Endpoint (v1.1.0+):**
```bash
# Check plugin status directly
curl -X GET "https://your-site.com/wp-json/seo-api-bridge/v1/status" \
  -u "username:application_password"
```

**Response:**
```json
{
  "plugin": "SEO API Bridge",
  "version": "1.1.0",
  "active": true,
  "seo_plugins": {
    "rank_math": {
      "active": true,
      "version": "1.0.257"
    },
    "yoast": {
      "active": false,
      "version": null
    }
  },
  "supported_post_types": ["post", "page", "product"],
  "message": "SEO API Bridge is active and working with Rank Math SEO."
}
```

3. **REST API Test:**
```bash
# Get any post and check if meta fields are present
curl -X GET "https://your-site.com/wp-json/wp/v2/posts/1" \
  -u "username:application_password"
```

4. **MCP Health Check:** The MCP server will automatically detect the plugin using the new endpoint

## Security

- ✅ All meta fields require authentication via Application Passwords
- ✅ Write access requires `edit_posts` capability
- ✅ Read access follows WordPress post visibility rules
- ✅ No sensitive data exposed without proper permissions

## Troubleshooting

### MCP Server Cannot Detect Plugin

**Issue:** MCP reports "SEO API Bridge plugin not detected" even though plugin is active

**Solution for v1.1.0+:**
1. **Upgrade to v1.1.0** - This version adds a dedicated health check endpoint
2. **Restart MCP server** - New detection logic will be used
3. **Test endpoint directly:**
   ```bash
   curl "https://your-site.com/wp-json/seo-api-bridge/v1/status" -u "user:pass"
   ```

**Solution for v1.0.0 (legacy):**
1. Create at least one post or product with SEO metadata set
2. The old detection requires checking actual content meta fields
3. Upgrade to v1.1.0 to avoid this requirement

### SEO Plugin Not Detected

**Issue:** Admin notice says "Neither Rank Math SEO nor Yoast SEO is detected"

**Solution:**
1. Verify Rank Math or Yoast SEO is installed and activated
2. Try deactivating and reactivating SEO API Bridge
3. Check PHP error logs for any warnings

### Meta Fields Not Appearing in REST API

**Issue:** `/wp-json/wp/v2/posts/{id}` doesn't show `meta` object

**Solution:**
1. Ensure you're authenticated (use Application Password)
2. Check that you have `edit_posts` permission
3. Verify the post type is supported (post, page, product)

### Fields Are Read-Only

**Issue:** Can read SEO fields but cannot update them

**Solution:**
1. Verify authentication credentials
2. Check user has `edit_posts` capability
3. Ensure you're using POST/PUT request, not GET

## Compatibility

- ✅ WordPress 5.0+
- ✅ PHP 7.4+
- ✅ Rank Math SEO 1.0+
- ✅ Yoast SEO 14.0+
- ✅ WooCommerce 5.0+ (for product support)
- ✅ Classic Editor & Gutenberg
- ✅ Multisite compatible

## Support

For issues related to:
- **This plugin:** [GitHub Issues](https://github.com/airano-ir/mcphub/issues)
- **MCP Server:** [MCP Server Documentation](https://github.com/airano-ir/mcphub)
- **Rank Math SEO:** [Rank Math Support](https://rankmath.com/support/)
- **Yoast SEO:** [Yoast Support](https://yoast.com/help/)

## Changelog

### 1.1.0 (2025-01-10)
- 🎉 **NEW:** Health check REST API endpoint `/seo-api-bridge/v1/status`
- 🎉 **NEW:** Direct plugin detection without requiring posts/products
- 🎉 **IMPROVEMENT:** Better compatibility with sites that have no content
- 🎉 **IMPROVEMENT:** Returns SEO plugin versions in status endpoint
- 🎉 **FIX:** MCP server can now detect plugin even with zero posts

### 1.0.0 (2025-01-10)
- Initial release
- Rank Math SEO support (15 meta fields)
- Yoast SEO support (15 meta fields)
- WooCommerce product support
- Auto-detection of active SEO plugins
- Admin notices for status

## License

GPLv2 or later - See [LICENSE](https://www.gnu.org/licenses/gpl-2.0.html) for details

## Credits

Developed for use with MCP Hub to enable AI-powered SEO content management.
