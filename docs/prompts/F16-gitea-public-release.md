# F.16 — Gitea Plugin Review, Test & Public Release

> Session prompt. Copy and paste into a new Claude Code conversation.

---

## Prompt:

```
از مهارت project-ops برای آشنایی با محیط استفاده کن. پروژه mcphub-internal روی branch Phase-1 است.
فایل‌های مرجع:
- docs/plans/2026-03-25-v4-development-cycle.md
- CLAUDE.md
- CHANGELOG.md

## وضعیت فعلی
- نسخه: v3.5.0
- 565 ابزار در 9 پلاگین (4 پلاگین عمومی: WordPress, WooCommerce, Supabase, OpenPanel)
- FastMCP: `>=3.0.0,<4.0.0`
- CI سبز
- F.15 تکمیل شده — FastMCP 3.x upgrade + legacy cleanup

## هدف: فاز F.16 — Gitea Plugin Review, Test & Public Enablement

مشابه F.10 (OpenPanel) — بررسی، تست و فعال‌سازی عمومی پلاگین Gitea.

### بخش 1: بررسی و تحلیل
1. **ساختار پلاگین**: `plugins/gitea/` شامل 56 ابزار در 5 هندلر:
   - `handlers/repositories.py` — 16 tools (CRUD repos, branches, tags, files)
   - `handlers/issues.py` — 12 tools (issues, comments, labels, milestones)
   - `handlers/pull_requests.py` — 15 tools (PRs, reviews, merge, diff)
   - `handlers/users.py` — 8 tools (users, orgs, teams)
   - `handlers/webhooks.py` — 5 tools (CRUD webhooks, test)
2. **مشکلات شناسایی‌شده**:
   - `update_webhook` در client.py هست ولی به عنوان tool expose نشده
   - هیچ تست اختصاصی‌ای ندارد (0 تست!)
   - فعلاً admin-only هست (نه در ENABLED_PLUGINS)
3. **تست واقعی**: سایت Gitea از MCPHub MCP endpoint:
   - از ابزارهای Supabase MCP (`mcp.example.com`) استفاده کنید تا سایت Gitea موجود را پیدا کنید
   - یا یک Gitea instance جدید از طریق داشبورد اضافه کنید
   - هر دسته tool را با API واقعی تست کنید

### بخش 2: تست نوشتن
مشابه `tests/test_openpanel_plugin.py` (الگو — 767 خط, 62 تست):
1. `tests/test_gitea_plugin.py` بنویسید:
   - Client initialization + health check
   - Tool spec validation (نام‌ها، پارامترها، type ها)
   - Handler delegation (mock client)
   - Error handling
   - Pagination
2. هدف: حداقل 80 تست (56 tool + edge cases)

### بخش 3: رفع مشکلات
1. `update_webhook` را به عنوان tool expose کنید
2. هر tool که در تست واقعی مشکل دارد را fix کنید
3. توضیحات service page برای Gitea بنویسید
4. health check endpoint را بررسی کنید

### بخش 4: فعال‌سازی عمومی
1. `core/plugin_visibility.py`: اضافه کردن `gitea` به `DEFAULT_PUBLIC_PLUGINS`
2. `env.example`: آپدیت ENABLED_PLUGINS default
3. `glama.json`: آپدیت description اگر لازمه

### بخش 5: Release
1. Version bump: `3.5.0` → `3.6.0`
2. CHANGELOG update
3. Lint: `uvx --python 3.12 black .` && `uvx ruff check --fix .`
4. Commit + push Phase-1
5. Sync: `python3.11 scripts/community-build/sync.py --output ../mcphub/`
6. بعد از sync حتماً `uvx --python 3.12 black .` در public repo هم بزنید!
7. Commit + push public repo

### مراحل پیشنهادی
1. **تحلیل**: خواندن کامل هر handler + client + schemas
2. **تست واقعی**: اتصال به Gitea instance و تست ابزارها
3. **پلن اجرایی**: ارائه پلن و تایید قبل از شروع
4. **تست نوشتن**: test_gitea_plugin.py
5. **رفع مشکلات**: fix هر tool مشکل‌دار
6. **فعال‌سازی**: ENABLED_PLUGINS update
7. **Release**: v3.6.0

### نکات فنی
- Private repo: /config/workspace/mcphub-internal (branch Phase-1)
- Public repo: /config/workspace/mcphub (branch main)
- Lint: `uvx --python 3.12 black .` && `uvx ruff check --fix .`
- Sync: `python3.11 scripts/community-build/sync.py --output ../mcphub/`
- ایمیل git عمومی: hi.airano@gmail.com
- **مهم**: اول پلن بده، بدون تایید شروع نکن
- **الگوی مرجع**: F.10 (OpenPanel) — بخش "Phase F.10" در plan و `tests/test_openpanel_plugin.py`
```
