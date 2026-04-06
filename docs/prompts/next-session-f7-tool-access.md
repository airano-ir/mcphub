از مهارت project-ops برای آشنایی با محیط استفاده کن. حافظه و فایل‌های مرجع را بررسی کن.

## فایل‌های مرجع
- docs/plans/2026-03-25-v4-development-cycle.md (mcphub-internal) ← Phase F.7 طراحی کامل
- core/tool_generator.py (mcphub-internal) ← تولید ابزار فعلی
- core/tool_registry.py (mcphub-internal) ← رجیستری ابزار
- core/user_endpoints.py (mcphub-internal) ← فیلتر ابزار در endpoint کاربر
- core/user_keys.py (mcphub-internal) ← سیستم API key کاربر
- core/database.py (mcphub-internal) ← دیتابیس و مایگریشن
- core/plugin_visibility.py (mcphub-internal) ← فیلتر پلاگین فعلی
- core/dashboard/routes.py (mcphub-internal) ← روت‌های داشبورد
- server.py (mcphub-internal) ← middleware و scope enforcement
- CLAUDE.md (mcphub-internal)

## وضعیت فعلی
- MCPHub: v3.8.0 — 633 ابزار، 10 پلاگین، 67 ابزار Coolify
- تست‌ها: 766 (internal), 734 (public)
- CI سبز
- Scope فعلی: read/write/admin (سه سطح ساده)
- فیلتر فعلی: فقط plugin-level (ENABLED_PLUGINS) — بدون per-tool toggle

## ریپازیتوری
- MCPHub (internal): `/config/workspace/mcphub-internal` (branch Phase-1)

## هدف session: F.7 — Smart Tool Visibility & Scope-Based Access Control

### مشکلاتی که حل می‌شوند
1. همه ابزارهای یک پلاگین فعال به همه کاربران نشان داده می‌شوند — کنترل per-tool نداریم
2. وقتی کاربر API key با scope خاص (مثلا read) می‌سازد، باز هم همه ابزارها در tools/list نمایش داده می‌شوند
3. ابزارهای وردپرس که نیاز به افزونه‌های کمکی دارند (SEO Bridge, WP-CLI) بدون بررسی prerequisite نشان داده می‌شوند
4. کاربران نمی‌توانند ابزارهایی که نیاز ندارند را غیرفعال کنند

### مدل scope پیشنهادی (گسترش‌یافته)
فعلی: `read`, `write`, `admin`
جدید:
- `deploy` — عملیات lifecycle (start/stop/restart/deploy) + read
- `read:sensitive` — read + لاگ، env var، بکاپ، connection string

**نگاشت scope → دسته‌بندی ابزار:**
| Scope | ابزارها |
|-------|---------|
| `read` | list_*, get_* (بدون sensitive) |
| `read:sensitive` | read + *_logs, *_envs, *_backups |
| `deploy` | read + start_*, stop_*, restart_*, deploy |
| `write` | deploy + create_*, update_*, delete_*_env |
| `admin` | write + delete_* (منابع)، create_server |

### بخش اول: Core — ساختار داده و مدیریت دسترسی (بدون UI)

#### مرحله ۱: دیتابیس
- [ ] جدول `user_tool_toggles` در `core/database.py`
  ```sql
  CREATE TABLE user_tool_toggles (
      id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      tool_name TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1,
      reason TEXT, updated_at TEXT NOT NULL, UNIQUE(user_id, tool_name)
  );
  ```
- [ ] جدول `scope_presets` — پریست‌های scope سیستمی + سفارشی
- [ ] Migration اجرا شود

#### مرحله ۲: ماژول tool_access.py
- [ ] `core/tool_access.py` — کلاس `ToolAccessManager`
- [ ] `get_visible_tools(user_id, scopes, plugin_type)` → لیست فیلتر شده
- [ ] `apply_scope_filter(tools, scopes)` → فقط ابزارهای مجاز بر اساس scope
- [ ] `apply_user_toggles(tools, user_id)` → اعمال toggle‌های کاربر
- [ ] `toggle_tool(user_id, tool_name, enabled)` → ذخیره تنظیم
- [ ] `bulk_toggle_by_scope(user_id, scope_name)` → فعال/غیرفعال دسته‌جمعی

#### مرحله ۳: Tool metadata enhancement
- [ ] اضافه کردن `sensitivity` و `category` به tool specs در handler‌ها:
  - `sensitivity`: "normal" | "sensitive" (لاگ، env، بکاپ)
  - `category`: "read" | "lifecycle" | "crud" | "env" | "backup" | "system"
- [ ] شروع از Coolify (آخرین و تمیزترین) سپس سایر پلاگین‌ها
- [ ] ToolDefinition در tool_registry.py آپدیت شود

#### مرحله ۴: فیلتر در user_endpoints.py
- [ ] `_get_tools_for_plugin()` از ToolAccessManager استفاده کند
- [ ] Pipeline فیلتر:
  1. plugin_visibility (موجود)
  2. scope-to-tool mapping (جدید)
  3. user toggles (جدید)
- [ ] Scope enforcement در middleware آپدیت شود (server.py)

#### مرحله ۵: تست
- [ ] `tests/test_tool_access.py` — unit tests
- [ ] تست‌های scope mapping: key با scope "read" → فقط ابزارهای read
- [ ] تست‌های toggle: کاربر disable کرده → ابزار در tools/list نیست
- [ ] تست‌های integration: API key scope → فیلتر واقعی

### بخش دوم: API — روت‌های مدیریت toggle

- [ ] `GET /api/user/tools` — لیست ابزارها با وضعیت toggle
- [ ] `PATCH /api/user/tools/{tool_name}` — تغییر toggle
- [ ] `POST /api/user/tools/bulk-toggle` — toggle دسته‌جمعی بر اساس scope
- [ ] `GET /api/user/scope-presets` — لیست preset‌ها
- [ ] تست: روت‌ها کار کنند

### بخش سوم: Prerequisites (وردپرس/ووکامرس)

- [ ] `check_prerequisites(tools, site_config)` در tool_access.py
- [ ] تشخیص SEO Bridge: `wp-json/airano-mcp-seo-bridge/v1/status`
- [ ] تشخیص WP-CLI: بررسی `container` field در credentials
- [ ] تشخیص WooCommerce: `wp-json/wc/v3/system_status`
- [ ] ابزارهای وابسته علامت‌گذاری شوند (نه حذف — فقط annotation)

### بخش چهارم: UI — صفحه مدیریت ابزار

- [ ] `core/templates/dashboard/tool-preferences.html`
- [ ] لیست ابزارها گروه‌بندی شده بر اساس category
- [ ] Toggle switch برای هر ابزار
- [ ] Badge برای prerequisite (نصب نشده / نیاز به Docker)
- [ ] Dropdown برای اعمال scope preset
- [ ] در صفحه Connect: پیش‌نمایش ابزارها هنگام ساخت API key

### بخش پنجم: ثبت و تست نهایی

- [ ] `uvx --python 3.12 black .`
- [ ] `uvx ruff check --fix .`
- [ ] `pytest` — همه تست‌ها سبز
- [ ] Commit: `feat(F.7): add smart tool visibility and scope-based access control`
- [ ] Push و درخواست redeploy
- [ ] تست live: ساخت API key با scope "read" → بررسی tools/list
- [ ] Sync به نسخه عمومی
- [ ] آپدیت ورژن به v3.9.0 (اگر تأیید شد)
- [ ] حافظه آپدیت شود
- [ ] پلن آپدیت شود (F.7 complete)

## نکات مهم
- فیلتر scope باید backward-compatible باشد — key‌های موجود بدون تغییر کار کنند
- Default: همه ابزارها فعال — فقط explicit disable ذخیره شود
- `user_tool_toggles` فقط overrideها رو ذخیره می‌کنه، نه همه ابزارها
- Prerequisite check باید non-blocking باشه — ابزار حذف نشه، فقط annotate بشه
- server.py نیازی به تغییر زیاد ندارد — فقط middleware scope check آپدیت شود
- ایمیل git داخلی: mcphub.dev@gmail.com
- بخش اول و دوم اولویت اصلی هستند — بخش سوم و چهارم اگر وقت شد
