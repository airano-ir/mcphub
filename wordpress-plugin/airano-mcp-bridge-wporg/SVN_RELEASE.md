# wp.org SVN release log

**Latest: v2.11.0 — 2026-06-04**

- ✅ `airano-mcp-bridge` trunk → `r3561108` ("v2.11.0 — WP 7.0 + 4 new routes")
- ✅ `airano-mcp-bridge` tag `2.11.0` → `r3561109`
- ✅ `airano-mcp-seo-bridge` (legacy) trunk → `r3561112` ("v1.3.2 — Tested up to 7.0")
- ✅ `airano-mcp-seo-bridge` (legacy) tag `1.3.2` → `r3561115`

v2.11.0 cycle highlights (the next session will care about these):

- Ported 4 routes from internal v2.20.0: `/opcache-reset`,
  `/transients`, `/term-update`, plus `scope=object|page|all` on
  `/cache-purge`. Multilingual routes (`/post-language`,
  `/term-language`) intentionally deferred — they pull in ~30 helpers
  and need real WPML/Polylang test coverage.
- Bumped `Tested up to` 6.9 → 7.0 (WordPress 7.0 release cycle).
- Bumped `Requires at least` 5.0 → 5.6 because Plugin Check flagged
  the existing `/site-health` route's use of `wp_timezone_string()`
  (WP 5.3) and `wp_is_application_passwords_available()` (WP 5.6)
  against the 5.0 floor. WP 5.6 is from 2020-12 so no practical impact.
- Scrubbed two pre-existing `coolify-mcp-hub` (old private-repo name)
  links from README.md — replaced with the public `mcphub` mirror so
  the README on the wp.org page no longer leaks the private repo.

For the full release runbook (what to port, version policy, asset
regeneration, etc.) see [../UPGRADE_GUIDE.md](../UPGRADE_GUIDE.md).

---

## Prior release history

**v2.10.3 — 2026-05-10 (first wp.org-approved release of the new slug)**

- ✅ trunk committed at `r3527909` (`svn ci`-ed by maintainer)
- ✅ assets committed at `r3527917` (icon-128/256, banner-772x250 / 1544x500)
- ✅ tag `2.10.3` committed at `r3527918`
- ✅ legacy slug `airano-mcp-seo-bridge` updated to v1.3.1 at
  `r3527927/r3527928` with migration notice pointing here

Live page: <https://wordpress.org/plugins/airano-mcp-bridge/>

The rest of this file is the original runbook, kept as reference for
future releases.

---

---

## What is already staged for you

A working copy is checked out at
`wordpress-plugin/airano-mcp-bridge-wporg-svn/` (gitignored). The three
plugin files have been copied into `trunk/` and `svn add`-ed:

```
A       trunk/README.md
A       trunk/airano-mcp-bridge.php
A       trunk/readme.txt
```

The files are byte-identical to
`wordpress-plugin/airano-mcp-bridge-wporg/airano-mcp-bridge/`, which is
the version that just passed review.

---

## Step 1 — confirm credentials

If the approval email landed less than an hour ago, wait until the hour
is up. Then verify your SVN password at:

  https://profiles.wordpress.org/me/profile/edit/group/3/?screen=svn-password

The SVN username is your wordpress.org login: `airano` (case-sensitive).

---

## Step 2 — commit the initial release to trunk

```bash
cd wordpress-plugin/airano-mcp-bridge-wporg-svn

svn ci -m "Initial release v2.10.3"
# → SVN will prompt for username (airano) and password the first time.
#   Tick "store password" if you trust the machine.
```

Wait for the response. A successful commit ends with `Committed revision XXXXXXX.`

---

## Step 3 — tag the release

wp.org expects every released version to also exist as a tag under
`tags/<version>/`. The Stable Tag in `readme.txt` already points to
`2.10.3`, so this tag is what `wp.org` actually serves to users.

```bash
# Still inside wordpress-plugin/airano-mcp-bridge-wporg-svn/
svn cp trunk tags/2.10.3
svn ci -m "Tag 2.10.3"
```

After this, `https://wordpress.org/plugins/airano-mcp-bridge/` will start
serving v2.10.3 within a few minutes.

---

## Step 4 — verify on wp.org

- Plugin page: <https://wordpress.org/plugins/airano-mcp-bridge/>
- Latest tag: <https://plugins.svn.wordpress.org/airano-mcp-bridge/tags/2.10.3/>
- Trunk:      <https://plugins.svn.wordpress.org/airano-mcp-bridge/trunk/>

The "Tested up to" badge, version number, and changelog should all show
2.10.3.

---

## Optional but recommended — plugin assets

Plugin assets (icon, banner, screenshots) live in the SVN `assets/`
directory at the same level as `trunk/` — NOT inside `trunk/assets/`.

Required filenames (any of):
```
assets/icon-128x128.png   (or .jpg / icon.svg)
assets/icon-256x256.png   (high-DPI)
assets/banner-772x250.png (header image, listing card)
assets/banner-1544x500.png (high-DPI header)
assets/screenshot-1.png   (matched by readme.txt "== Screenshots ==" entries)
assets/screenshot-2.png
```

To upload after creating them locally:
```bash
cd wordpress-plugin/airano-mcp-bridge-wporg-svn
cp /path/to/icon-256x256.png assets/
cp /path/to/banner-1544x500.png assets/
svn add assets/icon-256x256.png assets/banner-1544x500.png
svn ci -m "Add plugin assets — icon + banner"
```

Spec: <https://developer.wordpress.org/plugins/wordpress-org/plugin-assets/>

---

## Optional — close the old slug

The old slug `airano-mcp-seo-bridge` (the SEO-only ancestor) is still
live. After v2.10.3 of the new slug is on the directory, you have two
options:

**(a) Push a final 1.x release to the old slug** that simply prints an
admin notice ("This plugin is now Airano MCP Bridge — please install
that and deactivate this one"). Less disruptive for existing users.

**(b) Email `plugins@wordpress.org`** asking to close the old slug as
"author request — superseded by airano-mcp-bridge". Faster.

Either is fine. Do this *after* the new slug is live and you've
confirmed at least one install path works.
