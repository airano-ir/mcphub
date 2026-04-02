# Next Session — F.17 Coolify MCP Plugin (MVP)

> Session prompt. Copy and paste into a new Claude Code conversation.

---

## Prompt:

```
از مهارت project-ops برای آشنایی با محیط استفاده کن. حافظه و فایل‌های مرجع را بررسی کن.

## فایل‌های مرجع
- docs/plans/2026-04-02-coolify-mcp-plugin-design.md (mcphub-internal) ← طرح کامل پلاگین
- docs/plans/2026-03-25-v4-development-cycle.md (mcphub-internal, branch Phase-1) ← فاز F.17
- CLAUDE.md (mcphub-internal)
- plugins/gitea/ (mcphub-internal) ← الگوی مرجع (آخرین پلاگین ساخته‌شده)
- plugins/base.py (mcphub-internal) ← BasePlugin interface

## وضعیت فعلی
- MCPHub: v3.6.0 — 566 ابزار، 5 پلاگین عمومی
- FastMCP: >=3.0.0,<4.0.0
- CI سبز
- طرح Coolify: نوشته شده — ~68 ابزار در 6 handler

## ریپازیتوری
- MCPHub (internal): `/config/workspace/mcphub-internal` (branch Phase-1)

## هدف session: F.17 Phase 1 — Coolify MVP

### پیش‌نیاز اول: Coolify API Token
- [ ] در داشبورد Coolify، بخش Keys & Tokens، یک API token بساز
- [ ] تست اتصال: `curl -s https://COOLIFY_URL/api/v1/version -H "Authorization: Bearer TOKEN"`
- [ ] اگر URL و TOKEN مشخص نبود، از کاربر بپرس

### مرحله ۱: ساختار اولیه پلاگین
- [ ] `plugins/coolify/__init__.py` (خالی)
- [ ] `plugins/coolify/client.py` — CoolifyClient با Bearer Token auth
  - الگو از `plugins/gitea/client.py` بگیر
  - متدها: `request()`, `get()`, `post()`, `patch()`, `delete()`
  - Error handling + retry مشابه Gitea client
- [ ] `plugins/coolify/plugin.py` — CoolifyPlugin(BasePlugin)
  - الگو از `plugins/gitea/plugin.py` بگیر
  - `get_tool_specifications()` باید ابزارهای handler ها رو جمع کنه
- [ ] `plugins/coolify/handlers/__init__.py`
- [ ] `plugins/coolify/schemas/__init__.py`
- [ ] `plugins/coolify/schemas/common.py` — مدل‌های مشترک (UUID, pagination)

### مرحله ۲: Handler — Applications (18 ابزار)
- [ ] `plugins/coolify/handlers/applications.py`
- [ ] ابزارها (از طرح):
  - list_applications, get_application
  - create_application_public, create_application_dockerfile, create_application_docker_image, create_application_compose
  - update_application, delete_application
  - start_application, stop_application, restart_application
  - get_application_logs
  - list_application_envs, create_application_env, update_application_env, update_application_envs_bulk, delete_application_env
- [ ] schemas/application.py — Pydantic models

### مرحله ۳: Handler — Deployments (5 ابزار)
- [ ] `plugins/coolify/handlers/deployments.py`
- [ ] ابزارها: list_deployments, get_deployment, cancel_deployment, deploy, list_app_deployments

### مرحله ۴: Handler — Servers (8 ابزار)
- [ ] `plugins/coolify/handlers/servers.py`
- [ ] ابزارها: list_servers, get_server, create_server, update_server, delete_server, get_server_resources, get_server_domains, validate_server
- [ ] schemas/server.py

### مرحله ۵: ثبت پلاگین و تنظیمات
- [ ] در `plugins/__init__.py` اضافه کن: `from plugins.coolify.plugin import CoolifyPlugin` + `registry.register("coolify", CoolifyPlugin)`
- [ ] در `env.example` اضافه کن: `COOLIFY_URL`, `COOLIFY_TOKEN`
- [ ] پلاگین فعلا admin-only باشد (به ENABLED_PLUGINS اضافه نشود)

### مرحله ۶: تست
- [ ] `tests/test_coolify.py` — Unit tests با mocked HTTP
  - الگو از `tests/test_gitea*.py` بگیر
  - حداقل: test_list_applications, test_get_application, test_deploy, test_list_servers
- [ ] `pytest tests/test_coolify.py -v`
- [ ] اگر API Token موجود بود: integration test با Coolify واقعی

### مرحله ۷: تست نهایی و commit
- [ ] `uvx --python 3.12 black .`
- [ ] `uvx ruff check --fix .`
- [ ] `pytest` (همه تست‌ها سبز)
- [ ] Commit: `feat(F.17): add Coolify MCP plugin — Phase 1 MVP (~31 tools)`
- [ ] Push to Phase-1

## قوانین
- اول پلن بده، بدون تایید شروع نکن
- از Gitea plugin به عنوان الگوی اصلی استفاده کن (آخرین و تمیزترین پلاگین)
- هر مرحله commit شود
- tool specifications باید دقیقا مطابق فرمت BasePlugin باشند (name, method_name, description, schema, scope)
- scope ها: read, write, admin — مطابق جدول در طرح
- حافظه آپدیت شود بعد از اتمام
- ایمیل git داخلی: mcphub.dev@gmail.com
```
