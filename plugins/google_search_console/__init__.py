"""Google Search Console Plugin — read-only GSC API via OAuth (webmasters.readonly).

Provides read-only tools for multi-property Search Console management:
- List accessible properties and permission levels
- List sitemaps and their submission status
- URL Inspection (index status, crawl data, mobile usability)
- Search Analytics queries with bounded dimensions/date ranges

OAuth credentials (access_token, refresh_token, token_expires_at) are stored
encrypted in SQLite by SiteManager and decrypted at call time. Token refresh
uses GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET from environment variables.
All tools are read-only — no write endpoints are called.
"""
