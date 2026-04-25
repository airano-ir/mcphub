"""OpenAI image-generation provider (DALL-E 3 + gpt-image-1).

DALL-E 3 returns a time-limited URL (~1h TTL). gpt-image-1 can return
``b64_json`` directly. In both cases we return the raw bytes immediately
to the caller so the 1h URL expiry is never a concern downstream.
"""

from __future__ import annotations

import asyncio
import base64
import logging
from typing import Any

import aiohttp

from plugins.ai_image.providers.base import (
    BaseImageProvider,
    GenerationRequest,
    GenerationResult,
    ProviderError,
)

_logger = logging.getLogger("mcphub.ai_image.openai")

_API_URL = "https://api.openai.com/v1/images/generations"
_DEFAULT_MODEL = "dall-e-3"
_RETRY_STATUS = {429, 500, 502, 503, 504}
_MAX_RETRIES = 3
_REQUEST_TIMEOUT = 90

# Rough per-image pricing (USD) for audit logging. These are documented
# public list prices at the time of writing and may drift — treat as
# ballpark for cost dashboards, not billing.
_COST_TABLE: dict[tuple[str, str, str], float] = {
    ("dall-e-3", "1024x1024", "standard"): 0.040,
    ("dall-e-3", "1024x1024", "hd"): 0.080,
    ("dall-e-3", "1792x1024", "standard"): 0.080,
    ("dall-e-3", "1024x1792", "standard"): 0.080,
    ("dall-e-3", "1792x1024", "hd"): 0.120,
    ("dall-e-3", "1024x1792", "hd"): 0.120,
    ("gpt-image-1", "1024x1024", "low"): 0.011,
    ("gpt-image-1", "1024x1024", "medium"): 0.042,
    ("gpt-image-1", "1024x1024", "high"): 0.167,
}


def _estimate_cost(model: str, size: str, quality: str) -> float | None:
    return _COST_TABLE.get((model, size, quality))


class OpenAIProvider(BaseImageProvider):
    name = "openai"

    async def generate(self, api_key: str, request: GenerationRequest) -> GenerationResult:
        if not api_key:
            raise ProviderError("PROVIDER_AUTH", "OpenAI API key is missing.")

        model = request.model or _DEFAULT_MODEL
        payload: dict[str, Any] = {
            "model": model,
            "prompt": request.prompt,
            "size": request.size,
            "n": 1,
        }
        if model == "dall-e-3":
            payload["quality"] = request.quality or "standard"
            payload["response_format"] = "url"
        else:
            payload["response_format"] = "b64_json"
            if request.quality:
                payload["quality"] = request.quality

        data, meta = await self._post_with_retry(api_key, payload)

        items = data.get("data") or []
        if not items:
            raise ProviderError("PROVIDER_BAD_RESPONSE", "OpenAI returned no images.")
        first = items[0]

        if first.get("b64_json"):
            image_bytes = base64.b64decode(first["b64_json"])
        elif first.get("url"):
            image_bytes = await _fetch_url(first["url"])
        else:
            raise ProviderError(
                "PROVIDER_BAD_RESPONSE",
                "OpenAI response contained no b64_json or url.",
            )

        meta = dict(meta)
        if first.get("revised_prompt"):
            meta["revised_prompt"] = first["revised_prompt"]
        meta["model"] = model
        meta["size"] = request.size

        return GenerationResult(
            data=image_bytes,
            mime="image/png",
            filename=f"openai-{model}.png",
            meta=meta,
            cost_usd=_estimate_cost(model, request.size, request.quality or "standard"),
        )

    async def _post_with_retry(
        self, api_key: str, payload: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        last_error: str = ""
        delay = 1.0
        timeout = aiohttp.ClientTimeout(total=_REQUEST_TIMEOUT)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            for attempt in range(1, _MAX_RETRIES + 1):
                try:
                    async with session.post(_API_URL, json=payload, headers=headers) as resp:
                        if resp.status == 200:
                            body = await resp.json()
                            return body, {"attempt": attempt, "status": 200}
                        text = await resp.text()
                        last_error = text[:500]
                        if resp.status == 401:
                            raise ProviderError(
                                "PROVIDER_AUTH",
                                "OpenAI rejected the API key (401).",
                                {"body": last_error},
                            )
                        if resp.status == 400:
                            raise ProviderError(
                                "PROVIDER_BAD_REQUEST",
                                f"OpenAI rejected request (400): {last_error}",
                                {"body": last_error},
                            )
                        if resp.status == 429 and attempt < _MAX_RETRIES:
                            _logger.warning("OpenAI 429, retry %d", attempt)
                            await asyncio.sleep(delay)
                            delay *= 2
                            continue
                        if resp.status in _RETRY_STATUS and attempt < _MAX_RETRIES:
                            _logger.warning("OpenAI %d, retry %d", resp.status, attempt)
                            await asyncio.sleep(delay)
                            delay *= 2
                            continue
                        if resp.status == 429:
                            raise ProviderError(
                                "PROVIDER_QUOTA",
                                "OpenAI quota/rate-limit hit after retries.",
                                {"status": 429, "body": last_error},
                            )
                        raise ProviderError(
                            "PROVIDER_UNAVAILABLE",
                            f"OpenAI upstream error HTTP {resp.status}.",
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
                        "OpenAI request timed out after retries.",
                    ) from exc
        raise ProviderError(
            "PROVIDER_UNAVAILABLE",
            f"OpenAI call failed after {_MAX_RETRIES} attempts: {last_error}",
        )


async def _fetch_url(url: str) -> bytes:
    """Fetch a DALL-E URL immediately. URLs expire in ~1h, so no caching."""
    timeout = aiohttp.ClientTimeout(total=_REQUEST_TIMEOUT)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                raise ProviderError(
                    "PROVIDER_BAD_RESPONSE",
                    f"Failed to fetch OpenAI image URL (HTTP {resp.status}).",
                    {"status": resp.status},
                )
            return await resp.read()
