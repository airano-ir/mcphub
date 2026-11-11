# WordPress and WooCommerce Least-Privilege Recipes

Use the smallest tool surface that completes the user task. Add write or
specialist access only when the agent must change that part of the site.

## Quick Matrix

| Task | Minimum useful access | Safe by default | Usually unnecessary |
|---|---|---|---|
| Blog or editorial article without product context | WordPress content read/write: posts, pages, categories, tags, media | Draft/update posts, upload and attach media | WooCommerce, specialist/admin tools |
| Product-aware article, buying guide, SEO roundup | WordPress content write + WooCommerce read | Read live products, stock, prices, product categories/tags, images, permalinks | WooCommerce product write, order/customer tools, specialist/admin tools |
| WooCommerce analytics for content agents | WooCommerce read reports + `list_orders(summary=true)` when order samples are needed | Aggregate/top-seller facts without billing, shipping, email, payment, transaction IDs | `summary=false`, `get_order`, customer tools |
| Product catalog management | WooCommerce product read/write + media tools if images are changed | Create/update products, prices, stock, categories, tags, images | WordPress post publishing unless content is in scope |
| Media upload from chat/local files | WordPress media write, preferably chunked upload start/finish | Server-side intake avoids large base64 payloads in tool calls | Plugin/theme install tools |
| AI image generation for content | WordPress media write + configured image provider key | Generate/upload media, attach to posts/products | Provider keys when the user already has a file or URL |
| Plugin/theme/site maintenance | WordPress Specialist/admin on a backed-up site, ideally staging | Plugin/theme install/update, cache, transients, DB checks | Content or WooCommerce order/customer access |

## Recipes

### Blog or Editorial Article

Grant WordPress content tools that can list previous posts, create drafts,
update posts/pages, manage categories/tags, and upload media.

Do not grant WooCommerce unless the agent needs live product context. A writer
does not need plugin/theme install, user admin, DB maintenance, or order data.

### Product-Aware Content

Grant WordPress content write plus WooCommerce read. The agent can discover
recent or in-stock products with:

```text
woocommerce_list_products(status="publish", stock_status="instock", orderby="date", order="desc")
woocommerce_list_products(category=<id>, orderby="modified", order="desc")
woocommerce_list_products(tag=<id>, status="publish")
```

The product list response is designed for discovery: status, stock, categories,
tags, first image, short description, permalink, modified date, and compact
price summary. Fetch a single product only after narrowing candidates.

### WooCommerce Analytics and Order Summaries

For content and analytics agents, prefer aggregate tools:

```text
woocommerce_get_top_sellers(period="month")
woocommerce_list_orders(summary=true, include_line_items=true)
```

`get_top_sellers` returns aggregate product totals and falls back to order line
items if WooCommerce reports are empty or unavailable. The fallback does not
include customer names, emails, billing/shipping addresses, payment labels,
transaction IDs, or customer notes.

`list_orders` defaults to `summary=true`. Use `summary=false` only for explicit
operational/admin tasks where customer or payment details are required.

### Product Catalog Management

Grant WooCommerce product write when the agent must create or update products,
prices, stock, descriptions, product categories, product tags, attributes, or
images. Add WordPress media write when the workflow includes uploading or
attaching product images.

Do not grant WordPress post write unless the same agent must publish content.

### Media Upload

If the user provides a public HTTPS URL, use URL upload tools. If the user
provides a local/chat attachment or large file, prefer the HTTP intake returned
by the chunked start tool:

```text
wordpress_upload_media_chunked_start(filename, total_bytes, mime, sha256)
PUT upload.url with the same MCP bearer token
wordpress_upload_media_chunked_finish(session_id, title?, alt_text?, attach_to_post?, set_featured?)
```

This keeps large bytes out of the chat/tool payload and lets MCPHub forward the
completed file through the normal WordPress media path.

### Specialist/Admin Maintenance

Use WordPress Specialist/admin tools only for maintenance tasks such as
plugin/theme install or update, cache purge, transient cleanup, site health,
DB checks, or layout/theme operations. Prefer staging and current backups.

These tools are not needed for normal editorial content, product discovery, or
privacy-safe WooCommerce analytics.
