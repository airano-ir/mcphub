"""Cloudflare Plugin — DNS, Workers, KV, R2 and cache management via the Cloudflare API v4.

Static-credential plugin (per-site ``api_token``). Public users can add
their own Cloudflare account with a scoped API token. Tools are classified
by universal scope tiers (``read`` / ``write`` / ``admin``) so API-key
scope presets and per-site toggles apply exactly like other plugins:

- ``read``   — inventory + diagnostics (zones, DNS, workers, KV, R2, user)
- ``write``  — non-destructive changes (create/update DNS, KV put,
               create namespace/bucket, cache purge)
- ``admin``  — destructive operations (delete DNS record, KV key/namespace,
               R2 bucket, Workers script)
"""
