# Gmail MCP — Owner setup guide

You've now got a Gmail plugin deployed in MCPHub. This walks you through the
**one-time steps only you can do** (GCP OAuth client + consent + pasting
credentials into the dashboard). After that, I wire both environments
(code-server + Hermes) and we verify end-to-end.

---

## Step 1 — Create the GCP OAuth client (only you can do this)

1. Go to **Google Cloud Console** → create or pick a project.
2. **APIs & Services → Enabled APIs & Services → Enable APIs & Services →**
   search **Gmail API** → **Enable**.
3. **APIs & Services → OAuth consent screen**:
   - User type: **External** → Create.
   - Fill app name (anything, e.g. "Personal Gmail MCP"), your email as
     developer + support contact, save.
   - Go to **Test users** → **+ Add Users** → add the Gmail address you want
     to give access to. **Save.**
   - Leave the screen in **Testing** mode (do NOT click "Publish"). Sensitive
     scopes work without Google verification as long as you stay in Testing
     and the account is a test user — fine for personal use.
4. **APIs & Services → Credentials → Create Credentials → OAuth client ID**:
   - Application type: **Desktop app** (NOT Web app — Desktop uses a
     loopback redirect; no published redirect URI needed).
   - Name anything (e.g. "gmail-mcp").
   - **Create.**
   - Note the **Client ID** (ends in `.apps.googleusercontent.com`) and the
     **Client secret** (starts `GOCSPX-`).

> Scope we request: `https://www.googleapis.com/auth/gmail.modify` — read +
> manage (list/get/search/labels/attachments, mark read/unread, add/remove
> labels, trash). `gmail.send` is intentionally **not** requested yet; we add
> it later only if you want sending.

---

## Step 2 — Run the one-time consent script (only you can do this)

Run this on **any machine with a browser** (your laptop is fine — it does NOT
have to be the server). You need Python + the `requests` package:

```bash
pip install requests
python3 plugins/gmail/bootstrap/get_refresh_token.py \
    --client-id     "YOUR_CLIENT_ID.apps.googleusercontent.com" \
    --client-secret "GOCSPX-your-secret"
```

What happens:
- A browser opens to a Google consent screen.
- You log in with the Gmail account you added as a test user, approve.
- Google redirects back to a local `http://localhost:8733/callback`.
- The script prints a **refresh token** (long string starting `1//` or
  similar) and writes `gmail_oauth_credentials.json` next to it.

**Copy the refresh token, client ID, and client secret** — you'll paste them
into the dashboard next. **Delete `gmail_oauth_credentials.json`** after
copying (it contains the same values).

The refresh token is long-lived (does not expire unless you revoke it in
Google Account → Security → Third-party access).

> If the script does NOT return a refresh token (Google sometimes omits it for
> accounts that already granted offline access), re-run it — the
> `prompt=consent` flag forces a fresh consent which prevents this.

---

## Step 3 — Add the Gmail site in the MCPHub dashboard (only you can do this)

1. Open the MCPHub dashboard: **https://mcp.palebluedot.live/dashboard-v2/sites**
   (or `/dashboard/sites` legacy). Log in as your OAuth admin user.
2. **Add Site →** plugin type **Gmail**.
3. Fill:
   - **Site URL:** `https://gmail.googleapis.com` (the plugin ignores this;
     the dashboard requires a URL field — this is the right placeholder).
   - **Alias:** `gmail` (lowercase; this becomes the endpoint segment
     `/u/{your_user_id}/gmail/mcp`).
   - **OAuth Client ID:** from Step 1.
   - **OAuth Client Secret:** from Step 1.
   - **Refresh Token:** from Step 2.
   - Account Email: optional.
4. **Test Connection.** It runs a real refresh-token exchange + profile
   fetch, so a green "OK — Gmail account <email> accessible" proves all three
   creds + the gmail.modify scope are correct. If it fails, the message says
   which step (token refresh vs profile fetch).
5. **Save.** This auto-creates the per-user endpoint
   `https://mcp.palebluedot.live/u/{your_user_id}/gmail/mcp`.

---

## Step 4 — Tell me when done, and I do the rest

Once the site is saved and Test Connection is green, tell me. I then:
- Wire code-server: add the `gmail` entry to `.claude.json` (your user_id UUID
  + the existing `mhu_` Bearer key, alias `gmail`).
- Wire Hermes: append the same entry to `~/.hermes/config.yaml` inside the
  Hermes container (via the ask-hermes bridge — that file is not mounted
  into code-server, so I edit it through a Hermes run).
- Verify end-to-end: `gmail_list_messages` from here, the same call from
  Hermes, `gmail_mark_read` + `gmail_get_message` to confirm a manage op.

After that both environments can read + manage your Gmail through MCPHub.

## Security notes

- Refresh token + client secret are stored **encrypted in MCPHub SQLite**
  (AES-256-GCM), not in a volume file or env var.
- No new public Docker port; Gmail is reachable only via the authenticated
  MCPHub endpoint both environments already use.
- If you prefer, point this at a **dedicated/alias Google account** rather
  than your primary inbox (your call).
- To revoke access anytime: Google Account → Security → Third-party apps →
  remove the app; the refresh token stops working and MCPHub's Test
  Connection will report the failure.
- `gmail.modify` is a sensitive scope; staying in GCP Testing mode + your
  email as a test user is what avoids Google's verification process.

## Optional: gate the destructive tools

If you want a confirmation prompt before `gmail_trash_message` (mirroring how
the coolify deploy/delete tools are gated), I can add it to
`/config/.claude/settings.json` `permissions.ask`. Say the word.