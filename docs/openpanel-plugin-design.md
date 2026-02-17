# OpenPanel Plugin Design - Phase H

> **MCP Plugin for OpenPanel Analytics Management (Self-Hosted)**

**Version**: v1.0.0 (Design)
**Priority**: Highest
**Estimated Tools**: 72-78

---

## Why OpenPanel over Plausible?

### Comparison Summary

| Feature | Plausible | OpenPanel | Winner |
|---------|-----------|-----------|--------|
| Web Analytics | Yes | Yes | Tie |
| Product Analytics | No | Yes (Funnels, Cohorts) | OpenPanel |
| User Profiles | No | Yes | OpenPanel |
| A/B Testing | No | Yes | OpenPanel |
| Retention Analysis | No | Yes | OpenPanel |
| Session Recording | No | Yes | OpenPanel |
| Multi-platform | Web only | Web, Mobile, Server | OpenPanel |
| API Completeness | Stats API only | Track + Export + Management | OpenPanel |
| Custom Dashboards | Limited | Full flexibility | OpenPanel |
| Self-Hosted | Yes | Yes | Tie |
| Privacy (GDPR) | Yes | Yes | Tie |

**Decision**: **OpenPanel** - More comprehensive analytics with Product Analytics features that Plausible lacks.

### Key OpenPanel Advantages

1. **Product Analytics** - Funnels, cohorts, user profiles, retention
2. **A/B Testing** - Built-in variant testing
3. **Multi-platform** - Web, iOS, Android, Server-side SDKs
4. **Comprehensive API** - Track, Export, and Management APIs
5. **Custom Dashboards** - Flexible chart creation
6. **Self-Hosted on Coolify** - Full data control

Sources:
- [OpenPanel](https://openpanel.dev/)
- [OpenPanel GitHub](https://github.com/Openpanel-dev/openpanel)
- [Coolify OpenPanel Docs](https://coolify.io/docs/services/openpanel)

---

## Overview

Plugin for managing **OpenPanel Self-Hosted** instances deployed on Coolify.

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│              OpenPanel Self-Hosted Architecture                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    OpenPanel Stack                        │    │
│  ├─────────────────────────────────────────────────────────┤    │
│  │                                                           │    │
│  │  Next.js Dashboard (:3000)                               │    │
│  │  └── tRPC API (internal management)                      │    │
│  │                                                           │    │
│  │  Fastify Event API (:3333)                               │    │
│  │  └── /track - Event ingestion                            │    │
│  │  └── /export - Data export                               │    │
│  │                                                           │    │
│  │  PostgreSQL - Metadata & config                          │    │
│  │  ClickHouse - Event storage (high-volume)                │    │
│  │  Redis - Cache, pub/sub, queues                          │    │
│  │  BullMQ - Job processing                                 │    │
│  │                                                           │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Authentication

### API Authentication

```
┌─────────────────────────────────────────────────────────────────┐
│                  OpenPanel Authentication                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Required Headers:                                               │
│  ├── openpanel-client-id: YOUR_CLIENT_ID                        │
│  └── openpanel-client-secret: YOUR_CLIENT_SECRET                │
│                                                                  │
│  Client Modes:                                                   │
│  ├── write - Can send events (tracking)                         │
│  ├── read  - Can read data (export)                             │
│  └── root  - Full access (management + read + write)            │
│                                                                  │
│  For Self-Hosted: Create clients via Dashboard or API           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Environment Variables

```bash
# OpenPanel Self-Hosted Instance (Required)
OPENPANEL_SITE1_URL=https://analytics.example.com
OPENPANEL_SITE1_CLIENT_ID=your-client-id
OPENPANEL_SITE1_CLIENT_SECRET=your-client-secret
OPENPANEL_SITE1_PROJECT_ID=your-project-id  # Required for Export/Read APIs
OPENPANEL_SITE1_ALIAS=myanalytics

# Optional: Multiple Instances
OPENPANEL_SITE2_URL=https://analytics-staging.example.com
OPENPANEL_SITE2_CLIENT_ID=client-id-staging
OPENPANEL_SITE2_CLIENT_SECRET=client-secret-staging
OPENPANEL_SITE2_PROJECT_ID=staging-project-id
OPENPANEL_SITE2_ALIAS=staging
```

**Finding Your Project ID:**
1. Log in to your OpenPanel Dashboard
2. Go to Project Settings
3. Copy the Project ID

**Note:**
- `CLIENT_ID` and `CLIENT_SECRET` are used for authentication
- `PROJECT_ID` is required for Export/Read APIs (get_event_count, export_events, etc.)
- Track APIs (identify_user, track_event) work without PROJECT_ID

---

## API Endpoints

### Track API (Fastify - /api)

Primary endpoint for event ingestion:

```
POST /track
Headers:
  openpanel-client-id: YOUR_CLIENT_ID
  openpanel-client-secret: YOUR_CLIENT_SECRET
  x-client-ip: CLIENT_IP (optional, for geo)
  user-agent: USER_AGENT (optional, for device info)
```

**Operation Types:**

| Type | Description | Use Case |
|------|-------------|----------|
| `track` | Track custom event | Page view, button click, purchase |
| `identify` | Identify user | Set user profile properties |
| `increment` | Increment property | Visit count, purchase count |
| `decrement` | Decrement property | Credits used, inventory |
| `alias` | Alias profile ID | Link anonymous to authenticated |

### Export API (Fastify - /export)

```
GET /export/events
  - Retrieve raw event data
  - Filters: projectId, profileId, event, start, end
  - Pagination: page, limit
  - Includes: profile, meta

GET /export/charts
  - Retrieve aggregated chart data
  - Events with breakdowns
  - Intervals: minute, hour, day, week, month
  - Ranges: 30min, today, 7d, 30d, 6m, 12m, etc.
```

### Dashboard tRPC API (Next.js - /api/trpc)

Internal API for dashboard management:

```
Projects:
  - project.list, project.get, project.create, project.update, project.delete

Dashboards:
  - dashboard.list, dashboard.get, dashboard.create, dashboard.update, dashboard.delete

Charts:
  - chart.create, chart.update, chart.delete

Clients:
  - client.list, client.create, client.delete, client.regenerate

Funnels:
  - funnel.list, funnel.get, funnel.create, funnel.update, funnel.delete

Reports:
  - report.overview, report.retention, report.paths

Users/Profiles:
  - profile.list, profile.get, profile.events
```

---

## Plugin Architecture

### Project Structure

```
plugins/openpanel/
├── __init__.py              # Export: OpenPanelPlugin, OpenPanelClient
├── plugin.py                # Main OpenPanelPlugin class
├── client.py                # OpenPanelClient (unified client)
└── handlers/
    ├── __init__.py
    ├── events.py            # Event tracking (10 tools)
    ├── export.py            # Data export (10 tools)
    ├── projects.py          # Project management (8 tools)
    ├── dashboards.py        # Dashboard management (10 tools)
    ├── funnels.py           # Funnel analytics (8 tools)
    ├── profiles.py          # User profiles (8 tools)
    ├── clients.py           # API client management (6 tools)
    ├── reports.py           # Analytics reports (8 tools)
    └── system.py            # Health & stats (6 tools)
```

### Client Architecture

```python
class OpenPanelClient:
    """
    Unified client for OpenPanel Self-Hosted APIs

    Handles both Track/Export API (Fastify) and
    Dashboard tRPC API (Next.js) where available.
    """
    def __init__(
        self,
        base_url: str,           # e.g., https://analytics.example.com
        client_id: str,          # Client ID for authentication
        client_secret: str,      # Client Secret for authentication
    ):
        self.base_url = base_url.rstrip('/')
        self.api_url = f"{self.base_url}/api"
        self.client_id = client_id
        self.client_secret = client_secret

    def _get_headers(self, include_ip: str = None) -> Dict[str, str]:
        """Get authentication headers"""
        headers = {
            "Content-Type": "application/json",
            "openpanel-client-id": self.client_id,
            "openpanel-client-secret": self.client_secret
        }
        if include_ip:
            headers["x-client-ip"] = include_ip
        return headers

    async def track(
        self,
        event_type: str,
        payload: Dict[str, Any],
        client_ip: str = None
    ) -> Dict[str, Any]:
        """Send tracking request to /track endpoint"""
        ...

    async def export_events(
        self,
        project_id: str,
        **filters
    ) -> Dict[str, Any]:
        """Export events from /export/events"""
        ...
```

---

## Tool Categories

### 1. Events Handler (10 tools)

Event tracking and ingestion operations.

| Tool | Type | Scope | Description |
|------|------|-------|-------------|
| `track_event` | track | write | Track custom event with properties |
| `track_page_view` | track | write | Track page view event |
| `track_screen_view` | track | write | Track screen view (mobile) |
| `identify_user` | identify | write | Identify user with profile data |
| `set_user_properties` | identify | write | Update user properties |
| `increment_property` | increment | write | Increment numeric property |
| `decrement_property` | decrement | write | Decrement numeric property |
| `alias_user` | alias | write | Link two profile IDs |
| `track_revenue` | track | write | Track revenue/purchase event |
| `track_batch` | track | write | Track multiple events in batch |

```python
# Example: track_event
{
    "name": "track_event",
    "method_name": "track_event",
    "description": "Track a custom event with properties. Events can have any custom properties.",
    "schema": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Event name (e.g., 'button_clicked', 'purchase_completed')"
            },
            "properties": {
                "type": "object",
                "description": "Custom properties for the event"
            },
            "profile_id": {
                "type": "string",
                "description": "User/profile ID to associate with event"
            },
            "timestamp": {
                "type": "string",
                "format": "date-time",
                "description": "Event timestamp (ISO 8601, defaults to now)"
            }
        },
        "required": ["name"]
    },
    "scope": "write"
}
```

### 2. Export Handler (10 tools)

Data export and retrieval operations.

| Tool | Type | Scope | Description |
|------|------|-------|-------------|
| `export_events` | GET | read | Export raw event data |
| `export_events_csv` | GET | read | Export events as CSV |
| `export_chart_data` | GET | read | Export aggregated chart data |
| `get_event_count` | GET | read | Get event counts with filters |
| `get_unique_users` | GET | read | Get unique user count |
| `get_page_views` | GET | read | Get page view statistics |
| `get_top_pages` | GET | read | Get top pages by views |
| `get_top_referrers` | GET | read | Get top traffic sources |
| `get_geo_data` | GET | read | Get geographic distribution |
| `get_device_data` | GET | read | Get device/browser breakdown |

```python
# Example: export_events
{
    "name": "export_events",
    "method_name": "export_events",
    "description": "Export raw event data with filters and pagination",
    "schema": {
        "type": "object",
        "properties": {
            "project_id": {
                "type": "string",
                "description": "Project ID to export from"
            },
            "event": {
                "anyOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}}],
                "description": "Event name(s) to filter"
            },
            "profile_id": {
                "type": "string",
                "description": "Filter by user/profile ID"
            },
            "start": {
                "type": "string",
                "format": "date",
                "description": "Start date (YYYY-MM-DD)"
            },
            "end": {
                "type": "string",
                "format": "date",
                "description": "End date (YYYY-MM-DD)"
            },
            "limit": {
                "type": "integer",
                "default": 50,
                "maximum": 1000
            },
            "page": {
                "type": "integer",
                "default": 1
            },
            "includes": {
                "type": "array",
                "items": {"type": "string", "enum": ["profile", "meta"]},
                "description": "Additional data to include"
            }
        },
        "required": ["project_id"]
    },
    "scope": "read"
}
```

### 3. Projects Handler (8 tools)

Project management operations.

| Tool | Method | Scope | Description |
|------|--------|-------|-------------|
| `list_projects` | GET | read | List all projects |
| `get_project` | GET | read | Get project details |
| `create_project` | POST | admin | Create new project |
| `update_project` | PUT | admin | Update project settings |
| `delete_project` | DELETE | admin | Delete project |
| `get_project_stats` | GET | read | Get project statistics |
| `get_project_settings` | GET | read | Get project configuration |
| `update_project_settings` | PUT | admin | Update project configuration |

### 4. Dashboards Handler (10 tools)

Dashboard and chart management.

| Tool | Method | Scope | Description |
|------|--------|-------|-------------|
| `list_dashboards` | GET | read | List all dashboards |
| `get_dashboard` | GET | read | Get dashboard with charts |
| `create_dashboard` | POST | write | Create new dashboard |
| `update_dashboard` | PUT | write | Update dashboard |
| `delete_dashboard` | DELETE | write | Delete dashboard |
| `add_chart` | POST | write | Add chart to dashboard |
| `update_chart` | PUT | write | Update chart configuration |
| `delete_chart` | DELETE | write | Remove chart from dashboard |
| `duplicate_dashboard` | POST | write | Clone existing dashboard |
| `share_dashboard` | POST | write | Generate shareable link |

### 5. Funnels Handler (8 tools)

Funnel analysis operations.

| Tool | Method | Scope | Description |
|------|--------|-------|-------------|
| `list_funnels` | GET | read | List all funnels |
| `get_funnel` | GET | read | Get funnel with conversion data |
| `create_funnel` | POST | write | Create new funnel |
| `update_funnel` | PUT | write | Update funnel steps |
| `delete_funnel` | DELETE | write | Delete funnel |
| `get_funnel_conversion` | GET | read | Get conversion rates |
| `get_funnel_breakdown` | GET | read | Get breakdown by segment |
| `compare_funnels` | GET | read | Compare multiple funnels |

```python
# Example: create_funnel
{
    "name": "create_funnel",
    "method_name": "create_funnel",
    "description": "Create a funnel to track user journey through steps",
    "schema": {
        "type": "object",
        "properties": {
            "project_id": {
                "type": "string",
                "description": "Project ID"
            },
            "name": {
                "type": "string",
                "description": "Funnel name"
            },
            "steps": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "event": {"type": "string"},
                        "filters": {"type": "array"}
                    },
                    "required": ["name", "event"]
                },
                "description": "Funnel steps (events in sequence)",
                "minItems": 2
            },
            "window_days": {
                "type": "integer",
                "default": 14,
                "description": "Conversion window in days"
            }
        },
        "required": ["project_id", "name", "steps"]
    },
    "scope": "write"
}
```

### 6. Profiles Handler (8 tools)

User profile management.

| Tool | Method | Scope | Description |
|------|--------|-------|-------------|
| `list_profiles` | GET | read | List user profiles |
| `get_profile` | GET | read | Get profile details |
| `search_profiles` | GET | read | Search profiles by property |
| `get_profile_events` | GET | read | Get events for profile |
| `get_profile_sessions` | GET | read | Get sessions for profile |
| `delete_profile` | DELETE | admin | Delete profile data (GDPR) |
| `merge_profiles` | POST | admin | Merge duplicate profiles |
| `export_profile_data` | GET | read | Export all profile data (GDPR) |

### 7. Clients Handler (6 tools)

API client/key management.

| Tool | Method | Scope | Description |
|------|--------|-------|-------------|
| `list_clients` | GET | read | List API clients |
| `get_client` | GET | read | Get client details |
| `create_client` | POST | admin | Create new API client |
| `delete_client` | DELETE | admin | Delete API client |
| `regenerate_secret` | POST | admin | Regenerate client secret |
| `update_client_mode` | PUT | admin | Update client permissions |

### 8. Reports Handler (8 tools)

Analytics and reporting.

| Tool | Method | Scope | Description |
|------|--------|-------|-------------|
| `get_overview_report` | GET | read | Get overview statistics |
| `get_retention_report` | GET | read | Get retention analysis |
| `get_cohort_report` | GET | read | Get cohort analysis |
| `get_paths_report` | GET | read | Get user flow paths |
| `get_realtime_stats` | GET | read | Get real-time visitors |
| `get_ab_test_results` | GET | read | Get A/B test results |
| `create_report` | POST | write | Create scheduled report |
| `export_report` | GET | read | Export report as PDF/CSV |

### 9. System Handler (6 tools)

System health and management.

| Tool | Method | Scope | Description |
|------|--------|-------|-------------|
| `health_check` | GET | read | Check service health |
| `get_instance_info` | GET | read | Get instance information |
| `get_usage_stats` | GET | read | Get usage statistics |
| `get_storage_stats` | GET | read | Get storage usage (ClickHouse) |
| `test_connection` | GET | read | Test API connection |
| `get_rate_limit_status` | GET | read | Check rate limit status |

---

## Tool Summary

| Handler | Tools | Description |
|---------|-------|-------------|
| Events | 10 | Event tracking & ingestion |
| Export | 10 | Data export & retrieval |
| Projects | 8 | Project management |
| Dashboards | 10 | Dashboard & chart management |
| Funnels | 8 | Funnel analysis |
| Profiles | 8 | User profile management |
| Clients | 6 | API client management |
| Reports | 8 | Analytics & reporting |
| System | 6 | Health & instance info |
| **Total** | **74** | |

---

## Implementation Phases

### Phase H.1: Core (Required)

**Goal**: Basic event tracking and data export

1. **OpenPanelPlugin** class
2. **OpenPanelClient** (unified)
3. **Events Handler** (10 tools)
4. **Export Handler** (10 tools)
5. **System Handler** (6 tools)

**Tools**: 26

### Phase H.2: Analytics (Recommended)

**Goal**: Advanced analytics features

1. **Reports Handler** (8 tools)
2. **Funnels Handler** (8 tools)
3. **Profiles Handler** (8 tools)

**Tools**: 24 (Total: 50)

### Phase H.3: Management (Complete)

**Goal**: Full dashboard and project management

1. **Projects Handler** (8 tools)
2. **Dashboards Handler** (10 tools)
3. **Clients Handler** (6 tools)

**Tools**: 24 (Total: 74)

---

## Export API Reference

### Event Segmentation Types

| Segment | Description |
|---------|-------------|
| `event` | Count total events |
| `user` | Count unique users |
| `session` | Count unique sessions |
| `user_average` | Average per user |
| `one_event_per_user` | First event per user |
| `property_sum` | Sum of property values |
| `property_average` | Average of property values |
| `property_min` | Minimum property value |
| `property_max` | Maximum property value |

### Filter Operators

| Operator | Description |
|----------|-------------|
| `is` | Exact match |
| `isNot` | Not equal |
| `contains` | Contains substring |
| `doesNotContain` | Does not contain |
| `startsWith` | Starts with |
| `endsWith` | Ends with |
| `regex` | Regular expression |
| `isNull` | Is null/undefined |
| `isNotNull` | Is not null |

### Breakdown Dimensions

| Dimension | Description |
|-----------|-------------|
| `country` | Country |
| `region` | Region/State |
| `city` | City |
| `device` | Device type |
| `browser` | Browser name |
| `os` | Operating system |
| `referrer` | Traffic source |
| `path` | Page path |

### Date Ranges

```
30min, lastHour, today, yesterday
7d, 30d, 6m, 12m
monthToDate, lastMonth
yearToDate, lastYear
```

---

## Error Handling

### HTTP Status Codes

| Code | Description | Action |
|------|-------------|--------|
| 200 | Success | Return data |
| 400 | Bad Request | Validate input |
| 401 | Unauthorized | Check credentials |
| 403 | Forbidden | Check client mode |
| 404 | Not Found | Resource doesn't exist |
| 429 | Rate Limited | Implement backoff |
| 500 | Server Error | Retry with backoff |

### Rate Limiting

```
Limit: 100 requests per 10 seconds per client
Backoff: Exponential (1s, 2s, 4s, 8s...)

Headers:
  X-RateLimit-Limit: 100
  X-RateLimit-Remaining: 95
  X-RateLimit-Reset: 1699999999
```

---

## Security Considerations

### Client Secret Protection

```
┌─────────────────────────────────────────────────────────────────┐
│                    Client Security                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  write mode client:                                              │
│  ├── Can send events only                                        │
│  ├── Cannot read data                                            │
│  └── Safe for client-side (with domain restrictions)             │
│                                                                  │
│  read mode client:                                               │
│  ├── Can export data                                             │
│  ├── Cannot send events                                          │
│  └── Server-side only                                            │
│                                                                  │
│  root mode client:                                               │
│  ├── Full access                                                 │
│  ├── Can manage projects, clients                                │
│  └── ⚠️ Server-side only - Never expose!                         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Best Practices

1. **Use appropriate client mode** - write for tracking, read for export
2. **Never expose root clients** - Server-side only
3. **Implement rate limiting** - Respect API limits
4. **GDPR compliance** - Use profile deletion tools
5. **Audit data exports** - Log who exports what

---

## Example Usage

### Track Event

```json
{
    "tool": "track_event",
    "args": {
        "site": "myanalytics",
        "name": "purchase_completed",
        "properties": {
            "product_id": "prod_123",
            "amount": 99.99,
            "currency": "USD",
            "category": "electronics"
        },
        "profile_id": "user_456"
    }
}
```

### Identify User

```json
{
    "tool": "identify_user",
    "args": {
        "site": "myanalytics",
        "profile_id": "user_456",
        "properties": {
            "firstName": "John",
            "lastName": "Doe",
            "email": "john@example.com",
            "plan": "premium",
            "company": "Acme Inc"
        }
    }
}
```

### Export Events

```json
{
    "tool": "export_events",
    "args": {
        "site": "myanalytics",
        "project_id": "proj_abc",
        "event": "purchase_completed",
        "start": "2025-11-01",
        "end": "2025-11-30",
        "limit": 100,
        "includes": ["profile"]
    }
}
```

### Create Funnel

```json
{
    "tool": "create_funnel",
    "args": {
        "site": "myanalytics",
        "project_id": "proj_abc",
        "name": "Checkout Flow",
        "steps": [
            {"name": "View Product", "event": "product_viewed"},
            {"name": "Add to Cart", "event": "cart_added"},
            {"name": "Start Checkout", "event": "checkout_started"},
            {"name": "Complete Purchase", "event": "purchase_completed"}
        ],
        "window_days": 7
    }
}
```

### Get Retention Report

```json
{
    "tool": "get_retention_report",
    "args": {
        "site": "myanalytics",
        "project_id": "proj_abc",
        "start_event": "signup_completed",
        "return_event": "app_opened",
        "period": "week",
        "cohorts": 12
    }
}
```

---

## Coolify Deployment Notes

### OpenPanel Services

```yaml
# OpenPanel services in Coolify
services:
  dashboard:     # Next.js - port 3000
  api:           # Fastify Event API - port 3333
  worker:        # BullMQ worker
  postgres:      # PostgreSQL - metadata
  clickhouse:    # ClickHouse - events
  redis:         # Redis - cache/queue
```

### Environment Variables (Coolify)

```bash
# Required
NEXT_PUBLIC_DASHBOARD_URL=https://analytics.example.com
DATABASE_URL=postgresql://...
CLICKHOUSE_URL=http://clickhouse:8123
REDIS_URL=redis://redis:6379

# Optional
RESEND_API_KEY=re_...
OPENAI_API_KEY=sk-...  # For AI features
ANTHROPIC_API_KEY=sk-...
```

### Finding Credentials

1. **URL**: Coolify Dashboard → Project → OpenPanel → Domain
2. **Client ID/Secret**: OpenPanel Dashboard → Settings → Clients

---

## Endpoint Registration

### Endpoint Config

```python
# core/endpoints/config.py

EndpointType.OPENPANEL: EndpointConfig(
    path="/openpanel",
    name="OpenPanel Analytics",
    description="OpenPanel product analytics management (events, funnels, dashboards)",
    endpoint_type=EndpointType.OPENPANEL,
    plugin_types=["openpanel"],
    require_master_key=False,
    allowed_scopes={"read", "write", "admin"},
    tool_blacklist={
        "manage_api_keys_create",
        "manage_api_keys_delete",
        "oauth_register_client",
        "oauth_revoke_client",
    },
    max_tools=80,
),
```

---

## Testing Checklist

### Unit Tests

- [ ] OpenPanelClient authentication
- [ ] Track API operations (track, identify, increment)
- [ ] Export API operations (events, charts)
- [ ] Error handling for all endpoints
- [ ] Rate limiting behavior

### Integration Tests

- [ ] Track event and verify in export
- [ ] Create funnel and get conversion data
- [ ] Create dashboard with charts
- [ ] Profile identification and merging
- [ ] GDPR data export and deletion

---

## Comparison with Other Plugins

| Aspect | Supabase | n8n | OpenPanel |
|--------|----------|-----|-----------|
| Primary Focus | Database/Backend | Automation | Analytics |
| Auth Method | JWT Keys | API Key | Client ID/Secret |
| Main APIs | PostgREST, GoTrue | REST API | Track, Export |
| Tools | 70 | 56 | 74 |
| Phases | 3 | 1 | 3 |

---

## References

- [OpenPanel Documentation](https://openpanel.dev/docs)
- [OpenPanel GitHub](https://github.com/Openpanel-dev/openpanel)
- [Track API Reference](https://openpanel.dev/docs/api/track)
- [Export API Reference](https://openpanel.dev/docs/api/export)
- [Coolify OpenPanel](https://coolify.io/docs/services/openpanel)

---

**Created**: 2025-11-30
**Author**: Claude AI Assistant
**Status**: Design Phase
