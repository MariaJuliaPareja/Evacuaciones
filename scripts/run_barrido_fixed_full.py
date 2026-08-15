"""Orquesta barridos N=100 post-fix ocupación, guardando un PKL por escenario.

Orden de escenarios (liviano → pesado, según pedido del usuario):
  sala_de_clases → base → avion_dos_puertas

Dentro de cada escenario: densidades ρ=0.25→1.0 (orden de RHO_VALS en el barrido).
Por escenario corre PRU y luego PFF, guarda PKL al terminar cada uno, mide pico RSS,
y para PRU verifica % superposición en una muestra ρ=1.0.
"""
from __future__ import annotations

import gc
import importlib
import json
import os
import sys
import threading
import time
import traceback
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT_DIR = ROOT / "salidas" / "experimentos"
LOG_PATH = OUT_DIR / "barrido_fixed_run.log"
STATUS_PATH = OUT_DIR / "barrido_fixed_status.jsonl"

SCENARIOS = ["sala_de_clases", "base", "avion_dos_puertas"]
N_SIMS = 100


def _rss_mb() -> float:
    try:
        import psutil

        return psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)
    except ImportError:
        import ctypes
        from ctypes import wintypes

        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(counters)
        ctypes.windll.psapi.GetProcessMemoryInfo(
            ctypes.windll.kernel32.GetCurrentProcess(),
            ctypes.byref(counters),
            counters.cb,
        )
        return counters.WorkingSetSize / (1024 * 1024)


def _peak_ws_mb() -> float:
    try:
        import psutil

        # psutil no expone peak WS en Windows de forma portable; usamos RSS actual
        # y el máximo observado en el runner.
        return _rss_mb()
    except ImportError:
        import ctypes
        from ctypes import wintypes

        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(counters)
        ctypes.windll.psapi.GetProcessMemoryInfo(
            ctypes.windll.kernel32.GetCurrentProcess(),
            ctypes.byref(counters),
            counters.cb,
        )
        return counters.PeakWorkingSetSize / (1024 * 1024)


def _log(msg: str) -> None:
    line = msg.rstrip()
    print(line, flush=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def _status(event: dict[str, Any]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with STATUS_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def _load_scenario(name: str) -> dict[str, Any]:
    mod_name = "escenario_base" if name == "base" else name
    esc = importlib.import_module(f"escenarios.{mod_name}")
    return {
        "width": int(esc.width),
        "height": int(esc.height),
        "puertas": list(esc.puertas),
        "obstaculos": list(getattr(esc, "obstaculos", []) or []),
    }


def _overlap_frac_pru(scenario: str, n_steps_cap: int = 200, seed: int = 12345) -> dict[str, Any]:
    """Muestra rápida ρ=1.0: fracción de agent-frames activos con celda compartida."""
    import experimento.barrido_propuesta1 as bp
    from simulacion.pathfinding_propuesta.agent_extendido import (
        AgentExtendido,
        mover_agentes_con_conflictos,
    )
    from simulacion.grilla_clasica.floor_field import Floor_field
    from simulacion.pathfinding_propuesta.path_selector import PathSelector

    esc = _load_scenario(scenario)
    d_inv = float(bp.D_INV_VALS[8])
    rho = 1.0
    rng_seed = seed + int(1_000_000 * rho) + int(10_000 * d_inv)

    # Reusa el setup de una historia pero instrumenta overlap frame a frame.
    ff = Floor_field(esc["width"], esc["height"], esc["puertas"], esc["obstaculos"])
    path_selector = PathSelector(ff, umbral_recalculo=0.6, anxiety_thresholds=(30, 70))
    AgentExtendido.instances = []
    AgentExtendido.history = []

    import random
    import numpy as np

    rng = random.Random(rng_seed)
    np.random.seed(rng_seed)
    posiciones = bp._generar_posiciones_iniciales(
        esc["width"], esc["height"], esc["obstaculos"], rho, rng
    )
    d = 1.0 / d_inv
    for pos in posiciones:
        bp._crear_agente(ff, pos, d, 2.0 * d, path_selector, True)

    agent_frames = 0
    overlap_agent_frames = 0
    frames = 0
    for _ in range(min(n_steps_cap, bp.MAX_PASOS)):
        activos = [a for a in AgentExtendido.instances if a.activo]
        if not activos:
            break
        mover_agentes_con_conflictos(AgentExtendido.instances)
        activos = [a for a in AgentExtendido.instances if a.activo]
        counts = Counter((a.pos_x, a.pos_y) for a in activos)
        for a in activos:
            agent_frames += 1
            if counts[(a.pos_x, a.pos_y)] > 1:
                overlap_agent_frames += 1
        frames += 1

    AgentExtendido.instances = []
    AgentExtendido.history = []
    gc.collect()
    frac = (100.0 * overlap_agent_frames / agent_frames) if agent_frames else 0.0
    return {
        "frames": frames,
        "agent_frames": agent_frames,
        "overlap_agent_frames": overlap_agent_frames,
        "overlap_pct": frac,
    }


class _RssSampler:
    """Muestrea RSS en un hilo mientras corre el barrido."""

    def __init__(self, interval_s: float = 1.0) -> None:
        self.interval_s = interval_s
        self.peak_mb = _rss_mb()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="rss-sampler", daemon=True)

    def _run(self) -> None:
        while not self._stop.wait(self.interval_s):
            try:
                self.peak_mb = max(self.peak_mb, _rss_mb())
            except Exception:
                pass

    def __enter__(self) -> "_RssSampler":
        self._thread.start()
        return self

    def __exit__(self, *args: Any) -> None:
        self._stop.set()
        self._thread.join(timeout=5)
        self.peak_mb = max(self.peak_mb, _rss_mb(), _peak_ws_mb())


def _run_pru(scenario: str) -> Path:
    import experimento.barrido_propuesta1 as bp

    def _loader():
        return _load_scenario(scenario)

    bp._cargar_escenario_base = _loader
    bp.N_SIMS = N_SIMS
    out = OUT_DIR / f"barrido_propuesta1_{scenario}_fixed.pkl"
    data = bp.ejecutar_barrido()
    data.setdefault("meta", {})
    data["meta"]["motor"] = "PRU-A*"
    data["meta"]["tag"] = "fixed_post_occupation_bug"
    data["meta"]["scenario"] = scenario
    bp.guardar_resultados(data, out)
    return out


def _run_pff(scenario: str) -> Path:
    import experimento.barrido_pff as bp

    def _loader():
        return _load_scenario(scenario)

    bp._cargar_escenario_base = _loader
    bp.N_SIMS = N_SIMS
    out = OUT_DIR / f"barrido_pff_{scenario}_fixed.pkl"
    data = bp.ejecutar_barrido()
    data.setdefault("meta", {})
    data["meta"]["motor"] = "PFF"
    data["meta"]["tag"] = "fixed_post_occupation_bug"
    data["meta"]["scenario"] = scenario
    bp.guardar_resultados(data, out)
    return out


def main(scenarios: list[str] | None = None, append_log: bool = False) -> int:
    scenarios = list(scenarios) if scenarios is not None else list(SCENARIOS)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    mode = "a" if append_log else "w"
    with LOG_PATH.open(mode, encoding="utf-8") as f:
        f.write(f"==== fixed barridos N={N_SIMS} {time.strftime('%Y-%m-%dT%H:%M:%S')} ====\n")
        f.write(f"order scenarios: {scenarios}\n")
        f.write("densities: 0.25 -> 1.0 (RHO_VALS)\n")

    _log(f"START_FULL order={scenarios} N_SIMS={N_SIMS}")
    _status({"event": "start", "scenarios": scenarios, "n_sims": N_SIMS})

    overall_t0 = time.perf_counter()
    for scenario in scenarios:
        # --- PRU ---
        _log(f"START_SCENARIO motor=PRU scenario={scenario}")
        _status({"event": "start_scenario", "motor": "PRU", "scenario": scenario})
        gc.collect()
        rss0 = _rss_mb()
        t0 = time.perf_counter()
        try:
            with _RssSampler() as samp:
                out = _run_pru(scenario)
            peak = samp.peak_mb
            elapsed = time.perf_counter() - t0
            overlap = _overlap_frac_pru(scenario)
            peak = max(peak, _rss_mb())
            payload = {
                "event": "SCENARIO_DONE",
                "motor": "PRU",
                "scenario": scenario,
                "out": str(out),
                "elapsed_s": round(elapsed, 1),
                "peak_rss_mb": round(peak, 1),
                "rss0_mb": round(rss0, 1),
                "overlap_pct": round(overlap["overlap_pct"], 4),
                "overlap_detail": overlap,
                "ok": True,
            }
            _log(
                "SCENARIO_DONE "
                f"motor=PRU scenario={scenario} elapsed_s={payload['elapsed_s']} "
                f"peak_rss_mb={payload['peak_rss_mb']} overlap_pct={payload['overlap_pct']} "
                f"out={out.name}"
            )
            _status(payload)
        except Exception as exc:
            _log(f"SCENARIO_FAIL motor=PRU scenario={scenario} err={exc}")
            _status(
                {
                    "event": "SCENARIO_FAIL",
                    "motor": "PRU",
                    "scenario": scenario,
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                }
            )
            _log(traceback.format_exc())
            return 1

        # --- PFF ---
        _log(f"START_SCENARIO motor=PFF scenario={scenario}")
        _status({"event": "start_scenario", "motor": "PFF", "scenario": scenario})
        gc.collect()
        rss0 = _rss_mb()
        t0 = time.perf_counter()
        try:
            with _RssSampler() as samp:
                out = _run_pff(scenario)
            peak = samp.peak_mb
            elapsed = time.perf_counter() - t0
            payload = {
                "event": "SCENARIO_DONE",
                "motor": "PFF",
                "scenario": scenario,
                "out": str(out),
                "elapsed_s": round(elapsed, 1),
                "peak_rss_mb": round(peak, 1),
                "rss0_mb": round(rss0, 1),
                "overlap_pct": 0.0,
                "overlap_note": "PFF filtra ocupadas al proponer; muestra no instrumentada",
                "ok": True,
            }
            _log(
                "SCENARIO_DONE "
                f"motor=PFF scenario={scenario} elapsed_s={payload['elapsed_s']} "
                f"peak_rss_mb={payload['peak_rss_mb']} overlap_pct=0 "
                f"out={out.name}"
            )
            _status(payload)
        except Exception as exc:
            _log(f"SCENARIO_FAIL motor=PFF scenario={scenario} err={exc}")
            _status(
                {
                    "event": "SCENARIO_FAIL",
                    "motor": "PFF",
                    "scenario": scenario,
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                }
            )
            _log(traceback.format_exc())
            return 1

    total = time.perf_counter() - overall_t0
    _log(f"ALL_FIXED_BARRIDOS_OK total_s={total:.1f}")
    _status({"event": "all_done", "total_s": round(total, 1)})
    return 0


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scenarios",
        nargs="+",
        default=None,
        choices=["sala_de_clases", "base", "avion_dos_puertas"],
        help="Subset of scenarios (default: full SCENARIOS list)",
    )
    parser.add_argument("--append-log", action="store_true")
    args = parser.parse_args()
    sys.exit(main(scenarios=args.scenarios, append_log=args.append_log))
