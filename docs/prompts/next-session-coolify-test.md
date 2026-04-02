# Next Session — Coolify MCP Plugin Testing & Next Steps

> Session prompt. Copy and paste into a new Claude Code conversation.

---

## Prompt:

```
از مهارت project-ops برای آشنایی با محیط استفاده کن. حافظه و فایل‌های مرجع را بررسی کن.

## هدف: تست پلاگین Coolify MCP و مراحل بعدی

### پیش‌نیاز
- MCPHub redeploy شده و سایت Coolify اضافه شده
- MCP endpoint `mcphub-coolify` در `.claude.json` تنظیم شده
- پلاگین 30 ابزار دارد (17 application + 5 deployment + 8 server)

### مرحله ۱: تأیید اتصال MCP
- [ ] لیست ابزارهای coolify را از MCP بگیر (باید 30 ابزار باشد)
- [ ] اگر ابزار coolify در لیست نبود، `.claude.json` و `settings.json` را بررسی کن

### مرحله ۲: تست ابزارهای read
- [ ] `coolify_list_servers` — لیست سرورها
- [ ] `coolify_list_applications` — لیست اپلیکیشن‌ها
- [ ] `coolify_list_deployments` — لیست دیپلویمنت‌های در حال اجرا
- [ ] `coolify_get_server_resources(uuid=SERVER_UUID)` — منابع سرور
- [ ] `coolify_get_server_domains(uuid=SERVER_UUID)` — دامنه‌های سرور
- [ ] یک اپلیکیشن انتخاب کن و:
  - [ ] `coolify_get_application(uuid=APP_UUID)` — جزئیات
  - [ ] `coolify_get_application_logs(uuid=APP_UUID, lines=50)` — لاگ‌ها
  - [ ] `coolify_list_application_envs(uuid=APP_UUID)` — متغیرهای محیطی
- [ ] `coolify_list_app_deployments(uuid=APP_UUID)` — تاریخچه دیپلوی

### مرحله ۳: تست ابزارهای write (با احتیاط)
- [ ] از کاربر بپرس آیا مجاز است یک env var تست ایجاد/حذف کند
- [ ] اگر بله:
  - [ ] `coolify_create_application_env(uuid=APP_UUID, key="TEST_VAR", value="test123")`
  - [ ] `coolify_delete_application_env(uuid=APP_UUID, env_uuid=...)`

### مرحله ۴: گزارش نتایج
- [ ] خلاصه نتایج تست (چند ابزار کار کرد، مشکلات)
- [ ] مقایسه با ابزارهای Gitea و Supabase MCP (کیفیت پاسخ‌ها)

### مرحله ۵: اگر تست موفق بود — Sync به نسخه عمومی
- [ ] `python3.11 scripts/community-build/sync.py --output ../mcphub/`
- [ ] `cd /config/workspace/mcphub && uvx --python 3.12 black . && uvx ruff check --fix .`
- [ ] تست‌ها: `python3.11 -m pytest tests/ -q`
- [ ] Commit و push نسخه عمومی

### مرحله ۶: آپدیت‌ها
- [ ] mcp-skills/skills/coolify/SKILL.md — از planned به active تغییر کرده (بررسی شود)
- [ ] حافظه آپدیت شود

## پیشنهاد مراحل بعدی (بعد از تست)

### فوری
1. **F.17 Phase 2**: اضافه کردن databases (16 ابزار) + services (13 ابزار) → ~59 ابزار کل
2. **F.17 Phase 3**: projects (8 ابزار) → ~67 ابزار کل — تکمیل طرح اصلی

### میان‌مدت
3. **Coolify Workflow Skill**: مهارت اختصاصی برای عملیات متداول (deploy all, backup all, health check all)
4. **Integration Test**: تست خودکار با Coolify واقعی (pytest mark integration)
5. **F.14a**: ثبت MCPHub در Smithery + Official MCP Registry

### بلندمدت
6. **Blog Post**: نوشتن مقاله درباره "Self-hosted MCP Hub with Coolify Integration"
7. **F.5a**: Base64 media upload برای WordPress
8. **F.6**: Claude Code skills بومی

## قوانین
- اول ابزارهای read تست شوند، بعد write
- قبل از هر عملیات write از کاربر تأیید بگیر
- نتایج تست دقیق گزارش شود (UUID ها، خطاها، زمان پاسخ)
- حافظه آپدیت شود بعد از اتمام
- ایمیل git داخلی: mcphub.dev@gmail.com
```
