# WordPress Chat Attachment Ingestion

Issue #118 defines the MCPHub handoff for files that a user attaches in a
chat UI or IDE agent. MCP does not assume that every UI exposes the same
attachment primitive. Agents should choose the narrowest transport based on
what they actually received.

## Handoff Contract

Use one of these inputs:

| Agent has | Use | Why |
|---|---|---|
| Public or short-lived HTTPS URL that the WordPress host can fetch | `wordpress_upload_media_from_url`, `wp_plugin_install_from_zip(zip_url=...)`, or `wp_theme_install_from_zip(zip_url=...)` | Avoids moving bytes through the chat/tool context. |
| Small media bytes already in the tool-call context | `wordpress_upload_media_from_base64` | Single request is simplest for small images/files. |
| Large media bytes, or a chat attachment local to the agent | `wordpress_upload_media_chunked_start` -> HTTP `PUT upload_url` -> `_finish` when `upload_url` is returned. Fallback: repeated `_chunk` -> `_finish`. | MCPHub stores bytes server-side, then uploads to WordPress media without forcing large base64 payloads through tool calls. |
| Plugin/theme zip on the MCPHub host filesystem | `wp_plugin_install_from_zip(zip_path=...)` or `wp_theme_install_from_zip(zip_path=...)` | MCPHub reads the file and forwards the existing companion `zip_base64` contract. |
| Plugin/theme zip local to the agent/chat workspace | `wp_zip_install_chunked_start` -> HTTP `PUT upload_url` when returned -> `wp_plugin_install_from_zip(zip_session_id=...)` or `wp_theme_install_from_zip(zip_session_id=...)`. Fallback: repeated `_chunk` -> install. | Solves the "install this attached zip" flow when MCPHub cannot read the agent filesystem, without pushing zip bytes through tool-call JSON. |
| wp.org plugin slug | `wp_plugin_install_from_slug` | Prefer curated wp.org package installs over arbitrary zip installs. |

Do not hard-code vendor UI limits. Claude, IDEs, hosted ChatGPT-style
surfaces, and API clients change their attachment limits independently.
Instead, inspect the attachment the agent actually received:

- If the UI gave a URL, prefer the URL path.
- If the UI gave local bytes/path only, prefer the HTTP `upload_url` returned
  by `wordpress_upload_media_chunked_start` for media or
  `wp_zip_install_chunked_start` for plugin/theme zips. If no URL is
  returned, stream base64 chunks.
- If a file is already small enough to fit comfortably in one JSON tool call,
  inline base64 is acceptable.
- If the file is large or binary zip-like, use chunked staging.

## Limits Exposed To Agents

The `*_start` response includes:

- `max_bytes`
- `recommended_chunk_bytes`
- `handoff`, either `"http_binary_put"` or `"stream_base64_chunks"`
- `session_id`
- `received_bytes`
- `next_chunk`
- `expires_at`

On per-user MCP endpoints, the start response also includes:

- `upload.method: "PUT"`
- `upload.url`, either
  `"/u/{user_id}/{alias}/media-upload/{session_id}"` for user media or
  `"/u/{user_id}/{alias}/zip-install-upload/{session_id}"` for install zips.
- Admin/master sessions use `"/admin/media-upload/{session_id}"` and the same
  `Authorization: Bearer ...` header; the master key is never placed in a URL
  or returned in the upload payload.
- Admin sessions also return `browser_url`, a short-lived session-scoped link.
  Its bearer token is in the URL fragment (`#token=...`), not the query string,
  so it is not sent to the server or ordinary proxy access logs. The page uses
  same-origin `fetch` to PUT chunks to the admin upload URL.
- `upload.auth: "Use the same Authorization: Bearer *** as this MCP endpoint."`

For the preferred HTTP path, stream the local file directly. Media example:

```bash
curl -X PUT \
  -H "Authorization: Bearer $MCPHUB_TOKEN" \
  -H "Content-Type: application/octet-stream" \
  --data-binary @hero.png \
  "https://mcp.example.com/u/{user_id}/{alias}/media-upload/{session_id}"
```

Zip install example:

```bash
curl -X PUT \
  -H "Authorization: Bearer $MCPHUB_TOKEN" \
  -H "Content-Type: application/zip" \
  --data-binary @premium-plugin.zip \
  "https://mcp.example.com/u/{user_id}/{alias}/zip-install-upload/{session_id}"
```

The media response includes `ready_to_finish`. When true, call
`wordpress_upload_media_chunked_finish`. The zip response includes
`ready_to_install`. When true, call `wp_plugin_install_from_zip` or
`wp_theme_install_from_zip` with `zip_session_id`. If `upload_url` is not
returned, send raw chunks of at most `recommended_chunk_bytes`, base64 encoded
in the `data_b64` field. Base64 expands the payload by roughly one third, so
keep raw chunks moderate even when the transport accepts larger JSON bodies.

Current MCPHub limits:

| Flow | Tool family | Max bytes | TTL | Resume |
|---|---:|---:|---:|---|
| Media attachment | `wordpress_upload_media_chunked_*` | 500 MB per session | 1 hour | `wordpress_upload_media_chunked_status` |
| Plugin/theme zip | `wp_zip_install_chunked_*` | 50 MB per session | 1 hour | `wp_zip_install_chunked_status` |
| Inline media base64 | `wordpress_upload_media_from_base64` | About 10 MB practical envelope | Single call | No |
| Inline install zip base64 | `wp_plugin_install_from_zip(zip_base64=...)` / `wp_theme_install_from_zip(zip_base64=...)` | 50 MB decoded hard cap, but avoid for chat-context payloads | Single call | No |

## Media Workflow

1. Call `wordpress_media_upload_workflow_status` if the agent is unsure
   whether AI image generation is enabled. It reports
   `ai_image_generation.status`, including `disabled_missing_provider_key`.
2. Compute `sha256` if available.
3. Call `wordpress_upload_media_chunked_start(filename, total_bytes, mime, sha256)`.
4. If `upload.url` is present, `PUT` the raw local file bytes to that URL with
   the same Bearer token used for MCP. This is the public-user path for large
   agent-generated or chat-attached media.
5. If `upload.url` is not present, send sequential chunks with
   `wordpress_upload_media_chunked_chunk(session_id, index, data_b64, chunk_sha256?)`.
6. On disconnect, call `wordpress_upload_media_chunked_status(session_id)` and
   resume from `next_chunk`.
7. Call `wordpress_upload_media_chunked_finish(session_id, title?, alt_text?, caption?, attach_to_post?, set_featured?)`.

The finish step reuses the normal WordPress media path. If the companion
advertises `/upload-and-attach`, MCPHub uses the one-round-trip upload,
metadata, attach, and featured-image route. Otherwise it falls back to the
stock REST sequence.

## Plugin/Theme Zip Workflow

1. Confirm the user intended to install an arbitrary zip. Prefer
   `wp_plugin_install_from_slug` for wp.org plugins.
2. Compute `sha256` if available.
3. Call `wp_zip_install_chunked_start(filename, total_bytes, sha256)`.
4. If `upload.url` is present, `PUT` the raw local zip bytes to that URL with
   the same Bearer token used for MCP. This is the public-user path for large
   agent-local or chat-attached plugin/theme zips.
5. If `upload.url` is not present, send sequential chunks with
   `wp_zip_install_chunked_chunk(session_id, index, data_b64, chunk_sha256?)`.
6. On disconnect, call `wp_zip_install_chunked_status(session_id)` and resume from `next_chunk`.
7. Install with `wp_plugin_install_from_zip(zip_session_id=session_id, activate?, overwrite?)` or `wp_theme_install_from_zip(zip_session_id=session_id, activate?, overwrite?)`.

The install call finalizes and consumes the staging session. If validation
fails before finalization, abort the session with `wp_zip_install_chunked_abort`.

## Safety Notes

- Zip installs are admin-tier because arbitrary plugin/theme packages can
  execute code on the WordPress host.
- The zip HTTP intake route is only available for `wordpress_specialist`
  sites and requires admin scope, site-level admin access, and enabled
  `wp_zip_install_chunked_start/chunk` tools.
- Staged zip sessions are validated as real zip archives before MCPHub sends
  them to the companion.
- `zip_path` is only for files readable by the MCPHub process. Agent-local
  paths from Claude Code, code-server, or an IDE extension usually require
  `zip_session_id` instead.
- The companion still enforces WordPress capabilities such as
  `install_plugins`, `install_themes`, `switch_themes`, and `activate_plugins`.
