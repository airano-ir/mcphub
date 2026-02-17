# Appwrite Plugin Design - Phase I

> **MCP Plugin برای مدیریت Appwrite Self-Hosted روی Coolify**

**Version**: v1.0.0 (طراحی)
**Priority**: High (جایگزین Phase J)
**Estimated Tools**: 85-95

---

## Overview

پلاگین Appwrite برای مدیریت **Appwrite Self-Hosted** روی Coolify طراحی شده است. Appwrite یک پلتفرم Backend-as-a-Service متن‌باز است که امکانات جامعی برای Database، Authentication، Storage، Functions و Messaging ارائه می‌دهد.

### مقایسه با Supabase

```
┌─────────────────────────────────────────────────────────────────┐
│              Appwrite vs Supabase Self-Hosted                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Appwrite:                                                       │
│  ├── Document-based Database (NoSQL-like)                       │
│  ├── Built-in Users & Teams management                          │
│  ├── Messaging (Email, SMS, Push) built-in                      │
│  ├── 30+ OAuth providers                                         │
│  ├── Multi-runtime Functions (Node, Python, PHP, etc.)          │
│  ├── Database Transactions (v1.8+)                              │
│  └── GraphQL + REST APIs                                         │
│                                                                  │
│  Supabase:                                                       │
│  ├── PostgreSQL (relational)                                    │
│  ├── GoTrue for Auth                                            │
│  ├── No built-in messaging                                      │
│  ├── Deno-only Edge Functions                                   │
│  └── PostgREST for REST API                                     │
│                                                                  │
│  هر دو: Self-Hosted، Open Source، Coolify-compatible            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### ویژگی‌های Self-Hosted Appwrite

```
✅ موجود در Self-Hosted:
├── Database API (Collections, Documents, Queries)
├── Users API (Users, Sessions, Teams, Memberships)
├── Storage API (Buckets, Files, Image Transformation)
├── Functions API (Deployments, Executions, Variables)
├── Messaging API (Email, SMS, Push Notifications)
├── Health API (Service status, Queue monitoring)
├── Avatars API (Image utilities)
├── Realtime API (WebSocket subscriptions)
├── GraphQL API (Alternative to REST)
└── Webhooks & Events

❌ محدودیت‌ها:
├── Console API (Project management) - نیاز به Console access
├── Rate limiting بالا (پیش‌فرض 60/دقیقه) - قابل تنظیم
└── بعضی features نیاز به تنظیمات اضافی دارند
```

---

## Authentication

### روش‌های احراز هویت

```
┌─────────────────────────────────────────────────────────────────┐
│               Appwrite Self-Hosted Authentication                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  API Key:                                                        │
│  ├── X-Appwrite-Key header                                       │
│  ├── Server-side only                                            │
│  ├── Scoped permissions                                          │
│  ├── Bypasses rate limits                                        │
│  └── Admin mode (bypasses permissions)                           │
│                                                                  │
│  JWT Token:                                                       │
│  ├── Authorization: Bearer {token}                               │
│  ├── 15-minute expiration                                        │
│  ├── Respects user permissions                                   │
│  └── Rate limited (10 tokens/60min/user)                         │
│                                                                  │
│  Session (Client):                                                │
│  ├── Cookie-based                                                │
│  ├── For client SDKs                                             │
│  └── Subject to rate limiting                                    │
│                                                                  │
│  Project ID:                                                      │
│  ├── X-Appwrite-Project header (required)                        │
│  └── Identifies which project to access                          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Environment Variables

```bash
# Appwrite Self-Hosted Instance (Required)
APPWRITE_SITE1_URL=https://appwrite.example.com/v1
APPWRITE_SITE1_PROJECT_ID=your-project-id
APPWRITE_SITE1_API_KEY=your-api-key-with-scopes
APPWRITE_SITE1_ALIAS=myappwrite

# Multiple Instances
APPWRITE_SITE2_URL=https://appwrite-staging.example.com/v1
APPWRITE_SITE2_PROJECT_ID=staging-project-id
APPWRITE_SITE2_API_KEY=staging-api-key
APPWRITE_SITE2_ALIAS=staging
```

### API Key Scopes

```
Authentication & Users:
├── sessions.read / sessions.write
├── users.read / users.write
└── teams.read / teams.write

Database:
├── databases.read / databases.write
├── collections.read / collections.write (tables)
├── attributes.read / attributes.write (columns)
├── indexes.read / indexes.write
└── documents.read / documents.write (rows)

Storage:
├── buckets.read / buckets.write
└── files.read / files.write

Functions:
├── functions.read / functions.write
└── execution.read / execution.write

Messaging:
├── messages.read / messages.write
├── providers.read / providers.write
├── topics.read / topics.write
└── subscribers.read / subscribers.write

Other:
├── health.read
├── locale.read
└── avatars.read
```

---

## API Endpoints

### Base URL Structure

```
Self-Hosted: https://[SERVER_HOSTNAME]/v1

Database:
  GET/POST        /databases
  GET/PUT/DELETE  /databases/{databaseId}
  GET/POST        /databases/{databaseId}/collections
  GET/POST        /databases/{databaseId}/collections/{collectionId}/documents
  ...

Users:
  GET/POST        /users
  GET/PUT/DELETE  /users/{userId}
  GET/DELETE      /users/{userId}/sessions
  ...

Storage:
  GET/POST        /storage/buckets
  GET/POST        /storage/buckets/{bucketId}/files
  GET             /storage/buckets/{bucketId}/files/{fileId}/preview
  ...

Functions:
  GET/POST        /functions
  POST            /functions/{functionId}/executions
  ...

Messaging:
  GET/POST        /messaging/providers
  GET/POST        /messaging/topics
  POST            /messaging/messages
  ...

Health:
  GET             /health
  GET             /health/db
  GET             /health/queue
  ...
```

---

## Architecture

### Project Structure

```
plugins/appwrite/
├── __init__.py              # Export: AppwritePlugin, AppwriteClient
├── plugin.py                # کلاس اصلی AppwritePlugin
├── client.py                # AppwriteClient (REST client)
└── handlers/
    ├── __init__.py
    ├── databases.py         # Database & Collections (18 tools)
    ├── documents.py         # Document CRUD & Queries (12 tools)
    ├── users.py             # User management (12 tools)
    ├── teams.py             # Teams & Memberships (10 tools)
    ├── storage.py           # Buckets & Files (14 tools)
    ├── functions.py         # Functions & Executions (14 tools)
    ├── messaging.py         # Email, SMS, Push (12 tools)
    └── system.py            # Health & Avatars (8 tools)
```

### Client Architecture

```python
class AppwriteClient:
    """
    REST API Client for Appwrite Self-Hosted

    All requests include Project ID and API Key headers.
    """
    def __init__(
        self,
        base_url: str,           # e.g., https://appwrite.example.com/v1
        project_id: str,         # Appwrite project ID
        api_key: str,            # API key with required scopes
    ):
        self.base_url = base_url.rstrip('/')
        self.project_id = project_id
        self.api_key = api_key

    def _get_headers(self, additional_headers: Optional[Dict] = None) -> Dict[str, str]:
        """Get request headers with authentication."""
        headers = {
            "Content-Type": "application/json",
            "X-Appwrite-Project": self.project_id,
            "X-Appwrite-Key": self.api_key,
        }
        if additional_headers:
            headers.update(additional_headers)
        return headers

    async def request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        json_data: Optional[Dict] = None,
        headers_override: Optional[Dict] = None
    ) -> Any:
        """Make authenticated request to Appwrite API"""
        url = f"{self.base_url}{endpoint}"
        headers = self._get_headers(headers_override)
        # ... request logic
```

---

## Tool Categories

### 1. Databases Handler (18 tools)

مدیریت Databases و Collections

| Tool | Method | Scope | Description |
|------|--------|-------|-------------|
| `list_databases` | GET | read | لیست databases |
| `get_database` | GET | read | جزئیات database |
| `create_database` | POST | write | ایجاد database |
| `update_database` | PUT | write | به‌روزرسانی database |
| `delete_database` | DELETE | admin | حذف database |
| `list_collections` | GET | read | لیست collections |
| `get_collection` | GET | read | جزئیات collection |
| `create_collection` | POST | write | ایجاد collection |
| `update_collection` | PUT | write | به‌روزرسانی collection |
| `delete_collection` | DELETE | admin | حذف collection |
| `list_attributes` | GET | read | لیست attributes |
| `create_string_attribute` | POST | write | attribute متنی |
| `create_integer_attribute` | POST | write | attribute عددی |
| `create_boolean_attribute` | POST | write | attribute boolean |
| `create_enum_attribute` | POST | write | attribute enum |
| `create_datetime_attribute` | POST | write | attribute تاریخ |
| `delete_attribute` | DELETE | admin | حذف attribute |
| `list_indexes` | GET | read | لیست indexes |
| `create_index` | POST | write | ایجاد index |
| `delete_index` | DELETE | admin | حذف index |

```python
# Create Collection Example
{
    "name": "create_collection",
    "method_name": "create_collection",
    "description": "Create a new collection in database",
    "schema": {
        "type": "object",
        "properties": {
            "database_id": {
                "type": "string",
                "description": "Database ID"
            },
            "collection_id": {
                "type": "string",
                "description": "Unique collection ID (use 'unique()' for auto)"
            },
            "name": {
                "type": "string",
                "description": "Collection name"
            },
            "permissions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Array of permission strings",
                "default": []
            },
            "document_security": {
                "type": "boolean",
                "description": "Enable document-level permissions",
                "default": true
            },
            "enabled": {
                "type": "boolean",
                "default": true
            }
        },
        "required": ["database_id", "collection_id", "name"]
    },
    "scope": "write"
}
```

### 2. Documents Handler (12 tools)

عملیات CRUD روی Documents

| Tool | Method | Scope | Description |
|------|--------|-------|-------------|
| `list_documents` | GET | read | لیست documents با فیلتر |
| `get_document` | GET | read | دریافت یک document |
| `create_document` | POST | write | ایجاد document |
| `update_document` | PATCH | write | به‌روزرسانی document |
| `delete_document` | DELETE | write | حذف document |
| `bulk_create_documents` | POST | write | ایجاد دسته‌ای |
| `bulk_update_documents` | PATCH | write | به‌روزرسانی دسته‌ای |
| `bulk_delete_documents` | DELETE | write | حذف دسته‌ای |
| `count_documents` | GET | read | شمارش documents |
| `search_documents` | GET | read | جستجوی full-text |
| `create_transaction` | POST | admin | شروع transaction (v1.8+) |
| `commit_transaction` | PUT | admin | commit/rollback transaction |

```python
# List Documents with Queries
{
    "name": "list_documents",
    "method_name": "list_documents",
    "description": "List documents with queries, filters, and pagination",
    "schema": {
        "type": "object",
        "properties": {
            "database_id": {
                "type": "string",
                "description": "Database ID"
            },
            "collection_id": {
                "type": "string",
                "description": "Collection ID"
            },
            "queries": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Query strings (e.g., 'equal(\"status\", \"active\")')",
                "examples": [
                    "equal(\"status\", [\"active\"])",
                    "greaterThan(\"price\", 100)",
                    "search(\"title\", \"keyword\")",
                    "orderDesc(\"createdAt\")",
                    "limit(25)",
                    "offset(0)"
                ]
            }
        },
        "required": ["database_id", "collection_id"]
    },
    "scope": "read"
}
```

### 3. Users Handler (12 tools)

مدیریت کاربران

| Tool | Method | Scope | Description |
|------|--------|-------|-------------|
| `list_users` | GET | read | لیست کاربران |
| `get_user` | GET | read | جزئیات کاربر |
| `create_user` | POST | write | ایجاد کاربر |
| `update_user` | PATCH | write | به‌روزرسانی کاربر |
| `delete_user` | DELETE | admin | حذف کاربر |
| `update_user_email` | PATCH | write | تغییر ایمیل |
| `update_user_phone` | PATCH | write | تغییر تلفن |
| `update_user_status` | PATCH | admin | فعال/غیرفعال کردن |
| `update_user_labels` | PUT | admin | تنظیم labels |
| `list_user_sessions` | GET | read | لیست sessions |
| `delete_user_sessions` | DELETE | admin | حذف همه sessions |
| `delete_user_session` | DELETE | admin | حذف یک session |

```python
# Create User Example
{
    "name": "create_user",
    "method_name": "create_user",
    "description": "Create a new user",
    "schema": {
        "type": "object",
        "properties": {
            "user_id": {
                "type": "string",
                "description": "Unique user ID (use 'unique()' for auto)"
            },
            "email": {
                "type": "string",
                "format": "email",
                "description": "User email"
            },
            "phone": {
                "type": "string",
                "description": "Phone number (E.164 format)"
            },
            "password": {
                "type": "string",
                "minLength": 8,
                "description": "Password (min 8 chars)"
            },
            "name": {
                "type": "string",
                "description": "User display name"
            }
        },
        "required": ["user_id"]
    },
    "scope": "write"
}
```

### 4. Teams Handler (10 tools)

مدیریت Teams و Memberships

| Tool | Method | Scope | Description |
|------|--------|-------|-------------|
| `list_teams` | GET | read | لیست teams |
| `get_team` | GET | read | جزئیات team |
| `create_team` | POST | write | ایجاد team |
| `update_team` | PUT | write | به‌روزرسانی team |
| `delete_team` | DELETE | admin | حذف team |
| `list_team_memberships` | GET | read | لیست اعضا |
| `create_team_membership` | POST | write | دعوت عضو |
| `update_membership` | PATCH | write | به‌روزرسانی عضویت |
| `delete_membership` | DELETE | write | حذف عضو |
| `update_membership_status` | PATCH | write | تایید/رد عضویت |

### 5. Storage Handler (14 tools)

مدیریت Buckets و Files

| Tool | Method | Scope | Description |
|------|--------|-------|-------------|
| `list_buckets` | GET | read | لیست buckets |
| `get_bucket` | GET | read | جزئیات bucket |
| `create_bucket` | POST | write | ایجاد bucket |
| `update_bucket` | PUT | write | به‌روزرسانی bucket |
| `delete_bucket` | DELETE | admin | حذف bucket |
| `list_files` | GET | read | لیست فایل‌ها |
| `get_file` | GET | read | جزئیات فایل |
| `create_file` | POST | write | آپلود فایل |
| `update_file` | PUT | write | به‌روزرسانی فایل |
| `delete_file` | DELETE | write | حذف فایل |
| `get_file_download` | GET | read | دانلود فایل |
| `get_file_preview` | GET | read | پیش‌نمایش تصویر |
| `get_file_view` | GET | read | مشاهده در browser |
| `move_file` | PUT | write | انتقال فایل |

```python
# Get File Preview with Transformations
{
    "name": "get_file_preview",
    "method_name": "get_file_preview",
    "description": "Get image preview with transformations",
    "schema": {
        "type": "object",
        "properties": {
            "bucket_id": {"type": "string"},
            "file_id": {"type": "string"},
            "width": {
                "type": "integer",
                "minimum": 0,
                "maximum": 4000,
                "description": "Preview width (0-4000)"
            },
            "height": {
                "type": "integer",
                "minimum": 0,
                "maximum": 4000,
                "description": "Preview height (0-4000)"
            },
            "gravity": {
                "type": "string",
                "enum": ["center", "top", "top-left", "top-right",
                         "left", "right", "bottom", "bottom-left", "bottom-right"],
                "default": "center"
            },
            "quality": {
                "type": "integer",
                "minimum": 0,
                "maximum": 100,
                "default": 90
            },
            "output": {
                "type": "string",
                "enum": ["jpeg", "jpg", "png", "gif", "webp", "avif"],
                "default": "webp"
            },
            "rotation": {
                "type": "integer",
                "minimum": 0,
                "maximum": 360
            },
            "background": {
                "type": "string",
                "description": "Background color (hex without #)"
            },
            "border_width": {"type": "integer"},
            "border_color": {"type": "string"},
            "border_radius": {"type": "integer"}
        },
        "required": ["bucket_id", "file_id"]
    },
    "scope": "read"
}
```

### 6. Functions Handler (14 tools)

مدیریت Serverless Functions

| Tool | Method | Scope | Description |
|------|--------|-------|-------------|
| `list_functions` | GET | read | لیست functions |
| `get_function` | GET | read | جزئیات function |
| `create_function` | POST | write | ایجاد function |
| `update_function` | PUT | write | به‌روزرسانی function |
| `delete_function` | DELETE | admin | حذف function |
| `list_deployments` | GET | read | لیست deployments |
| `get_deployment` | GET | read | جزئیات deployment |
| `create_deployment` | POST | write | deploy کد جدید |
| `delete_deployment` | DELETE | write | حذف deployment |
| `update_deployment` | PATCH | write | فعال کردن deployment |
| `list_executions` | GET | read | لیست executions |
| `get_execution` | GET | read | جزئیات execution |
| `create_execution` | POST | write | اجرای function |
| `delete_execution` | DELETE | write | حذف execution log |

```python
# Create Execution (Run Function)
{
    "name": "create_execution",
    "method_name": "create_execution",
    "description": "Execute a function",
    "schema": {
        "type": "object",
        "properties": {
            "function_id": {
                "type": "string",
                "description": "Function ID"
            },
            "body": {
                "type": "string",
                "description": "Request body (string or JSON string)"
            },
            "async": {
                "type": "boolean",
                "default": false,
                "description": "Run asynchronously"
            },
            "path": {
                "type": "string",
                "description": "Custom execution path"
            },
            "method": {
                "type": "string",
                "enum": ["GET", "POST", "PUT", "PATCH", "DELETE"],
                "default": "POST"
            },
            "headers": {
                "type": "object",
                "description": "Custom headers"
            }
        },
        "required": ["function_id"]
    },
    "scope": "write"
}
```

### 7. Messaging Handler (12 tools)

ارسال پیام از طریق Email, SMS, Push

| Tool | Method | Scope | Description |
|------|--------|-------|-------------|
| `list_providers` | GET | read | لیست providers |
| `get_provider` | GET | read | جزئیات provider |
| `create_email_provider` | POST | admin | ایجاد email provider |
| `create_sms_provider` | POST | admin | ایجاد SMS provider |
| `create_push_provider` | POST | admin | ایجاد push provider |
| `delete_provider` | DELETE | admin | حذف provider |
| `list_topics` | GET | read | لیست topics |
| `create_topic` | POST | write | ایجاد topic |
| `delete_topic` | DELETE | write | حذف topic |
| `create_subscriber` | POST | write | اضافه کردن subscriber |
| `delete_subscriber` | DELETE | write | حذف subscriber |
| `send_message` | POST | write | ارسال پیام |

```python
# Send Email Message
{
    "name": "send_message",
    "method_name": "send_message",
    "description": "Send email, SMS, or push notification",
    "schema": {
        "type": "object",
        "properties": {
            "message_id": {
                "type": "string",
                "description": "Unique message ID"
            },
            "type": {
                "type": "string",
                "enum": ["email", "sms", "push"],
                "description": "Message type"
            },
            "topics": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Target topic IDs"
            },
            "targets": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Target user IDs"
            },
            "subject": {
                "type": "string",
                "description": "Email subject"
            },
            "content": {
                "type": "string",
                "description": "Message content (HTML for email)"
            },
            "scheduled_at": {
                "type": "string",
                "format": "date-time",
                "description": "Schedule delivery time"
            }
        },
        "required": ["message_id", "type", "content"]
    },
    "scope": "write"
}
```

### 8. System Handler (8 tools)

سلامت سیستم و Utilities

| Tool | Method | Scope | Description |
|------|--------|-------|-------------|
| `health_check` | GET | read | وضعیت کلی سرور |
| `health_db` | GET | read | وضعیت database |
| `health_cache` | GET | read | وضعیت cache |
| `health_queue` | GET | read | وضعیت queue |
| `health_storage` | GET | read | وضعیت storage |
| `health_time` | GET | read | همزمانی ساعت |
| `get_avatar_initials` | GET | read | آواتار از initials |
| `get_avatar_image` | GET | read | آواتار از URL |

---

## Query System

### Query Operators

Appwrite از سیستم Query مخصوص خود استفاده می‌کند:

```javascript
// Comparison
Query.equal("status", ["active"])
Query.notEqual("status", ["deleted"])
Query.lessThan("price", 100)
Query.lessThanOrEqual("price", 100)
Query.greaterThan("price", 50)
Query.greaterThanOrEqual("price", 50)
Query.between("price", 50, 100)

// String
Query.startsWith("name", "John")
Query.endsWith("email", "@example.com")
Query.search("title", "keyword")          // Requires fulltext index

// Array
Query.contains("tags", ["featured"])
Query.isNull("deleted_at")
Query.isNotNull("published_at")

// Sorting & Pagination
Query.orderAsc("created_at")
Query.orderDesc("created_at")
Query.limit(25)
Query.offset(0)
Query.cursorAfter("document_id")
Query.cursorBefore("document_id")

// Selection
Query.select(["id", "name", "email"])
```

### Query در REST API

```bash
# Example: List active users, sorted by creation date
GET /databases/{dbId}/collections/{colId}/documents?queries[]=equal("status",["active"])&queries[]=orderDesc("$createdAt")&queries[]=limit(25)
```

---

## Tool Summary

| Handler | Tools | Description |
|---------|-------|-------------|
| Databases | 18 | Database, Collections, Attributes, Indexes |
| Documents | 12 | Document CRUD, Bulk ops, Transactions |
| Users | 12 | User management |
| Teams | 10 | Teams & Memberships |
| Storage | 14 | Buckets, Files, Image transformation |
| Functions | 14 | Functions, Deployments, Executions |
| Messaging | 12 | Email, SMS, Push notifications |
| System | 8 | Health checks, Avatars |
| **Total** | **100** | |

---

## Implementation Phases

### Phase I.1: Core (Database + System) - 38 tools

**هدف**: دسترسی اولیه به Appwrite Self-Hosted

1. **AppwritePlugin** class
2. **AppwriteClient** (REST client)
3. **Databases Handler** (18 tools)
4. **Documents Handler** (12 tools)
5. **System Handler** (8 tools)

### Phase I.2: Auth & Teams - 22 tools

**هدف**: مدیریت کاربران و تیم‌ها

1. **Users Handler** (12 tools)
2. **Teams Handler** (10 tools)

**جمع**: 60 tools

### Phase I.3: Storage - 14 tools

**هدف**: مدیریت فایل‌ها

1. **Storage Handler** (14 tools)

**جمع**: 74 tools

### Phase I.4: Functions & Messaging - 26 tools

**هدف**: قابلیت‌های پیشرفته

1. **Functions Handler** (14 tools)
2. **Messaging Handler** (12 tools)

**جمع**: 100 tools

---

## Error Handling

### HTTP Status Codes

```python
async def handle_appwrite_error(response):
    """Handle Appwrite API errors"""
    data = await response.json()

    message = data.get("message", "Unknown error")
    code = data.get("code", response.status)
    error_type = data.get("type", "general_error")

    if response.status == 400:
        raise ValidationError(f"Bad Request: {message}")
    elif response.status == 401:
        raise AuthError("Invalid API key or missing authentication")
    elif response.status == 403:
        raise PermissionError(f"Permission denied: {message}")
    elif response.status == 404:
        raise NotFoundError(f"Resource not found: {message}")
    elif response.status == 409:
        raise ConflictError(f"Conflict: {message}")
    elif response.status == 429:
        raise RateLimitError("Rate limit exceeded. Try again later.")
    elif response.status >= 500:
        raise ServerError(f"Server error ({code}): {message}")
    else:
        raise AppwriteError(f"Error ({code}): {message}")
```

### Common Error Types

```
user_not_found          - کاربر پیدا نشد
document_not_found      - document پیدا نشد
collection_not_found    - collection پیدا نشد
database_not_found      - database پیدا نشد
storage_bucket_not_found - bucket پیدا نشد
storage_file_not_found  - فایل پیدا نشد
document_already_exists - document تکراری
user_already_exists     - کاربر تکراری
attribute_already_exists - attribute تکراری
```

---

## Security Considerations

### API Key Security

```
┌─────────────────────────────────────────────────────────────────┐
│                    API Key Best Practices                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ✅ Best Practices:                                              │
│  ├── Create separate keys for different purposes                │
│  ├── Use minimal required scopes                                │
│  ├── Rotate keys periodically                                   │
│  ├── Never expose keys in client-side code                      │
│  └── Use environment variables for storage                      │
│                                                                  │
│  ⚠️ Scope Recommendations:                                       │
│  ├── Read operations: *.read scopes only                        │
│  ├── Write operations: specific *.write scopes                  │
│  └── Admin operations: all scopes + careful monitoring          │
│                                                                  │
│  ❌ Never Do:                                                    │
│  ├── Log API keys (even partially)                              │
│  ├── Commit keys to version control                             │
│  ├── Share keys across different services                       │
│  └── Use single key for all operations                          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Permission System

```python
# Document-level permissions
permissions = [
    "read(\"user:123\")",      # Specific user can read
    "write(\"user:123\")",     # Specific user can write
    "read(\"team:456\")",      # Team members can read
    "read(\"any\")",           # Anyone can read (public)
    "create(\"users\")",       # Any authenticated user
    "update(\"label:admin\")", # Users with admin label
]
```

---

## Example Usage

### Query Documents

```json
{
    "tool": "list_documents",
    "args": {
        "site": "myappwrite",
        "database_id": "main",
        "collection_id": "posts",
        "queries": [
            "equal(\"status\", [\"published\"])",
            "greaterThan(\"views\", 100)",
            "orderDesc(\"$createdAt\")",
            "limit(20)"
        ]
    }
}
```

### Create User

```json
{
    "tool": "create_user",
    "args": {
        "site": "myappwrite",
        "user_id": "unique()",
        "email": "user@example.com",
        "password": "securePassword123",
        "name": "John Doe"
    }
}
```

### Upload File

```json
{
    "tool": "create_file",
    "args": {
        "site": "myappwrite",
        "bucket_id": "avatars",
        "file_id": "unique()",
        "file_content_base64": "iVBORw0KGgoAAAANSUhEUgAA...",
        "file_name": "avatar.png",
        "permissions": ["read(\"any\")"]
    }
}
```

### Execute Function

```json
{
    "tool": "create_execution",
    "args": {
        "site": "myappwrite",
        "function_id": "send-welcome-email",
        "body": "{\"userId\": \"123\", \"template\": \"welcome\"}",
        "async": false
    }
}
```

### Send Email

```json
{
    "tool": "send_message",
    "args": {
        "site": "myappwrite",
        "message_id": "unique()",
        "type": "email",
        "targets": ["user-123"],
        "subject": "Welcome to our platform!",
        "content": "<h1>Welcome!</h1><p>Thanks for signing up.</p>"
    }
}
```

---

## Coolify Deployment Notes

### Finding Appwrite Credentials

در Coolify، بعد از deploy کردن Appwrite:

1. **URL**: از Coolify dashboard → Project → Appwrite → Domain
   - معمولاً: `https://appwrite.yourdomain.com/v1`

2. **Project ID**:
   - در Appwrite Console → Settings → Project ID
   - یا از URL بعد از login

3. **API Key**:
   - Appwrite Console → Project → Settings → API Keys → Create
   - Scopes مورد نیاز را انتخاب کنید

### Docker Compose Services

```yaml
# Appwrite services on Coolify
services:
  appwrite:           # Main API - port 80
  appwrite-realtime:  # Realtime WebSocket
  appwrite-executor:  # Function execution
  appwrite-worker-*:  # Background workers
  mariadb:           # Database
  redis:             # Cache
  influxdb:          # Metrics (optional)
```

### Environment Variables (Appwrite Server)

```bash
# Key settings in Appwrite .env
_APP_ENV=production
_APP_DOMAIN=appwrite.yourdomain.com
_APP_DOMAIN_TARGET=appwrite.yourdomain.com
_APP_OPTIONS_ABUSE=enabled     # Rate limiting
_APP_FUNCTIONS_RUNTIMES=node-18.0,python-3.9,php-8.0
```

---

## Endpoint Registration

### Endpoint Config

```python
# core/endpoints/config.py

EndpointType.APPWRITE: EndpointConfig(
    path="/appwrite",
    name="Appwrite Manager",
    description="Appwrite Self-Hosted management (database, auth, storage, functions, messaging)",
    endpoint_type=EndpointType.APPWRITE,
    plugin_types=["appwrite"],
    require_master_key=False,
    allowed_scopes={"read", "write", "admin"},
    tool_blacklist={
        "manage_api_keys_create",
        "manage_api_keys_delete",
        "manage_api_keys_rotate",
        "oauth_register_client",
        "oauth_revoke_client",
    },
    max_tools=110,
),
```

---

## Comparison: Appwrite vs Supabase Tools

| Feature | Appwrite | Supabase |
|---------|----------|----------|
| Database Tools | 30 (Documents + Databases) | 18 (PostgREST) |
| Auth Tools | 22 (Users + Teams) | 14 (GoTrue) |
| Storage Tools | 14 | 12 |
| Functions Tools | 14 | 8 |
| Messaging Tools | 12 | 0 (not built-in) |
| System Tools | 8 | 6 |
| Admin Tools | - | 12 (postgres-meta) |
| **Total** | **100** | **70** |

**نکته**: Appwrite ابزارهای بیشتری دارد چون:
- Messaging built-in دارد
- Teams management جداگانه دارد
- Document/Collection model متفاوت است
- Image transformation پیشرفته‌تر است

---

## Testing Checklist

### Unit Tests

- [ ] AppwriteClient authentication
- [ ] Database CRUD operations
- [ ] Document queries with all operators
- [ ] User management operations
- [ ] Team operations
- [ ] File upload/download
- [ ] Function execution
- [ ] Message sending
- [ ] Error handling

### Integration Tests

- [ ] Create database and collection
- [ ] CRUD documents with queries
- [ ] Create user and authenticate
- [ ] Upload and preview image
- [ ] Execute serverless function
- [ ] Send email through messaging
- [ ] Health check all services
- [ ] Rate limit handling

---

## Function Runtimes

### Supported Runtimes (v1.8+)

| Runtime | Versions |
|---------|----------|
| Node.js | 18.x, 20.x |
| Python | 3.9, 3.10, 3.11, 3.12 |
| PHP | 8.0, 8.1, 8.2, 8.3 |
| Ruby | 3.0, 3.1, 3.2, 3.3 |
| Java | 11, 17, 21 |
| Go | 1.18, 1.19, 1.20, 1.21 |
| Dart | 3.0, 3.1, 3.2, 3.3 |
| Rust | 1.60, 1.65, 1.70, 1.75 |
| C# | 8, 11, 12 |
| Swift | 5.5, 5.8, 5.9 |
| Kotlin | 1.8 |

---

## References

- [Appwrite Documentation](https://appwrite.io/docs)
- [Appwrite REST API Reference](https://appwrite.io/docs/apis/rest)
- [Appwrite Self-Hosting Guide](https://appwrite.io/docs/advanced/self-hosting)
- [Appwrite Server SDKs](https://appwrite.io/docs/sdks)
- [Appwrite GitHub Repository](https://github.com/appwrite/appwrite)
- [Appwrite Database Queries](https://appwrite.io/docs/products/databases/queries)
- [Appwrite Permissions](https://appwrite.io/docs/advanced/platform/permissions)
- [Appwrite Functions](https://appwrite.io/docs/products/functions)
- [Appwrite Messaging](https://appwrite.io/docs/products/messaging)

---

**Created**: 2025-12-02
**Author**: Claude AI Assistant
**Status**: Design Phase (Ready for Implementation)
