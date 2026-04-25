"""OpenRouter image-generation provider.

OpenRouter is an aggregator that routes requests to many model vendors.
For image generation, the usable path is their chat-completions endpoint
with ``modalities=["image","text"]`` — models like
``google/gemini-2.5-flash-image`` (a.k.a. "Nano Banana") return the
generated image as a ``data:``-prefixed base64 URL inside the message
``images`` array; other models may return ``image_url``-style pointers.

Why this provider is worth adding:

* Unlocks Gemini image models without needing a Google Cloud project.
* Lets users concentrate AI spend on a single OpenRouter key rather
  than managing separate OpenAI / Stability / Replicate accounts.
* Supported models (as of F.X.fix 2026-04-18):
    - ``google/gemini-2.5-flash-image`` (default, GA)
    - ``google/gemini-2.5-flash-image-preview`` (DEPRECATED; 404 on
      fresh OpenRouter accounts — kept as a recognised alias so we can
      emit ``PROVIDER_MODEL_DEPRECATED`` with a clear hint)
    - Any other OpenRouter model that returns image parts in
      ``message.images[]`` — the parser is tolerant of newer entries.

The default model is picked to cover the most common use case (hero
images for WordPress / WooCommerce posts); callers can override via
``GenerationRequest.model``.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import os
import time
from typing import Any

import aiohttp

from plugins.ai_image.providers.base import (
    BaseImageProvider,
    GenerationRequest,
    GenerationResult,
    ProviderError,
)

_logger = logging.getLogger("mcphub.ai_image.openrouter")

_API_URL = "https://openrouter.ai/api/v1/chat/completions"
_MODELS_URL = "https://openrouter.ai/api/v1/models"
# GA endpoint. The preview alias (...-image-preview) was deprecated after
# Google promoted the model to GA — new OpenRouter accounts get 404 on
# the preview ID.
_DEFAULT_MODEL = "google/gemini-2.5-flash-image"
_DEPRECATED_MODELS: dict[str, str] = {
    "google/gemini-2.5-flash-image-preview": "google/gemini-2.5-flash-image",
}
_RETRY_STATUS = {429, 500, 502, 503, 504}
_MAX_RETRIES = 3
_REQUEST_TIMEOUT = 120

# USD-per-image price table. Figures are conservative upper bounds from
# public OpenRouter pricing (2026-04); operators who negotiate custom
# rates can override via ``OPENROUTER_PRICING_OVERRIDE`` (JSON map of
# model_id -> price USD).
_MODEL_PRICING: dict[str, float] = {
    "google/gemini-2.5-flash-image": 0.00039,
    "google/gemini-2.5-flash-image-preview": 0.00039,
    "google/imagen-3.0-generate": 0.04,
    "google/imagen-3.0-fast": 0.02,
    "openai/dall-e-3": 0.04,
    "openai/dall-e-3-hd": 0.08,
    "openai/gpt-image-1": 0.017,
    "black-forest-labs/flux-1.1-pro": 0.04,
    "black-forest-labs/flux-pro": 0.055,
    "black-forest-labs/flux-schnell": 0.003,
    "stability-ai/stable-diffusion-3.5-large": 0.065,
}


def _pricing_table() -> dict[str, float]:
    """Return the effective price table, merging env override if present."""
    import json as _json

    override = os.environ.get("OPENROUTER_PRICING_OVERRIDE", "").strip()
    if not override:
        return _MODEL_PRICING
    try:
        parsed = _json.loads(override)
    except Exception as exc:  # noqa: BLE001
        _logger.warning("OPENROUTER_PRICING_OVERRIDE is not valid JSON: %s", exc)
        return _MODEL_PRICING
    if not isinstance(parsed, dict):
        return _MODEL_PRICING
    merged = dict(_MODEL_PRICING)
    for k, v in parsed.items():
        try:
            merged[str(k)] = float(v)
        except (TypeError, ValueError):
            continue
    return merged


def _cost_for(model: str) -> float | None:
    """Return USD cost for a known model, else None (logs at debug)."""
    price = _pricing_table().get(model)
    if price is None:
        _logger.debug("openrouter: no pricing entry for model %r", model)
    return price


# Module-level cache for list_image_models() — 1h TTL is plenty; model
# catalog drift is measured in days, not minutes.
_MODELS_CACHE_TTL_SECONDS = 3600
_models_cache: dict[str, Any] = {"fetched_at": 0.0, "payload": None}


class OpenRouterProvider(BaseImageProvider):
    name = "openrouter"

    async def generate(self, api_key: str, request: GenerationRequest) -> GenerationResult:
        if not api_key:
            raise ProviderError("PROVIDER_AUTH", "OpenRouter API key is missing.")

        requested_model = request.model or _DEFAULT_MODEL
        replacement = _DEPRECATED_MODELS.get(requested_model)
        if replacement is not None:
            raise ProviderError(
                "PROVIDER_MODEL_DEPRECATED",
                (
                    f"OpenRouter model '{requested_model}' is deprecated. "
                    f"Use '{replacement}' instead."
                ),
                {"requested_model": requested_model, "replacement_model": replacement},
            )
        model = requested_model

        # Chat-completions shape with image modality declared. The
        # prompt is sent as the single user message; size hints are
        # advisory — Gemini picks an output size internally.
        user_content: str = request.prompt
        if request.negative_prompt:
            user_content = f"{user_content}\n\nAvoid: {request.negative_prompt}"

        payload: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": user_content}],
            "modalities": ["image", "text"],
        }

        body = await self._post_with_retry(api_key, payload)

        image_url = _extract_image_url(body)
        if not image_url:
            raise ProviderError(
                "PROVIDER_BAD_RESPONSE",
                "OpenRouter response contained no image data. Is the "
                f"model '{model}' configured for image output?",
                {"model": model},
            )

        image_bytes, mime = await _materialise_image(image_url)
        if not image_bytes:
            raise ProviderError(
                "PROVIDER_BAD_RESPONSE",
                "OpenRouter image URL could not be fetched / decoded.",
                {"model": model},
            )

        # Derive a useful filename suffix from the mime type.
        ext = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}.get(mime, "png")
        meta: dict[str, Any] = {"model": model, "size": request.size}
        # Attach OpenRouter usage if present so audit logs can correlate.
        usage = body.get("usage") or {}
        if isinstance(usage, dict):
            for k in ("prompt_tokens", "completion_tokens", "total_tokens"):
                if k in usage:
                    meta[k] = usage[k]

        return GenerationResult(
            data=image_bytes,
            mime=mime,
            filename=f"openrouter-{model.replace('/', '-')}.{ext}",
            meta=meta,
            cost_usd=_cost_for(model),
        )

    async def _post_with_retry(self, api_key: str, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            # OpenRouter recommends identifying the calling app for
            # observability. Using a stable string so admins can spot
            # traffic from MCPHub in their OpenRouter dashboard.
            "HTTP-Referer": "https://github.com/airano-ir/mcphub",
            "X-Title": "MCPHub",
        }
        last_error: str = ""
        delay = 1.0
        timeout = aiohttp.ClientTimeout(total=_REQUEST_TIMEOUT)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            for attempt in range(1, _MAX_RETRIES + 1):
                try:
                    async with session.post(_API_URL, json=payload, headers=headers) as resp:
                        if resp.status == 200:
                            return await resp.json()
                        text = await resp.text()
                        last_error = text[:500]
                        if resp.status == 401:
                            raise ProviderError(
                                "PROVIDER_AUTH",
                                "OpenRouter rejected the API key (401).",
                                {"body": last_error},
                            )
                        if resp.status == 400:
                            raise ProviderError(
                                "PROVIDER_BAD_REQUEST",
                                f"OpenRouter rejected request (400): {last_error}",
                                {"body": last_error},
                            )
                        if resp.status in _RETRY_STATUS and attempt < _MAX_RETRIES:
                            _logger.warning(
                                "OpenRouter %d, retry %d/%d", resp.status, attempt, _MAX_RETRIES
                            )
                            await asyncio.sleep(delay)
                            delay *= 2
                            continue
                        if resp.status == 429:
                            raise ProviderError(
                                "PROVIDER_QUOTA",
                                "OpenRouter quota/rate-limit hit after retries.",
                                {"status": 429, "body": last_error},
                            )
                        raise ProviderError(
                            "PROVIDER_UNAVAILABLE",
                            f"OpenRouter upstream error HTTP {resp.status}.",
                            {"status": resp.status, "body": last_error},
                        )
                except TimeoutError as exc:
                    last_error = f"timeout: {exc}"
                    if attempt < _MAX_RETRIES:
                        await asyncio.sleep(delay)
                        delay *= 2
                        continue
                    raise ProviderError(
                        "PROVIDER_TIMEOUT",
                        "OpenRouter request timed out after retries.",
                    ) from exc
        raise ProviderError(
            "PROVIDER_UNAVAILABLE",
            f"OpenRouter call failed after {_MAX_RETRIES} attempts: {last_error}",
        )

    async def list_image_models(
        self, api_key: str | None = None, *, force: bool = False
    ) -> list[dict[str, Any]]:
        """Return OpenRouter catalog entries whose modality includes image.

        The catalog drifts slowly (days) so we cache the whole filtered
        list at module scope for 1h. ``api_key`` is optional — the
        ``/v1/models`` endpoint is public, but authenticated callers see
        per-account availability flags. On any upstream error the
        previous cache (if any) is returned; otherwise an empty list.
        """
        now = time.time()
        payload = _models_cache.get("payload")
        fetched_at = _models_cache.get("fetched_at", 0.0)
        if not force and payload is not None and (now - fetched_at) < _MODELS_CACHE_TTL_SECONDS:
            return list(payload)

        headers = {
            "HTTP-Referer": "https://github.com/airano-ir/mcphub",
            "X-Title": "MCPHub",
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        timeout = aiohttp.ClientTimeout(total=_REQUEST_TIMEOUT)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(_MODELS_URL, headers=headers) as resp:
                    if resp.status != 200:
                        _logger.warning("openrouter /v1/models HTTP %s", resp.status)
                        return list(payload or [])
                    body = await resp.json()
        except Exception as exc:  # noqa: BLE001
            _logger.warning("openrouter /v1/models fetch failed: %s", exc)
            return list(payload or [])

        raw_models = body.get("data") or []
        pricing = _pricing_table()
        filtered: list[dict[str, Any]] = []
        for item in raw_models:
            if not isinstance(item, dict):
                continue
            if not _model_is_image(item):
                continue
            model_id = str(item.get("id") or "")
            if not model_id or model_id in _DEPRECATED_MODELS:
                continue
            filtered.append(
                {
                    "id": model_id,
                    "name": item.get("name") or model_id,
                    "description": (item.get("description") or "")[:400],
                    "context_length": item.get("context_length"),
                    "input_modalities": _modalities_of(item, "input"),
                    "output_modalities": _modalities_of(item, "output"),
                    "price_per_image_usd": pricing.get(model_id),
                }
            )

        filtered.sort(key=lambda m: m["id"])
        _models_cache["fetched_at"] = now
        _models_cache["payload"] = filtered
        return list(filtered)


def _modalities_of(item: dict[str, Any], side: str) -> list[str]:
    """Extract input/output modality list from an OpenRouter model entry."""
    arch = item.get("architecture") or {}
    if isinstance(arch, dict):
        key = "input_modalities" if side == "input" else "output_modalities"
        mods = arch.get(key)
        if isinstance(mods, list):
            return [str(m) for m in mods if isinstance(m, str)]
        modality = arch.get("modality")
        if isinstance(modality, str):
            parts = modality.split("->")
            if len(parts) == 2:
                idx = 0 if side == "input" else 1
                return [p.strip() for p in parts[idx].split("+") if p.strip()]
    return []


def _model_is_image(item: dict[str, Any]) -> bool:
    """True when an OpenRouter model entry emits image output."""
    out = _modalities_of(item, "output")
    if any("image" in m.lower() for m in out):
        return True
    # Legacy catalog rows without structured modalities — fall back to a
    # name/description heuristic so we don't silently drop valid models.
    blob = " ".join(str(item.get(k, "") or "") for k in ("id", "name", "description")).lower()
    return "image" in blob and "gen" in blob


def _extract_image_url(body: dict[str, Any]) -> str | None:
    """Pull the first image URL out of an OpenRouter chat response.

    The wire format varies by model vendor. We recognise:

      * ``choices[0].message.images[i].image_url.url`` — a string that
        may be a ``data:image/...;base64,...`` URL or an https URL.
      * ``choices[0].message.content`` when it is a list of parts, each
        of shape ``{type: "image_url", image_url: {url: ...}}`` —
        OpenAI-compatible multimodal reply shape.

    Returns None if no usable reference was found.
    """
    choices = body.get("choices") or []
    if not isinstance(choices, list) or not choices:
        return None
    message = (choices[0] or {}).get("message") or {}

    # Shape 1: message.images (Gemini via OpenRouter).
    for entry in message.get("images") or []:
        url = _image_url_from_entry(entry)
        if url:
            return url

    # Shape 2: message.content as list of parts.
    content = message.get("content")
    if isinstance(content, list):
        for part in content:
            if not isinstance(part, dict):
                continue
            if part.get("type") == "image_url":
                url = _image_url_from_entry(part)
                if url:
                    return url

    return None


def _image_url_from_entry(entry: Any) -> str | None:
    """Handle both ``{image_url: {url: ...}}`` and ``{image_url: "..."}``."""
    if not isinstance(entry, dict):
        return None
    iu = entry.get("image_url")
    if isinstance(iu, str):
        return iu
    if isinstance(iu, dict):
        u = iu.get("url")
        return u if isinstance(u, str) else None
    # Some providers emit a bare "url" key.
    u = entry.get("url")
    return u if isinstance(u, str) else None


async def _materialise_image(url: str) -> tuple[bytes, str]:
    """Turn an image URL (data: or https) into raw bytes + MIME.

    Returns ``(b"", "")`` on any failure so the caller can emit a
    uniform ``PROVIDER_BAD_RESPONSE`` error.
    """
    if url.startswith("data:"):
        try:
            header, payload = url.split(",", 1)
        except ValueError:
            return b"", ""
        mime = "image/png"
        rest = header[len("data:") :] if header.startswith("data:") else header
        if ";" in rest:
            mime = rest.split(";", 1)[0] or mime
        elif rest:
            mime = rest
        if "base64" in header:
            try:
                return base64.b64decode(payload), mime
            except Exception:
                return b"", mime
        return payload.encode("latin-1", errors="ignore"), mime

    if url.startswith("http://") or url.startswith("https://"):
        timeout = aiohttp.ClientTimeout(total=_REQUEST_TIMEOUT)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return b"", ""
                mime = resp.headers.get("Content-Type", "image/png").split(";", 1)[0].strip()
                return await resp.read(), mime or "image/png"

    return b"", ""


# ---------------------------------------------------------------------------
# Starlette handler — GET /api/providers/openrouter/models
# ---------------------------------------------------------------------------


async def api_openrouter_models(request: Any) -> Any:
    """Return the cached OpenRouter image-model catalog.

    Auth: same OAuth user session guard as the other /api/ endpoints.
    Query params:
      * ``force=1`` — bypass the 1h module cache.
      * ``site_id=<uuid>`` — if present, the user's OpenRouter key for
        that site is used as bearer so availability flags reflect the
        operator's account; otherwise the endpoint is fetched unauthed.
    """
    from starlette.responses import JSONResponse

    from core.dashboard.routes import _require_user_session

    user_session, redirect = _require_user_session(request)
    if redirect or user_session is None:
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)

    force = request.query_params.get("force") in {"1", "true", "True"}
    api_key: str | None = None
    site_id = (request.query_params.get("site_id") or "").strip()
    if site_id:
        try:
            from core.database import get_database
            from core.site_api import get_site_provider_key

            db = get_database()
            site = await db.get_site(site_id, user_session["user_id"])
            if site is not None:
                api_key = await get_site_provider_key(site_id, "openrouter")
        except Exception as exc:  # noqa: BLE001
            _logger.debug("openrouter models: site key lookup skipped: %s", exc)

    provider = OpenRouterProvider()
    models = await provider.list_image_models(api_key=api_key, force=force)
    return JSONResponse({"ok": True, "provider": "openrouter", "models": models})
