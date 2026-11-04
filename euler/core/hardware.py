"""
Hardware probing and local model selection.

Runs once on first launch and is cached in settings; re-probing on every start
would cost seconds for nothing. The probe reads memory through ``psutil`` when
available and falls back to platform APIs otherwise.
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
from dataclasses import dataclass

RESERVE_GB = 2.0
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass(frozen=True)
class ModelSpec:
    """One entry of the local model catalogue."""

    name: str
    size_gb: float
    ram_gb: float
    note: str


# Sizes approximate the Q4_K_M quantisation. Verify with ``ollama show``
# before publishing a release.
CATALOG: tuple[ModelSpec, ...] = (
    ModelSpec("qwen2.5:14b", 9.0, 16.0, "highest quality, needs a discrete GPU"),
    ModelSpec("qwen2.5:7b", 4.7, 10.0, "balanced quality and speed"),
    ModelSpec("qwen2.5:3b", 2.0, 6.0, "fast on CPU, weaker on long answers"),
    ModelSpec("qwen2.5:1.5b", 1.0, 4.0, "for low-end laptops"),
    ModelSpec("qwen2.5:0.5b", 0.4, 2.5, "smoke test only"),
)

# Multimodal entries. Kept separate so the picker can offer them explicitly.
VISION_CATALOG: tuple[ModelSpec, ...] = (
    ModelSpec("qwen2-vl:7b", 4.9, 12.0, "strong image understanding"),
    ModelSpec("llava:7b", 4.7, 12.0, "reads photos of handwritten tasks"),
)


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


def _vram_gb() -> float | None:
    executable = shutil.which("nvidia-smi")
    if not executable:
        return None
    try:
        output = subprocess.run(
            [executable, "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5, check=True,
            creationflags=CREATE_NO_WINDOW,
        ).stdout
        return round(int(output.strip().splitlines()[0]) / 1024, 1)
    except (subprocess.SubprocessError, OSError, ValueError, IndexError):
        return None


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



def _gpu_info() -> tuple[str, str, float | None]:
    """Return ``(name, vendor, vram_gb)`` for the first usable GPU.

    NVIDIA is read through ``nvidia-smi``, which every driver ships. AMD and
    Intel cards are detected by name only: their VRAM is not exposed through a
    portable API, so the value stays ``None`` and the model picker falls back to
    system RAM.
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
        try:
            out = subprocess.run(
                ["wmic", "path", "win32_VideoController", "get", "name"],
                capture_output=True, text=True, timeout=6,
                creationflags=CREATE_NO_WINDOW,
            ).stdout
            lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
            for line in lines[1:]:
                low = line.lower()
                if any(tag in low for tag in ("microsoft basic", "remote", "virtual")):
                    continue
                vendor = ("amd" if ("amd" in low or "radeon" in low)
                          else "intel" if "intel" in low
                          else "nvidia" if "nvidia" in low else "")
                return line, vendor, None
        except (subprocess.SubprocessError, OSError):
            pass

    if platform.system() == "Linux":
        try:
            out = subprocess.run(["lspci"], capture_output=True, text=True, timeout=5).stdout
            for line in out.splitlines():
                if "VGA" in line or "3D controller" in line:
                    return line.split(":")[-1].strip(), "linux", None
        except (subprocess.SubprocessError, OSError):
            pass

    return "", "", None


def estimate(hardware: "Hardware", model_name: str) -> dict:
    """Rough throughput forecast for the chosen model.

    The numbers are empirical: a 7B model at Q4 runs at roughly
    ``vram_gb * 6`` tokens per second on GPU and ``cpu_cores * 1.4`` on CPU.
    They are labelled as estimates in the interface rather than promises.
    """
    spec = next((m for m in CATALOG + VISION_CATALOG if m.name == model_name), None)
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
    gpu_name, gpu_vendor, gpu_vram = _gpu_info()
    vram = gpu_vram if gpu_vram is not None else _vram_gb()

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
         ) -> tuple[ModelSpec, str]:
    """
    Choose the largest model that fits.

    :returns: the specification and a human-readable explanation, which the
              interface shows so a smaller model is never a silent surprise.
    """
    budget = hardware.budget_gb

    for spec in catalog:
        if spec.ram_gb > budget:
            continue
        if hardware.vram_gb and spec.ram_gb <= hardware.vram_gb:
            reason = f"fits in VRAM ({hardware.vram_gb} GB), inference runs on GPU"
        else:
            reason = f"RAM {hardware.total_ram_gb} GB, {budget} GB usable"
        return spec, f"{reason}; model needs {spec.ram_gb} GB"

    lightest = catalog[-1]
    return lightest, (
        f"only {budget} GB available, using the smallest model. "
        "High-quality local answers are not possible on this hardware."
    )


def recommend() -> dict:
    """Full recommendation payload consumed by the onboarding screen."""
    hardware = detect()
    spec, reason = pick(hardware)
    vision_spec, _ = pick(hardware, VISION_CATALOG + CATALOG)

    return {
        "model": spec.name,
        "reason": reason,
        "note": spec.note,
        "size_gb": spec.size_gb,
        "vision_model": vision_spec.name,
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
        {"name": spec.name, "size_gb": spec.size_gb,
         "ram_gb": spec.ram_gb, "note": spec.note,
         "vision": spec in VISION_CATALOG}
        for spec in CATALOG + VISION_CATALOG
    ]


__all__ = ["Hardware", "ModelSpec", "detect", "pick", "recommend",
           "catalogue", "CATALOG", "VISION_CATALOG"]
