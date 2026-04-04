# Next Session — F.17 Phase 3: Projects + Phase 2: Databases & Services

> Session prompt. Copy and paste into a new Claude Code conversation.

---

## Prompt:

```
از مهارت project-ops برای آشنایی با محیط استفاده کن. حافظه و فایل‌های مرجع را بررسی کن.

## فایل‌های مرجع
- docs/plans/2026-04-02-coolify-mcp-plugin-design.md (mcphub-internal) ← طرح کامل پلاگین
- docs/plans/2026-03-25-v4-development-cycle.md (mcphub-internal) ← Phase F.17 آپدیت شده
- plugins/coolify/ (mcphub-internal) ← پلاگین Phase 1 (الگوی اصلی)
- plugins/gitea/ (mcphub-internal) ← الگوی مرجع معماری
- CLAUDE.md (mcphub-internal)

## وضعیت فعلی
- MCPHub: v3.7.0 — 596 ابزار، 10 پلاگین
- Coolify Phase 1: ✅ 30 ابزار (17 app + 5 deploy + 8 server) — deployed, tested, synced
- MCP endpoint فعال: mcphub-coolify در Claude Code (30 ابزار لود شده)
- CI سبز، 718 تست (internal), 686 تست (public)

## ریپازیتوری
- MCPHub (internal): `/config/workspace/mcphub-internal` (branch Phase-1)

## هدف session: F.17 Phase 3 + Phase 2

### بخش اول: Phase 3 — Projects & Environments (8 ابزار)
> اولویت بالا — بدون project_uuid ساخت app/db/service بلاک است

#### مرحله ۱: Projects Handler
- [ ] `plugins/coolify/handlers/projects.py`
- [ ] ابزارها:
  - list_projects (GET /projects) — read
  - get_project (GET /projects/{uuid}) — read
  - create_project (POST /projects) — write
  - update_project (PATCH /projects/{uuid}) — write
  - delete_project (DELETE /projects/{uuid}) — admin
  - list_environments (GET /projects/{uuid}/environments) — read
  - get_environment (GET /projects/{uuid}/environments/{name}) — read
  - create_environment (POST /projects/{uuid}/environments) — write
- [ ] متدهای client در `client.py` اضافه شود
- [ ] در `handlers/__init__.py` ایمپورت projects اضافه شود
- [ ] در `plugin.py` — specs و __getattr__ آپدیت شود

#### مرحله ۲: تست و دیپلوی Phase 3
- [ ] `tests/test_coolify_projects.py` — Unit tests با mocked HTTP
- [ ] `pytest tests/test_coolify*.py -v`
- [ ] Commit: `feat(F.17): add projects handler — Phase 3 (8 tools)`
- [ ] Push و درخواست redeploy
- [ ] تست live: list_projects → پیدا کردن project_uuid
- [ ] تست ساخت container: create_application_docker_image با project_uuid واقعی → دیپلوی nginx → تأیید → حذف

### بخش دوم: Phase 2 — Databases (16 ابزار)
- [ ] `plugins/coolify/handlers/databases.py`
- [ ] ابزارها:
  - list_databases, get_database — read
  - update_database — write
  - delete_database — admin
  - start_database, stop_database, restart_database — write
  - create_postgresql, create_mysql, create_mariadb — write
  - create_mongodb, create_redis, create_clickhouse — write
  - get_database_backups — read
  - create_database_backup — write
  - list_backup_executions — read
- [ ] متدهای client اضافه شود
- [ ] تست: `tests/test_coolify_databases.py`

### بخش سوم: Phase 2 — Services (13 ابزار)
- [ ] `plugins/coolify/handlers/services.py`
- [ ] ابزارها:
  - list_services, get_service — read
  - create_service — write
  - update_service — write
  - delete_service — admin
  - start_service, stop_service, restart_service — write
  - list_service_envs — read
  - create_service_env — write
  - update_service_env — write
  - update_service_envs_bulk — write
  - delete_service_env — write
- [ ] متدهای client اضافه شود
- [ ] تست: `tests/test_coolify_services.py`

### بخش چهارم: ثبت و تست نهایی
- [ ] handlers/__init__.py آپدیت (projects, databases, services)
- [ ] plugin.py آپدیت (specs + __getattr__)
- [ ] server.py — نیازی به تغییر ندارد (coolify قبلا ثبت شده)
- [ ] `uvx --python 3.12 black .`
- [ ] `uvx ruff check --fix .`
- [ ] `pytest` (همه تست‌ها سبز)
- [ ] Commit: `feat(F.17): add databases + services handlers — Phase 2 (29 tools)`
- [ ] Push و درخواست redeploy
- [ ] تست live: list_databases, list_services
- [ ] آپدیت ورژن به v3.8.0 (اگر تأیید شد)

### بخش پنجم: Sync و داکیومنت
- [ ] Sync به نسخه عمومی: `python3.11 scripts/community-build/sync.py --output ../mcphub/`
- [ ] black + ruff + pytest در نسخه عمومی
- [ ] README آپدیت (تعداد ابزار، جدول Coolify)
- [ ] Commit و push نسخه عمومی
- [ ] mcp-skills/skills/coolify/SKILL.md آپدیت (67 ابزار)
- [ ] حافظه آپدیت شود
- [ ] پلن آپدیت شود (Phase 2+3 complete)

## نکات مهم
- server.py نیازی به تغییر ندارد — coolify قبلا register شده و generate_tools خودکار specs جدید رو می‌خونه
- site_api.py نیازی به تغییر ندارد — credential fields و display name قبلا اضافه شده
- الگوی handler: از applications.py کپی کن (آخرین و تمیزترین)
- هر بخش (Phase 3, databases, services) جداگانه commit شود
- قبل از هر عملیات write در تست live از کاربر تأیید بگیر
- ایمیل git داخلی: mcphub.dev@gmail.com
```
