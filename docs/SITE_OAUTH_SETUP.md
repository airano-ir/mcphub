# OAuth Site Plugins — Setup Guide

This guide covers connecting **Google-based OAuth plugins** (Gmail, Google Search
Console) to MCPHub. These plugins use a per-site OAuth flow: each site you add
gets its own authorization through Google's consent screen.

---

## Prerequisites

### 1. Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project or select an existing one.
3. Note the **Project ID** — you'll need it for enabling APIs.

### 2. Enable the Required APIs

Enable each API your plugins need:

| Plugin | API to Enable | Link |
|--------|--------------|------|
| Gmail | Gmail API | `https://console.developers.google.com/apis/api/gmail.googleapis.com/overview?project=PROJECT_ID` |
| Google Search Console | Google Search Console API | `https://console.developers.google.com/apis/api/searchconsole.googleapis.com/overview?project=PROJECT_ID` |

> ⚠️ **Common error:** If you see `HTTP 403: API has not been used in project
> before or it is disabled`, you forgot this step. Enable the API and retry.

### 3. Configure the OAuth Consent Screen

1. Go to **APIs & Services → OAuth consent screen**.
2. Set **User type** to **External** → Create.
3. Fill in:
   - **App name**: e.g. "My MCPHub"
   - **Developer contact**: your email
   - **Support email**: your email
   - **Authorized domains**: your MCPHub domain (e.g. `example.com`)
4. **Scopes**: Add the scopes your plugins need:
   - Gmail: `https://www.googleapis.com/auth/gmail.modify`
   - Google Search Console: `https://www.googleapis.com/auth/webmasters.readonly`
5. **Test users**: Add the Google accounts that will authorize sites. Only
   these accounts can grant consent while the app is in Testing mode.
6. **Leave the consent screen in Testing mode.** Do NOT click "Publish".

> Staying in Testing mode avoids Google's lengthy app verification process.
> You can add up to 100 test users, which is plenty for personal or
> small-team use.

### 4. Create OAuth Credentials

1. Go to **APIs & Services → Credentials → Create Credentials → OAuth client ID**.
2. **Application type**: **Web application** (NOT Desktop — the site OAuth
   flow uses a server-side redirect).
3. **Name**: e.g. "MCPHub Site OAuth"
4. **Authorized redirect URIs**: Add this URL:
   ```
   https://YOUR_MCPHUB_DOMAIN/oauth/site/callback
   ```
   Replace `YOUR_MCPHUB_DOMAIN` with your actual MCPHub domain (e.g.
   `https://mcp.example.com/oauth/site/callback`).
5. **Create** → note the **Client ID** and **Client Secret**.

> ⚠️ **Common error:** `redirect_uri_mismatch` means the redirect URI you
> added here doesn't match what MCPHub sends. Make sure the URL is exactly
> `https://YOUR_DOMAIN/oauth/site/callback` (no trailing slash, correct
> protocol).

### 5. Set Environment Variables

On your MCPHub server, set these environment variables:

```bash
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
PUBLIC_URL=https://your-mcphub-domain
```

If you deploy with Coolify or Docker, add these to your environment
configuration (Coolify: Application → Environment Variables).

---

## Connecting a Site

### Gmail

1. In the MCPHub dashboard, go to **Sites → Add site**.
2. Select plugin type **Gmail**.
3. **Alias**: a short identifier (e.g. `gmail`). This becomes the endpoint
   path `/u/{user_id}/gmail/mcp`.
4. **URL**: `https://gmail.googleapis.com` (the plugin ignores this; the
   dashboard requires a URL field).
5. Click **Save** — you'll be redirected to Google's consent screen.
6. Authorize with the Google account you added as a test user.
7. After consent, you'll be redirected back to MCPHub. The site status
   should change to **Active**.
8. Click **Test Connection** to verify.

### Google Search Console

Same flow as Gmail, but:
- **URL**: `https://www.googleapis.com/webmasters/v3` (placeholder)
- Scope: `webmasters.readonly` (read-only access to your Search Console data)

---

## "Google hasn't verified this app" Warning

When you authorize a site, Google may show this screen:

> **Google hasn't verified this app**
> The app is requesting access to sensitive info in your Google Account.
> Until the developer verifies this app with Google, you shouldn't use it.

This is **expected behaviour** for apps in Testing mode that request sensitive
scopes (Gmail, Search Console). It is **not an error** — Google displays this
for any unverified app.

### How to proceed

1. Click **Advanced** (or "Show details" on some screens).
2. Click **Go to [your app name] (unsafe)**.
3. Continue with the authorization.

### Is this safe?

**Yes**, as long as:
- You are the app developer (you created the OAuth client in your own GCP
  project).
- The OAuth consent screen is in **Testing** mode.
- Only Google accounts you explicitly added as **test users** can authorize.
- No third party has access to your OAuth client credentials.

The warning exists because Google requires a formal verification process
(security review, privacy policy, etc.) before an app can request sensitive
scopes without this warning. For personal or small-team use, Testing mode is
sufficient and safe.

### When you might want to publish

If you plan to make your MCPHub instance publicly available (not just for
yourself or a small team), you should:
1. Complete Google's verification process.
2. Publish the consent screen from Testing to Production.
3. This removes the "unverified" warning for all users.

For most self-hosted deployments, **staying in Testing mode is the right
choice**.

---

## Troubleshooting

### `redirect_uri_mismatch` (HTTP 400)

The redirect URI MCPHub sends doesn't match what's in Google Cloud Console.

**Fix:** In Google Cloud Console → Credentials → your OAuth client →
Authorized redirect URIs, add:
```
https://YOUR_MCPHUB_DOMAIN/oauth/site/callback
```

### `Access forbidden (HTTP 403): API has not been used in project`

The required Google API is not enabled in your GCP project.

**Fix:** Enable the API:
- Gmail: [Enable Gmail API](https://console.developers.google.com/apis/api/gmail.googleapis.com/overview)
- Search Console: [Enable Search Console API](https://console.developers.google.com/apis/api/searchconsole.googleapis.com/overview)

### `Access forbidden (HTTP 403): Request had insufficient authentication scopes`

The access token doesn't have the right scope. This happens when:
- You authorized with an old scope and the code was updated.
- The OAuth client doesn't have the scope configured.

**Fix:**
1. In Google Cloud Console → OAuth consent screen → Scopes, add the correct
   scope (`gmail.modify` or `webmasters.readonly`).
2. In MCPHub dashboard, click **Re-authorize** to get a new token with the
   correct scope.

### `No refresh token — re-authorize this site`

The stored refresh token is missing or was revoked.

**Fix:** Click **Re-authorize** in the MCPHub dashboard. This triggers a
fresh OAuth consent flow with `prompt=consent` to ensure a new refresh token
is issued.

### `Token refresh failed: InvalidGrantError`

The refresh token has been revoked or expired.

**Fix:**
1. Go to [Google Account → Security → Third-party access](https://myaccount.google.com/security).
2. Remove the app's access.
3. In MCPHub dashboard, click **Re-authorize**.

---

## Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `GOOGLE_CLIENT_ID` | Yes | Google OAuth client ID (Web application type) |
| `GOOGLE_CLIENT_SECRET` | Yes | Google OAuth client secret |
| `PUBLIC_URL` | Yes | Your MCPHub instance's public URL (e.g. `https://mcp.example.com`) |

## OAuth Scopes Reference

| Plugin | Scope | Access Level |
|--------|-------|-------------|
| Gmail | `https://www.googleapis.com/auth/gmail.modify` | Read + manage (list, read, search, labels, trash) |
| Google Search Console | `https://www.googleapis.com/auth/webmasters.readonly` | Read-only (list sites, sitemaps, search analytics) |
