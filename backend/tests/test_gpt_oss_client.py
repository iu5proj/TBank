"""Tests for backend GPT-OSS client response parsing."""

from __future__ import annotations

import pytest

from app.config import settings
from app.services.gpt_oss_client import GptOssClientError, _load_prompt, _parse_json_object


def test_parse_json_object_accepts_fenced_json():
    assert _parse_json_object('```json\n{"ok": true}\n```') == {"ok": True}


def test_parse_json_object_extracts_json_from_runner_text():
    assert _parse_json_object('thinking...\n{"ok": true, "nested": {"n": 1}}\n') == {
        "ok": True,
        "nested": {"n": 1},
    }


def test_parse_json_object_rejects_non_object_json():
    with pytest.raises(ValueError):
        _parse_json_object("[1, 2, 3]")


def test_load_prompt_fails_for_unknown_configured_version(monkeypatch):
    monkeypatch.setattr(settings, "GPT_OSS_PROMPT_VERSION", "missing_prompt_version")

    with pytest.raises(GptOssClientError):
        _load_prompt()
