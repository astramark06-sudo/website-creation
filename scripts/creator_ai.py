"""Opt-in, bounded local Ollama drafting of structured website specifications."""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request

try:
    from .creator_project import validate_spec, require_text, MAX_SPEC
except ImportError:
    from creator_project import validate_spec, require_text, MAX_SPEC

ENDPOINT = "http://127.0.0.1:11434"
MAX_RESPONSE = 512 * 1024
MODEL_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}\Z")
SYSTEM = (
    "Create an independently authored website draft from the user's requirements. "
    "Return only a JSON object with title, description, theme and pages. "
    "Theme must be teal, blue, plum, forest, terracotta or slate. Pages must contain 1 to 8 objects, "
    "each with slug, title, intro, sections and interaction. First slug is home. "
    "Slugs use lowercase ASCII letters, digits and hyphens. Sections contain "
    "heading and body strings, at least one per page, and optionally kind: card, article, callout, faq, list or steps. For list or steps use one item per line in body. Interaction is none or tasks. "
    "Use original plain text, never HTML, code, copied branding, credentials or claims "
    "of rights, approval or completed external actions. Avoid invented testimonials. "
    "Use tasks only for a browser-local task list; unsupported features need later work."
)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def valid_model(name):
    return isinstance(name, str) and MODEL_NAME.fullmatch(name) and "cloud" not in name.casefold()


def local_request(path, data=None):
    if path not in ("/api/tags", "/api/generate"):
        raise ValueError("Unexpected endpoint")
    # Disable system proxies and redirects; only the fixed loopback service is used.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    body = None if data is None else json.dumps(data).encode("utf-8")
    request = urllib.request.Request(ENDPOINT + path, data=body, headers={"Content-Type": "application/json"})
    try:
        with opener.open(request, timeout=120 if data else 5) as response:
            raw = response.read(MAX_RESPONSE + 1)
        if len(raw) > MAX_RESPONSE:
            raise ValueError("Local model response exceeds limit")
        return json.loads(raw.decode("utf-8"))
    except (OSError, urllib.error.URLError, ValueError) as exc:
        raise ValueError("Local Ollama unavailable or response invalid") from exc


def installed_model(model, transport=local_request):
    if not valid_model(model):
        raise ValueError("Use a configured local model name, not a cloud model")
    result = transport("/api/tags")
    if not isinstance(result, dict):
        raise ValueError("Invalid local model inventory")
    for item in result.get("models", []):
        if (isinstance(item, dict) and item.get("name") == model and
                isinstance(item.get("size"), int) and item["size"] > 0 and
                item.get("digest") and not item.get("remote_host") and
                not item.get("remote_model")):
            return
    raise ValueError("Configured local model is not installed; no model is downloaded automatically")


def generate_draft(prompt, model, transport=local_request):
    prompt = require_text(prompt, "Website requirements", 4000)
    installed_model(model, transport)
    response = transport("/api/generate", {
        "model": model, "system": SYSTEM, "prompt": prompt,
        "stream": False, "format": "json", "keep_alive": 0,
        "options": {"temperature": 0.4, "num_predict": 3000},
    })
    if not isinstance(response, dict) or response.get("done") is not True:
        raise ValueError("Incomplete local model response")
    content = response.get("response")
    if not isinstance(content, str) or len(content.encode("utf-8")) > MAX_SPEC:
        raise ValueError("Invalid draft response")
    draft = json.loads(content)
    if not isinstance(draft, dict) or set(draft) != {"title", "description", "theme", "pages"}:
        raise ValueError("Local model did not return the expected draft fields")
    draft["version"] = 1
    draft["review"] = {"content_rights_confirmed": False, "originality_reviewed": False, "publish_approved": False}
    validate_spec(draft)
    if len(draft["pages"]) > 8:
        raise ValueError("AI drafts support at most eight pages")
    return draft
