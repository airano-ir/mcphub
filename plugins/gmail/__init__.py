"""Gmail Plugin — read + manage a Gmail inbox via OAuth (gmail.modify scope).

Admin-only plugin (like Coolify): tools are reachable via the admin /mcp
endpoint and the per-user /u/{user_id}/{alias}/mcp endpoint, not via a
public /gmail/mcp mount. Per-site credentials (client_id, client_secret,
refresh_token) are encrypted in SQLite by SiteManager and decrypted at call
time — never read from env vars or a volume file.
"""
