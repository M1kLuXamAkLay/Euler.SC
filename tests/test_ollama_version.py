"""Ollama version gate in front of model downloads."""
from __future__ import annotations

import urllib.error

import pytest

from euler.core import llm


def test_parse_version_reads_leading_triplet() -> None:
    assert llm.parse_version("0.19.0") == (0, 19, 0)
    assert llm.parse_version("0.20.0-rc1") == (0, 20, 0)
    assert llm.parse_version("") is None
    assert llm.parse_version("unknown") is None


def test_gemma_rejected_below_minimum(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm, "installed_version", lambda: (0, 19, 0))
    with pytest.raises(llm.OllamaError) as caught:
        llm.ensure_version("gemma4:e4b")
    assert str(caught.value) == "ExprError.ollama_too_old:0.19.0:0.20.0"


def test_qwen_accepted_at_minimum(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm, "installed_version", lambda: (0, 17, 5))
    llm.ensure_version("qwen3.5:4b")


def test_unknown_family_is_not_checked(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail() -> None:
        raise AssertionError("version must not be queried for an unlisted family")
    monkeypatch.setattr(llm, "installed_version", fail)
    llm.ensure_version("qwen2.5:0.5b")


def test_unreachable_service_is_left_to_the_download(monkeypatch: pytest.MonkeyPatch) -> None:
    def down(*_args, **_kwargs):
        raise urllib.error.URLError("refused")
    monkeypatch.setattr(llm, "_get", down)
    llm.ensure_version("gemma4:e4b")


def test_pull_412_becomes_version_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm, "installed_version", lambda: (0, 19, 0))

    def refuse(*_args, **_kwargs):
        raise urllib.error.HTTPError("http://x", 412, "Precondition Failed", None, None)
    monkeypatch.setattr(llm, "_pull_once", refuse)
    monkeypatch.setattr(llm, "ensure_version", lambda _name: None)
    with pytest.raises(llm.OllamaError) as caught:
        llm.pull("gemma4:e4b")
    assert str(caught.value) == "ExprError.ollama_too_old:0.19.0:0.20.0"
