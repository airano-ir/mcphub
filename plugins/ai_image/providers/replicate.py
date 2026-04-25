"""Replicate provider (Flux family + other image models).

Replicate runs predictions asynchronously: POST to ``/v1/predictions``
returns a job id, and we poll ``/v1/predictions/{id}`` until status is
``succeeded`` or ``failed``. The final output is a URL (or list of URLs)
that must be fetched to get bytes.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

from plugins.ai_image.providers.base import (
    BaseImageProvider,
    GenerationRequest,
    GenerationResult,
    ProviderError,
)

_logger = logging.getLogger("mcphub.ai_image.replicate")

_PREDICTIONS_URL = "https://api.replicate.com/v1/predictions"
_DEFAULT_MODEL = "black-forest-labs/flux-schnell"
_MAX_RETRIES = 3
_POLL_INTERVAL = 2.0
_POLL_TIMEOUT = 180
_REQUEST_TIMEOUT = 60
_RETRY_STATUS = {429, 500, 502, 503, 504}

_COST_TABLE: dict[str, float] = {
    "black-forest-labs/flux-schnell": 0.003,
    "black-forest-labs/flux-dev": 0.025,
    "black-forest-labs/flux-pro": 0.055,
}


def _aspect_from_size(size: str) -> str:
    """Replicate's Flux models accept an aspect_ratio enum, not WxH."""
    mapping = {
        "1024x1024": "1:1",
        "1344x768": "16:9",
        "768x1344": "9:16",
        "1152x896": "3:2",
        "896x1152": "2:3",
    }
    return mapping.get(size, "1:1")


class ReplicateProvider(BaseImageProvider):
    name = "replicate"

    async def generate(self, api_key: str, request: GenerationRequest) -> GenerationResult:
        if not api_key:
            raise ProviderError("PROVIDER_AUTH", "Replicate API token is missing.")

        model = request.model or _DEFAULT_MODEL
        payload: dict[str, Any] = {
            "model": model,
            "input": {
                "prompt": request.prompt,
                "aspect_ratio": _aspect_from_size(request.size),
                **(request.extras or {}),
            },
        }
        if request.negative_prompt:
            payload["input"]["negative_prompt"] = request.negative_prompt

        prediction = await self._create_prediction(api_key, payload)
        final = await self._poll_until_done(api_key, prediction)

        output = final.get("output")
        url = _first_url(output)
        if not url:
            raise ProviderError(
                "PROVIDER_BAD_RESPONSE",
                "Replicate prediction finished without an image URL.",
                {"prediction": final},
            )
        image_bytes = await _fetch_url(url)

        meta = {
            "model": model,
            "prediction_id": final.get("id"),
            "status": final.get("status"),
            "metrics": final.get("metrics", {}),
        }
        return GenerationResult(
            data=image_bytes,
            mime="image/webp" if url.endswith(".webp") else "image/png",
            filename=f"replicate-{model.split('/')[-1]}.png",
            meta=meta,
            cost_usd=_COST_TABLE.get(model),
        )

    async def _create_prediction(self, api_key: str, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Prefer": "wait=0",
        }
        delay = 1.0
        last_error = ""
        timeout = aiohttp.ClientTimeout(total=_REQUEST_TIMEOUT)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            for attempt in range(1, _MAX_RETRIES + 1):
                async with session.post(_PREDICTIONS_URL, json=payload, headers=headers) as resp:
                    if resp.status in (200, 201):
                        return await resp.json()
                    text = await resp.text()
                    last_error = text[:500]
                    if resp.status in (401, 403):
                        raise ProviderError(
                            "PROVIDER_AUTH",
                            f"Replicate rejected auth ({resp.status}).",
                            {"body": last_error},
                        )
                    if resp.status == 422:
                        raise ProviderError(
                            "PROVIDER_BAD_REQUEST",
                            f"Replicate rejected request: {last_error}",
                            {"body": last_error},
                        )
                    if resp.status in _RETRY_STATUS and attempt < _MAX_RETRIES:
                        _logger.warning("Replicate %d, retry %d", resp.status, attempt)
                        await asyncio.sleep(delay)
                        delay *= 2
                        continue
                    if resp.status == 429:
                        raise ProviderError(
                            "PROVIDER_QUOTA",
                            "Replicate rate-limit hit.",
                            {"status": 429, "body": last_error},
                        )
                    raise ProviderError(
                        "PROVIDER_UNAVAILABLE",
                        f"Replicate HTTP {resp.status}.",
                        {"status": resp.status, "body": last_error},
                    )
        raise ProviderError(
            "PROVIDER_UNAVAILABLE",
            f"Replicate create_prediction failed after retries: {last_error}",
        )

    async def _poll_until_done(self, api_key: str, prediction: dict[str, Any]) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {api_key}"}
        poll_url = (prediction.get("urls") or {}).get("get") or (
            f"{_PREDICTIONS_URL}/{prediction.get('id')}"
        )
        timeout = aiohttp.ClientTimeout(total=_REQUEST_TIMEOUT)
        deadline = asyncio.get_event_loop().time() + _POLL_TIMEOUT
        async with aiohttp.ClientSession(timeout=timeout) as session:
            while True:
                if asyncio.get_event_loop().time() > deadline:
                    raise ProviderError(
                        "PROVIDER_TIMEOUT",
                        "Replicate prediction did not finish within timeout.",
                        {"prediction_id": prediction.get("id")},
                    )
                async with session.get(poll_url, headers=headers) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        raise ProviderError(
                            "PROVIDER_UNAVAILABLE",
                            f"Replicate poll HTTP {resp.status}.",
                            {"body": text[:500]},
                        )
                    body = await resp.json()
                status = body.get("status")
                if status in ("succeeded",):
                    return body
                if status in ("failed", "canceled"):
                    raise ProviderError(
                        "PROVIDER_BAD_RESPONSE",
                        f"Replicate prediction {status}: {body.get('error')}",
                        {"prediction": body},
                    )
                await asyncio.sleep(_POLL_INTERVAL)


def _first_url(output: Any) -> str | None:
    if isinstance(output, str):
        return output
    if isinstance(output, list) and output:
        first = output[0]
        if isinstance(first, str):
            return first
    return None


async def _fetch_url(url: str) -> bytes:
    timeout = aiohttp.ClientTimeout(total=_REQUEST_TIMEOUT)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                raise ProviderError(
                    "PROVIDER_BAD_RESPONSE",
                    f"Failed to fetch Replicate output (HTTP {resp.status}).",
                    {"status": resp.status},
                )
            return await resp.read()
