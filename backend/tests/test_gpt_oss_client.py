"""Tests for backend GPT-OSS client response parsing."""

from __future__ import annotations

import pytest

from app.services.gpt_oss_client import _parse_json_object


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
