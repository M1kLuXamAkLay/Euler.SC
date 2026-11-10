"""Model catalogue invariants and the per-family request flags."""
from __future__ import annotations

import re
from pathlib import Path

from euler.core import hardware, llm

ROOT = Path(__file__).resolve().parent.parent


def _hw(ram: float, vram: float | None = None) -> hardware.Hardware:
    return hardware.Hardware(total_ram_gb=ram, vram_gb=vram, cpu_cores=8,
                             cpu_name="cpu", os_name="os", arch="x86_64")


def test_catalogue_is_third_generation_plus_two_light_fallbacks() -> None:
    names = [spec.name for spec in hardware.CATALOG]
    legacy = [name for name in names if name.startswith("qwen2.5")]
    assert legacy == ["qwen2.5:1.5b", "qwen2.5:0.5b"]
    assert {"gemma4:e4b", "gemma4:26b"} <= set(names)
    assert not any(name.startswith(("llava", "qwen2-vl")) for name in names)


def test_catalogue_is_ordered_largest_first() -> None:
    budgets = [spec.ram_gb for spec in hardware.CATALOG]
    assert budgets == sorted(budgets, reverse=True)


def test_vision_flag_agrees_with_family_check() -> None:
    for spec in hardware.CATALOG:
        assert spec.vision == hardware.supports_vision(spec.name), spec.name


def test_default_model_is_in_catalogue() -> None:
    assert hardware.spec_for(hardware.DEFAULT_MODEL) is not None


def test_pick_follows_memory() -> None:
    assert hardware.pick(_hw(4))[0].name == "qwen2.5:0.5b"
    assert hardware.pick(_hw(8))[0].name == "qwen3.5:2b"
    assert hardware.pick(_hw(16))[0].name == "qwen3.5:9b"


def test_dense_27b_needs_vram() -> None:
    assert hardware.pick(_hw(64))[0].name != "qwen3.5:27b"
    assert hardware.pick(_hw(64, vram=24))[0].name == "qwen3.5:27b"


def test_think_flag_only_for_reasoning_families() -> None:
    assert llm.is_thinking_model("qwen3.5:4b")
    assert llm.is_thinking_model("gemma4:e4b")
    assert not llm.is_thinking_model("qwen2.5:0.5b")


def test_interface_has_no_second_catalogue() -> None:
    source = (ROOT / "app" / "web" / "app.js").read_text(encoding="utf-8")
    assert not re.search(r"tag:\s*'qwen", source)


def test_interface_constants_are_declared() -> None:
    web = ROOT / "app" / "web"
    app = (web / "app.js").read_text(encoding="utf-8")
    declared = set()
    for name in ("app.js", "i18n.js", "drawgeom.js"):
        declared |= set(re.findall(r"\b(?:const|let|var)\s+([A-Z][A-Z0-9_]+)\b",
                                   (web / name).read_text(encoding="utf-8")))
    app = re.sub(r"/\*.*?\*/|(?<![:'\"])//[^\n]*", "", app, flags=re.S)
    used = set(re.findall(r"\$\{([A-Z][A-Z0-9_]+)\}", app))
    used |= set(re.findall(r"(?<![\w.'\"-])([A-Z][A-Z0-9_]+)(?=[.\[])", app))
    missing = sorted(used - declared - {"JSON", "URL"})
    assert not missing, f"undeclared constants in app.js: {missing}"
