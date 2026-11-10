"""
Hardware probing and local model selection.

The probe runs once on first launch and is cached in settings; re-probing on
every start would cost seconds for nothing. Memory is read through ``psutil``
when available and through kernel APIs otherwise.
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
from dataclasses import dataclass

RESERVE_GB = 2.0
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# Families whose models accept images. Ollama reports this per model, but the
# picker has to decide before the model is downloaded.
VISION_FAMILIES = ("qwen3.5", "qwen3-vl", "gemma4", "gemma3", "llava", "moondream",
                   "qwen2.5vl", "minicpm-v", "bakllava")


@dataclass(frozen=True)
class ModelSpec:
    """One entry of the model catalogue."""

    name: str
    size_gb: float          # download size
    ram_gb: float           # budget that keeps it off the swap file
    note: str
    tier: str
    vision: bool = False
    needs_gpu: bool = False


def family(model: str) -> str:
    """``qwen3.5:4b`` -> ``qwen3.5``."""
    return model.split(":", 1)[0].strip().lower()


def supports_vision(model: str) -> bool:
    """True when the model family accepts images."""
    name = model.strip().lower()
    return any(name.startswith(tag) for tag in VISION_FAMILIES)


# Download sizes come from the Ollama registry manifests; ``ram_gb`` is a
# judgement call that leaves room for the KV cache and the OS. Ordered largest
# first, because ``pick`` returns the first entry that fits.
CATALOG: tuple[ModelSpec, ...] = (
    ModelSpec("qwen3.5:27b", 17.5, 24.0, "best answers, needs a discrete GPU",
              "pro", vision=True, needs_gpu=True),
    ModelSpec("gemma4:26b", 18.7, 24.0, "mixture-of-experts, fast for its size",
              "moe", vision=True),
    ModelSpec("qwen3.5:9b", 6.6, 12.0, "balanced quality and speed",
              "balanced", vision=True),
    ModelSpec("gemma4:e4b", 6.6, 12.0, "Google alternative, handles images",
              "balanced", vision=True),
    ModelSpec("qwen3.5:4b", 3.3, 8.0, "fits a mid-range laptop",
              "light", vision=True),
    ModelSpec("qwen3.5:2b", 2.7, 6.0, "fast on CPU, weaker on long answers",
              "light", vision=True),
    ModelSpec("qwen2.5:1.5b", 1.0, 4.0, "text only, for a weak machine",
              "minimal"),
    ModelSpec("qwen2.5:0.5b", 0.4, 2.5, "text only, smoke test",
              "minimal"),
)

DEFAULT_MODEL = "qwen3.5:4b"


def spec_for(model: str) -> ModelSpec | None:
    """Catalogue entry for an exact tag, or None for a model the user installed by hand."""
    return next((item for item in CATALOG if item.name == model), None)


@dataclass
class Hardware:
    """Detected machine capabilities."""

    total_ram_gb: float
    vram_gb: float | None
    cpu_cores: int
    cpu_name: str
    os_name: str
    arch: str
    gpu_name: str = ""
    gpu_vendor: str = ""

    @property
    def budget_gb(self) -> float:
        """Memory available to a model after reserving space for the OS."""
        usable = max(self.total_ram_gb - RESERVE_GB, 0.1)
        if self.vram_gb:
            usable = max(usable, self.vram_gb - 0.5)
        return round(usable, 1)

    @property
    def has_gpu(self) -> bool:
        return bool(self.vram_gb and self.vram_gb >= 4.0)


def _total_ram_gb() -> float:
    try:
        import psutil
        return round(psutil.virtual_memory().total / 1024 ** 3, 1)
    except ImportError:
        pass

    try:
        if platform.system() == "Windows":
            import ctypes

            class _MemoryStatus(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            status = _MemoryStatus()
            status.dwLength = ctypes.sizeof(_MemoryStatus)
            if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                raise OSError("GlobalMemoryStatusEx failed")
            return round(status.ullTotalPhys / 1024 ** 3, 1)

        with open("/proc/meminfo", encoding="ascii") as handle:
            for line in handle:
                if line.startswith("MemTotal:"):
                    return round(int(line.split()[1]) / 1024 ** 2, 1)
    except (OSError, ValueError, AttributeError):
        pass

    return 8.0


def _cpu_info() -> tuple[str, int]:
    cores = os.cpu_count() or 1
    name = platform.processor() or platform.machine() or "unknown"

    try:
        if platform.system() == "Windows":
            import winreg
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"HARDWARE\DESCRIPTION\System\CentralProcessor\0",
            ) as key:
                name = winreg.QueryValueEx(key, "ProcessorNameString")[0].strip()
        elif platform.system() == "Linux":
            with open("/proc/cpuinfo", encoding="utf-8", errors="ignore") as handle:
                for line in handle:
                    if line.lower().startswith("model name"):
                        name = line.split(":", 1)[1].strip()
                        break
    except (OSError, ImportError, IndexError):
        pass

    return name, cores


def _gpu_names_windows() -> list[str]:
    """Adapter names from Win32_VideoController.

    ``wmic`` is deprecated and absent from recent Windows builds, so this goes
    through PowerShell, which ships with every supported version.
    """
    try:
        output = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name"],
            capture_output=True, text=True, timeout=10, check=True,
            creationflags=CREATE_NO_WINDOW,
        ).stdout
    except (subprocess.SubprocessError, OSError):
        return []
    return [line.strip() for line in output.splitlines() if line.strip()]


def _gpu_info() -> tuple[str, str, float | None]:
    """Return ``(name, vendor, vram_gb)`` for the first usable GPU.

    NVIDIA is read through ``nvidia-smi``, which every driver ships. AMD and
    Intel cards are detected by name only: their VRAM is not exposed through a
    portable API, so the picker falls back to system RAM for the budget.
    """
    exe = shutil.which("nvidia-smi")
    if exe:
        try:
            out = subprocess.run(
                [exe, "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=6, check=True,
                creationflags=CREATE_NO_WINDOW,
            ).stdout.strip().splitlines()
            if out:
                name, mem = [p.strip() for p in out[0].split(",")[:2]]
                return name, "nvidia", round(float(mem) / 1024, 1)
        except (subprocess.SubprocessError, OSError, ValueError, IndexError):
            pass

    if platform.system() == "Windows":
        for line in _gpu_names_windows():
            low = line.lower()
            if any(tag in low for tag in ("microsoft basic", "remote", "virtual")):
                continue
            vendor = ("amd" if ("amd" in low or "radeon" in low)
                      else "intel" if "intel" in low
                      else "nvidia" if "nvidia" in low else "")
            return line, vendor, None

    if platform.system() == "Linux":
        try:
            out = subprocess.run(["lspci"], capture_output=True, text=True,
                                 timeout=5, check=False).stdout
            for line in out.splitlines():
                if "VGA" in line or "3D controller" in line:
                    return line.split(":")[-1].strip(), "linux", None
        except (subprocess.SubprocessError, OSError):
            pass

    return "", "", None


def estimate(hardware: Hardware, model: str) -> dict:
    """Rough throughput forecast, labelled as an estimate in the interface.

    Empirical: a 7B model at Q4 runs at about ``vram_gb * 6`` tokens per second
    on a GPU and ``cpu_cores * 1.4`` on a CPU; other sizes are not scaled.
    """
    spec = spec_for(model)
    if spec is None:
        return {"device": "unknown", "tokens_per_s": 0, "note": "model not in catalogue"}

    fits_vram = bool(hardware.vram_gb and spec.ram_gb <= hardware.vram_gb)
    if fits_vram:
        rate = max(hardware.vram_gb * 6.0, 4.0)
        return {
            "device": "gpu",
            "tokens_per_s": round(rate, 1),
            "note": f"{spec.name} fits in {hardware.vram_gb} GB VRAM",
        }

    if spec.ram_gb <= hardware.budget_gb:
        rate = max(hardware.cpu_cores * 1.4, 1.5)
        return {
            "device": "cpu",
            "tokens_per_s": round(rate, 1),
            "note": f"{spec.name} runs on CPU with {hardware.budget_gb} GB available",
        }

    return {
        "device": "cpu",
        "tokens_per_s": round(max(hardware.budget_gb * 1.2, 0.6), 1),
        "note": f"{spec.name} exceeds available memory and will swap",
    }


def detect() -> Hardware:
    """Probe CPU, RAM and GPU in one pass."""
    cpu_name, cores = _cpu_info()
    gpu_name, gpu_vendor, vram = _gpu_info()

    return Hardware(
        total_ram_gb=_total_ram_gb(),
        vram_gb=vram,
        cpu_cores=cores,
        cpu_name=cpu_name,
        os_name=f"{platform.system()} {platform.release()}",
        arch=platform.machine(),
        gpu_name=gpu_name,
        gpu_vendor=gpu_vendor,
    )


def pick(hardware: Hardware, catalog: tuple[ModelSpec, ...] = CATALOG
         ) -> tuple[ModelSpec, dict]:
    """Choose the largest model that fits.

    A model flagged ``needs_gpu`` is skipped unless its whole budget fits in
    VRAM: a dense 27B model on CPU answers at a few tokens per second, which
    reads as a broken assistant.

    :returns: the specification and a machine-readable reason (a code and its
              numbers); the interface renders it in the user's language.
    """
    budget = hardware.budget_gb

    for spec in catalog:
        if spec.ram_gb > budget:
            continue
        if spec.needs_gpu and not (hardware.vram_gb or 0) >= spec.ram_gb:
            continue   # partial offload of a dense 27B runs slower than the 9B on CPU
        if hardware.vram_gb and spec.ram_gb <= hardware.vram_gb:
            reason = {"code": "vram", "vram": hardware.vram_gb, "needs": spec.ram_gb}
        else:
            reason = {"code": "ram", "ram": hardware.total_ram_gb,
                      "budget": budget, "needs": spec.ram_gb}
        return spec, reason

    return catalog[-1], {"code": "low", "budget": budget}


def recommend() -> dict:
    """Full recommendation payload consumed by the onboarding screen."""
    hardware = detect()
    spec, reason = pick(hardware)

    return {
        "model": spec.name,
        "reason": reason,
        "note": spec.note,
        "size_gb": spec.size_gb,
        "vision": spec.vision,
        "throughput": estimate(hardware, spec.name),
        "hardware": {
            "cpu": hardware.cpu_name,
            "cores": hardware.cpu_cores,
            "ram_gb": hardware.total_ram_gb,
            "vram_gb": hardware.vram_gb,
            "gpu": hardware.gpu_name,
            "gpu_vendor": hardware.gpu_vendor,
            "os": hardware.os_name,
            "arch": hardware.arch,
            "budget_gb": hardware.budget_gb,
            "has_gpu": hardware.has_gpu,
        },
    }


def catalogue() -> list[dict]:
    """Selectable models with their requirements."""
    return [
        {"name": item.name, "size_gb": item.size_gb, "ram_gb": item.ram_gb,
         "note": item.note, "tier": item.tier, "vision": item.vision,
         "needs_gpu": item.needs_gpu}
        for item in CATALOG
    ]


__all__ = ["Hardware", "ModelSpec", "detect", "pick", "recommend", "estimate",
           "catalogue", "spec_for", "supports_vision", "family", "CATALOG",
           "DEFAULT_MODEL", "VISION_FAMILIES"]
