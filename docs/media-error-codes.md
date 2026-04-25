# Media Upload Error Codes (F.5a.6.2)

All media-upload tools return structured JSON errors shaped as:

```json
{
  "error_code": "TOO_LARGE",
  "message": "File is 12345678 bytes; limit is 10485760 bytes ...",
  "details": { "size": 12345678, "max": 10485760 }
}
```

The `error_code` values below are **stable**: renaming or removing one is
a breaking change. The source of truth is
[`core/media_error_codes.py`](../core/media_error_codes.py) (the set
`MEDIA_ERROR_CODES`) and the stability test in
[`tests/plugins/wordpress/test_media_error_taxonomy.py`](../tests/plugins/wordpress/test_media_error_taxonomy.py).

## Input / validation

| Code              | When it fires                                                                         |
| ----------------- | ------------------------------------------------------------------------------------- |
| `BAD_BASE64`      | The supplied base64 payload (full upload or single chunk) fails to decode.            |
| `BAD_MODE`        | `mode` argument to attach tools is not `append` or `replace`.                         |
| `BAD_ROLE`        | `role` argument to attach tools is not `main` or `gallery`.                           |
| `BAD_SIZE`        | Chunked `total_bytes` is `<= 0`.                                                      |
| `BAD_SOURCE`      | Attach-upload helper given a `source` other than `base64` / `url`.                    |
| `EMPTY_FILE`      | Decoded payload is zero bytes.                                                        |
| `MEDIA_NOT_FOUND` | A supplied `media_id` does not exist in the WP media library.                         |
| `MIME_REJECTED`   | Sniffed MIME is not in the allow-list (`ALLOWED_MIMES`).                              |
| `MISSING_FIELD`   | A required field is missing (e.g. `data` for base64, `url` for URL sideload).         |
| `SSRF`            | URL resolves to private/loopback/link-local/metadata IP or is on the host blocklist. |
| `TOO_LARGE`       | Payload exceeds `WP_MEDIA_MAX_MB` / streamed download exceeds the byte cap.           |
| `URL_FETCH_FAILED`| Remote URL returned `>= 400` while downloading.                                       |

## WordPress REST upstream

| Code              | When it fires                                                                         |
| ----------------- | ------------------------------------------------------------------------------------- |
| `WP_413`          | WordPress rejected the upload with HTTP 413 (server `upload_max_filesize` too low).   |
| `WP_AUTH`         | WordPress rejected auth (401/403). Application Password likely invalid/expired.       |
| `WP_BAD_RESPONSE` | Upload accepted but WP returned a non-JSON body.                                      |
| `WP_CREDENTIALS_MISSING` | (WC sites only) Tool needs a WP Application Password to hit `/wp/v2/media`. WC Consumer Key + Secret do not authenticate the WP core REST. Add `wp_username` + `wp_app_password` in Connection Settings → advanced. |
| `WP_<status>`     | Any other non-2xx status from WP — e.g. `WP_400`, `WP_500`. Dynamic.                  |

## Companion plugin `upload-chunk` route (F.5a.7)

These only fire when MCPHub chose the companion `/airano-mcp/v1/upload-chunk` route
(because the probe advertises the helper and the payload exceeds `upload_max_filesize`).
A companion failure is **non-fatal**: MCPHub falls back to the standard `/wp/v2/media`
route on any error here, so these codes usually surface in logs, not to end users.

| Code                     | When it fires                                                         |
| ------------------------ | --------------------------------------------------------------------- |
| `COMPANION_BAD_RESPONSE` | Companion route returned 2xx but the body was not parseable JSON.     |
| `COMPANION_<status>`     | Any non-2xx status from the companion route — e.g. `COMPANION_500`.   |

## Chunked upload session

| Code                | When it fires                                                                |
| ------------------- | ---------------------------------------------------------------------------- |
| `BAD_STATE`         | Session exists but is not in `open` state (already finalized/aborted).       |
| `CHECKSUM_MISMATCH` | Assembled sha256 does not match value supplied at `start`.                   |
| `CHUNK_CHECKSUM`    | Per-chunk sha256 does not match the value supplied with the chunk.           |
| `CHUNK_ORDER`       | Chunk index does not match `next_chunk`.                                     |
| `CHUNK_OVERFLOW`    | Appending this chunk would exceed declared `total_bytes`.                    |
| `EXPIRED`           | Session's TTL has elapsed.                                                   |
| `INCOMPLETE`        | Finalize called before all declared bytes arrived.                           |
| `NO_SESSION`        | `session_id` is unknown.                                                     |
| `QUOTA_EXCEEDED`    | User already has `MCPHUB_UPLOAD_MAX_CONCURRENT` open sessions.               |
| `SESSION_TOO_LARGE` | Declared `total_bytes` exceeds the hard session cap (default 500 MB).        |

## AI generation providers

| Code                    | When it fires                                                          |
| ----------------------- | ---------------------------------------------------------------------- |
| `GENERATION_FAILED`     | Generic provider failure not covered by a more specific code.          |
| `NO_PROVIDER_KEY`       | No per-user key stored and no env fallback for the selected provider.  |
| `PROVIDER_AUTH`         | Provider rejected the supplied API key.                                |
| `PROVIDER_BAD_REQUEST`  | Provider returned 4xx — prompt or size was invalid.                    |
| `PROVIDER_BAD_RESPONSE` | Provider returned a 2xx with an unexpected shape.                      |
| `PROVIDER_QUOTA`        | Provider returned 429 / quota error.                                   |
| `PROVIDER_TIMEOUT`      | Provider timed out.                                                    |
| `PROVIDER_UNAVAILABLE`  | Provider returned 5xx / circuit open.                                  |
| `PROVIDER_UNKNOWN`      | `provider` argument is not one of the registered providers.            |

## Rate / policy

| Code                 | When it fires                                                         |
| -------------------- | --------------------------------------------------------------------- |
| `TOOL_RATE_LIMITED`  | Per-tool, per-user cap exceeded (see `core/tool_rate_limiter.py`).    |

## Catchall

| Code       | When it fires                                                                      |
| ---------- | ---------------------------------------------------------------------------------- |
| `INTERNAL` | Unexpected exception reached the top of a tool handler. Details in `message`.      |
