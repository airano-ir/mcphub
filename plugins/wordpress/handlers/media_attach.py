"""F.5a.3: WooCommerce product image attachment + WP featured-image tool.

WooCommerce `PUT /products/{id}` with `images: []` REPLACES the whole gallery.
For additive behaviour we GET-merge-PUT. We only ever reference existing
media by `id` (never pass external `src` — WC would re-download it).
"""

from __future__ import annotations

import json
from typing import Any

from plugins.wordpress.client import WordPressClient
from plugins.wordpress.handlers._media_core import (
    fetch_url_bytes,
    wp_raw_upload,
    wp_set_featured_media,
    wp_update_media_metadata,
)
from plugins.wordpress.handlers._media_security import (
    DEFAULT_MAX_BYTES,
    UploadError,
    ssrf_check,
)
from plugins.wordpress.handlers.media import _decode_base64, _maybe_optimize


def get_tool_specifications() -> list[dict[str, Any]]:
    return [
        {
            "name": "attach_media_to_product",
            "method_name": "attach_media_to_product",
            "description": "Attach existing media library items to a WooCommerce product. Use role='main' for the primary image (gallery index 0) or role='gallery' for extra images. mode='append' preserves the existing gallery; mode='replace' wipes and rewrites it.",
            "schema": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "integer", "minimum": 1},
                    "media_ids": {
                        "type": "array",
                        "items": {"type": "integer", "minimum": 1},
                        "minItems": 1,
                    },
                    "role": {"type": "string", "enum": ["main", "gallery"], "default": "gallery"},
                    "mode": {
                        "type": "string",
                        "enum": ["append", "replace"],
                        "default": "append",
                    },
                },
                "required": ["product_id", "media_ids"],
            },
            "scope": "write",
        },
        {
            "name": "upload_and_attach_to_product",
            "method_name": "upload_and_attach_to_product",
            "description": "Upload a single image (from base64 or URL) and attach it to a WooCommerce product in one call.",
            "schema": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "integer", "minimum": 1},
                    "source": {"type": "string", "enum": ["base64", "url"]},
                    "data": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Base64 payload (when source=base64)",
                    },
                    "url": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Public URL (when source=url)",
                    },
                    "filename": {"type": "string"},
                    "mime": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                    "alt_text": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                    "role": {"type": "string", "enum": ["main", "gallery"], "default": "gallery"},
                    "mode": {
                        "type": "string",
                        "enum": ["append", "replace"],
                        "default": "append",
                    },
                    "skip_optimize": {"type": "boolean", "default": False},
                },
                "required": ["product_id", "source", "filename"],
            },
            "scope": "write",
        },
        {
            "name": "set_featured_image",
            "method_name": "set_featured_image",
            "description": "Set a WordPress post's featured image to an existing media library item.",
            "schema": {
                "type": "object",
                "properties": {
                    "post_id": {"type": "integer", "minimum": 1},
                    "media_id": {"type": "integer", "minimum": 1},
                },
                "required": ["post_id", "media_id"],
            },
            "scope": "write",
        },
    ]


class MediaAttachHandler:
    """Media-to-product and media-to-post attachment helpers.

    F.X.fix-pass4 — Two clients, one purpose:

    * ``self.client`` authenticates WC REST (``/wc/v3/*``) — typically
      a Consumer Key / Secret pair on a WC site.
    * ``self.wp_media_client`` authenticates WP core REST
      (``/wp/v2/media``, ``/wp/v2/posts/{id}``) — must be a WP user +
      Application Password. WC keys do NOT work for /wp/v2/.

    Resolution logic at call time:

    * If a dedicated ``wp_media_client`` was passed in, use it for
      /wp/v2/* — this is the explicit "user configured WP App Password
      on a WC site" path.
    * Else, if ``self.client.username`` starts with ``ck_`` we know
      the primary is a WC-keys pair that cannot hit /wp/v2/* — surface
      the structured ``WP_CREDENTIALS_MISSING`` error so the user
      knows where to add credentials.
    * Else, fall back to ``self.client`` — for the legacy
      single-credential WC mode (Application Password only) and for
      tests instantiating the handler with a plain WordPressClient.
    """

    def __init__(
        self,
        client: WordPressClient,
        *,
        wp_media_client: WordPressClient | None = None,
    ):
        self.client = client
        self.wp_media_client = wp_media_client

    def _require_wp_media_client(self) -> WordPressClient | None:
        """Pick the right client for /wp/v2/* calls, or None if no
        viable credential set is available."""
        if self.wp_media_client is not None:
            return self.wp_media_client
        primary_user = getattr(self.client, "username", "") or ""
        if primary_user.startswith("ck_"):
            # Primary is a WC consumer key — won't authenticate WP REST.
            return None
        # Primary is an Application Password (WP plugin mode or
        # legacy single-credential WC mode) — same client works.
        return self.client

    @staticmethod
    def _wp_credentials_missing_error() -> str:
        """Standard error when wp_media_client is None on WC sites."""
        return json.dumps(
            {
                "error_code": "WP_CREDENTIALS_MISSING",
                "message": (
                    "This tool needs a WordPress Application Password to upload "
                    "media via /wp/v2/media. WooCommerce Consumer Key + Secret "
                    "do NOT authenticate the WP core REST API. Open the site in "
                    "the dashboard and fill 'WordPress Username' + 'WordPress "
                    "Application Password' under Connection Settings (advanced)."
                ),
                "remediation": {
                    "where": "Dashboard → site → Connection Settings",
                    "fields": ["wp_username", "wp_app_password"],
                    "wp_admin_path": "Users → Profile → Application Passwords",
                },
            },
            indent=2,
        )

    async def attach_media_to_product(
        self,
        product_id: int,
        media_ids: list[int],
        role: str = "gallery",
        mode: str = "append",
    ) -> str:
        try:
            if role not in ("main", "gallery"):
                raise UploadError("BAD_ROLE", f"role must be 'main' or 'gallery', got '{role}'.")
            if mode not in ("append", "replace"):
                raise UploadError("BAD_MODE", f"mode must be 'append' or 'replace', got '{mode}'.")

            # /wp/v2/media GET to validate media_ids needs WP creds.
            if self._require_wp_media_client() is None:
                return self._wp_credentials_missing_error()

            await self._validate_media_ids(media_ids)

            new_images = _merge_product_images(
                existing=await self._get_product_images(product_id),
                new_ids=media_ids,
                role=role,
                mode=mode,
            )
            updated = await self.client.put(
                f"products/{product_id}",
                json_data={"images": new_images},
                use_woocommerce=True,
            )
            return json.dumps(
                {
                    "product_id": product_id,
                    "images": [
                        {"id": i.get("id"), "src": i.get("src")} for i in updated.get("images", [])
                    ],
                    "message": f"Attached {len(media_ids)} media item(s) to product {product_id}.",
                },
                indent=2,
            )
        except UploadError as e:
            return json.dumps(e.to_dict(), indent=2)
        except Exception as e:
            return json.dumps(
                {"error_code": "INTERNAL", "message": f"Attach failed: {e}"}, indent=2
            )

    async def upload_and_attach_to_product(
        self,
        product_id: int,
        source: str,
        filename: str,
        data: str | None = None,
        url: str | None = None,
        mime: str | None = None,
        alt_text: str | None = None,
        role: str = "gallery",
        mode: str = "append",
        skip_optimize: bool = False,
    ) -> str:
        try:
            wp_client = self._require_wp_media_client()
            if wp_client is None:
                return self._wp_credentials_missing_error()
            if source == "base64":
                if not data:
                    raise UploadError("MISSING_FIELD", "source=base64 requires 'data'.")
                raw = _decode_base64(data)
                mime_hint = mime
            elif source == "url":
                if not url:
                    raise UploadError("MISSING_FIELD", "source=url requires 'url'.")
                ssrf = ssrf_check(url)
                if not ssrf.allowed:
                    raise UploadError("SSRF", ssrf.reason or "URL rejected.", {"url": url})
                raw, declared_ct, _ = await fetch_url_bytes(url, max_bytes=DEFAULT_MAX_BYTES)
                mime_hint = mime or declared_ct
            else:
                raise UploadError(
                    "BAD_SOURCE", f"source must be 'base64' or 'url', got '{source}'."
                )

            raw, mime_hint = _maybe_optimize(raw, mime_hint, skip=skip_optimize)
            media = await wp_raw_upload(wp_client, raw, filename=filename, mime_hint=mime_hint)
            if alt_text is not None:
                await wp_update_media_metadata(wp_client, media["id"], alt_text=alt_text)

            # Chain into attach
            attach_json = await self.attach_media_to_product(
                product_id=product_id, media_ids=[media["id"]], role=role, mode=mode
            )
            attach = json.loads(attach_json)
            return json.dumps(
                {
                    "media_id": media["id"],
                    "media_url": media.get("source_url"),
                    "product_id": product_id,
                    "attach_result": attach,
                },
                indent=2,
            )
        except UploadError as e:
            return json.dumps(e.to_dict(), indent=2)
        except Exception as e:
            return json.dumps(
                {"error_code": "INTERNAL", "message": f"Upload+attach failed: {e}"}, indent=2
            )

    async def set_featured_image(self, post_id: int, media_id: int) -> str:
        """Set the featured image of a WC product OR a WP post.

        F.X.fix-pass5 — auto-detect routing: WC products (CPT) are not
        addressable via ``/wp/v2/posts/{id}``; their featured image is
        the first entry of the ``images`` array on the WC product
        record. We try the WC ``products/{id}`` endpoint first because
        this tool is WC-namespaced; if that 404s we fall through to
        the legacy WP REST behaviour for regular posts/pages.
        """
        try:
            wp_client = self._require_wp_media_client()
            if wp_client is None:
                return self._wp_credentials_missing_error()
            await self._validate_media_ids([media_id])

            # 1. Try WC product first.
            wc_product: dict[str, Any] | None = None
            try:
                wc_product = await self.client.get(f"products/{post_id}", use_woocommerce=True)
            except Exception:
                wc_product = None

            if isinstance(wc_product, dict) and wc_product.get("id"):
                # Featured = images[0]; preserve gallery via the existing
                # role="main" mode="replace" merge logic.
                new_images = _merge_product_images(
                    existing=list(wc_product.get("images") or []),
                    new_ids=[media_id],
                    role="main",
                    mode="replace",
                )
                updated = await self.client.put(
                    f"products/{post_id}",
                    json_data={"images": new_images},
                    use_woocommerce=True,
                )
                featured_id = (updated.get("images") or [{}])[0].get("id", media_id)
                return json.dumps(
                    {
                        "post_id": post_id,
                        "featured_media": featured_id,
                        "context": "product",
                        "message": (
                            f"Set media {media_id} as featured image of WooCommerce "
                            f"product {post_id}."
                        ),
                    },
                    indent=2,
                )

            # 2. Fall back to WP REST for regular posts/pages.
            result = await wp_set_featured_media(wp_client, post_id, media_id)
            return json.dumps(
                {
                    "post_id": post_id,
                    "featured_media": result.get("featured_media", media_id),
                    "context": "post",
                    "message": f"Set media {media_id} as featured image of post {post_id}.",
                },
                indent=2,
            )
        except UploadError as e:
            return json.dumps(e.to_dict(), indent=2)
        except Exception as e:
            return json.dumps(
                {"error_code": "INTERNAL", "message": f"Set featured failed: {e}"}, indent=2
            )

    # --- internals ----------------------------------------------------------

    async def _get_product_images(self, product_id: int) -> list[dict[str, Any]]:
        product = await self.client.get(f"products/{product_id}", use_woocommerce=True)
        return list(product.get("images", []))

    async def _validate_media_ids(self, media_ids: list[int]) -> None:
        if not media_ids:
            raise UploadError("MISSING_FIELD", "media_ids must not be empty.")
        # /wp/v2/media GET — needs WP creds. Caller has already
        # validated wp_media_client is present.
        wp_client = self.wp_media_client or self.client
        for mid in media_ids:
            try:
                await wp_client.get(f"media/{mid}")
            except Exception as e:
                raise UploadError(
                    "MEDIA_NOT_FOUND",
                    f"Media id {mid} not found in the library.",
                    {"media_id": mid, "error": str(e)},
                ) from e


def _merge_product_images(
    existing: list[dict[str, Any]],
    new_ids: list[int],
    *,
    role: str,
    mode: str,
) -> list[dict[str, Any]]:
    """Pure function — easy to unit-test."""
    new_entries = [{"id": mid} for mid in new_ids]

    if mode == "replace":
        if role == "main":
            # First = main, rest = gallery
            return new_entries
        # role=gallery + mode=replace → keep existing main (index 0), replace the rest
        main = existing[:1]
        return main + new_entries

    # mode == "append"
    if role == "main":
        # New first image becomes main; existing main demoted into gallery
        return new_entries + existing
    # role=gallery + mode=append → keep existing, add new to the end (dedupe by id)
    seen_ids = {i.get("id") for i in existing if i.get("id") is not None}
    tail = [e for e in new_entries if e["id"] not in seen_ids]
    return existing + tail
