"""AI bank generation — the studio's optional bridge to a music generation server.

purrd stays model-free at runtime; the studio is the only place that asks for
AI-generated ambience, and only when ``PURRD_AI_URL`` points at a compatible
server (off by default). This module holds the style→tags map (purrd owns it,
it knows its styles) and the HTTP call to the server's /api/bank/generate,
which runs a text-to-music model such as ACE-Step, tracks the job, and drops
instrumental WAVs into the bank. Pure and testable — no GTK here.

Expected server API (JSON over HTTP):

- ``POST /api/bank/generate`` with ``{"tags", "label", "count"}`` -> ``{"id", "status", ...}``
- ``GET /api/jobs/<id>`` -> ``{"status", "output"}``
"""

from __future__ import annotations

import json
import os
import urllib.request
from typing import Any

from purrd.patterns import STYLE_NAMES

# ACE-Step tags per style. All instrumental, no vocals (waiting music). The
# user's prompt is appended on top for flavour. Every STYLE_NAMES entry must
# have one — the test enforces it.
STYLE_TAGS: dict[str, str] = {
    "classic": "lo-fi hip hop, mellow, warm, instrumental, no vocals",
    "chill": "chill, downtempo, warm pads, soft keys, instrumental, no vocals",
    "drive": "synthwave, steady pulse, night drive, instrumental, no vocals",
    "noir": "dark jazz, film noir, moody, instrumental, no vocals",
    "minimal": "minimal, sparse, meditative, instrumental, no vocals, no drums",
    "jazz": "smooth jazz, mellow, brushed drums, instrumental, no vocals",
    "ambient": "ambient, soft warm pads, meditative, instrumental, no vocals, no drums",
    "reggae": "reggae dub, offbeat skank, laid back, instrumental, no vocals",
    "trap": "lo-fi trap, mellow, hazy, instrumental, no vocals",
    "funky": "funky groove, warm bass, clav, instrumental, no vocals",
    "techno": "gentle techno, hypnotic, warm, instrumental, no vocals",
    "latin": "bossa nova, nylon guitar, warm, instrumental, no vocals",
    "triphop": "trip hop, downtempo, moody, instrumental, no vocals",
    "hardrock": "warm instrumental rock, clean guitars, mellow, instrumental, no vocals",
    "house": "deep house, warm chords, soft groove, instrumental, no vocals",
}


ENV_VAR = "PURRD_AI_URL"


def base_url() -> str | None:
    """Where the generation server listens (``PURRD_AI_URL``), or None when unset."""
    url = (os.environ.get(ENV_VAR) or "").strip().rstrip("/")
    return url or None


def enabled() -> bool:
    """AI generation is opt-in: on only when ``PURRD_AI_URL`` is set."""
    return base_url() is not None


def _require_url() -> str:
    url = base_url()
    if url is None:
        raise RuntimeError(f"AI generation is disabled: set {ENV_VAR} to a generation server URL")
    return url


def tags_for(style: str, prompt: str = "") -> str:
    """The ACE-Step tags for a style, with the user's prompt appended."""
    tags = STYLE_TAGS.get(style, "ambient, instrumental, no vocals")
    prompt = (prompt or "").strip()
    return f"{tags}, {prompt}" if prompt else tags


def _post(path: str, payload: dict, timeout: float = 30.0) -> dict:
    req = urllib.request.Request(
        _require_url() + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode() or "{}")


def request_generation(style: str, count: int, prompt: str = "") -> dict[str, Any]:
    """Ask the generation server to generate `count` instrumental tracks for `style` into the
    bank. Returns the job dict ({id, kind, status, project, ...}). Raises on a
    transport or HTTP error; the caller shows the message."""
    return _post(
        "/api/bank/generate", {"tags": tags_for(style, prompt), "label": style, "count": int(count)}
    )


def job_status(job_id: str, timeout: float = 10.0) -> dict[str, Any]:
    """Poll a job's state (status, output like "12/20")."""
    with urllib.request.urlopen(_require_url() + f"/api/jobs/{job_id}", timeout=timeout) as r:
        return json.loads(r.read().decode() or "{}")


def styles() -> tuple[str, ...]:
    """The styles offered for AI generation — purrd's own list."""
    return STYLE_NAMES
