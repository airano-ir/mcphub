#!/usr/bin/env python3
"""READ-ONLY diagnostic for the "sites not visible / Site not found" issue.

Run INSIDE the mcphub container (it imports the app's own encryption module):

    cd /app && python scripts/diagnose_sites.py

It NEVER writes to the database and NEVER prints secret values — only
lengths/fingerprints — so it is safe to paste output back into chat.
"""

import hashlib
import json
import os
import sqlite3
from pathlib import Path

DB_PATH = os.getenv("DATABASE_PATH") or (
    "/app/data/mcphub.db" if Path("/app").exists() else "data/mcphub.db"
)


def fp(val: str | None) -> str:
    """Short, non-reversible fingerprint so we can compare keys without leaking them."""
    if not val:
        return "<EMPTY/UNSET>"
    digest = hashlib.sha256(val.encode()).hexdigest()[:8]
    return f"set (len={len(val)}, sha256[:8]={digest})"


print("=" * 70)
print("ENV VARS (presence only — values never printed)")
print("=" * 70)
for var in (
    "ENCRYPTION_KEY",
    "DASHBOARD_SESSION_SECRET",
    "OAUTH_JWT_SECRET_KEY",
    "ADMIN_EMAILS",
    "DATABASE_PATH",
    "DISABLE_MASTER_KEY_LOGIN",
    "PUBLIC_URL",
    "OAUTH_BASE_URL",
):
    print(
        f"  {var:26s}: {fp(os.getenv(var)) if var not in ('ADMIN_EMAILS','DATABASE_PATH','DISABLE_MASTER_KEY_LOGIN','PUBLIC_URL','OAUTH_BASE_URL') else (os.getenv(var) or '<EMPTY/UNSET>')}"
    )

print(f"\n  Resolved DB path : {DB_PATH}")
print(f"  DB exists        : {Path(DB_PATH).exists()}")
if Path(DB_PATH).exists():
    print(f"  DB size (bytes)  : {Path(DB_PATH).stat().st_size}")

if not Path(DB_PATH).exists():
    print("\n!! Database file does not exist at this path — wrong volume / DATABASE_PATH.")
    raise SystemExit(0)

con = sqlite3.connect(DB_PATH)
con.row_factory = sqlite3.Row

print("\n" + "=" * 70)
print("USERS")
print("=" * 70)
users = list(
    con.execute("SELECT id, email, provider, provider_id, role, created_at, last_login FROM users")
)
for u in users:
    print(
        f"  id={u['id']}  email={u['email']}  provider={u['provider']}  role={u['role']}  last_login={u['last_login']}"
    )
print(f"  -> total users: {len(users)}")

print("\n" + "=" * 70)
print("SITES (credentials blob NOT shown)")
print("=" * 70)
sites = list(
    con.execute(
        "SELECT id, user_id, plugin_type, alias, url, status, length(credentials) AS clen FROM sites"
    )
)
for s in sites:
    print(
        f"  site_id={s['id']}  user_id={s['user_id']}  type={s['plugin_type']}  alias={s['alias']}  status={s['status']}  cred_bytes={s['clen']}"
    )
print(f"  -> total sites: {len(sites)}")

print("\n" + "=" * 70)
print("USER API KEYS (hash NOT shown)")
print("=" * 70)
keys = list(
    con.execute("SELECT id, user_id, name, key_prefix, site_id, created_at FROM user_api_keys")
)
for k in keys:
    site_owner = "—"
    if k["site_id"]:
        row = con.execute("SELECT user_id FROM sites WHERE id=?", (k["site_id"],)).fetchone()
        site_owner = row["user_id"] if row else "MISSING-SITE"
    flag = ""
    if k["site_id"] and site_owner not in ("—", "MISSING-SITE") and site_owner != k["user_id"]:
        flag = "  <-- KEY.user_id != SITE.user_id  (MISMATCH)"
    if site_owner == "MISSING-SITE":
        flag = "  <-- referenced site row does not exist"
    print(
        f"  key={k['name']!r}  key_user={k['user_id']}  site_id={k['site_id']}  site_owner={site_owner}{flag}"
    )
print(f"  -> total user keys: {len(keys)}")

print("\n" + "=" * 70)
print("DECRYPTION TEST (does current ENCRYPTION_KEY match what sites were encrypted with?)")
print("=" * 70)
if not os.getenv("ENCRYPTION_KEY"):
    print("  ENCRYPTION_KEY is unset — cannot test. Site management is disabled in this state.")
elif not sites:
    print("  No site rows to test.")
else:
    try:
        from core.encryption import CredentialEncryption

        enc = CredentialEncryption(os.getenv("ENCRYPTION_KEY"))
        for s in sites:
            blob = con.execute("SELECT credentials FROM sites WHERE id=?", (s["id"],)).fetchone()[
                "credentials"
            ]
            try:
                creds = enc.decrypt_credentials(blob, s["id"])
                print(f"  site {s['alias']}: DECRYPT OK  (fields: {sorted(creds.keys())})")
            except Exception as e:
                print(f"  site {s['alias']}: DECRYPT FAILED -> {type(e).__name__}: {e}")
    except Exception as e:
        print(f"  Could not init encryption: {type(e).__name__}: {e}")

print("\n" + "=" * 70)
print("ADMIN PROJECT KEYS (data/api_keys.json — separate from user keys above)")
print("=" * 70)
akp = Path("/app/data/api_keys.json")
if not akp.exists():
    akp = Path("data/api_keys.json")
if akp.exists():
    try:
        data = json.loads(akp.read_text())
        print(f"  file: {akp}  total admin keys: {len(data)}")
        for _kid, k in data.items():
            print(
                f"    desc={k.get('description')!r}  project_id={k.get('project_id')}  scopes={k.get('scopes')}  revoked={k.get('revoked')}"
            )
    except Exception as e:
        print(f"  could not read {akp}: {e}")
else:
    print("  no admin api_keys.json found")

con.close()
print("\nDone. (read-only — nothing was modified)")
