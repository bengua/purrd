"""The studio's AI-bank bridge: tags per style and the generation request. No GTK,
no network (urlopen is faked)."""

from __future__ import annotations

import io
import json

import pytest

from purrd.patterns import STYLE_NAMES
from purrd.studio import ai_bank


def test_every_style_has_instrumental_tags():
    for style in STYLE_NAMES:
        tags = ai_bank.tags_for(style)
        assert style in ai_bank.STYLE_TAGS, f"{style} has no tags"
        assert "instrumental" in tags and "no vocals" in tags


def test_prompt_is_appended():
    t = ai_bank.tags_for("ambient", "rainy night, analog warmth")
    assert t.startswith(ai_bank.STYLE_TAGS["ambient"])
    assert t.endswith("rainy night, analog warmth")
    # No prompt: tags unchanged, no trailing comma.
    assert ai_bank.tags_for("ambient") == ai_bank.STYLE_TAGS["ambient"]


def test_disabled_by_default(monkeypatch):
    monkeypatch.delenv("PURRD_AI_URL", raising=False)
    assert ai_bank.base_url() is None
    assert not ai_bank.enabled()
    with pytest.raises(RuntimeError, match="PURRD_AI_URL"):
        ai_bank.request_generation("ambient", 1)


def test_base_url_honours_env(monkeypatch):
    monkeypatch.setenv("PURRD_AI_URL", "http://localhost:8420/")
    assert ai_bank.base_url() == "http://localhost:8420"
    assert ai_bank.enabled()


def test_request_generation_posts_the_right_payload(monkeypatch):
    seen = {}

    def fake_urlopen(req, timeout=None):
        seen["url"] = req.full_url
        seen["method"] = req.get_method()
        seen["body"] = json.loads(req.data.decode())
        return io.BytesIO(json.dumps({"id": "abc", "kind": "bank", "status": "running"}).encode())

    monkeypatch.setenv("PURRD_AI_URL", "http://localhost:8420")
    monkeypatch.setattr(ai_bank.urllib.request, "urlopen", fake_urlopen)
    job = ai_bank.request_generation("ambient", 20, "warm")
    assert job["id"] == "abc" and job["kind"] == "bank"
    assert seen["url"] == "http://localhost:8420/api/bank/generate"
    assert seen["method"] == "POST"
    assert seen["body"] == {
        "tags": ai_bank.tags_for("ambient", "warm"),
        "label": "ambient",
        "count": 20,
    }


def test_styles_are_purrd_styles():
    assert ai_bank.styles() == STYLE_NAMES
