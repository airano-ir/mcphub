# airano-mcp-seo-bridge — deprecated (migration release)

This folder is the source of the **final** v1.3.1 release of the legacy
slug `airano-mcp-seo-bridge`, kept here so it stays under git review.

The slug itself is still alive at:
<https://wordpress.org/plugins/airano-mcp-seo-bridge/>

But it has been superseded by the broader `airano-mcp-bridge` plugin
(approved 2026-05-10, published from
[`wordpress-plugin/airano-mcp-bridge-wporg/`](../airano-mcp-bridge-wporg/)).

## What v1.3.1 changes vs v1.3.0

Only one thing: a dismissible admin notice that points users to
`airano-mcp-bridge`.

- **No** REST routes changed.
- **No** behaviour change for existing API consumers.
- New methods: `handle_migration_notice_dismiss()` (consumes a
  nonce-protected `?airano_seo_bridge_dismiss_migration=1` GET),
  `render_migration_notice()` (renders the notice on every admin page
  for users with `install_plugins`, hidden once dismissed via
  `update_user_meta`).
- New constant: `SEO_API_Bridge::MIGRATION_DISMISS_META`.

## Files

- `airano-mcp-seo-bridge.php` — main plugin file, v1.3.1
- `readme.txt` — wp.org-format readme with the migration banner in
  the description and the 1.3.1 changelog/upgrade-notice entries

## SVN release flow (already done as r3527927/r3527928)

```bash
# Working copy (gitignored):
svn co https://plugins.svn.wordpress.org/airano-mcp-seo-bridge \
       wordpress-plugin/airano-mcp-seo-bridge-svn

# Copy these two files into trunk:
cp airano-mcp-seo-bridge.php readme.txt \
   wordpress-plugin/airano-mcp-seo-bridge-svn/trunk/

# Then:
svn ci wordpress-plugin/airano-mcp-seo-bridge-svn/trunk/ \
  -m "v1.3.1 — Add migration notice pointing to airano-mcp-bridge"
svn cp  wordpress-plugin/airano-mcp-seo-bridge-svn/trunk \
        wordpress-plugin/airano-mcp-seo-bridge-svn/tags/1.3.1
svn ci  wordpress-plugin/airano-mcp-seo-bridge-svn/tags/1.3.1 \
  -m "Tag 1.3.1"
```

## What happens next

The migration notice will appear for every admin (with `install_plugins`)
on every admin page until they either install the replacement plugin or
click the **Dismiss** link in the notice.

When confident that most active installs have migrated, an email to
`plugins@wordpress.org` with subject "Author request — close
airano-mcp-seo-bridge (superseded by airano-mcp-bridge)" closes the slug
permanently. Don't rush this — leave it open for several months so
late migrators still get the notice.
