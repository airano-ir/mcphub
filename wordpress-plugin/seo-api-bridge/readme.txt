=== SEO API Bridge ===
Contributors: airano
Tags: seo, rest-api, rank-math, yoast, mcp
Requires at least: 5.0
Tested up to: 6.9
Requires PHP: 7.4
Stable tag: 1.3.0
License: GPLv2 or later
License URI: https://www.gnu.org/licenses/gpl-2.0.html

Exposes Rank Math SEO and Yoast SEO meta fields via WordPress REST API for use with MCP servers and AI agents.

== Description ==

SEO API Bridge is a WordPress plugin that exposes Rank Math SEO and Yoast SEO meta fields via dedicated REST API endpoints. This enables MCP servers, AI agents, and other applications to read and write SEO metadata programmatically for posts, pages, and WooCommerce products.

**Features:**

* **Rank Math SEO Support** — Full access to all Rank Math meta fields
* **Yoast SEO Support** — Full access to all Yoast SEO meta fields
* **WooCommerce Compatible** — Works with product post types
* **Secure** — Requires WordPress Application Password and edit_posts capability
* **Auto-Detection** — Automatically detects which SEO plugin is active
* **Status Endpoint** — Dedicated API endpoint for plugin and SEO detection
* **Zero Configuration** — Works out of the box after activation

**REST API Endpoints:**

* `GET/POST /wp-json/seo-api-bridge/v1/posts/{id}/seo` — Post SEO data
* `GET/POST /wp-json/seo-api-bridge/v1/pages/{id}/seo` — Page SEO data
* `GET/POST /wp-json/seo-api-bridge/v1/products/{id}/seo` — Product SEO data (WooCommerce)
* `GET /wp-json/seo-api-bridge/v1/status` — Plugin status and SEO detection

**Designed for [MCP Hub](https://github.com/airano-ir/mcphub)** — the AI-native management hub for WordPress and self-hosted services.

== Installation ==

1. Upload the `seo-api-bridge` folder to `/wp-content/plugins/`
2. Activate the plugin through the 'Plugins' menu in WordPress
3. Ensure either Rank Math SEO or Yoast SEO is active
4. The REST API endpoints are now available

== Frequently Asked Questions ==

= Which SEO plugins are supported? =

Rank Math SEO and Yoast SEO. The plugin auto-detects which one is active.

= Does it work with WooCommerce? =

Yes. Product SEO endpoints are available when WooCommerce is active.

= How is authentication handled? =

All endpoints require WordPress Application Password authentication and the `edit_posts` capability. POST requests require the same capability.

= Can I use this without MCP Hub? =

Yes. The REST API endpoints work with any application that can make HTTP requests with proper WordPress authentication.

== Changelog ==

= 1.3.0 =
* Added REST API endpoints for posts, pages, and products (GET/POST operations)
* Added authentication requirement for all endpoints
* Fixed rank_math_title meta key registration

= 1.2.0 =
* Enhanced WooCommerce product support
* Improved MariaDB compatibility

= 1.1.0 =
* Added status endpoint for plugin detection
* Improved error handling

= 1.0.0 =
* Initial release with Rank Math and Yoast SEO support

== Upgrade Notice ==

= 1.3.0 =
GET endpoints now require authentication (edit_posts capability). Update your API clients if needed.
