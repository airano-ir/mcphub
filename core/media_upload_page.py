"""Small same-origin browser client for an existing media upload session."""

from __future__ import annotations

import json

from starlette.requests import Request
from starlette.responses import HTMLResponse

_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; connect-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<meta name="referrer" content="no-referrer">
<title>MCPHub media upload</title>
<style>
body{font:16px system-ui,sans-serif;max-width:42rem;margin:3rem auto;padding:0 1rem;color:#17202a}
main{border:1px solid #ccd6dd;border-radius:12px;padding:1.5rem}button{padding:.6rem 1rem;cursor:pointer}
#drop{border:2px dashed #9aa9b2;border-radius:8px;padding:2rem;text-align:center;margin:1rem 0}
#drop.ready{border-color:#26734d;background:#f2fbf5}progress{width:100%;height:1.2rem;margin-top:1rem}
.small{color:#586773;font-size:.9rem;white-space:pre-wrap}#error{color:#a11}
</style>
</head>
<body><main>
<h1>Upload media</h1>
<p>Select the file for the upload session. The server validates size, MIME and content before WordPress intake.</p>
<div id="drop">Drop a file here or <input id="file" type="file"></div>
<button id="start" type="button" disabled>Upload</button>
<progress id="progress" value="0" max="1" hidden></progress>
<p id="status" class="small">Waiting for a file.</p><p id="error"></p>
<script>
(() => {
  "use strict";
  const uploadPath = __UPLOAD_PATH__;
  const token = new URLSearchParams(location.hash.slice(1)).get("token");
  history.replaceState(null, "", location.pathname);
  const input = document.getElementById("file");
  const drop = document.getElementById("drop");
  const button = document.getElementById("start");
  const progress = document.getElementById("progress");
  const status = document.getElementById("status");
  const error = document.getElementById("error");
  let selected = null;
  const chunkBytes = 1024 * 1024;
  if (!token) { error.textContent = "This upload link is missing its short-lived session token."; return; }
  function choose(file) { selected = file || null; button.disabled = !selected;
    status.textContent = selected ? `Selected ${selected.name} (${selected.size} bytes).` : "Waiting for a file."; }
  input.addEventListener("change", () => choose(input.files[0]));
  ["dragenter", "dragover"].forEach((event) => drop.addEventListener(event, (e) => { e.preventDefault(); drop.classList.add("ready"); }));
  ["dragleave", "drop"].forEach((event) => drop.addEventListener(event, (e) => { e.preventDefault(); drop.classList.remove("ready"); }));
  drop.addEventListener("drop", (e) => choose(e.dataTransfer.files[0]));
  async function digest(blob) { const bytes = await blob.arrayBuffer(); const hash = await crypto.subtle.digest("SHA-256", bytes); return [...new Uint8Array(hash)].map((b) => b.toString(16).padStart(2, "0")).join(""); }
  async function send(chunk, index) {
    const headers = {"Authorization": `Bearer ${token}`, "Content-Type": "application/octet-stream", "X-MCPHub-Chunk-Index": String(index), "X-MCPHub-Chunk-SHA256": await digest(chunk)};
    let last = "";
    for (let attempt = 0; attempt < 3; attempt++) {
      try { const response = await fetch(uploadPath, {method: "PUT", headers, body: chunk}); const body = await response.json();
        if (response.ok) return body; last = body.message || `HTTP ${response.status}`;
      } catch (e) { last = "Network error"; }
      await new Promise((resolve) => setTimeout(resolve, 500 * (attempt + 1)));
    }
    throw new Error(last || "Chunk upload failed");
  }
  button.addEventListener("click", async () => {
    if (!selected) return; button.disabled = true; input.disabled = true; progress.hidden = false; error.textContent = "";
    try { const count = Math.ceil(selected.size / chunkBytes); let result = null;
      for (let index = 0; index < count; index++) { const chunk = selected.slice(index * chunkBytes, (index + 1) * chunkBytes); result = await send(chunk, index); progress.value = (index + 1) / count; status.textContent = `Uploaded ${index + 1} of ${count} chunks.`; }
      status.textContent = result && result.ready_to_finish ? "Upload assembled. Return to chat and call the finish tool to run WordPress validation and intake." : "Upload finished; check the session status in chat.";
    } catch (e) { error.textContent = e instanceof Error ? e.message : "Upload failed."; button.disabled = false; input.disabled = false; }
  });
})();
</script></main></body></html>"""


def browser_upload_page(request: Request, *, upload_path: str | None = None) -> HTMLResponse:
    """Render a token-free page; the scoped token arrives only in the URL fragment."""
    if upload_path is None:
        upload_path = request.url.path.removesuffix("/browser")
    encoded_path = json.dumps(upload_path).replace("<", "\\u003c").replace(">", "\\u003e")
    body = _PAGE.replace("__UPLOAD_PATH__", encoded_path)
    return HTMLResponse(
        body,
        headers={
            "Cache-Control": "no-store",
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
        },
    )
