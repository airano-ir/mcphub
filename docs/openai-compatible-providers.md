# OpenAI-compatible provider connections

WordPress and WooCommerce site owners can add one or more connections from the
site's **Tools → Add OpenAI Compatible** card. A connection stores:

- a user-facing name;
- **API Type**;
- **Base URL**;
- an encrypted **API Key**;
- an optional pinned **Model ID**.

API keys are encrypted with a per-site/per-connection scope. List responses
never contain plaintext keys or ciphertext. Base URLs are checked by the
existing SSRF guard; private, loopback, link-local, reserved, multicast, and
metadata destinations are rejected. HTTP is disabled unless
`ALLOW_HTTP_PROVIDER_URLS=true` is explicitly set for local development.

## API types

### Chat Completions (OpenAI-compatible)

Uses:

```text
POST {base_url}/chat/completions
```

The request asks for `modalities: ["image", "text"]`. Image edits include
base64 `input_image` content parts.

### OpenAI Images

Uses the independent Image API contracts:

```text
POST {base_url}/images/generations
POST {base_url}/images/edits
```

Generation sends JSON. An input image sends multipart form data to `/images/edits`.

### OpenAI Responses

Uses the independent Responses contract:

```text
POST {base_url}/responses
```

The request includes the `image_generation` tool. Input images are represented
as Responses `input_image` content parts. Responses image-generation calls are
decoded from `output[].type == "image_generation_call"`.

Video and other media contracts remain separate from image generation. This
provider does not route video requests through `/images/*`.

## Model import and selection

After a connection is saved, MCP Hub calls:

```text
GET {base_url}/models
Authorization: Bearer {api_key}
```

The OpenAI-compatible `{object: "list", data: [...]}` response is normalized
and cached per Base URL plus an API-key hash. Every returned model is imported
and shown in the selector. Advertised image capabilities are retained as
metadata and shown beside capable models; providers that omit capability
metadata are not silently discarded.

The selected Model ID is used for image generation. If no Model ID is pinned,
the provider prefers an imported image-capable model and otherwise uses the
first imported model.

## Dashboard endpoints

The dashboard uses these authenticated routes:

- `GET /api/sites/{site_id}/ai-providers`
- `POST /api/sites/{site_id}/ai-providers`
- `DELETE /api/sites/{site_id}/ai-providers/{config_id}`
- `GET /api/sites/{site_id}/ai-providers/{config_id}/models`
- `PATCH /api/sites/{site_id}/ai-providers/{config_id}/model`

The MCP image tools accept `provider="openai_compatible"` and the selected
`connection_id`. Existing OpenAI, Stability, Replicate, and legacy OpenRouter
configurations remain backward compatible.

## FastMCP dependency alignment

`requirements.txt`, `pyproject.toml`, and `uv.lock` are aligned on FastMCP
3.x. Dashboard custom routes are registered before `mcp.http_app()` is
materialized, which keeps the route table consistent with FastMCP 3.x.

The internal companion ZIP and the WordPress.org ZIP are not modified for this
server-side capability.
