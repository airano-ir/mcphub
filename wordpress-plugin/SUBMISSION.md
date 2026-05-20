# Airano MCP Bridge — wp.org Submission Handoff

This document covers the full transition from the legacy `airano-mcp-seo-bridge` slug to the new `airano-mcp-bridge` slug on WordPress.org.

---

## Phase 1 — Local prep (DONE)

- [x] readme.txt header: `Stable tag: 2.10.1`, `Tested up to: 6.9` (major.minor only — Plugin Check rejects `6.9.4`)
- [x] PHP header: `Plugin URI` (live site) and `Author URI` (GitHub org) are now distinct — Plugin Check rejected when both pointed to the same URL
- [x] readme.txt: changelog entries for 2.10.0 and 2.10.1, matching upgrade notices
- [x] readme.txt + main PHP: live-site link (`https://mcp.palebluedot.live`) added; GitHub source kept as secondary
- [x] README.md version bumped to 2.10.1
- [x] Plugin URI + Author URI in main PHP point to live site
- [x] Submission zip rebuilt with POSIX paths: `wordpress-plugin/airano-mcp-bridge.zip` (33.9 KB, 3 files)
- [x] SVN staging layout prepared at `wordpress-plugin/airano-mcp-bridge-svn/`:
  - `trunk/` — final files
  - `assets/icon.svg` — copied from `core/templates/static/logo.svg`
  - `tags/` — empty (release tags created in Phase 3)

---

## Phase 2 — Submit to wp.org (USER ACTION, in browser)

### Step 1 — Go to the submission form

https://wordpress.org/plugins/developers/add/

Sign in with the same wp.org account that owns `airano-mcp-seo-bridge` (`airano`).

### Step 2 — Upload the ZIP

The submission form has **one upload field** + **one "Additional Information" textbox**. The plugin name, slug, tags and full description all come from the `readme.txt` inside the ZIP — the form does NOT ask for them separately.

- **ZIP**: `wordpress-plugin/airano-mcp-bridge.zip`
- **Additional Information**: paste the short message in Step 3 below

### Step 3 — "Additional Information" message (paste this)

This field is read by reviewers, not end users. Keep it short and give context they can't infer from the readme.

```
Companion plugin for MCP Hub (https://mcp.palebluedot.live), a self-hosted
hub that lets AI assistants manage WordPress, WooCommerce and other
self-hosted services through the Model Context Protocol.

The plugin extends the WordPress REST API with a few routes the stock
endpoints can't cover — raw-binary media uploads that bypass
upload_max_filesize, bulk meta writes, cache purge, transient cleanup,
unified site-health snapshot, HMAC-signed audit webhook, and SEO meta
for Rank Math / Yoast. All routes are gated by WordPress capability
checks and require Application Password authentication.

Submission notes for the review team:

- Same author account ("airano") previously published
  https://wordpress.org/plugins/airano-mcp-seo-bridge/ (1.3.0, 30+ active
  installs). That earlier plugin was SEO-only. Over the past two months
  it grew well beyond SEO, so we are submitting under a new slug
  (airano-mcp-bridge) that better reflects the broader scope. The old
  slug will get a final release with a migration notice and then be
  retired — we won't rename or replace its main file.

- All file I/O uses WP_Filesystem, not bare PHP file functions.
- All output is escaped (esc_html, esc_url, wp_kses_post as appropriate).
- Translations use the 'airano-mcp-bridge' text domain (36 strings).
- No bundled binaries, no obfuscation, no remote calls except the
  user-configured audit-hook webhook (which is opt-in and fully disabled
  by default).
```

### Step 4 — After submitting

You'll get an automated confirmation email. Reviewers may take **1-14 days** to respond. They might:

- **Approve immediately** (clean readme + standards-compliant code) → SVN credentials emailed
- **Ask for fixes** (e.g. extra escaping, license clarifications) → reply with patches
- **Reject** → reasons given; address and resubmit

**While you wait:** the old slug `airano-mcp-seo-bridge` stays live and untouched. If you need to push an urgent fix to the existing 30+ installs in the meantime, you can — see `Fallback` section below.

---

## Phase 3 — After approval (CLI commands, run from this repo)

When wp.org emails the SVN URL (`https://plugins.svn.wordpress.org/airano-mcp-bridge/`):

```bash
# 1. Checkout the empty SVN repo
svn co https://plugins.svn.wordpress.org/airano-mcp-bridge/ /tmp/airano-mcp-bridge-svn

# 2. Copy our prepared layout into it
cp -r wordpress-plugin/airano-mcp-bridge-svn/trunk/*  /tmp/airano-mcp-bridge-svn/trunk/
cp -r wordpress-plugin/airano-mcp-bridge-svn/assets/* /tmp/airano-mcp-bridge-svn/assets/

# 3. Stage everything
cd /tmp/airano-mcp-bridge-svn
svn add trunk/* --force
svn add assets/* --force

# 4. First commit to trunk
svn ci -m "Initial release 2.10.1 — companion plugin for MCP Hub"

# 5. Tag the release (so wp.org indexes it as v2.10.1)
svn cp trunk tags/2.10.1
svn ci -m "Tag 2.10.1"
```

### Asset checklist (Phase 3 polish — can be done after first release)

- [x] `assets/icon.svg` — staged
- [ ] `assets/icon-256x256.png` — render the SVG at 256x256 (any online SVG-to-PNG tool, e.g. [cloudconvert](https://cloudconvert.com/svg-to-png))
- [ ] `assets/banner-772x250.png` — needs design (logo + "Airano MCP Bridge" text + tagline on a #51b9f4 / #fec13d brand background)
- [ ] `assets/banner-1544x500.png` — 2x retina version of the banner
- [ ] `assets/screenshot-1.png` (optional) — could be a screenshot of MCP Hub dashboard showing the connected WP site, or skipped entirely

---

## Phase 4 — Deprecate old slug (LATER, weeks after Phase 3 is stable)

### Strategy: soft handover, then closure

1. **Wait** until the new plugin has its own organic traffic and a working install base (~2-4 weeks).
2. **Push a final 1.x release** to the OLD slug (`airano-mcp-seo-bridge`) that does **two things**:
   - Adds a persistent admin notice: *"Airano MCP SEO Meta Bridge has been renamed and rebuilt as **Airano MCP Bridge**. Install the new plugin and deactivate this one. → \[Install link]"*
   - Keeps the old REST routes (`airano-mcp-seo-bridge/v1/*`) working so existing MCP Hub deployments don't break overnight.
3. **Email closure** to `plugins@wordpress.org` from the author email **only after** the new plugin has been live for at least a month.

### Closure email template (use later, NOT NOW)

```
To: plugins@wordpress.org
Subject: Plugin closure request — airano-mcp-seo-bridge

Hello,

Please close the plugin with slug "airano-mcp-seo-bridge"
(https://wordpress.org/plugins/airano-mcp-seo-bridge/).

Reason: The plugin has been rebuilt and rebranded as "Airano MCP Bridge"
(slug: airano-mcp-bridge), available at
https://wordpress.org/plugins/airano-mcp-bridge/. The old slug's name
and SEO-only scope no longer reflect what the plugin does.

A migration notice has been published to the old slug since version 1.4.0
directing users to the new plugin.

Author: airano
```

---

## Fallback — if wp.org rejects or you need to ship to old users first

The old slug still works. To push an urgent fix (e.g. critical bug) without waiting for the new plugin to be approved:

```bash
# Checkout old slug SVN
svn co https://plugins.svn.wordpress.org/airano-mcp-seo-bridge/ /tmp/old-svn

# Copy current code in (need to rename main file back to airano-mcp-seo-bridge.php
# and adjust Plugin Name in the header to match the old display name)
# ... then commit + tag as you would for a normal release

# Bump the version in trunk/readme.txt and trunk/airano-mcp-seo-bridge.php
# svn ci -m "Bug fix release X.Y.Z"
# svn cp trunk tags/X.Y.Z
# svn ci -m "Tag X.Y.Z"
```

⚠️ Don't push the new file `airano-mcp-bridge.php` directly to the old slug — wp.org tracks the main plugin file by name and renaming it breaks WordPress's auto-update.

---

## Files touched in Phase 1

- `wordpress-plugin/airano-mcp-bridge/readme.txt` — version, changelog, upgrade notice, live-site link
- `wordpress-plugin/airano-mcp-bridge/README.md` — version, live-site link
- `wordpress-plugin/airano-mcp-bridge/airano-mcp-bridge.php` — Plugin URI, Author URI
- `wordpress-plugin/airano-mcp-bridge.zip` — rebuilt with POSIX paths

## New files (staging only — not yet committed anywhere)

- `wordpress-plugin/airano-mcp-bridge-svn/{trunk,assets,tags}/` — pre-built SVN layout
- `wordpress-plugin/SUBMISSION.md` — this file
