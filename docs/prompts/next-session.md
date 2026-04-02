# Next Session — Registry + MCP Skills + Infrastructure

> Session prompt. Copy and paste into a new Claude Code conversation.

---

## Prompt:

```
از مهارت project-ops برای آشنایی با محیط استفاده کن. حافظه و فایل‌های مرجع را بررسی کن.

## فایل‌های مرجع
- docs/plans/2026-03-25-v4-development-cycle.md (mcphub-internal, branch Phase-1)
- CLAUDE.md (mcphub-internal)
- CHANGELOG.md (mcphub-internal)

## وضعیت فعلی
- MCPHub: v3.6.0 — 567 ابزار، 5 پلاگین عمومی (WordPress, WooCommerce, Supabase, OpenPanel, Gitea)
- FastMCP: >=3.0.0,<4.0.0
- CI سبز

## MCP Endpoints فعال
- mcphub-supabase: 70 ابزار Supabase (DB, auth, storage)
- mcphub-gitea: 58 ابزار Gitea (repos, issues, PRs, webhooks)

## ریپازیتوری‌ها
### GitHub (airano-ir)
- mcphub (public) → /config/workspace/mcphub
- mcphub (private, Phase-1) → /config/workspace/mcphub-internal  
- mcp-skills (private, خالی) → /config/workspace/mcp-skills
- skillhub-internal → /config/workspace/skillhub-internal
- skillhub (public) → /config/workspace/skillhub

### Gitea (atlatl @ gitea.example.com)
- polymarket (private) → /config/workspace/polymarket
- polymarket-skill (private) → /config/workspace/polymarket-skill
- project-ops (private) → مهارت در /config/.claude/skills/project-ops/

## اهداف این session (به ترتیب اولویت)

### 1. Registry Submissions (F.14a)
وضعیت فعلی:
- Glama: ثبت شده (Score: A)، glama.json اضافه شده
- awesome-mcp-servers: PR #2147 باز — badge SVG + tool count اصلاح شده، منتظر merge
- Smithery.ai: ثبت نشده → از smithery.ai/new ثبت کن (نیاز به public HTTPS URL: mcp.example.com)
- Official MCP Registry: ثبت نشده → بررسی `mcp-publisher` CLI
کارها:
- [ ] وضعیت PR #2147 چک شود — اگر feedback جدید دارد رفع شود
- [ ] ثبت در Smithery.ai
- [ ] بررسی Official MCP Registry submission process

### 2. MCP Skills — اولین مهارت‌ها (github:airano-ir/mcp-skills)
ریپازیتوری خالی ساخته شده. ساختار:
```
mcp-skills/skills/
├── wordpress/    ← اولین مهارت
├── supabase/
├── gitea/
├── woocommerce/
├── openpanel/
└── coolify/      ← آینده
```
کارها:
- [ ] از SkillHub بهترین مهارت‌های مرتبط را جستجو کن: `npx skillhub search "wordpress mcp" --sort aiScore`
- [ ] اگر مهارت با کیفیت بالا (aiScore > 70) پیدا نشد، با skill-creator مهارت جدید بساز
- [ ] اولین مهارت: WordPress content workflow (استفاده از MCP endpoint مستقیم)
- [ ] هر مهارت باید SKILL.md + اسکریپت‌های عملی داشته باشد
- [ ] بعد از تست، commit و push به github:airano-ir/mcp-skills

### 3. Project-Ops Sync با Gitea
- [ ] محتوای `/config/.claude/skills/project-ops/SKILL.md` را به `gitea:atlatl/project-ops` push کن
- [ ] مطمئن شو backup در Gitea up-to-date است

### 4. Blog Workspace Setup
- [ ] WordPress MCP endpoint اضافه کن از داشبورد mcp.example.com (blog.example.com)
- [ ] یک پست تست با MCP WordPress tools بنویس
- [ ] اگر API مشکلی داشت، در mcphub-internal fix کن

### 5. بررسی Coolify MCP (F.17)
- [ ] API documentation کولیفای را بررسی کن
- [ ] بررسی آیا Coolify API در دسترس است از این محیط
- [ ] یک طرح اولیه از tools مورد نیاز بنویس
- [ ] نتیجه را در docs/plans/ ذخیره کن

## قوانین
- اول پلن بده، بدون تایید شروع نکن
- هر مرحله commit شود
- حافظه و project-ops در صورت نیاز آپدیت شود
- از SkillHub برای پیدا کردن بهترین مهارت‌ها استفاده کن (aiScore بالاترین)
- اگر مهارتی بررسی نشده، با auto-review بررسی کن
- ایمیل git عمومی: hi.airano@gmail.com
- ایمیل git داخلی: mcphub.dev@gmail.com
```
