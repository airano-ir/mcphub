# Supabase Plugin Design - Phase G

> **MCP Plugin برای مدیریت Supabase Self-Hosted روی Coolify**

**Version**: v1.1.0 (طراحی - Self-Hosted)
**Priority**: High
**Estimated Tools**: 70-75

---

## Overview

پلاگین Supabase برای مدیریت **Supabase Self-Hosted** روی Coolify طراحی شده است.

### تفاوت Self-Hosted با Cloud

```
┌─────────────────────────────────────────────────────────────────┐
│              Supabase Self-Hosted vs Cloud                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ✅ موجود در Self-Hosted:                                       │
│  ├── Database API (PostgREST) - /rest/v1/                       │
│  ├── Auth API (GoTrue) - /auth/v1/                              │
│  ├── Storage API - /storage/v1/                                 │
│  ├── Edge Functions - /functions/v1/                            │
│  ├── postgres-meta (DB Admin) - /pg/                            │
│  └── Realtime - /realtime/v1/ (WebSocket)                       │
│                                                                  │
│  ❌ فقط در Cloud:                                                │
│  ├── Management API (api.supabase.com)                          │
│  ├── Projects & Organizations                                    │
│  ├── Database Branches                                           │
│  ├── Platform Analytics                                          │
│  └── Secrets Management (platform-level)                         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**نکته مهم**: در Self-Hosted، هر instance یک پروژه است. Management API وجود ندارد.

---

## Authentication

### سطح واحد احراز هویت

```
┌─────────────────────────────────────────────────────────────────┐
│                 Supabase Self-Hosted Auth                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  API Keys (JWT-based):                                           │
│  ├── anon_key                                                    │
│  │   ├── Public/client-safe                                      │
│  │   ├── Protected by RLS policies                               │
│  │   └── role: "anon" in JWT                                     │
│  │                                                               │
│  └── service_role_key                                            │
│      ├── ⚠️ SERVER-ONLY - Never expose!                          │
│      ├── Bypasses ALL RLS policies                               │
│      └── role: "service_role" in JWT                             │
│                                                                  │
│  All keys signed with JWT_SECRET from .env                       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Environment Variables

```bash
# Supabase Self-Hosted Instance (Required)
SUPABASE_SITE1_URL=https://supabase.example.com
SUPABASE_SITE1_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_SITE1_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_SITE1_ALIAS=mysupabase

# Optional: Direct database access for postgres-meta
SUPABASE_SITE1_DB_HOST=db.supabase.example.com
SUPABASE_SITE1_DB_PORT=5432
SUPABASE_SITE1_DB_NAME=postgres
SUPABASE_SITE1_DB_USER=postgres
SUPABASE_SITE1_DB_PASSWORD=your-db-password

# Multiple Instances
SUPABASE_SITE2_URL=https://supabase-staging.example.com
SUPABASE_SITE2_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_SITE2_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_SITE2_ALIAS=staging
```

---

## API Endpoints (Kong Gateway)

تمام API ها از طریق Kong API Gateway (پورت 8000) در دسترس هستند:

```
Base URL: https://supabase.example.com (یا http://localhost:8000)

Database (PostgREST):
  GET/POST/PATCH/DELETE /rest/v1/{table}
  POST /rest/v1/rpc/{function}

Auth (GoTrue):
  POST /auth/v1/signup
  POST /auth/v1/token
  GET  /auth/v1/user
  POST /auth/v1/admin/users
  ...

Storage:
  GET/POST/DELETE /storage/v1/bucket
  GET/POST/DELETE /storage/v1/object/{bucket}/{path}
  ...

Edge Functions:
  POST /functions/v1/{function_name}

postgres-meta (Admin):
  GET  /pg/tables
  GET  /pg/columns
  GET  /pg/policies
  ...
```

---

## Architecture

### Project Structure

```
plugins/supabase/
├── __init__.py              # Export: SupabasePlugin, SupabaseClient
├── plugin.py                # کلاس اصلی SupabasePlugin
├── client.py                # SupabaseClient (unified client)
└── handlers/
    ├── __init__.py
    ├── database.py          # Database operations (18 tools)
    ├── auth.py              # User management (14 tools)
    ├── storage.py           # File management (12 tools)
    ├── functions.py         # Edge Functions (8 tools)
    ├── admin.py             # postgres-meta admin (12 tools)
    └── system.py            # Health & info (6 tools)
```

### Client Architecture

```python
class SupabaseClient:
    """
    Unified client for Supabase Self-Hosted APIs

    All requests go through Kong gateway on single base URL.
    """
    def __init__(
        self,
        base_url: str,               # e.g., https://supabase.example.com
        anon_key: str,               # For public/RLS-protected operations
        service_role_key: str,       # For admin operations (bypasses RLS)
    ):
        self.base_url = base_url.rstrip('/')
        self.anon_key = anon_key
        self.service_role_key = service_role_key

    async def request(
        self,
        method: str,
        endpoint: str,
        use_service_role: bool = False,
        **kwargs
    ) -> Any:
        """Make authenticated request to Supabase API"""
        key = self.service_role_key if use_service_role else self.anon_key
        headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json"
        }
        url = f"{self.base_url}{endpoint}"
        # ... request logic
```

---

## Tool Categories

### 1. Database Handler (18 tools)

عملیات CRUD روی دیتابیس PostgreSQL از طریق PostgREST

| Tool | Method | Scope | Description |
|------|--------|-------|-------------|
| `list_tables` | GET | read | لیست جداول (via postgres-meta) |
| `get_table_schema` | GET | read | ساختار جدول |
| `query_table` | GET | read | کوئری SELECT با فیلتر |
| `insert_rows` | POST | write | درج رکوردها |
| `update_rows` | PATCH | write | به‌روزرسانی رکوردها |
| `upsert_rows` | POST | write | درج/به‌روزرسانی |
| `delete_rows` | DELETE | write | حذف رکوردها |
| `execute_rpc` | POST | write | اجرای stored procedure |
| `count_rows` | GET | read | شمارش رکوردها |
| `get_row_by_id` | GET | read | دریافت یک رکورد با ID |
| `bulk_insert` | POST | write | درج دسته‌ای |
| `bulk_update` | PATCH | write | به‌روزرسانی دسته‌ای |
| `bulk_delete` | DELETE | write | حذف دسته‌ای |
| `search_text` | GET | read | جستجوی Full-text |
| `get_foreign_tables` | GET | read | جداول مرتبط |
| `execute_sql` | POST | admin | اجرای SQL مستقیم (via postgres-meta) |
| `create_table` | POST | admin | ایجاد جدول جدید |
| `drop_table` | DELETE | admin | حذف جدول |

```python
# Query Table Example
{
    "name": "supabase_query_table",
    "description": "Query data from a Supabase table with filters and pagination",
    "schema": {
        "type": "object",
        "properties": {
            "site": {
                "type": "string",
                "description": "Supabase instance alias or site ID"
            },
            "table": {
                "type": "string",
                "description": "Table name"
            },
            "select": {
                "type": "string",
                "description": "Columns to select (e.g., 'id,name,email' or '*')",
                "default": "*"
            },
            "filters": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "column": {"type": "string"},
                        "operator": {
                            "type": "string",
                            "enum": ["eq", "neq", "gt", "gte", "lt", "lte",
                                     "like", "ilike", "in", "is", "cs", "cd"]
                        },
                        "value": {}
                    }
                },
                "description": "PostgREST filter conditions"
            },
            "order": {
                "type": "string",
                "description": "Order by (e.g., 'created_at.desc')"
            },
            "limit": {
                "type": "integer",
                "default": 100,
                "maximum": 1000
            },
            "offset": {
                "type": "integer",
                "default": 0
            }
        },
        "required": ["table"]
    },
    "scope": "read"
}
```

### 2. Auth Handler (14 tools)

مدیریت کاربران از طریق GoTrue Admin API

| Tool | Method | Scope | Description |
|------|--------|-------|-------------|
| `list_users` | GET | admin | لیست کاربران |
| `get_user` | GET | read | جزئیات کاربر |
| `create_user` | POST | admin | ایجاد کاربر |
| `update_user` | PUT | admin | به‌روزرسانی کاربر |
| `delete_user` | DELETE | admin | حذف کاربر |
| `invite_user` | POST | admin | ارسال دعوت‌نامه |
| `generate_link` | POST | admin | تولید magic/recovery link |
| `ban_user` | PUT | admin | مسدود کردن کاربر |
| `unban_user` | PUT | admin | رفع مسدودیت |
| `list_factors` | GET | read | لیست MFA factors |
| `delete_factor` | DELETE | admin | حذف MFA factor |
| `get_audit_logs` | GET | read | لاگ‌های auth |
| `verify_otp` | POST | write | تایید OTP |
| `resend_otp` | POST | write | ارسال مجدد OTP |

```python
# Create User Example
{
    "name": "supabase_create_user",
    "description": "Create a new user in Supabase Auth",
    "schema": {
        "type": "object",
        "properties": {
            "site": {"type": "string"},
            "email": {
                "type": "string",
                "format": "email"
            },
            "password": {
                "type": "string",
                "minLength": 6
            },
            "phone": {
                "type": "string",
                "description": "Phone number (E.164 format)"
            },
            "email_confirm": {
                "type": "boolean",
                "default": false,
                "description": "Auto-confirm email"
            },
            "user_metadata": {
                "type": "object",
                "description": "Custom user metadata"
            },
            "app_metadata": {
                "type": "object",
                "description": "App-specific metadata"
            }
        },
        "required": ["email", "password"]
    },
    "scope": "admin"
}
```

### 3. Storage Handler (12 tools)

مدیریت فایل‌ها و bucket ها

| Tool | Method | Scope | Description |
|------|--------|-------|-------------|
| `list_buckets` | GET | read | لیست bucket ها |
| `get_bucket` | GET | read | جزئیات bucket |
| `create_bucket` | POST | admin | ایجاد bucket |
| `update_bucket` | PUT | admin | به‌روزرسانی bucket |
| `delete_bucket` | DELETE | admin | حذف bucket |
| `empty_bucket` | POST | admin | خالی کردن bucket |
| `list_files` | GET | read | لیست فایل‌ها در مسیر |
| `upload_file` | POST | write | آپلود فایل |
| `download_file` | GET | read | دانلود فایل (base64) |
| `delete_files` | DELETE | write | حذف فایل‌ها |
| `move_file` | POST | write | انتقال/تغییر نام فایل |
| `get_public_url` | GET | read | دریافت URL عمومی |

### 4. Functions Handler (8 tools)

مدیریت و اجرای Edge Functions

| Tool | Method | Scope | Description |
|------|--------|-------|-------------|
| `list_functions` | GET | read | لیست functions موجود |
| `invoke_function` | POST | write | اجرای function |
| `invoke_function_get` | GET | read | اجرای function با GET |
| `get_function_body` | GET | read | دریافت کد function |
| `deploy_function` | POST | admin | deploy function جدید |
| `delete_function` | DELETE | admin | حذف function |
| `get_function_logs` | GET | read | لاگ‌های اخیر |
| `update_function_secrets` | PATCH | admin | تنظیم secrets |

**نکته**: در Self-Hosted، functions در `volumes/functions/` ذخیره می‌شوند.

### 5. Admin Handler (12 tools)

عملیات مدیریتی دیتابیس از طریق postgres-meta

| Tool | Method | Scope | Description |
|------|--------|-------|-------------|
| `list_schemas` | GET | read | لیست schemas |
| `list_extensions` | GET | read | لیست extensions |
| `enable_extension` | POST | admin | فعال‌سازی extension |
| `disable_extension` | DELETE | admin | غیرفعال‌سازی extension |
| `list_policies` | GET | read | لیست RLS policies |
| `create_policy` | POST | admin | ایجاد RLS policy |
| `update_policy` | PATCH | admin | به‌روزرسانی policy |
| `delete_policy` | DELETE | admin | حذف policy |
| `list_roles` | GET | read | لیست database roles |
| `list_triggers` | GET | read | لیست triggers |
| `list_functions_db` | GET | read | لیست DB functions |
| `get_database_size` | GET | read | سایز دیتابیس |

### 6. System Handler (6 tools)

سلامت و اطلاعات سیستم

| Tool | Method | Scope | Description |
|------|--------|-------|-------------|
| `health_check` | GET | read | بررسی سلامت |
| `get_config` | GET | read | تنظیمات فعلی |
| `get_version` | GET | read | نسخه سرویس‌ها |
| `test_connection` | GET | read | تست اتصال |
| `get_stats` | GET | read | آمار سرویس‌ها |
| `ping` | GET | read | Ping ساده |

---

## Tool Summary

| Handler | Tools | Description |
|---------|-------|-------------|
| Database | 18 | PostgREST CRUD + SQL |
| Auth | 14 | GoTrue user management |
| Storage | 12 | File & bucket management |
| Functions | 8 | Edge Functions |
| Admin | 12 | postgres-meta DB admin |
| System | 6 | Health & info |
| **Total** | **70** | |

---

## Implementation Phases

### Phase G.1: Core (Required)

**هدف**: دسترسی اولیه به Supabase Self-Hosted

1. **SupabasePlugin** class
2. **SupabaseClient** (unified)
3. **Database Handler** (18 tools)
4. **System Handler** (6 tools)

**ابزارها**: 24

### Phase G.2: Auth & Storage (Recommended)

**هدف**: مدیریت کاربران و فایل‌ها

1. **Auth Handler** (14 tools)
2. **Storage Handler** (12 tools)

**ابزارها**: 26 (جمع: 50)

### Phase G.3: Advanced (Complete)

**هدف**: قابلیت‌های پیشرفته

1. **Functions Handler** (8 tools)
2. **Admin Handler** (12 tools)

**ابزارها**: 20 (جمع: 70)

---

## PostgREST Operators Reference

| Operator | Description | Example |
|----------|-------------|---------|
| `eq` | Equal | `?column=eq.value` |
| `neq` | Not equal | `?column=neq.value` |
| `gt` | Greater than | `?column=gt.5` |
| `gte` | Greater or equal | `?column=gte.5` |
| `lt` | Less than | `?column=lt.10` |
| `lte` | Less or equal | `?column=lte.10` |
| `like` | LIKE (case-sensitive) | `?column=like.*pattern*` |
| `ilike` | LIKE (case-insensitive) | `?column=ilike.*pattern*` |
| `in` | IN array | `?column=in.(a,b,c)` |
| `is` | IS (null, true, false) | `?column=is.null` |
| `cs` | Contains (arrays) | `?column=cs.{a,b}` |
| `cd` | Contained by | `?column=cd.{a,b,c}` |
| `fts` | Full-text search | `?column=fts.query` |

---

## Error Handling

### PostgREST Errors

```python
async def handle_postgrest_error(response):
    data = await response.json()

    if response.status == 400:
        # Validation error
        raise ValidationError(data.get("message", "Invalid request"))
    elif response.status == 401:
        raise AuthError("Invalid API key")
    elif response.status == 403:
        # RLS policy violation
        raise RLSError(f"Row Level Security: {data.get('message')}")
    elif response.status == 404:
        raise NotFoundError("Resource not found")
    elif response.status == 409:
        raise ConflictError("Unique constraint violation")
    elif response.status == 406:
        raise NotAcceptableError("Invalid Accept header")
```

### GoTrue Errors

```python
async def handle_gotrue_error(response):
    data = await response.json()

    error_code = data.get("error_code") or data.get("code")
    message = data.get("msg") or data.get("message") or data.get("error_description")

    if error_code == "user_not_found":
        raise UserNotFoundError(message)
    elif error_code == "email_exists":
        raise DuplicateError("Email already registered")
    # ... more error codes
```

---

## Security Considerations

### Key Security

```
┌─────────────────────────────────────────────────────────────────┐
│                    API Key Security                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  anon_key:                                                       │
│  ├── ✅ Safe for client-side                                     │
│  ├── ✅ Protected by RLS policies                                │
│  ├── ⚠️ Always enable RLS on tables                              │
│  └── Used for: read operations, authenticated user actions      │
│                                                                  │
│  service_role_key:                                               │
│  ├── ❌ NEVER expose to client                                   │
│  ├── ❌ Bypasses ALL RLS policies                                │
│  ├── ✅ Server-side only                                         │
│  └── Used for: admin operations, background jobs                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Best Practices

1. **Always use RLS** - حتی با service_role_key، RLS را فعال نگه دارید
2. **Minimal service_role usage** - فقط وقتی واقعاً نیاز است
3. **Never log keys** - حتی در error messages
4. **Validate input** - قبل از اجرای SQL
5. **Audit admin operations** - تمام عملیات admin لاگ شود

---

## Example Usage

### Query Database

```json
{
    "tool": "supabase_query_table",
    "args": {
        "site": "mysupabase",
        "table": "users",
        "select": "id,email,created_at",
        "filters": [
            {"column": "role", "operator": "eq", "value": "admin"}
        ],
        "order": "created_at.desc",
        "limit": 50
    }
}
```

### Create User

```json
{
    "tool": "supabase_create_user",
    "args": {
        "site": "mysupabase",
        "email": "user@example.com",
        "password": "secure-password",
        "email_confirm": true,
        "user_metadata": {
            "name": "John Doe",
            "role": "editor"
        }
    }
}
```

### Upload File

```json
{
    "tool": "supabase_upload_file",
    "args": {
        "site": "mysupabase",
        "bucket": "avatars",
        "path": "users/123/profile.png",
        "content_base64": "iVBORw0KGgoAAAANSUhEUgAA...",
        "content_type": "image/png",
        "upsert": true
    }
}
```

### Invoke Edge Function

```json
{
    "tool": "supabase_invoke_function",
    "args": {
        "site": "mysupabase",
        "function_name": "send-notification",
        "body": {
            "user_id": "123",
            "message": "Hello from AI!"
        }
    }
}
```

---

## Coolify Deployment Notes

### Finding Supabase Credentials

در Coolify، بعد از deploy کردن Supabase:

1. **URL**: از Coolify dashboard → Project → Supabase → Domain
2. **Keys**: در Environment Variables:
   - `ANON_KEY` - کلید عمومی
   - `SERVICE_ROLE_KEY` - کلید ادمین
   - `JWT_SECRET` - برای verify کردن tokens

### Kong Gateway Port

```
Default: 8000
HTTPS: 8443 (اگر SSL فعال باشد)

Coolify معمولاً reverse proxy می‌کند:
https://supabase.example.com → Kong:8000
```

### Docker Compose Services

```yaml
# Supabase services on Coolify
services:
  kong:        # API Gateway - port 8000
  auth:        # GoTrue - /auth/v1/
  rest:        # PostgREST - /rest/v1/
  storage:     # Storage API - /storage/v1/
  meta:        # postgres-meta - /pg/
  functions:   # Edge Functions - /functions/v1/
  db:          # PostgreSQL
  realtime:    # Realtime WebSocket
```

---

## Endpoint Registration

### Endpoint Config

```python
# core/endpoints/config.py

EndpointType.SUPABASE: EndpointConfig(
    path="/supabase",
    name="Supabase Manager",
    description="Supabase Self-Hosted management (database, auth, storage, functions)",
    endpoint_type=EndpointType.SUPABASE,
    plugin_types=["supabase"],
    require_master_key=False,
    allowed_scopes={"read", "write", "admin"},
    tool_blacklist={
        "manage_api_keys_create",
        "manage_api_keys_delete",
        "manage_api_keys_rotate",
        "oauth_register_client",
        "oauth_revoke_client",
    },
    max_tools=80,
),
```

---

## Testing Checklist

### Unit Tests

- [ ] SupabaseClient authentication
- [ ] PostgREST CRUD operations
- [ ] PostgREST filtering and pagination
- [ ] GoTrue user operations
- [ ] Storage file operations
- [ ] Error handling for all endpoints

### Integration Tests

- [ ] Query and modify database
- [ ] Create and authenticate user
- [ ] Upload and download file
- [ ] Invoke Edge Function
- [ ] RLS policy enforcement
- [ ] Service role bypass

---

## References

- [Supabase Self-Hosting Docker](https://supabase.com/docs/guides/self-hosting/docker)
- [PostgREST Documentation](https://postgrest.org/en/stable/)
- [GoTrue API Reference](https://github.com/supabase/auth)
- [Supabase Storage API](https://supabase.com/docs/guides/storage)
- [Kong API Gateway](https://docs.konghq.com/)
- [postgres-meta](https://github.com/supabase/postgres-meta)

---

**Created**: 2025-11-29
**Updated**: 2025-11-29 (Self-Hosted version)
**Author**: Claude AI Assistant
**Status**: Design Phase
