# Security Policy

---

### Supported Versions

| Version | Supported | Status |
|---------|-----------|--------|
| 3.0.x   | Yes       | Active (Current) |
| < 3.0   | No        | EOL |

We recommend always using the latest stable version for the best security posture.

---

### Reporting Vulnerabilities

If you discover a security vulnerability, please report it responsibly.

**DO NOT** open a public issue for security vulnerabilities.

#### Reporting Process

1. **Email**: security@mcphub.dev (or hello@mcphub.dev)
2. **Subject**: `[SECURITY] Brief description`
3. **Include**:
   - Detailed description of the vulnerability
   - Steps to reproduce
   - Potential impact assessment
   - Suggested fix (if any)

#### Response Timeline

| Severity | Initial Response | Fix Target |
|----------|-----------------|------------|
| Critical | 24 hours | 7 days |
| High     | 48 hours | 30 days |
| Medium   | 1 week | 90 days |
| Low      | 2 weeks | Next release |

#### Recognition

Security researchers who responsibly disclose vulnerabilities will be credited in release notes (if desired).

---

### Security Architecture

#### Authentication Layers

| Layer | Method | Scope |
|-------|--------|-------|
| Master API Key | Env-based shared secret | Full admin access |
| Per-Project API Keys | Scoped keys (read/write/admin) | Project-level access |
| OAuth 2.1 + PKCE | RFC 8414, 7591, 7636 compliant | Client app access |
| Dashboard Sessions | JWT-based sessions | Web UI access |

#### OAuth 2.1 Implementation

- **PKCE mandatory** (S256 only)
- **Refresh token rotation** (one-time use)
- **Authorization codes** are single-use
- **Open Dynamic Client Registration** (DCR) for Claude/ChatGPT auto-registration
- **Protected client registration** requires Master API Key

#### Rate Limiting

- 60 requests/minute per client
- 1,000 requests/hour per client
- 10,000 requests/day per client
- Token bucket algorithm with automatic throttling

#### Audit Logging

- GDPR-compliant structured JSON logging
- Sensitive data filtering (passwords, API keys masked)
- Automatic log rotation (10MB, 5 backups)
- Timezone-aware UTC timestamps

---

### Known Security Considerations

The following items are documented and tracked for improvement:

| Item | Risk | Mitigation | Planned Fix |
|------|------|------------|-------------|
| `exec()` in tool generation | Medium | Only executes internally generated code | Replace with closures |
| `create_subprocess_shell` in WP-CLI | Medium | Only runs pre-validated Docker commands | Migrate to `create_subprocess_exec` |
| SHA-256 for API key hashing | Low | Keys are high-entropy random strings | Migrate to bcrypt/argon2 |

---

### Security Best Practices for Deployment

#### Environment Variables

- Use `.env` file (never commit to git)
- Set a strong `MASTER_API_KEY` (32+ characters)
- Set `OAUTH_JWT_SECRET_KEY` explicitly (do not rely on auto-generation)
- Set `DASHBOARD_SESSION_SECRET` explicitly
- Rotate API keys regularly

#### Network Security

- Deploy behind a reverse proxy with TLS/HTTPS
- Restrict access to the management port (8000)
- Use firewall rules to limit access
- Consider VPN for remote access

#### Docker Security

- Containers run as non-root user
- Use read-only volume mounts where possible
- Keep base images updated
- Docker socket mount (`/var/run/docker.sock`) is needed for WP-CLI only — remove if not used

#### Monitoring

- Review `logs/audit.log` regularly
- Monitor health endpoint (`GET /health`)
- Set up alerts for error rate spikes (>10% threshold)

---

### Security Checklist

Before deploying to production:

- [ ] Strong `MASTER_API_KEY` configured (32+ characters)
- [ ] `OAUTH_JWT_SECRET_KEY` set explicitly
- [ ] `DASHBOARD_SESSION_SECRET` set explicitly
- [ ] `.env` file excluded from version control
- [ ] HTTPS enabled for all WordPress/WooCommerce sites
- [ ] Application Passwords are strong (16+ characters)
- [ ] WooCommerce API permissions are minimal (read-only where possible)
- [ ] Rate limiting is active
- [ ] Audit logging is enabled
- [ ] Health monitoring is running
- [ ] Docker containers run as non-root
- [ ] All dependencies are up-to-date

---
