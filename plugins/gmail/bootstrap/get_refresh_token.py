#!/usr/bin/env python3
"""One-time Gmail OAuth bootstrap — obtain a long-lived refresh token.

Run this ONCE on a machine with a browser to produce the refresh token you
then paste into the MCPHub dashboard's "Add Gmail site" form. The MCPHub
plugin itself never serves an OAuth callback — it only refreshes tokens.

Prerequisites
-------------
1. In Google Cloud Console:
   - Create an OAuth client ID of type **Desktop app** (NOT Web app).
   - Enable the **Gmail API** for the project.
   - OAuth consent screen: User type External, status **Testing**,
     add your own Google email as a **test user**.
2. ``pip install requests`` (only dependency; uses stdlib for the rest).

Usage
-----
::

    python get_refresh_token.py --client-id <ID> --client-secret <SECRET>

It opens a browser to Google's consent screen
(scope ``https://www.googleapis.com/auth/gmail.modify``, ``access_type=offline``,
``prompt=consent``), receives the authorization code on a loopback
``http://localhost:8733/callback``, exchanges it for tokens, and prints the
``refresh_token``.

``gmail.modify`` is a sensitive scope. Keeping the OAuth client in "Testing"
mode + your own email as a test user lets it work WITHOUT Google's
verification process — fine for personal use.

The refresh token is long-lived (does not expire unless you revoke it).
Store it in MCPHub (encrypted in SQLite), never in a volume file.
"""

from __future__ import annotations

import argparse
import http.server
import json
import sys
import threading
import urllib.parse
import webbrowser

try:
    import requests  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - bootstrap-time hint
    sys.exit("Missing dependency: pip install requests")

# Loopback redirect — Desktop OAuth clients use http://localhost:<port>.
REDIRECT_HOST = "127.0.0.1"
REDIRECT_PORT = 8733
REDIRECT_URI = f"http://{REDIRECT_HOST}:{REDIRECT_PORT}/callback"

# gmail.modify = read + manage (list/get/search/labels/attachments,
# mark read/unread, add/remove labels, trash). Superset of gmail.readonly.
SCOPE = "https://www.googleapis.com/auth/gmail.modify"

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"


def build_consent_url(client_id: str) -> str:
    """Build the Google consent URL with offline + consent prompt."""
    params = {
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",
        "prompt": "consent",  # force consent so a refresh_token is returned
    }
    return f"{AUTH_URL}?{urllib.parse.urlencode(params)}"


def wait_for_code() -> str:
    """Start a loopback HTTP server and block until Google redirects back."""
    holder: dict[str, str | None] = {"code": None, "error": None}

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args: object) -> None:  # silence default logging
            pass

        def do_GET(self) -> None:  # noqa: N802 - http.server contract
            parsed = urllib.parse.urlparse(self.path)
            qs = urllib.parse.parse_qs(parsed.query)
            if "code" in qs:
                holder["code"] = qs["code"][0]
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(
                    b"<h2>Authorization received.</h2>"
                    b"<p>You can close this tab and return to the terminal.</p>"
                )
            else:
                holder["error"] = qs.get("error", ["unknown"])[0]
                self.send_response(400)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"<h2>Authorization failed.</h2>")

    server = http.server.HTTPServer((REDIRECT_HOST, REDIRECT_PORT), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        # Block until the callback sets the code or an error.
        while holder["code"] is None and holder["error"] is None:
            threading.Event().wait(0.2)
    finally:
        server.shutdown()
        server.server_close()

    if holder["error"]:
        sys.exit(f"Google returned an error: {holder['error']}")
    assert holder["code"] is not None
    return holder["code"]


def exchange_code(client_id: str, client_secret: str, code: str) -> dict:
    """Exchange the authorization code for access + refresh tokens."""
    resp = requests.post(
        TOKEN_URL,
        data={
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": REDIRECT_URI,
            "grant_type": "authorization_code",
        },
        timeout=30,
    )
    if resp.status_code != 200:
        sys.exit(f"Token exchange failed (HTTP {resp.status_code}): {resp.text}")
    return resp.json()


def main() -> None:
    parser = argparse.ArgumentParser(description="Obtain a Gmail OAuth refresh token (one-time).")
    parser.add_argument("--client-id", required=True, help="GCP OAuth Desktop client ID")
    parser.add_argument("--client-secret", required=True, help="GCP OAuth Desktop client secret")
    args = parser.parse_args()

    consent_url = build_consent_url(args.client_id)
    print("Opening browser for Google consent...\n")
    print(f"If it does not open, visit this URL manually:\n\n{consent_url}\n")
    webbrowser.open(consent_url)

    code = wait_for_code()
    print("Exchanging authorization code for tokens...")
    tokens = exchange_code(args.client_id, args.client_secret, code)

    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        sys.exit(
            "No refresh_token in the response. Re-run — Google sometimes omits it "
            "for accounts that already granted offline access. The prompt=consent "
            "flag above forces a fresh consent to prevent this."
        )

    print("\n" + "=" * 60)
    print("SUCCESS — copy the refresh token below into MCPHub:")
    print("=" * 60)
    print(f"\n  refresh_token = {refresh_token}\n")
    print("Also keep these (you'll paste them into the same Add-Site form):")
    print(f"  client_id     = {args.client_id}")
    print(f"  client_secret = {args.client_secret}")
    print("\nScope granted:", SCOPE)
    print("\nThe refresh token is long-lived. Store it only in MCPHub (encrypted).")

    # Also write a JSON blob for convenience (caller deletes it).
    blob = {
        "client_id": args.client_id,
        "client_secret": args.client_secret,
        "refresh_token": refresh_token,
        "scope": SCOPE,
    }
    with open("gmail_oauth_credentials.json", "w") as fh:
        json.dump(blob, fh, indent=2)
    print("\nWrote gmail_oauth_credentials.json — DELETE this file after pasting into MCPHub.")


if __name__ == "__main__":
    main()
