از مهارت project-ops برای آشنایی با محیط استفاده کن. حافظه و فایل‌های مرجع را بررسی کن.

## فایل‌های مرجع
- docs/plans/2026-04-04-f7b-site-scoped-tool-access.md ← پلن کامل F.7b
- core/tool_access.py ← ToolAccessManager (سایت‌محور — session 1)
- core/dashboard/routes.py ← روت‌های API site tools (بخش F.7b)
- core/templates/dashboard/sites/edit.html ← صفحه edit سایت (بدون بخش tools)
- core/templates/dashboard/connect.html ← صفحه connect فعلی (config snippets + keys)
- core/templates/dashboard/api-keys/list.html ← صفحه admin کلیدها (UI بهتر)
- core/dashboard/routes.py::dashboard_connect_page / dashboard_api_keys_list
- CLAUDE.md (mcphub-internal)

## وضعیت فعلی
- MCPHub: v3.8.0 + F.7b session 1 (commit روی Phase-1)
- Tests: 813 passed، CI سبز
- Backend F.7b کامل است: per-site tool_scope + site_tool_toggles + 4 روت جدید تحت `/api/sites/{site_id}/...` + `/api/scope-presets`
- فقط UI باقی مانده — هدف این session

## ریپازیتوری
- MCPHub (internal): `/config/workspace/mcphub-internal` (branch Phase-1)

## هدف session: F.7b — UI + page merge

### ۱. بخش "Tool Access" در صفحه edit سایت
فایل: `core/templates/dashboard/sites/edit.html`

- [ ] اضافه کردن یک کارت جدید "Tool Access" بعد از فرم credentials
- [ ] Dropdown برای `tool_scope` (values: read / read:sensitive / deploy / write / admin / custom)
  - PATCH روی `/api/sites/{site_id}/tool-scope` با body `{scope: "..."}`
  - توضیح کوتاه کنار هر گزینه: "Read (X tools)" — شمارش زنده از `/api/sites/{site_id}/tools`
- [ ] Collapsible "Advanced — per-tool overrides":
  - گرید/لیست گروه‌بندی شده بر اساس `category` (read / read_sensitive / lifecycle / crud / env / backup / system)
  - Toggle switch برای هر ابزار → PATCH `/api/sites/{site_id}/tools/{tool_name}` با `{enabled: bool}`
  - Badge قرمز برای `sensitivity=sensitive`
  - نام کوتاه از `name`، tooltip با `description`
- [ ] استفاده از HTMX (در پروژه موجود است) برای updates بدون full reload
- [ ] CSRF token از cookie `dashboard_csrf` به header `X-CSRF-Token`

### ۲. انتقال config snippets از connect به صفحه سایت
فایل: `core/templates/dashboard/sites/view.html` (یا ایجاد اگر وجود ندارد)

- [ ] هر سایت در `/dashboard/sites/{id}` نمایش دهد:
  - URL MCP مخصوص آن سایت: `{PUBLIC_URL}/u/{user_id}/{alias}/mcp`
  - Tabs یا accordion با snippets برای Claude Desktop / Cursor / Zed / کلاینت‌های دیگر
  - استفاده از `core/config_snippets.py::get_supported_clients` (موجود)
- [ ] از صفحه `/dashboard/sites` (list) دکمه "Connect" به این صفحه لینک بزند

### ۳. ادغام `/dashboard/connect` و `/dashboard/api-keys` → `/dashboard/keys` (گزینه A)
UI مبنا: `core/templates/dashboard/api-keys/list.html` (قشنگ‌تر و کامل‌تر است طبق تأیید کاربر)

- [ ] ساخت handler `dashboard_keys_unified(request)` که بر اساس session type branch می‌زند:
  - OAuth user → نمایش `user_api_keys` برای آن کاربر
  - Admin/master → نمایش کامل `api_keys` (همان view فعلی)
- [ ] template جدید `core/templates/dashboard/keys/list.html` با ادغام design از `api-keys/list.html`
  - User view: ساده‌تر، scope selector در create dialog، لیست کلیدهای خود کاربر
  - Admin view: فیلترهای کامل (project, status, search, pagination) — بدون تغییر
- [ ] **Scope selector در create-key dialog** — این بخش حیاتی است:
  - Radio/select: read / read:sensitive / deploy / write / admin
  - Helper text: "Per-site tool filters are set in Site Settings"
  - POST به `/api/keys` (همان endpoint فعلی) با `scopes: "<selected>"`
- [ ] Redirect های قدیمی:
  - `/dashboard/connect` → `/dashboard/keys` (301)
  - `/dashboard/api-keys` → `/dashboard/keys` (301)
- [ ] حذف handler های قدیمی `dashboard_connect_page` و `dashboard_api_keys_list` و یا تبدیل به thin wrapper redirect
- [ ] منوی navigation sidebar را update کن — فقط یک entry "API Keys"

### ۴. گزینه B (ادغام عمیق DB) — deferred
در پلن session 1 ذکر شده اما اجرا نمی‌کنیم مگر کاربر صراحتاً درخواست کند. کامنت در code اضافه کنید به `api_create_key` که "dual-table model is intentional — see F.7b plan".

### ۵. تست
- [ ] `tests/test_dashboard_keys_unified.py` — تست منوی unified، scope selector، 301 redirect از URL های قدیمی
- [ ] `tests/test_sites_tool_access_ui.py` — smoke test که edit page با tool_scope=read درست render شود (می‌توان با TestClient چک کرد که template بدون 500 می‌آید)
- [ ] به‌روزرسانی `tests/test_dashboard.py::test_dashboard_connect_page` → به `/dashboard/keys` منتقل شود یا به پذیرش redirect
- [ ] pytest کامل سبز

### ۶. ورژن، sync، commit
- [ ] `uvx --python 3.12 black . && uvx --python 3.12 ruff check --fix .`
- [ ] bump version به `v3.9.0` در pyproject.toml + `__version__` در server.py (اگر وجود دارد)
- [ ] Commit: `feat(F.7b): tool access UI + unified keys page (v3.9.0)`
- [ ] Push به Phase-1
- [ ] `python3.11 scripts/community-build/sync.py --output ../mcphub/` سپس در repo عمومی `black` + `ruff`
- [ ] Commit عمومی با ایمیل `hi.airano@gmail.com` و push
- [ ] درخواست deploy از کاربر

### ۷. تست live پس از deploy
- [ ] ورود به `/dashboard/sites/{id}/edit` → بخش Tool Access → تغییر scope به `read` → save
- [ ] بدون ساخت کلید جدید، MCP client (همان کلید admin موجود) روی آن alias → `tools/list` باید فقط ابزارهای read را نشان دهد
- [ ] تغییر به `custom` → Advanced → disable یک ابزار خاص (مثلاً `coolify_delete_server`) → تست
- [ ] ساخت کلید جدید از صفحه unified با scope=`read` → بررسی در لیست

## نکات مهم
- **Backward compatibility:** سایت‌های موجود `tool_scope='admin'` دارند (default migration v7) → هیچ تغییر رفتاری روی سایت‌های قدیمی
- **فیلترها:** key scope و site scope **intersect** می‌شوند. admin key + site=read → فقط read. write key + site=deploy → فقط read + lifecycle.
- **CSRF:** middleware روی `/api/sites/*` فعال است. UI باید header `X-CSRF-Token` از cookie `dashboard_csrf` بفرستد. HTMX این را با `hx-headers` هندل می‌کند.
- **CSS:** پروژه Tailwind دارد. از همان کلاس‌های موجود در `api-keys/list.html` استفاده کن برای consistency.
- **i18n:** پروژه EN/FA است. متن‌های جدید را به `core/i18n.py` اضافه کن.
- **ایمیل git داخلی:** mcphub.dev@gmail.com | ایمیل عمومی: hi.airano@gmail.com
- **نباید:** توابع F.7 v1 (با `user_` prefix) را بازگردانی کنی. همه سایت‌محور است.
