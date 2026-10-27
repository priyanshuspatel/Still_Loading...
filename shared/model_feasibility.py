"""Feasibility analysis and resource benchmarking for local LLMs on Still Loading... hardware.

Phase 7: Compares the zero-overhead rules-first explainer against local small
language models (SLMs) on the target Arduino UNO Q hardware (Qualcomm QRB2210)
and the host Mac.
"""

from __future__ import annotations

import os
import platform
import sys
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class HardwareProfile:
    platform_system: str
    machine: str
    cpu_count: int
    total_memory_mb: int
    available_memory_mb: int
    python_version: str


@dataclass(frozen=True)
class ModelFeasibilityReport:
    hardware: HardwareProfile
    is_uno_q_environment: bool
    recommended_engine: str  # "rules" | "local_slm" | "mac_offload"
    rationale: str
    gemma_placement: str  # "mac_offload" or "disabled_on_board"
    can_safely_load_500m_model: bool
    can_safely_load_1b_model: bool
    estimated_tokens_per_second: float

    def to_dict(self) -> dict:
        return asdict(self)


def get_hardware_profile() -> HardwareProfile:
    """Detect current system architecture, CPU cores, and memory capacity."""
    cpu_count = os.cpu_count() or 1
    total_mb = 0
    avail_mb = 0

    if sys.platform == "darwin":
        # macOS memory detection via sysctl
        try:
            import subprocess

            out = subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True)
            total_mb = int(int(out.strip()) / (1024 * 1024))
            avail_mb = int(total_mb * 0.4)  # Approximate available pool
        except Exception:
            total_mb = 8192
            avail_mb = 4096
    elif sys.platform.startswith("linux"):
        # Linux memory detection via /proc/meminfo
        try:
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        total_mb = int(line.split()[1]) // 1024
                    elif line.startswith("MemAvailable:"):
                        avail_mb = int(line.split()[1]) // 1024
        except Exception:
            total_mb = 2048
            avail_mb = 1024
    else:
        total_mb = 2048
        avail_mb = 1024

    return HardwareProfile(
        platform_system=platform.system(),
        machine=platform.machine(),
        cpu_count=cpu_count,
        total_memory_mb=total_mb,
        available_memory_mb=avail_mb,
        python_version=platform.python_version(),
    )


def assess_feasibility(profile: HardwareProfile | None = None) -> ModelFeasibilityReport:
    """Evaluate whether local LLM inference is feasible on the active device.

    Rules:
    - Qualcomm QRB2210 (Debian ARM64 on UNO Q) has 2 GB or 4 GB LPDDR4 shared with
      the OS kernel, Docker container runtime, WiFi subsystem, and App Lab Bridge.
      Running a quantized model on-device risks OOM kill (exit 137) and adds
      6-15s thermal-throttled latency.
    - The zero-overhead rules explainer executes in <0.1 ms with 0 extra MB.
    """
    p = profile or get_hardware_profile()

    is_arm64_linux = p.platform_system == "Linux" and ("aarch64" in p.machine or "arm" in p.machine)
    is_uno_q = is_arm64_linux and p.total_memory_mb <= 4096

    if is_uno_q:
        safe_500m = p.available_memory_mb > 1200
        safe_1b = False
        tps = 1.8  # Cortex-A53 estimated tokens/sec
        rec = "rules"
        rationale = (
            f"Detected UNO Q Linux host ({p.total_memory_mb} MB total, {p.available_memory_mb} MB free). "
            "Gemma stays on the Mac. Running it on the QRB2210 risks OOM kills (exit 137), "
            "thermal throttling, and multi-second stalls. The board keeps the rules explainer "
            "and its existing light codes."
        )
    elif p.total_memory_mb >= 16384 and p.platform_system == "Darwin":
        # Host Mac development environment
        safe_500m = True
        safe_1b = True
        tps = 35.0  # Apple Silicon Neural Engine / Metal
        rec = "rules_with_mac_optional"
        rationale = (
            f"Host Mac detected ({p.total_memory_mb} MB RAM, {p.cpu_count} cores). "
            "Gemma can run here through the local OpenAI-compatible endpoint. "
            "The rules explainer remains the instant fallback. The UNO Q keeps its existing "
            "light codes; the written diagnosis stays on the Mac and in the web UI."
        )
    else:
        safe_500m = p.available_memory_mb > 1500
        safe_1b = p.available_memory_mb > 3000
        tps = 10.0
        rec = "rules"
        rationale = "Rules-first engine is safe and instant across all architectures."

    return ModelFeasibilityReport(
        hardware=p,
        is_uno_q_environment=is_uno_q,
        recommended_engine=rec,
        rationale=rationale,
        gemma_placement="disabled_on_board" if is_uno_q else "mac_offload",
        can_safely_load_500m_model=safe_500m,
        can_safely_load_1b_model=safe_1b,
        estimated_tokens_per_second=tps,
    )


if __name__ == "__main__":
    report = assess_feasibility()
    import json
    print(json.dumps(report.to_dict(), indent=2))
