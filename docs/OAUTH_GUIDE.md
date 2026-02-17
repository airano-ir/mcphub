# OAuth 2.1 Authentication Guide

Complete guide for using OAuth 2.1 authentication with MCP Hub.

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Configuration](#configuration)
4. [OAuth Flows](#oauth-flows)
5. [Registering OAuth Clients](#registering-oauth-clients)
6. [OpenAI GPT Integration](#openai-gpt-integration)
7. [Claude Custom Connectors](#claude-custom-connectors-remote-mcp)
8. [Testing](#testing)
9. [Security Best Practices](#security-best-practices)
10. [Troubleshooting](#troubleshooting)

---

## Overview

MCP Hub implements **OAuth 2.1** with **API Key-Based Authorization** and **MCP Specification Compliance**:

- ✅ **API Key Authentication** - Users authorize with their existing API Keys
- ✅ **Permission Inheritance** - OAuth tokens inherit API Key's scope and project access
- ✅ **PKCE Mandatory** - Proof Key for Code Exchange (S256)
- ✅ **Refresh Token Rotation** - Security best practice
- ✅ **JWT Access Tokens** - Stateless validation
- ✅ **Multiple Grant Types** - Authorization Code, Refresh Token, Client Credentials
- ✅ **Scope-based Authorization** - Fine-grained access control
- ✅ **Backward Compatible** - API Keys still work
- ✅ **Open DCR for MCP Clients** - Claude/ChatGPT can register automatically (RFC 7591) 🆕
- ✅ **Protected Resource Metadata** - RFC 9728 compliant endpoints 🆕
- ✅ **401 + WWW-Authenticate** - Proper OAuth discovery for MCP clients 🆕

### Security Model (Updated for MCP Compliance)

**🔓 Open DCR for Trusted Clients**: Claude and ChatGPT can automatically register OAuth clients without authentication:
- Redirect URIs must match allowlist (claude.ai, chatgpt.com, localhost)
- Rate limited per IP (10/min, 30/hour)
- All registrations are audit logged

**🔐 Protected DCR for Custom Apps**: Custom applications still require Master API Key for registration.

**🔒 API Key Authorization**: Users MUST provide their API Key when authorizing OAuth clients (required mode).

**🎯 Permission Inheritance**: OAuth tokens automatically inherit the API Key's permissions:
- **Master API Key** → OAuth token with full access
- **Per-project API Key** → OAuth token limited to that project
- **Read-only API Key** → OAuth token with read-only access

**✅ Claude/ChatGPT Integration**: MCP clients automatically discover OAuth endpoints and register themselves.

### Supported Grant Types

1. **Authorization Code** (with PKCE) - For third-party apps
2. **Refresh Token** (with rotation) - Renew access tokens
3. **Client Credentials** - Machine-to-machine auth

---

## Quick Start

### 1. Generate JWT Secret

```bash
# Generate a secure secret key
python -c "import secrets; print(secrets.token_urlsafe(64))"

# OR using openssl
openssl rand -base64 64
```

### 2. Configure Environment

Add to `.env`:

```bash
# Required
OAUTH_JWT_SECRET_KEY=your_generated_secret_key_here

# Optional (defaults shown)
OAUTH_JWT_ALGORITHM=HS256
OAUTH_ACCESS_TOKEN_TTL=3600      # 1 hour
OAUTH_REFRESH_TOKEN_TTL=604800   # 7 days
```

### 3. Rebuild & Deploy

```bash
# Local development
docker-compose up --build -d

# Coolify deployment
# Update environment variables in Coolify UI and redeploy
```

---

## Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `OAUTH_JWT_SECRET_KEY` | Secret key for signing JWTs | - | ✅ Yes |
| `OAUTH_JWT_ALGORITHM` | JWT signing algorithm | `HS256` | No |
| `OAUTH_ACCESS_TOKEN_TTL` | Access token lifetime (seconds) | `3600` (1h) | No |
| `OAUTH_REFRESH_TOKEN_TTL` | Refresh token lifetime (seconds) | `604800` (7d) | No |
| `OAUTH_STORAGE_TYPE` | Storage backend | `json` | No |
| `OAUTH_STORAGE_PATH` | Storage path for JSON files | `/app/data` | No |

### JWT Algorithms

Supported algorithms:

- `HS256` (default) - HMAC with SHA-256
- `HS384` - HMAC with SHA-384
- `HS512` - HMAC with SHA-512
- `RS256` - RSA with SHA-256 (requires RSA keys)
- `RS384` - RSA with SHA-384
- `RS512` - RSA with SHA-512

---

## OAuth Flows

### Authorization Code Flow (with PKCE)

**Use Case**: Third-party applications (like OpenAI GPTs)

```
┌──────────┐                                  ┌──────────────┐
│  Client  │                                  │  MCP Server  │
└────┬─────┘                                  └──────┬───────┘
     │                                                │
     │  1. Generate PKCE verifier & challenge         │
     │─────────────────────────────────────────────►  │
     │                                                │
     │  2. GET /oauth/authorize?                      │
     │     client_id=xxx&                             │
     │     redirect_uri=https://app.com/callback&     │
     │     response_type=code&                        │
     │     code_challenge=yyy&                        │
     │     code_challenge_method=S256&                │
     │     scope=read+write&                          │
     │     state=random_state                         │
     │───────────────────────────────────────────────►│
     │                                                │
     │  3. Authorization Code (5-min expiry)          │
     │◄───────────────────────────────────────────────│
     │                                                │
     │  4. POST /oauth/token                          │
     │     grant_type=authorization_code&             │
     │     client_id=xxx&                             │
     │     client_secret=zzz&                         │
     │     code=auth_abc&                             │
     │     redirect_uri=https://app.com/callback&     │
     │     code_verifier=original_verifier            │
     │───────────────────────────────────────────────►│
     │                                                │
     │  5. Access Token + Refresh Token               │
     │◄───────────────────────────────────────────────│
     │                                                │
```

### Refresh Token Flow

**Use Case**: Renewing expired access tokens

```
POST /oauth/token
Content-Type: application/x-www-form-urlencoded

grant_type=refresh_token&
client_id=cmp_client_xxx&
client_secret=your_secret&
refresh_token=rt_xxx
```

**Response**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "rt_new_token",
  "token_type": "Bearer",
  "expires_in": 3600,
  "scope": "read write"
}
```

**Security**: Old refresh token is immediately revoked (rotation).

### Client Credentials Flow

**Use Case**: Machine-to-machine authentication

```
POST /oauth/token
Content-Type: application/x-www-form-urlencoded

grant_type=client_credentials&
client_id=cmp_client_xxx&
client_secret=your_secret&
scope=read
```

**Response**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "scope": "read"
}
```

**Note**: No refresh token for client credentials.

---

## Registering OAuth Clients

### Two Registration Modes

The `/oauth/register` endpoint supports two authentication modes:

#### 1. Open DCR (No Auth Required) 🆕

For trusted MCP clients (Claude, ChatGPT), registration is automatic:

```bash
# Claude/ChatGPT automatically calls this - no auth needed
curl -X POST https://your-mcp-server.com/oauth/register \
  -H "Content-Type: application/json" \
  -d '{
    "client_name": "Claude MCP Client",
    "redirect_uris": ["https://claude.ai/oauth/callback"],
    "grant_types": ["authorization_code", "refresh_token"]
  }'
```

**Allowed Redirect URI Patterns:**
- `https://claude.ai/*`
- `https://claude.com/*`
- `https://chatgpt.com/*`
- `https://chat.openai.com/*`
- `https://platform.openai.com/*`
- `http://localhost:*/*` (development)
- `http://127.0.0.1:*/*` (development)

**Rate Limits (per IP):**
- 10 requests per minute
- 30 requests per hour

#### 2. Protected DCR (Master API Key Required)

For custom applications with non-allowlisted redirect URIs:

```bash
curl -X POST https://your-mcp-server.com/oauth/register \
  -H "Authorization: Bearer YOUR_MASTER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "client_name": "My Custom App",
    "redirect_uris": ["https://myapp.com/callback"],
    "grant_types": ["authorization_code", "refresh_token"],
    "scope": "read write"
  }'
```

### Security Flow (MCP Compliant)

```
1. MCP Client (Claude) discovers OAuth via /.well-known/oauth-authorization-server
2. MCP Client registers via Open DCR at /oauth/register (no auth for trusted URIs)
3. MCP Client receives client_id + client_secret
4. User is redirected to /oauth/authorize
5. User enters their API Key → Authorization code returned
6. MCP Client exchanges code for tokens at /oauth/token
7. OAuth token inherits user's API Key permissions
```

**Benefits**:
- ✅ Claude/ChatGPT connect with one click (Open DCR)
- ✅ Custom apps still require admin approval
- ✅ Users control their own permissions via API Keys
- ✅ Rate limiting prevents abuse

**Example**:
- User has "read-only" API Key → OAuth token gets "read-only" access
- User has project-specific API Key → OAuth token limited to that project
- User has Master API Key → OAuth token gets full access

### ChatGPT Integration (OAuth Manual Mode)

ChatGPT now supports **OAuth (manual)** integration where you manually configure the OAuth client credentials.

#### ⚠️ Security Considerations

**Current Limitation**: Due to ChatGPT OAuth (manual) design:
- ChatGPT cannot pass user-specific API Keys in authorization URL
- Must use `OAUTH_AUTH_MODE=optional` which allows anyone with the authorization URL to connect
- OAuth tokens issued to ChatGPT get **full access** (no API Key inheritance)

**Security Measures You Can Take**:

1. **Use Minimal Scopes** (Recommended):
   - Register ChatGPT client with `scope: "read"` only
   - Create separate clients for different access levels

2. **Private Deployment Only**:
   - Only share client credentials with trusted users
   - Use this integration for personal/team use, not public GPTs

3. **Monitor Usage**:
   - Check audit logs regularly: `tail -f logs/audit.log`
   - Review OAuth tokens: use `oauth_list_tokens()` tool

4. **Future Enhancement** (Phase E - Planned):
   - 🔒 **Custom Authorization Page** (Priority 2)
     - Beautiful HTML form for API Key input
     - OAUTH_AUTH_MODE=required works with ChatGPT
     - Per-user access control
     - Multi-language support (EN/FA)
     - See `docs/ROADMAP.md` Phase E for details
   - IP whitelisting for OAuth endpoints
   - Per-client rate limiting

**For Production/Public Use**: Consider using `OAUTH_AUTH_MODE=required` with a custom client that supports API Key parameters, instead of ChatGPT OAuth (manual).

---

#### Step-by-Step Setup:

**1. Register OAuth Client (Admin Only)**

Use MCP tool or API with Master API Key:

```bash
# Using curl with Master API Key
curl -X POST https://your-mcp-server.com/oauth/register \
  -H "Authorization: Bearer YOUR_MASTER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "client_name": "ChatGPT OAuth Integration",
    "redirect_uris": ["https://chatgpt.com/connector_platform_oauth_redirect"],
    "grant_types": ["authorization_code", "refresh_token"],
    "scope": "read"
  }'
```

**Response**: Save the `client_id` and `client_secret` (shown only once!)

**2. Configure ChatGPT**

1. Go to ChatGPT → Settings → Authentication
2. Select **OAuth (manual)**
3. Enter:
   - **Client ID**: `cmp_client_xxx` (from step 1)
   - **Client Secret**: `secret_xxx` (from step 1)
   - **Authorization URL**: `https://your-mcp-server.com/oauth/authorize`
   - **Token URL**: `https://your-mcp-server.com/oauth/token`
   - **Scope**: `read write`

**3. Configure Environment for ChatGPT**

⚠️ **IMPORTANT SECURITY NOTE**: ChatGPT OAuth (manual) has a limitation:

ChatGPT builds the authorization URL automatically and **does not allow users to add API Key parameters**. Therefore, you must use `optional` mode:

```bash
# In .env file
OAUTH_AUTH_MODE=optional
```

**Security Implications**:
- ⚠️ **Anyone with the URL can authorize** - Client ID/Secret alone don't prevent access
- ⚠️ **OAuth tokens get full access** - No API Key = no permission inheritance
- 🔒 **Mitigation**: Use restricted `scope` when registering the client

**Recommended Scopes for ChatGPT**:
- `read` - Read-only access (safest)
- `read write` - Allow content creation (moderate risk)
- ⚠️ Avoid `admin` scope for public ChatGPT integrations

**4. User Authorization**

When users connect ChatGPT to your MCP server:

1. ChatGPT redirects to authorization endpoint automatically
2. Server validates client_id and redirect_uri
3. User approves the connection
4. OAuth token is issued with the scope defined during client registration
5. Redirects back to ChatGPT - Done!

✅ **Best Practice**: Register separate OAuth clients for different use cases with minimal required scopes

### Using MCP Tools

You can also pre-register clients using MCP tools:

```python
# 1. Register a new OAuth client
result = await oauth_register_client(
    client_name="My OpenAI GPT",
    redirect_uris="https://chat.openai.com/aip/callback",
    grant_types="authorization_code,refresh_token",
    allowed_scopes="read,write"
)

# Save these credentials securely!
print(f"Client ID: {result['client_id']}")
print(f"Client Secret: {result['client_secret']}")  # Only shown once!
```

### Using Direct API (Admin Required)

⚠️ **Master API Key Required** - Only server administrators can register OAuth clients.

```bash
curl -X POST https://mcp-dev.mcphub.dev/oauth/register \
  -H "Authorization: Bearer YOUR_MASTER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "client_name": "My Application",
    "redirect_uris": ["https://example.com/callback"],
    "grant_types": ["authorization_code", "refresh_token"],
    "scope": "read write"
  }'
```

**Success Response** (201 Created):
```json
{
  "client_id": "cmp_client_abc123",
  "client_secret": "very_long_secret_string",
  "client_id_issued_at": 1234567890,
  "client_secret_expires_at": 0,
  "client_name": "My Application",
  "redirect_uris": ["https://example.com/callback"],
  "grant_types": ["authorization_code", "refresh_token"],
  "token_endpoint_auth_method": "client_secret_post"
}
```

⚠️ **Important**: Save `client_secret` immediately - it's shown only once!

**Error Response** (401 Unauthorized):
```json
{
  "error": "unauthorized",
  "error_description": "Master API Key required for OAuth client registration. Add 'Authorization: Bearer YOUR_MASTER_API_KEY' header."
}
```

### List Registered Clients

```python
result = await oauth_list_clients()

for client in result['clients']:
    print(f"{client['client_name']}: {client['client_id']}")
```

### Revoke a Client

```python
result = await oauth_revoke_client(
    client_id="cmp_client_abc123"
)
```

---

## OpenAI GPT Integration

### Step 1: Register OAuth Client

Use the MCP tool to register:

```python
result = await oauth_register_client(
    client_name="OpenAI GPT Integration",
    redirect_uris="https://chat.openai.com/aip/callback,https://chatgpt.com/aip/callback",
    allowed_scopes="read,write"
)

# Save these!
# Client ID: cmp_client_abc123
# Client Secret: very_long_secret_string
```

### Step 2: Configure GPT Action

In OpenAI GPT editor, add an Action with:

**Authentication Type**: OAuth

**Client ID**: `cmp_client_abc123`

**Client Secret**: `very_long_secret_string`

**Authorization URL**: `https://your-mcp-server.com/oauth/authorize`

**Token URL**: `https://your-mcp-server.com/oauth/token`

**Scope**: `read write`

**Token Exchange Method**: `POST` with Basic auth

### Step 3: Test Integration

1. In GPT conversation, trigger an action
2. OAuth consent flow will start
3. User approves (or auto-approved in MCP context)
4. GPT receives access token
5. GPT can now call MCP tools via OAuth!

---

## Claude Custom Connectors (Remote MCP)

Claude supports **Custom Connectors** for Remote MCP servers, allowing direct integration without SSH tunnels or local setup.

### Requirements

- **Claude Plan**: Pro, Max, Team, or Enterprise
- **MCP Server**: Publicly accessible with HTTPS
- **OAuth**: Automatically handled via Open DCR 🆕

### Step 1: Add Connector in Claude

1. Open Claude (claude.ai or desktop app)
2. Go to **Settings** → **Connectors** (or **Integrations**)
3. Click **Add custom connector**
4. Enter your MCP server URL:
   - Full access: `https://your-mcp-server.com/mcp`
   - Per-project: `https://your-mcp-server.com/project/{alias}/mcp`
5. Click **Add connector** or **Connect**

### Step 2: Authorize (Automatic Flow) 🆕

Thanks to **Open DCR** and **MCP OAuth Compliance**, the OAuth flow is now automatic:

1. Claude discovers OAuth metadata at `/.well-known/oauth-authorization-server`
2. Claude automatically registers via Open DCR at `/oauth/register`
3. Claude redirects you to the authorization page
4. Enter your API Key
5. Done! Claude now has access to your MCP tools

**No manual client registration required!**

### Alternative: Manual Registration (Optional)

If you prefer to pre-register the OAuth client:

```bash
curl -X POST https://your-mcp-server.com/oauth/register \
  -H "Content-Type: application/json" \
  -d '{
    "client_name": "Claude Custom Connector",
    "redirect_uris": ["https://claude.ai/oauth/callback"],
    "grant_types": ["authorization_code", "refresh_token"],
    "scope": "read write"
  }'
```

Note: Authorization header is optional for Claude's redirect URIs (Open DCR).

### Security Considerations

⚠️ **Important Security Notes**:

- **Only add trusted connectors** - Remote MCP servers have access to your Claude conversations
- **Use minimal scopes** - Register clients with only required permissions (`read` for safe exploration)
- **Disable write-actions** for Research feature if using with sensitive data
- **Monitor usage** via audit logs: `get_audit_log` tool

### Recommended Configuration

For **safe exploration** (read-only):
```bash
curl -X POST https://your-mcp-server.com/oauth/register \
  -H "Authorization: Bearer YOUR_MASTER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "client_name": "Claude (Read-Only)",
    "redirect_uris": ["https://claude.ai/api/mcp/auth_callback", "https://claude.com/api/mcp/auth_callback"],
    "scope": "read"
  }'
```

For **full access** (trusted environments):
```bash
curl -X POST https://your-mcp-server.com/oauth/register \
  -H "Authorization: Bearer YOUR_MASTER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "client_name": "Claude (Full Access)",
    "redirect_uris": ["https://claude.ai/api/mcp/auth_callback", "https://claude.com/api/mcp/auth_callback"],
    "scope": "read write admin"
  }'
```

### Using Per-Project Endpoints

For better security isolation, connect Claude to project-specific endpoints:

```
https://your-mcp-server.com/project/{alias}/mcp
```

This restricts Claude to tools for that specific project only.

### Troubleshooting Claude Connectors

#### "Configure" button instead of "Connect"
This was fixed in Phase K.1. If you still see this:
- Ensure server is updated to v2.10.0+
- Check that `OAuthRequiredMiddleware` is active
- Verify `/.well-known/oauth-protected-resource` returns 200

#### "Connection failed" or "Error connecting to server"
1. **Check server accessibility**: `curl https://your-server.com/health`
2. **Check OAuth metadata**: `curl https://your-server.com/.well-known/oauth-authorization-server`
3. **Check path-specific metadata**: `curl https://your-server.com/.well-known/oauth-protected-resource/mcp`
4. **Check logs** for errors:
   ```bash
   docker logs your-container | grep -i oauth
   ```

#### "Unauthorized" during authorization
- Enter a valid API Key on the authorization page
- Check that your API Key has the required scope

#### DCR Rate Limited
If you see rate limit errors:
- Wait 1 minute (per-minute limit: 10)
- Or wait 1 hour (per-hour limit: 30)
- Configure limits: `DCR_RATE_LIMIT_PER_MINUTE` and `DCR_RATE_LIMIT_PER_HOUR`

#### Tools not appearing
- Check endpoint path (should include `/mcp`)
- Verify OAuth scopes match tool requirements
- Review server logs for errors

---

## Testing

### Manual Testing

#### 1. Test Authorization Endpoint

```bash
# Generate PKCE challenge
python -c "
import secrets, hashlib, base64

verifier = secrets.token_urlsafe(64)[:64]
challenge = base64.urlsafe_b64encode(
    hashlib.sha256(verifier.encode()).digest()
).decode().rstrip('=')

print(f'Verifier: {verifier}')
print(f'Challenge: {challenge}')
"

# Call authorization endpoint
curl -X GET "http://localhost:8000/oauth/authorize?\
client_id=cmp_client_xxx&\
redirect_uri=http://localhost:3000/callback&\
response_type=code&\
code_challenge=YOUR_CHALLENGE&\
code_challenge_method=S256&\
scope=read+write"
```

#### 2. Test Token Endpoint

```bash
# Exchange authorization code for tokens
curl -X POST http://localhost:8000/oauth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=authorization_code&\
client_id=cmp_client_xxx&\
client_secret=YOUR_SECRET&\
code=auth_abc123&\
redirect_uri=http://localhost:3000/callback&\
code_verifier=YOUR_VERIFIER"
```

#### 3. Test Access Token

```bash
# Use access token to call MCP tools
curl -X POST http://localhost:8000/tools/wordpress_post_list \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"site": "site1", "status": "publish"}'
```

### Automated Testing

```bash
# Run integration tests
pytest tests/test_oauth_integration.py -v

# Run all OAuth tests
pytest tests/test_oauth*.py -v
```

---

## Security Best Practices

### 1. JWT Secret Key Management

✅ **DO**:
- Use cryptographically secure random keys (64+ characters)
- Store in environment variables, never in code
- Rotate keys periodically
- Use different keys for dev/staging/production

❌ **DON'T**:
- Use weak or predictable secrets
- Commit secrets to version control
- Share secrets between environments

### 2. Client Secrets

✅ **DO**:
- Save client secrets immediately after creation
- Store securely (password manager, secrets vault)
- Rotate if compromised

❌ **DON'T**:
- Log client secrets
- Expose in error messages
- Transmit over insecure channels

### 3. PKCE

✅ **DO**:
- Always use S256 method
- Generate new verifier for each flow
- Validate code_challenge correctly

❌ **DON'T**:
- Reuse code verifiers
- Use plain method (OAuth 2.1 disallows it)

### 4. Token Handling

✅ **DO**:
- Use short-lived access tokens (1 hour)
- Implement refresh token rotation
- Detect and prevent token reuse
- Validate JWT signatures

❌ **DON'T**:
- Store tokens in localStorage (XSS risk)
- Log tokens in production
- Ignore token expiration

### 5. Scope Management

✅ **DO**:
- Grant minimum necessary scopes
- Validate scopes on every request
- Document scope requirements

❌ **DON'T**:
- Grant "admin" scope by default
- Allow scope escalation

---

## Troubleshooting

### ChatGPT OAuth (Manual) Issues

#### 1. "Something went wrong with setting up the connection"

**Common Causes**:
- Wrong redirect URI
- OAUTH_AUTH_MODE is set to `required` (should be `optional` for ChatGPT)
- Client ID/Secret mismatch

**Solution**:
```bash
# 1. Check redirect URI in oauth_clients.json
cat /app/data/oauth_clients.json | grep -A 3 redirect_uris
# Should contain: "https://chatgpt.com/connector_platform_oauth_redirect"

# 2. Verify OAUTH_AUTH_MODE
echo $OAUTH_AUTH_MODE
# Should be: optional

# 3. Check logs for specific error
tail -f logs/audit.log | grep -i oauth
```

#### 2. "API Key is required" error during authorization

**Cause**: `OAUTH_AUTH_MODE=required` but ChatGPT cannot pass API Key

**Solution**:
```bash
# In .env file, change to:
OAUTH_AUTH_MODE=optional

# Then restart/redeploy
```

#### 3. "Invalid redirect_uri" error

**Cause**: Redirect URI mismatch between client registration and ChatGPT request

**Solution**:
```bash
# Register new client with correct URI
curl -X POST https://your-server.com/oauth/register \
  -H "Authorization: Bearer YOUR_MASTER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "client_name": "ChatGPT OAuth",
    "redirect_uris": ["https://chatgpt.com/connector_platform_oauth_redirect"],
    "grant_types": ["authorization_code", "refresh_token"],
    "scope": "read"
  }'

# Update ChatGPT config with new client_id and client_secret
```

#### 4. ChatGPT connection works but has too much access

**Cause**: OAuth client registered with broad scopes (e.g., "read write admin")

**Solution**:
```bash
# Revoke old client
curl -X POST https://your-server.com/tools/oauth_revoke_client \
  -H "Authorization: Bearer YOUR_MASTER_API_KEY" \
  -d '{"client_id": "cmp_client_old"}'

# Register new client with minimal scope
curl -X POST https://your-server.com/oauth/register \
  -H "Authorization: Bearer YOUR_MASTER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "client_name": "ChatGPT (Read-Only)",
    "redirect_uris": ["https://chatgpt.com/connector_platform_oauth_redirect"],
    "scope": "read"
  }'
```

---

### Common Issues

#### 1. "Invalid client credentials"

**Cause**: Wrong client_id or client_secret

**Solution**:
```bash
# List registered clients
curl -H "Authorization: Bearer $MASTER_API_KEY" \
  http://localhost:8000/tools/oauth_list_clients

# Verify credentials match
```

#### 2. "PKCE validation failed"

**Cause**: Mismatch between code_verifier and code_challenge

**Solution**:
- Ensure code_verifier used in token request matches the original
- Verify code_challenge was generated correctly with S256

#### 3. "Token expired"

**Cause**: Access token expired (default 1 hour)

**Solution**:
```bash
# Use refresh token to get new access token
curl -X POST http://localhost:8000/oauth/token \
  -d "grant_type=refresh_token&\
client_id=xxx&\
client_secret=yyy&\
refresh_token=rt_zzz"
```

#### 4. "Insufficient scope"

**Cause**: Access token doesn't have required scope

**Solution**:
- Request correct scopes during authorization
- Check allowed_scopes for the client
- Ensure scope is included in JWT payload

#### 5. "Authorization code already used"

**Cause**: Attempting to reuse authorization code

**Solution**:
- Authorization codes are single-use only
- Start a new authorization flow
- Check for client-side caching issues

### Debug Logging

Enable debug logging:

```bash
# .env
LOG_LEVEL=DEBUG
```

View logs:
```bash
docker-compose logs -f mcp-server | grep -i oauth
```

---

## API Reference

### Endpoints

#### GET /oauth/authorize

Authorization endpoint for OAuth flow.

**Query Parameters**:
- `client_id` (required) - OAuth client ID
- `redirect_uri` (required) - Callback URI
- `response_type` (required) - Must be "code"
- `code_challenge` (required) - PKCE challenge
- `code_challenge_method` (required) - Must be "S256"
- `scope` (optional) - Requested scopes (space-separated)
- `state` (optional) - CSRF protection token

**Response**:
```json
{
  "redirect_uri": "http://localhost:3000/callback?code=auth_xxx&state=yyy",
  "code": "auth_xxx",
  "expires_in": 300
}
```

#### POST /oauth/token

Token endpoint for all OAuth grants.

**Request Body** (application/x-www-form-urlencoded or JSON):
- `grant_type` (required) - "authorization_code" | "refresh_token" | "client_credentials"
- `client_id` (required) - OAuth client ID
- `client_secret` (required) - Client secret

For authorization_code:
- `code` (required) - Authorization code
- `redirect_uri` (required) - Same as /authorize
- `code_verifier` (required) - PKCE verifier

For refresh_token:
- `refresh_token` (required) - Current refresh token

For client_credentials:
- `scope` (optional) - Requested scopes

**Response**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "rt_xxx",
  "token_type": "Bearer",
  "expires_in": 3600,
  "scope": "read write"
}
```

### MCP Tools

#### oauth_register_client

Register a new OAuth client.

#### oauth_list_clients

List all registered OAuth clients.

#### oauth_revoke_client

Revoke (delete) an OAuth client.

---

## Resources

- [OAuth 2.1 Specification](https://datatracker.ietf.org/doc/html/draft-ietf-oauth-v2-1-10)
- [RFC 7636 - PKCE](https://datatracker.ietf.org/doc/html/rfc7636)
- [JWT Best Practices](https://datatracker.ietf.org/doc/html/rfc8725)
- [OpenAI Actions Documentation](https://platform.openai.com/docs/actions)

---

## Support

For issues or questions:
- GitHub Issues: https://github.com/airano-ir/mcphub/issues
- Documentation: `/docs`

---

**Last Updated**: 2025-12-05
**Version**: v2.10.0 (Phase K.1 - OAuth MCP Compliance, Open DCR, RFC 9728)
