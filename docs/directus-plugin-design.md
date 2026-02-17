# Directus CMS Plugin Design - Phase J

> **MCP Plugin برای مدیریت Directus Self-Hosted روی Coolify**

**Version**: v1.0.0 (طراحی)
**Priority**: High (جایگزین Phase J)
**Estimated Tools**: 85-95

---

## Overview

پلاگین Directus برای مدیریت **Directus Self-Hosted** روی Coolify طراحی شده است. Directus یک Headless CMS متن‌باز و قدرتمند است که به صورت خودکار REST و GraphQL API برای هر دیتابیس SQL ایجاد می‌کند.

### مقایسه با سایر پلاگین‌ها

```
┌─────────────────────────────────────────────────────────────────┐
│           Directus vs Appwrite vs Supabase                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Directus:                                                       │
│  ├── SQL-based (PostgreSQL, MySQL, SQLite, etc.)                │
│  ├── Auto-generated REST + GraphQL APIs                         │
│  ├── Built-in Admin UI (Data Studio)                            │
│  ├── Flows & Operations (automation)                            │
│  ├── Version control for content                                │
│  ├── Granular permissions & policies                            │
│  ├── Dashboards & Insights                                      │
│  └── Multi-language content (Translations)                      │
│                                                                  │
│  Appwrite:                                                       │
│  ├── Document-based (NoSQL-like)                                │
│  ├── Built-in Messaging (Email, SMS, Push)                      │
│  ├── Functions with 11+ runtimes                                │
│  └── Teams management                                           │
│                                                                  │
│  Supabase:                                                       │
│  ├── PostgreSQL only                                            │
│  ├── Realtime subscriptions                                     │
│  ├── Edge Functions (Deno)                                      │
│  └── Row Level Security (RLS)                                   │
│                                                                  │
│  همه: Self-Hosted، Open Source، Coolify-compatible              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### ویژگی‌های Self-Hosted Directus

```
✅ موجود در Self-Hosted:
├── Items API (CRUD for any collection)
├── Collections API (schema management)
├── Fields API (column definitions)
├── Relations API (foreign keys)
├── Files API (asset management)
├── Users API (user management)
├── Roles & Permissions API
├── Flows & Operations API (automation)
├── Webhooks API
├── Dashboards & Panels API
├── Activity & Revisions API
├── Settings API
├── Schema API
├── Server Info API
├── GraphQL API (alternative to REST)
└── Extensions API

❌ محدودیت‌ها:
├── Cloud-specific features (not applicable)
├── Rate limiting بستگی به تنظیمات سرور دارد
└── بعضی features نیاز به extensions دارند
```

---

## Authentication

### روش‌های احراز هویت

```
┌─────────────────────────────────────────────────────────────────┐
│               Directus Self-Hosted Authentication                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Static Token (Recommended for Server-to-Server):                │
│  ├── Set in directus_users.token column                         │
│  ├── Never expires                                               │
│  ├── Pass via Authorization: Bearer {token}                      │
│  ├── Or via ?access_token={token} query param                   │
│  └── Best for MCP integration                                    │
│                                                                  │
│  JWT (Temporary Token):                                          │
│  ├── POST /auth/login with email/password                       │
│  ├── Returns access_token + refresh_token                        │
│  ├── access_token expires (default 15m)                          │
│  ├── refresh_token expires (default 7d)                          │
│  └── Use for user-facing applications                            │
│                                                                  │
│  Session (Cookie-based):                                         │
│  ├── POST /auth/login?mode=session                               │
│  ├── Cookie-based authentication                                 │
│  └── For browser-based applications                              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Environment Variables

```bash
# Directus Self-Hosted Instance (Required)
DIRECTUS_SITE1_URL=https://directus.example.com
DIRECTUS_SITE1_TOKEN=your-static-admin-token
DIRECTUS_SITE1_ALIAS=mycms

# Multiple Instances
DIRECTUS_SITE2_URL=https://directus-staging.example.com
DIRECTUS_SITE2_TOKEN=staging-static-token
DIRECTUS_SITE2_ALIAS=staging
```

### Static Token Setup

```sql
-- Set static token for admin user in database
UPDATE directus_users
SET token = 'your-secure-static-token'
WHERE email = 'admin@example.com';
```

Or via Directus Admin UI:
1. Go to User Directory
2. Select user
3. Scroll to Token field
4. Generate or set token

---

## API Endpoints

### Base URL Structure

```
Self-Hosted: https://[DIRECTUS_HOST]

Items (Dynamic Collections):
  GET/POST        /items/{collection}
  GET/PATCH/DEL   /items/{collection}/{id}

Collections (Schema):
  GET/POST        /collections
  GET/PATCH/DEL   /collections/{collection}

Fields:
  GET/POST        /fields
  GET/POST        /fields/{collection}
  GET/PATCH/DEL   /fields/{collection}/{field}

Relations:
  GET/POST        /relations
  GET/PATCH/DEL   /relations/{id}

Files & Folders:
  GET/POST        /files
  GET/PATCH/DEL   /files/{id}
  GET/POST        /folders
  GET/PATCH/DEL   /folders/{id}

Users:
  GET/POST        /users
  GET/PATCH/DEL   /users/{id}
  GET             /users/me

Roles:
  GET/POST        /roles
  GET/PATCH/DEL   /roles/{id}

Permissions:
  GET/POST        /permissions
  GET/PATCH/DEL   /permissions/{id}
  GET             /permissions/me

Policies:
  GET/POST        /policies
  GET/PATCH/DEL   /policies/{id}

Flows:
  GET/POST        /flows
  GET/PATCH/DEL   /flows/{id}
  POST            /flows/trigger/{flow_uuid}

Operations:
  GET/POST        /operations
  GET/PATCH/DEL   /operations/{id}

Webhooks:
  GET/POST        /webhooks
  GET/PATCH/DEL   /webhooks/{id}

Activity:
  GET             /activity
  GET             /activity/{id}
  POST            /activity/comment

Revisions:
  GET             /revisions
  GET             /revisions/{id}

Versions:
  GET/POST        /versions
  GET/PATCH/DEL   /versions/{id}
  POST            /versions/{id}/promote

Dashboards:
  GET/POST        /dashboards
  GET/PATCH/DEL   /dashboards/{id}

Panels:
  GET/POST        /panels
  GET/PATCH/DEL   /panels/{id}

Settings:
  GET/PATCH       /settings

Server:
  GET             /server/info
  GET             /server/health
  GET             /server/specs/oas
  GET             /server/specs/graphql

Schema:
  GET             /schema/snapshot
  POST            /schema/diff
  POST            /schema/apply

Presets:
  GET/POST        /presets
  GET/PATCH/DEL   /presets/{id}

Shares:
  GET/POST        /shares
  GET/PATCH/DEL   /shares/{id}
  POST            /shares/info

Notifications:
  GET/POST        /notifications
  GET/PATCH/DEL   /notifications/{id}

Translations:
  GET/POST        /translations
  GET/PATCH/DEL   /translations/{id}

Comments:
  GET/POST        /comments
  GET/PATCH/DEL   /comments/{id}

Extensions:
  GET             /extensions
```

---

## Architecture

### Project Structure

```
plugins/directus/
├── __init__.py              # Export: DirectusPlugin, DirectusClient
├── plugin.py                # کلاس اصلی DirectusPlugin
├── client.py                # DirectusClient (REST client)
└── handlers/
    ├── __init__.py
    ├── items.py             # Items CRUD (12 tools)
    ├── collections.py       # Collections & Fields (14 tools)
    ├── files.py             # Files & Folders (12 tools)
    ├── users.py             # Users management (10 tools)
    ├── access.py            # Roles, Permissions, Policies (12 tools)
    ├── automation.py        # Flows, Operations, Webhooks (12 tools)
    ├── content.py           # Revisions, Versions, Comments (10 tools)
    ├── dashboards.py        # Dashboards & Panels (8 tools)
    └── system.py            # Settings, Server, Schema, Activity (10 tools)
```

### Client Architecture

```python
class DirectusClient:
    """
    REST API Client for Directus Self-Hosted

    Uses static token authentication for server-to-server communication.
    """
    def __init__(
        self,
        base_url: str,           # e.g., https://directus.example.com
        token: str,              # Static admin token
    ):
        self.base_url = base_url.rstrip('/')
        self.token = token

    def _get_headers(self, additional_headers: Optional[Dict] = None) -> Dict[str, str]:
        """Get request headers with authentication."""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}",
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
        """Make authenticated request to Directus API"""
        url = f"{self.base_url}{endpoint}"
        headers = self._get_headers(headers_override)
        # ... request logic
```

---

## Tool Categories

### 1. Items Handler (12 tools)

عملیات CRUD روی هر collection

| Tool | Method | Scope | Description |
|------|--------|-------|-------------|
| `list_items` | GET | read | لیست items با فیلتر و pagination |
| `get_item` | GET | read | دریافت یک item |
| `create_item` | POST | write | ایجاد item جدید |
| `create_items` | POST | write | ایجاد چندین item |
| `update_item` | PATCH | write | به‌روزرسانی item |
| `update_items` | PATCH | write | به‌روزرسانی چندین item |
| `delete_item` | DELETE | write | حذف item |
| `delete_items` | DELETE | write | حذف چندین item |
| `search_items` | GET | read | جستجوی full-text |
| `aggregate_items` | GET | read | محاسبات aggregate |
| `export_items` | GET | read | خروجی JSON/CSV |
| `import_items` | POST | write | وارد کردن items |

```python
# List Items Example
{
    "name": "list_items",
    "method_name": "list_items",
    "description": "List items from any collection with filters, sorting, and pagination",
    "schema": {
        "type": "object",
        "properties": {
            "collection": {
                "type": "string",
                "description": "Collection name (e.g., 'posts', 'products')"
            },
            "fields": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Fields to return (e.g., ['id', 'title', 'author.*'])"
            },
            "filter": {
                "type": "object",
                "description": "Filter object (e.g., {\"status\": {\"_eq\": \"published\"}})"
            },
            "sort": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Sort fields (e.g., ['-date_created', 'title'])"
            },
            "limit": {
                "type": "integer",
                "description": "Maximum items to return",
                "default": 100
            },
            "offset": {
                "type": "integer",
                "description": "Items to skip",
                "default": 0
            },
            "search": {
                "type": "string",
                "description": "Full-text search query"
            },
            "deep": {
                "type": "object",
                "description": "Deep filter for relational fields"
            }
        },
        "required": ["collection"]
    },
    "scope": "read"
}
```

### 2. Collections & Fields Handler (14 tools)

مدیریت schema

| Tool | Method | Scope | Description |
|------|--------|-------|-------------|
| `list_collections` | GET | read | لیست collections |
| `get_collection` | GET | read | جزئیات collection |
| `create_collection` | POST | admin | ایجاد collection |
| `update_collection` | PATCH | admin | به‌روزرسانی collection |
| `delete_collection` | DELETE | admin | حذف collection |
| `list_fields` | GET | read | لیست fields |
| `get_field` | GET | read | جزئیات field |
| `create_field` | POST | admin | ایجاد field |
| `update_field` | PATCH | admin | به‌روزرسانی field |
| `delete_field` | DELETE | admin | حذف field |
| `list_relations` | GET | read | لیست relations |
| `get_relation` | GET | read | جزئیات relation |
| `create_relation` | POST | admin | ایجاد relation |
| `delete_relation` | DELETE | admin | حذف relation |

```python
# Create Collection Example
{
    "name": "create_collection",
    "method_name": "create_collection",
    "description": "Create a new collection (table) in Directus",
    "schema": {
        "type": "object",
        "properties": {
            "collection": {
                "type": "string",
                "description": "Collection name (table name)"
            },
            "meta": {
                "type": "object",
                "properties": {
                    "icon": {"type": "string", "description": "Material icon name"},
                    "note": {"type": "string", "description": "Description"},
                    "hidden": {"type": "boolean", "default": False},
                    "singleton": {"type": "boolean", "default": False},
                    "translations": {"type": "array"},
                    "sort_field": {"type": "string"},
                    "archive_field": {"type": "string"},
                    "archive_value": {"type": "string"},
                    "unarchive_value": {"type": "string"}
                }
            },
            "schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "comment": {"type": "string"}
                }
            },
            "fields": {
                "type": "array",
                "description": "Initial fields to create with collection",
                "items": {
                    "type": "object",
                    "properties": {
                        "field": {"type": "string"},
                        "type": {"type": "string"},
                        "meta": {"type": "object"},
                        "schema": {"type": "object"}
                    }
                }
            }
        },
        "required": ["collection"]
    },
    "scope": "admin"
}
```

### 3. Files & Folders Handler (12 tools)

مدیریت assets

| Tool | Method | Scope | Description |
|------|--------|-------|-------------|
| `list_files` | GET | read | لیست فایل‌ها |
| `get_file` | GET | read | جزئیات فایل |
| `upload_file` | POST | write | آپلود فایل |
| `update_file` | PATCH | write | به‌روزرسانی metadata |
| `delete_file` | DELETE | write | حذف فایل |
| `delete_files` | DELETE | write | حذف چندین فایل |
| `list_folders` | GET | read | لیست پوشه‌ها |
| `get_folder` | GET | read | جزئیات پوشه |
| `create_folder` | POST | write | ایجاد پوشه |
| `update_folder` | PATCH | write | به‌روزرسانی پوشه |
| `delete_folder` | DELETE | write | حذف پوشه |
| `import_file_url` | POST | write | وارد کردن از URL |

```python
# Upload File Example
{
    "name": "upload_file",
    "method_name": "upload_file",
    "description": "Upload a file to Directus storage",
    "schema": {
        "type": "object",
        "properties": {
            "file_content_base64": {
                "type": "string",
                "description": "File content as base64 encoded string"
            },
            "filename_download": {
                "type": "string",
                "description": "Download filename"
            },
            "title": {
                "type": "string",
                "description": "File title"
            },
            "description": {
                "type": "string",
                "description": "File description"
            },
            "folder": {
                "type": "string",
                "description": "Folder UUID to upload to"
            },
            "storage": {
                "type": "string",
                "description": "Storage adapter (default: local)",
                "default": "local"
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "File tags"
            }
        },
        "required": ["file_content_base64", "filename_download"]
    },
    "scope": "write"
}
```

### 4. Users Handler (10 tools)

مدیریت کاربران

| Tool | Method | Scope | Description |
|------|--------|-------|-------------|
| `list_users` | GET | read | لیست کاربران |
| `get_user` | GET | read | جزئیات کاربر |
| `get_current_user` | GET | read | کاربر فعلی |
| `create_user` | POST | admin | ایجاد کاربر |
| `update_user` | PATCH | admin | به‌روزرسانی کاربر |
| `delete_user` | DELETE | admin | حذف کاربر |
| `delete_users` | DELETE | admin | حذف چندین کاربر |
| `invite_user` | POST | admin | دعوت کاربر |
| `accept_invite` | POST | write | پذیرش دعوت |
| `update_current_user` | PATCH | write | به‌روزرسانی پروفایل |

```python
# Create User Example
{
    "name": "create_user",
    "method_name": "create_user",
    "description": "Create a new user in Directus",
    "schema": {
        "type": "object",
        "properties": {
            "email": {
                "type": "string",
                "format": "email",
                "description": "User email address"
            },
            "password": {
                "type": "string",
                "minLength": 8,
                "description": "User password"
            },
            "first_name": {
                "type": "string",
                "description": "First name"
            },
            "last_name": {
                "type": "string",
                "description": "Last name"
            },
            "role": {
                "type": "string",
                "description": "Role UUID"
            },
            "status": {
                "type": "string",
                "enum": ["draft", "invited", "active", "suspended", "archived"],
                "default": "active"
            },
            "language": {
                "type": "string",
                "description": "User language preference"
            },
            "token": {
                "type": "string",
                "description": "Static API token"
            }
        },
        "required": ["email", "password", "role"]
    },
    "scope": "admin"
}
```

### 5. Access Control Handler (12 tools)

Roles, Permissions, Policies

| Tool | Method | Scope | Description |
|------|--------|-------|-------------|
| `list_roles` | GET | read | لیست roles |
| `get_role` | GET | read | جزئیات role |
| `create_role` | POST | admin | ایجاد role |
| `update_role` | PATCH | admin | به‌روزرسانی role |
| `delete_role` | DELETE | admin | حذف role |
| `list_permissions` | GET | read | لیست permissions |
| `get_permission` | GET | read | جزئیات permission |
| `create_permission` | POST | admin | ایجاد permission |
| `update_permission` | PATCH | admin | به‌روزرسانی permission |
| `delete_permission` | DELETE | admin | حذف permission |
| `list_policies` | GET | read | لیست policies |
| `get_my_permissions` | GET | read | permissions کاربر فعلی |

```python
# Create Permission Example
{
    "name": "create_permission",
    "method_name": "create_permission",
    "description": "Create a new permission rule",
    "schema": {
        "type": "object",
        "properties": {
            "role": {
                "type": "string",
                "description": "Role UUID (null for public)"
            },
            "collection": {
                "type": "string",
                "description": "Collection name"
            },
            "action": {
                "type": "string",
                "enum": ["create", "read", "update", "delete", "share"],
                "description": "Permission action"
            },
            "permissions": {
                "type": "object",
                "description": "Filter rules (JSON filter)"
            },
            "validation": {
                "type": "object",
                "description": "Validation rules for create/update"
            },
            "presets": {
                "type": "object",
                "description": "Default values for create"
            },
            "fields": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Allowed fields (* for all)"
            }
        },
        "required": ["collection", "action"]
    },
    "scope": "admin"
}
```

### 6. Automation Handler (12 tools)

Flows, Operations, Webhooks

| Tool | Method | Scope | Description |
|------|--------|-------|-------------|
| `list_flows` | GET | read | لیست flows |
| `get_flow` | GET | read | جزئیات flow |
| `create_flow` | POST | admin | ایجاد flow |
| `update_flow` | PATCH | admin | به‌روزرسانی flow |
| `delete_flow` | DELETE | admin | حذف flow |
| `trigger_flow` | POST | write | اجرای manual flow |
| `list_operations` | GET | read | لیست operations |
| `create_operation` | POST | admin | ایجاد operation |
| `list_webhooks` | GET | read | لیست webhooks |
| `create_webhook` | POST | admin | ایجاد webhook |
| `update_webhook` | PATCH | admin | به‌روزرسانی webhook |
| `delete_webhook` | DELETE | admin | حذف webhook |

```python
# Create Flow Example
{
    "name": "create_flow",
    "method_name": "create_flow",
    "description": "Create a new automation flow",
    "schema": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Flow name"
            },
            "icon": {
                "type": "string",
                "description": "Material icon"
            },
            "status": {
                "type": "string",
                "enum": ["active", "inactive"],
                "default": "active"
            },
            "trigger": {
                "type": "string",
                "enum": ["event", "schedule", "operation", "webhook", "manual"],
                "description": "Trigger type"
            },
            "options": {
                "type": "object",
                "description": "Trigger-specific options"
            },
            "accountability": {
                "type": "string",
                "enum": ["all", "activity", null],
                "description": "Accountability tracking"
            },
            "description": {
                "type": "string",
                "description": "Flow description"
            }
        },
        "required": ["name", "trigger"]
    },
    "scope": "admin"
}
```

### 7. Content Management Handler (10 tools)

Revisions, Versions, Comments

| Tool | Method | Scope | Description |
|------|--------|-------|-------------|
| `list_revisions` | GET | read | لیست revisions |
| `get_revision` | GET | read | جزئیات revision |
| `list_versions` | GET | read | لیست content versions |
| `get_version` | GET | read | جزئیات version |
| `create_version` | POST | write | ایجاد version |
| `update_version` | PATCH | write | به‌روزرسانی version |
| `delete_version` | DELETE | write | حذف version |
| `promote_version` | POST | write | ترویج version به main |
| `list_comments` | GET | read | لیست comments |
| `create_comment` | POST | write | ایجاد comment |

```python
# Create Version Example
{
    "name": "create_version",
    "method_name": "create_version",
    "description": "Create a new content version (draft)",
    "schema": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Version name"
            },
            "collection": {
                "type": "string",
                "description": "Collection name"
            },
            "item": {
                "type": "string",
                "description": "Item ID"
            },
            "key": {
                "type": "string",
                "description": "Version key (unique identifier)"
            },
            "delta": {
                "type": "object",
                "description": "Changes from main content"
            }
        },
        "required": ["name", "collection", "item"]
    },
    "scope": "write"
}
```

### 8. Dashboards Handler (8 tools)

Dashboards & Panels

| Tool | Method | Scope | Description |
|------|--------|-------|-------------|
| `list_dashboards` | GET | read | لیست dashboards |
| `get_dashboard` | GET | read | جزئیات dashboard |
| `create_dashboard` | POST | write | ایجاد dashboard |
| `update_dashboard` | PATCH | write | به‌روزرسانی dashboard |
| `delete_dashboard` | DELETE | write | حذف dashboard |
| `list_panels` | GET | read | لیست panels |
| `create_panel` | POST | write | ایجاد panel |
| `delete_panel` | DELETE | write | حذف panel |

```python
# Create Dashboard Example
{
    "name": "create_dashboard",
    "method_name": "create_dashboard",
    "description": "Create a new insights dashboard",
    "schema": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Dashboard name"
            },
            "icon": {
                "type": "string",
                "description": "Material icon",
                "default": "dashboard"
            },
            "note": {
                "type": "string",
                "description": "Dashboard description"
            },
            "color": {
                "type": "string",
                "description": "Accent color"
            }
        },
        "required": ["name"]
    },
    "scope": "write"
}
```

### 9. System Handler (10 tools)

Settings, Server, Schema, Activity

| Tool | Method | Scope | Description |
|------|--------|-------|-------------|
| `get_settings` | GET | read | تنظیمات سیستم |
| `update_settings` | PATCH | admin | به‌روزرسانی تنظیمات |
| `get_server_info` | GET | read | اطلاعات سرور |
| `health_check` | GET | read | بررسی سلامت |
| `get_schema_snapshot` | GET | admin | export schema |
| `apply_schema_diff` | POST | admin | apply schema changes |
| `list_activity` | GET | read | لیست activity log |
| `get_activity` | GET | read | جزئیات activity |
| `list_notifications` | GET | read | لیست اعلان‌ها |
| `list_presets` | GET | read | لیست presets |

```python
# Health Check Example
{
    "name": "health_check",
    "method_name": "health_check",
    "description": "Check Directus server health status",
    "schema": {
        "type": "object",
        "properties": {}
    },
    "scope": "read"
}

# Get Schema Snapshot Example
{
    "name": "get_schema_snapshot",
    "method_name": "get_schema_snapshot",
    "description": "Get complete schema snapshot for migration/backup",
    "schema": {
        "type": "object",
        "properties": {
            "format": {
                "type": "string",
                "enum": ["json", "yaml"],
                "default": "json"
            }
        }
    },
    "scope": "admin"
}
```

---

## Query System

### Filter Operators

Directus از filter operators قدرتمندی استفاده می‌کند:

```javascript
// Comparison
{"field": {"_eq": "value"}}           // Equal
{"field": {"_neq": "value"}}          // Not equal
{"field": {"_lt": 10}}                // Less than
{"field": {"_lte": 10}}               // Less than or equal
{"field": {"_gt": 10}}                // Greater than
{"field": {"_gte": 10}}               // Greater than or equal

// String
{"field": {"_contains": "text"}}      // Contains
{"field": {"_ncontains": "text"}}     // Not contains
{"field": {"_starts_with": "text"}}   // Starts with
{"field": {"_nstarts_with": "text"}}  // Not starts with
{"field": {"_ends_with": "text"}}     // Ends with
{"field": {"_nends_with": "text"}}    // Not ends with

// Array
{"field": {"_in": ["a", "b"]}}        // In array
{"field": {"_nin": ["a", "b"]}}       // Not in array

// Null
{"field": {"_null": true}}            // Is null
{"field": {"_nnull": true}}           // Is not null

// Empty
{"field": {"_empty": true}}           // Is empty
{"field": {"_nempty": true}}          // Is not empty

// Between
{"field": {"_between": [1, 10]}}      // Between
{"field": {"_nbetween": [1, 10]}}     // Not between

// Logical
{"_and": [{...}, {...}]}              // AND
{"_or": [{...}, {...}]}               // OR

// Relational
{"author": {"name": {"_eq": "John"}}} // Related field
```

### Deep Parameter (Relational Queries)

```javascript
// Filter related items
{
    "deep": {
        "translations": {
            "_filter": {
                "languages_code": {"_eq": "en-US"}
            }
        }
    }
}
```

---

## Tool Summary

| Handler | Tools | Description |
|---------|-------|-------------|
| Items | 12 | CRUD برای همه collections |
| Collections & Fields | 14 | مدیریت schema |
| Files & Folders | 12 | مدیریت assets |
| Users | 10 | مدیریت کاربران |
| Access Control | 12 | Roles, Permissions, Policies |
| Automation | 12 | Flows, Operations, Webhooks |
| Content | 10 | Revisions, Versions, Comments |
| Dashboards | 8 | Dashboards & Panels |
| System | 10 | Settings, Server, Schema, Activity |
| **Total** | **100** | |

---

## Implementation Phases

### Phase J.1: Core (Items + Schema) - 26 tools

**هدف**: دسترسی اولیه به Directus Self-Hosted

1. **DirectusPlugin** class
2. **DirectusClient** (REST client)
3. **Items Handler** (12 tools)
4. **Collections & Fields Handler** (14 tools)

### Phase J.2: Assets & Users - 22 tools

**هدف**: مدیریت فایل‌ها و کاربران

1. **Files & Folders Handler** (12 tools)
2. **Users Handler** (10 tools)

**جمع**: 48 tools

### Phase J.3: Access & Automation - 24 tools

**هدف**: امنیت و اتوماسیون

1. **Access Control Handler** (12 tools)
2. **Automation Handler** (12 tools)

**جمع**: 72 tools

### Phase J.4: Advanced - 28 tools

**هدف**: قابلیت‌های پیشرفته

1. **Content Handler** (10 tools)
2. **Dashboards Handler** (8 tools)
3. **System Handler** (10 tools)

**جمع**: 100 tools

---

## Error Handling

### HTTP Status Codes

```python
async def handle_directus_error(response):
    """Handle Directus API errors"""
    data = await response.json()

    errors = data.get("errors", [])
    message = errors[0].get("message", "Unknown error") if errors else "Unknown error"

    if response.status == 400:
        raise ValidationError(f"Bad Request: {message}")
    elif response.status == 401:
        raise AuthError("Invalid token or missing authentication")
    elif response.status == 403:
        raise PermissionError(f"Permission denied: {message}")
    elif response.status == 404:
        raise NotFoundError(f"Resource not found: {message}")
    elif response.status == 409:
        raise ConflictError(f"Conflict: {message}")
    elif response.status == 503:
        raise ServiceUnavailableError("Service temporarily unavailable")
    elif response.status >= 500:
        raise ServerError(f"Server error: {message}")
    else:
        raise DirectusError(f"Error: {message}")
```

### Common Error Codes

```
FORBIDDEN                - دسترسی غیرمجاز
INVALID_CREDENTIALS      - اطلاعات ورود نادرست
INVALID_TOKEN           - توکن نامعتبر
TOKEN_EXPIRED           - توکن منقضی شده
RECORD_NOT_UNIQUE       - رکورد تکراری
FAILED_VALIDATION       - خطای validation
ILLEGAL_ASSET_TRANSFORMATION - تبدیل فایل غیرمجاز
CONTENT_TOO_LARGE       - فایل بزرگتر از حد مجاز
```

---

## Security Considerations

### Token Security

```
┌─────────────────────────────────────────────────────────────────┐
│                    Token Best Practices                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ✅ Best Practices:                                              │
│  ├── Use static tokens for server-to-server (MCP)               │
│  ├── Store tokens in environment variables                       │
│  ├── Create dedicated service user with minimal permissions      │
│  ├── Rotate tokens periodically                                  │
│  └── Use HTTPS always                                            │
│                                                                  │
│  ⚠️ Scope Recommendations:                                       │
│  ├── Read operations: read-only role                            │
│  ├── Write operations: content editor role                       │
│  └── Admin operations: admin role (careful monitoring)           │
│                                                                  │
│  ❌ Never Do:                                                    │
│  ├── Log tokens (even partially)                                │
│  ├── Commit tokens to version control                           │
│  ├── Use admin token for public operations                       │
│  └── Share tokens across different services                      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Permission System

```python
# Create restricted role for MCP
role = {
    "name": "MCP Service",
    "icon": "smart_toy",
    "description": "Service role for MCP integration",
    "admin_access": False,
    "app_access": False
}

# Permission examples
permissions = [
    # Read all posts
    {"collection": "posts", "action": "read", "fields": ["*"]},

    # Create/update own posts only
    {"collection": "posts", "action": "create", "fields": ["*"]},
    {"collection": "posts", "action": "update", "permissions": {"user_created": {"_eq": "$CURRENT_USER"}}},

    # Read published only
    {"collection": "articles", "action": "read", "permissions": {"status": {"_eq": "published"}}}
]
```

---

## Example Usage

### Query Items with Filters

```json
{
    "tool": "list_items",
    "args": {
        "site": "mycms",
        "collection": "posts",
        "fields": ["id", "title", "date_created", "author.email"],
        "filter": {
            "_and": [
                {"status": {"_eq": "published"}},
                {"date_created": {"_gte": "$NOW(-30 days)"}}
            ]
        },
        "sort": ["-date_created"],
        "limit": 20
    }
}
```

### Create Item

```json
{
    "tool": "create_item",
    "args": {
        "site": "mycms",
        "collection": "posts",
        "data": {
            "title": "New Blog Post",
            "content": "<p>Hello World!</p>",
            "status": "draft",
            "tags": ["news", "featured"],
            "author": "user-uuid-here"
        }
    }
}
```

### Upload File

```json
{
    "tool": "upload_file",
    "args": {
        "site": "mycms",
        "file_content_base64": "iVBORw0KGgoAAAANSUhEUgAA...",
        "filename_download": "cover-image.png",
        "title": "Blog Cover Image",
        "folder": "folder-uuid-here",
        "tags": ["blog", "cover"]
    }
}
```

### Create Automation Flow

```json
{
    "tool": "create_flow",
    "args": {
        "site": "mycms",
        "name": "Send Welcome Email",
        "trigger": "event",
        "options": {
            "type": "action",
            "scope": ["items.create"],
            "collections": ["users"]
        },
        "status": "active"
    }
}
```

### Trigger Manual Flow

```json
{
    "tool": "trigger_flow",
    "args": {
        "site": "mycms",
        "flow_uuid": "flow-uuid-here",
        "data": {
            "email": "user@example.com",
            "template": "welcome"
        }
    }
}
```

---

## Coolify Deployment Notes

### Finding Directus Credentials

در Coolify، بعد از deploy کردن Directus:

1. **URL**: از Coolify dashboard → Project → Directus → Domain
   - معمولاً: `https://directus.yourdomain.com`

2. **Admin Email/Password**:
   - در Environment Variables:
     - `ADMIN_EMAIL`
     - `ADMIN_PASSWORD`

3. **Static Token**:
   - Login به Directus Admin
   - Settings → User Directory → Admin User
   - Token field → Generate

### Docker Compose Environment

```yaml
# Key Directus environment variables
services:
  directus:
    environment:
      # Database
      DB_CLIENT: 'pg'           # or mysql, sqlite, etc.
      DB_HOST: 'database'
      DB_PORT: '5432'
      DB_DATABASE: 'directus'
      DB_USER: 'directus'
      DB_PASSWORD: 'secure-password'

      # Auth
      SECRET: 'your-random-secret-key'
      ADMIN_EMAIL: 'admin@example.com'
      ADMIN_PASSWORD: 'secure-admin-password'

      # URLs
      PUBLIC_URL: 'https://directus.example.com'

      # Token settings
      ACCESS_TOKEN_TTL: '15m'
      REFRESH_TOKEN_TTL: '7d'

      # CORS
      CORS_ENABLED: 'true'
      CORS_ORIGIN: 'true'
```

### Database Support

```
Directus supports:
├── PostgreSQL (recommended)
├── MySQL / MariaDB
├── SQLite (development only)
├── MS SQL Server
├── OracleDB
└── CockroachDB
```

---

## Endpoint Registration

### Endpoint Config

```python
# core/endpoints/config.py

EndpointType.DIRECTUS: EndpointConfig(
    path="/directus",
    name="Directus CMS",
    description="Directus Self-Hosted CMS management (items, collections, files, users, flows)",
    endpoint_type=EndpointType.DIRECTUS,
    plugin_types=["directus"],
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

## Comparison: Directus vs Appwrite Tools

| Feature | Directus | Appwrite |
|---------|----------|----------|
| Items/Documents Tools | 12 | 12 |
| Schema Tools | 14 | 18 |
| Files/Storage Tools | 12 | 14 |
| Users Tools | 10 | 12 |
| Access Control Tools | 12 | 10 (Teams) |
| Automation Tools | 12 | 14 (Functions) |
| Content Versioning | 10 | 0 |
| Dashboards Tools | 8 | 0 |
| System Tools | 10 | 8 |
| Messaging Tools | 0 | 12 |
| **Total** | **100** | **100** |

**تفاوت‌های کلیدی:**
- Directus: Content versioning و Dashboards دارد
- Appwrite: Built-in Messaging و Functions runtime دارد
- Directus: SQL-based (flexible)
- Appwrite: Document-based (NoSQL-like)

---

## Testing Checklist

### Unit Tests

- [ ] DirectusClient authentication
- [ ] Items CRUD operations
- [ ] Filter operators
- [ ] Relational queries (deep)
- [ ] File upload/download
- [ ] User management
- [ ] Permission enforcement
- [ ] Flow triggering
- [ ] Error handling

### Integration Tests

- [ ] Create collection with fields
- [ ] CRUD items with relations
- [ ] Upload and retrieve files
- [ ] Create user with role
- [ ] Set permissions and verify access
- [ ] Create and trigger flow
- [ ] Create content version and promote
- [ ] Schema snapshot and restore
- [ ] Health check

---

## Field Types Reference

### Supported Field Types

| Type | Description | Interface |
|------|-------------|-----------|
| `string` | Single line text | Input |
| `text` | Multi-line text | Textarea |
| `integer` | Whole number | Input Numeric |
| `bigInteger` | Large whole number | Input |
| `float` | Decimal number | Input |
| `decimal` | Precise decimal | Input |
| `boolean` | True/False | Toggle |
| `json` | JSON object | Code (JSON) |
| `csv` | Comma-separated | Tags |
| `uuid` | UUID | Input |
| `hash` | Hashed value | Input Hash |
| `date` | Date only | DateTime |
| `time` | Time only | DateTime |
| `dateTime` | Date and time | DateTime |
| `timestamp` | Unix timestamp | DateTime |
| `geometry` | GeoJSON | Map |
| `alias` | Virtual field | Multiple |

### Special Field Types

| Type | Description |
|------|-------------|
| `file` | Foreign key to files |
| `files` | Many-to-many files |
| `m2o` | Many-to-one relation |
| `o2m` | One-to-many relation |
| `m2m` | Many-to-many relation |
| `m2a` | Many-to-any relation |
| `translations` | Translation links |
| `presentation` | UI-only (divider, notice) |
| `group` | Field group |

---

## References

- [Directus Documentation](https://docs.directus.io/)
- [Directus REST API Reference](https://docs.directus.io/reference/introduction)
- [Directus Self-Hosting Guide](https://docs.directus.io/self-hosted/quickstart)
- [Directus SDK](https://docs.directus.io/guides/sdk/getting-started)
- [Directus GitHub Repository](https://github.com/directus/directus)
- [Directus Flows & Operations](https://docs.directus.io/configuration/flows)
- [Directus Permissions](https://docs.directus.io/configuration/users-roles-permissions)

---

**Sources:**
- [Directus Docs](https://docs.directus.io/)
- [Directus API Reference](https://directus.io/docs/api)
- [Directus Authentication](https://directus.io/docs/api/authentication)
- [Directus Token Authentication Guide](https://www.restack.io/docs/directus-knowledge-directus-token-authentication)

---

**Created**: 2025-12-03
**Author**: Claude AI Assistant
**Status**: Design Phase (Ready for Implementation)
