"""Generic public OpenAI-compatible image provider.

A connection supplies an API type, base URL, key, and optional model.  The
The provider deliberately keeps contracts separate:
``openai_images`` uses /images/generations and /images/edits,
``openai_responses`` uses /responses with the image_generation tool, and
``openai_compatible`` uses /chat/completions with image modalities.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import os
import time
from typing import Any
from urllib.parse import urlparse

import aiohttp

from core import net_guard
from plugins.ai_image.providers.base import (
    BaseImageProvider,
    GenerationRequest,
    GenerationResult,
    ProviderError,
)

_CACHE_TTL = 3600
_TIMEOUT = 120
_RETRY_STATUS = {429, 500, 502, 503, 504}
_models_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}


class OpenAICompatibleProvider(BaseImageProvider):
    name = "openai_compatible"

    async def generate(self, api_key: str, request: GenerationRequest) -> GenerationResult:
        if not api_key:
            raise ProviderError("PROVIDER_AUTH", "OpenAI-compatible API key is missing.")
        config = request.extras or {}
        base_url = _base_url(config.get("base_url"))
        api_type = _api_type(config.get("api_type"))
        model = await self._resolve_model(api_key, base_url, request, config)
        if api_type == "openai_images":
            body = await self._images(api_key, base_url, model, request)
        elif api_type == "openai_responses":
            body = await self._responses(api_key, base_url, model, request)
        else:
            body = await self._chat(api_key, base_url, model, request)
        reference = _image_reference(body)
        data, mime = await _materialise(reference or "")
        if not data:
            raise ProviderError(
                "PROVIDER_BAD_RESPONSE", "Compatible provider returned no image data."
            )
        ext = {"image/jpeg": "jpg", "image/webp": "webp"}.get(mime, "png")
        return GenerationResult(
            data=data,
            mime=mime,
            filename=f"openai-compatible-{model.replace('/', '-')}.{ext}",
            meta={"model": model, "api_type": api_type, "usage": body.get("usage")},
        )

    async def list_models(
        self, api_key: str, base_url: str, *, force: bool = False
    ) -> list[dict[str, Any]]:
        base_url = _base_url(base_url)
        key = f"{base_url}:{hashlib.sha256(api_key.encode()).hexdigest()}"
        cached = _models_cache.get(key)
        if not force and cached and time.time() - cached[0] < _CACHE_TTL:
            return list(cached[1])
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        try:
            async with net_guard.guarded_session(
                timeout=aiohttp.ClientTimeout(total=_TIMEOUT)
            ) as session:
                async with session.get(f"{base_url}/models", headers=headers) as response:
                    if response.status == 401:
                        raise ProviderError(
                            "PROVIDER_AUTH", "Compatible provider rejected the API key."
                        )
                    if response.status != 200:
                        raise ProviderError(
                            "PROVIDER_UNAVAILABLE",
                            f"Compatible provider /models returned HTTP {response.status}.",
                        )
                    payload = await response.json()
        except ProviderError:
            raise
        except (aiohttp.ClientError, TimeoutError) as exc:
            raise ProviderError(
                "PROVIDER_TIMEOUT", "Compatible provider /models request failed."
            ) from exc
        rows = payload.get("data", []) if isinstance(payload, dict) else []
        models = sorted(
            (_normalise_model(row) for row in rows if isinstance(row, dict)),
            key=lambda item: item["id"],
        )
        _models_cache[key] = (time.time(), models)
        return models

    async def _resolve_model(
        self, api_key: str, base_url: str, request: GenerationRequest, config: dict[str, Any]
    ) -> str:
        chosen = request.model or config.get("model_id")
        if isinstance(chosen, str) and chosen.strip():
            chosen = chosen.strip()
            if not request.input_images:
                return chosen
            declared = config.get("model_capabilities")
            if isinstance(declared, dict):
                if _supports_edit(declared):
                    return chosen
                raise _edit_unsupported(chosen, declared)
            models = await self.list_models(api_key, base_url)
            model = next((item for item in models if item["id"] == chosen), None)
            if model is None or not _supports_edit(model):
                raise _edit_unsupported(chosen, model or {})
            return chosen
        models = await self.list_models(api_key, base_url)
        if request.input_images:
            image_models = [item["id"] for item in models if _supports_edit(item)]
            if not image_models:
                raise ProviderError(
                    "PROVIDER_EDIT_UNSUPPORTED",
                    "No compatible model declares both image input and image output.",
                    {
                        "provider": self.name,
                        "capability_required": ["supports_image_input", "supports_image_output"],
                    },
                )
            return image_models[0]
        image_models = [item["id"] for item in models if item["supports_image_output"]]
        if image_models:
            return image_models[0]
        if models:
            return models[0]["id"]
        raise ProviderError(
            "PROVIDER_MODEL_REQUIRED", "No model was returned by the compatible provider."
        )

    async def _images(
        self, key: str, base: str, model: str, request: GenerationRequest
    ) -> dict[str, Any]:
        endpoint = f"{base}/images/edits" if request.input_images else f"{base}/images/generations"
        if request.input_images:
            form = aiohttp.FormData()
            form.add_field("model", model)
            form.add_field("prompt", request.prompt)
            form.add_field("n", "1")
            if request.size:
                form.add_field("size", request.size)
            for index, image in enumerate(request.input_images):
                mime = (
                    request.input_image_mimes[index]
                    if index < len(request.input_image_mimes)
                    else "image/png"
                )
                form.add_field("image", image, filename=f"input-{index}.png", content_type=mime)
            return await self._request(key, endpoint, data=form)
        payload: dict[str, Any] = {"model": model, "prompt": request.prompt, "n": 1}
        if request.size:
            payload["size"] = request.size
        if request.quality:
            payload["quality"] = request.quality
        return await self._request(key, endpoint, json=payload)

    async def _chat(
        self, key: str, base: str, model: str, request: GenerationRequest
    ) -> dict[str, Any]:
        content: Any = request.prompt
        if request.input_images:
            parts: list[dict[str, Any]] = [{"type": "text", "text": request.prompt}]
            for index, image in enumerate(request.input_images):
                mime = (
                    request.input_image_mimes[index]
                    if index < len(request.input_image_mimes)
                    else "image/png"
                )
                parts.append(
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime};base64,{base64.b64encode(image).decode()}"
                        },
                    }
                )
            content = parts
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": content}],
            "modalities": ["image", "text"],
        }
        return await self._request(key, f"{base}/chat/completions", json=payload)

    async def _responses(
        self, key: str, base: str, model: str, request: GenerationRequest
    ) -> dict[str, Any]:
        content: list[dict[str, Any]] = [{"type": "input_text", "text": request.prompt}]
        for index, image in enumerate(request.input_images):
            mime = (
                request.input_image_mimes[index]
                if index < len(request.input_image_mimes)
                else "image/png"
            )
            content.append(
                {
                    "type": "input_image",
                    "image_url": f"data:{mime};base64,{base64.b64encode(image).decode()}",
                }
            )
        payload = {
            "model": model,
            "input": [{"role": "user", "content": content}],
            "tools": [{"type": "image_generation"}],
        }
        return await self._request(key, f"{base}/responses", json=payload)

    async def _request(self, key: str, endpoint: str, **kwargs: Any) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {key}"}
        delay = 1.0
        last = ""
        async with net_guard.guarded_session(
            timeout=aiohttp.ClientTimeout(total=_TIMEOUT)
        ) as session:
            for attempt in range(3):
                try:
                    async with session.post(endpoint, headers=headers, **kwargs) as response:
                        if response.status == 200:
                            body = await response.json()
                            if isinstance(body, dict):
                                return body
                            raise ProviderError(
                                "PROVIDER_BAD_RESPONSE", "Provider response was not an object."
                            )
                        last = (await response.text())[:500]
                        if response.status == 401:
                            raise ProviderError(
                                "PROVIDER_AUTH", "Compatible provider rejected the API key."
                            )
                        if response.status == 400:
                            raise ProviderError(
                                "PROVIDER_BAD_REQUEST",
                                "Compatible provider rejected the request.",
                                {"body": last},
                            )
                        if response.status not in _RETRY_STATUS or attempt == 2:
                            code = (
                                "PROVIDER_QUOTA"
                                if response.status == 429
                                else "PROVIDER_UNAVAILABLE"
                            )
                            raise ProviderError(
                                code, f"Compatible provider returned HTTP {response.status}."
                            )
                except ProviderError:
                    raise
                except (aiohttp.ClientError, TimeoutError) as exc:
                    if attempt == 2:
                        raise ProviderError(
                            "PROVIDER_TIMEOUT", "Compatible provider request failed."
                        ) from exc
                await asyncio.sleep(delay)
                delay *= 2
        raise ProviderError("PROVIDER_UNAVAILABLE", f"Compatible provider failed: {last}")


def _base_url(value: Any) -> str:
    result = str(value or "").strip().rstrip("/")
    parsed = urlparse(result)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ProviderError("PROVIDER_BAD_REQUEST", "base_url must be an absolute HTTP(S) URL.")
    return result


def _api_type(value: Any) -> str:
    value = str(value or "openai_compatible").strip().lower().replace("-", "_")
    aliases = {
        "openai_images": "openai_images",
        "images": "openai_images",
        "image": "openai_images",
        "chat": "openai_compatible",
        "chat_completions": "openai_compatible",
        "openai_compatible": "openai_compatible",
        "responses": "openai_responses",
        "response_api": "openai_responses",
        "openai_responses": "openai_responses",
    }
    if value not in aliases:
        raise ProviderError(
            "PROVIDER_BAD_REQUEST", "api_type must be OpenAI Compatible or OpenAI Images."
        )
    return aliases[value]


def _normalise_model(row: dict[str, Any]) -> dict[str, Any]:
    architecture = row.get("architecture") if isinstance(row.get("architecture"), dict) else {}
    inputs = _modalities(architecture, "input")
    outputs = _modalities(architecture, "output")
    declared_image_output = any("image" in item.lower() for item in outputs)
    text = " ".join(str(row.get(key) or "") for key in ("id", "name", "description")).lower()
    image_output = declared_image_output or any(
        marker in text for marker in ("image", "dall-e", "gpt-image", "imagen", "flux")
    )
    image_input = any("image" in item.lower() for item in inputs)
    return {
        "id": str(row.get("id") or ""),
        "name": str(row.get("name") or row.get("id") or ""),
        "description": str(row.get("description") or "")[:500],
        "owned_by": row.get("owned_by"),
        "input_modalities": inputs,
        "output_modalities": outputs,
        "supports_image_input": image_input,
        "supports_image_output": image_output,
        "supports_image_edit": image_input and declared_image_output,
    }


def _modalities(architecture: dict[str, Any], side: str) -> list[str]:
    values = architecture.get(f"{side}_modalities")
    if isinstance(values, list):
        return [str(value) for value in values if isinstance(value, str)]
    modality = architecture.get("modality")
    if isinstance(modality, str) and "->" in modality:
        part = modality.split("->", 1)[0 if side == "input" else 1]
        return [item.strip() for item in part.split("+") if item.strip()]
    return []


def _supports_edit(model: dict[str, Any]) -> bool:
    """Require the strictly declared image-edit capability."""
    return model.get("supports_image_edit") is True


def _edit_unsupported(model: str, capabilities: dict[str, Any]) -> ProviderError:
    observed = {
        key: capabilities[key]
        for key in ("supports_image_input", "supports_image_output", "supports_image_edit")
        if key in capabilities
    }
    return ProviderError(
        "PROVIDER_EDIT_UNSUPPORTED",
        f"Model '{model}' does not have verified image-edit capabilities.",
        {
            "provider": "openai_compatible",
            "model": model,
            "capabilities": observed,
            "required": ["supports_image_input", "supports_image_output", "supports_image_edit"],
        },
    )


def _image_reference(body: dict[str, Any]) -> str | None:
    for item in body.get("data", []) or []:
        if isinstance(item, dict):
            if isinstance(item.get("b64_json"), str):
                return f"data:image/png;base64,{item['b64_json']}"
            if isinstance(item.get("url"), str):
                return item["url"]
    choices = body.get("choices", []) or []
    message = choices[0].get("message", {}) if choices and isinstance(choices[0], dict) else {}
    for item in message.get("images", []) or []:
        if isinstance(item, dict):
            image_url = item.get("image_url")
            if isinstance(image_url, dict) and isinstance(image_url.get("url"), str):
                return image_url["url"]
            if isinstance(image_url, str):
                return image_url
    for item in body.get("output", []) or []:
        if isinstance(item, dict) and item.get("type") == "image_generation_call":
            if isinstance(item.get("result"), str):
                return f"data:image/png;base64,{item['result']}"
    return None


async def _materialise(reference: str) -> tuple[bytes, str]:
    if reference.startswith("data:"):
        try:
            header, encoded = reference.split(",", 1)
            mime = header[5:].split(";", 1)[0] or "image/png"
            return base64.b64decode(encoded), mime
        except (ValueError, base64.binascii.Error):
            return b"", ""
    if reference.startswith(("http://", "https://")):
        from plugins.wordpress.handlers._media_security import ssrf_check

        if not ssrf_check(
            reference,
            allow_http=os.getenv("ALLOW_HTTP_PROVIDER_URLS", "false").lower() == "true",
        ).allowed:
            return b"", ""
        async with net_guard.guarded_session(
            timeout=aiohttp.ClientTimeout(total=_TIMEOUT)
        ) as session:
            async with session.get(reference) as response:
                if response.status != 200:
                    return b"", ""
                return (
                    await response.read(),
                    response.headers.get("Content-Type", "image/png").split(";", 1)[0],
                )
    return b"", ""


# Compatibility aliases used by focused tests and integrations.
normalise_model = _normalise_model
