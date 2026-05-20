# Screenshot reference for the Track G review

Captured against the deployed mcp-test.palebluedot.live with the bilingual
visual-testing harness:

- 3 viewports: `mobile` (375×812), `tablet` (768×1024), `desktop` (1280×800)
- 2 locales: `en`, `fa`
- 8 authenticated dashboard pages under `/dashboard/*`: overview, sites,
  connect, api-keys, oauth-clients, health, audit-logs, settings

File name pattern: `{page}-{viewport}-{lang}.png` (48 files total). The
historical `v2-*` page prefixes are intentionally kept in filenames so md5 and
git diffs stay comparable across the G.12 cutover.

## How to regenerate

```bash
# One-time setup (Playwright + Chromium + 285 fallback fonts, all user-space)
cd /tmp && npm install playwright && npx playwright install chromium

# Re-run after a deploy
LD_LIBRARY_PATH=/tmp/playwright-libs/extracted/usr/lib/x86_64-linux-gnu \
FONTCONFIG_PATH=/config/.config/fontconfig \
FONTCONFIG_FILE=/config/.config/fontconfig/fonts.conf \
PLAYWRIGHT_BROWSERS_PATH=/config/.cache/ms-playwright \
MCPHUB_MASTER_KEY=<key> \
  node /config/workspace/mcp-skills/skills/bilingual-page-review/scripts/snap-auth.mjs
```

The harness logs in once via the legacy Jinja master-key form at
`/dashboard-legacy/login`, saves the storage state to `.auth-state.json`
(gitignored), then reuses that cookie for every shot against `/dashboard/*`.
Set `MCPHUB_MASTER_KEY` from the Coolify env (`MASTER_API_KEY`) so it never
lands in the script file.

## What to look for when reviewing

| Aspect | EN | FA |
| --- | --- | --- |
| Sidebar position | left | right |
| Topbar control order | hamburger \| crumbs \| ... \| globe/EN \| theme \| bell | bell \| theme \| globe/FA \| ... \| crumbs \| hamburger |
| Numbers in stat cards | `0-9` | `۰-۹` |
| Dates in tables | `2026/05/08 02:47` | `۱۴۰۵/۰۲/۱۸ ۰۲:۴۷` (Shamsi) |
| Wordmark | "MCP Hub" | "MCP Hub" — always LTR, never "Hub MCP" |
| Sidebar nav labels | English | فارسی (مدیریت / سایت‌ها / اتصال / …) |
