# airano-mcp-bridge — WordPress.org submission package

This folder is the **wp.org-bound** version of the companion plugin. It is
deliberately the small surface (≈15 routes — SEO, media uploads, capability
probe, cache/transient/site-health, audit-hook), **not** the full v2.18.x
internal build.

The internal build at [../airano-mcp-bridge/](../airano-mcp-bridge) carries
the admin namespace (plugins/themes/files/db/elementor/etc.) which is too
broad for wp.org's review bar and stays out of the public release.

## Layout

```
airano-mcp-bridge-wporg/
├── airano-mcp-bridge/        ← what goes in the zip
│   ├── airano-mcp-bridge.php
│   ├── readme.txt
│   └── README.md
├── tests/
│   ├── check.sh              ← static checks (headers, escaping, routes, etc.)
│   └── test_permission_callback.php   ← unit test for the new gate
└── airano-mcp-bridge.zip     ← ready-to-upload bundle (built from the folder)
```

## Pre-submission checks

```bash
# 1. Static / heuristic checks (no WordPress runtime required)
bash wordpress-plugin/airano-mcp-bridge-wporg/tests/check.sh

# 2. Unit tests on the new permission_callback (PHP-only, no WP bootstrap)
php wordpress-plugin/airano-mcp-bridge-wporg/tests/test_permission_callback.php
```

Both must exit 0 before zipping or uploading.

## Building the zip

```bash
python - <<'PY'
import io, os, re, glob, zipfile
src    = "wordpress-plugin/airano-mcp-bridge-wporg/airano-mcp-bridge"
outdir = "wordpress-plugin/airano-mcp-bridge-wporg"
# The filename carries the build AND the version on purpose — see the warning in step 7.
ver = re.search(r"\*\s*Version:\s*([0-9.]+)",
                io.open(src + "/airano-mcp-bridge.php", encoding="utf-8").read()).group(1)
for stale in glob.glob(outdir + "/airano-mcp-bridge-wporg-*.zip"):
    os.remove(stale)
dst = "%s/airano-mcp-bridge-wporg-%s.zip" % (outdir, ver)
with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    z.writestr(zipfile.ZipInfo("airano-mcp-bridge/"), b"")      # dir entry
    for f in ("airano-mcp-bridge.php", "readme.txt", "README.md"):
        z.write(src + "/" + f, "airano-mcp-bridge/" + f)
print("built:", dst, os.path.getsize(dst), "bytes")
PY
```

## Reply to the wp.org review email

Use the message in [SUBMISSION_REPLY.md](SUBMISSION_REPLY.md). Keep it
short — the wp.org guidance is "be brief and direct".

## What the v2.10.2 release fixes (vs the v2.10.1 they reviewed)

1. **Direct core file include**
   `wp-admin/includes/media.php` was loaded inside the `/upload-chunk` and
   `/upload-and-attach` REST callbacks but never used (the code only calls
   helpers from `file.php` and `image.php`). The redundant `require_once`
   lines are removed.

2. **`/upload-and-attach` permission gate**
   The route now uses a dedicated `require_upload_and_attach_capability`
   method that runs `current_user_can('edit_post', $attach_to_post)` at
   the route gate when `attach_to_post` is supplied. The check is no
   longer hidden inside the callback body, so static analysis can see it.
   The method also rejects `set_featured` without a target post.

3. **Ownership verification**
   DNS TXT record `wordpressorg-airano-verification` is published at
   `mcp.example.com`, which is also the `Plugin URI`. This pairs the
   submission with the domain the plugin advertises and satisfies the
   wp.org review request for a non-gmail.com proof of identity.
