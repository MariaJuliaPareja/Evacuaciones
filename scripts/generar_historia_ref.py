"""Generate a single-run history PKL compatible with visualizar_animacion_rutas.py.

Usage:
  PYTHONPATH=. python scripts/generar_historia_ref.py \\
      --scenario avion_dos_puertas --rho 1.0 --d_inv 0.039810717055349734 --seed 12345

Output (default):
  historia_ref_<scenario>.pkl
"""
from __future__ import annotations

import argparse
import importlib
import pickle
import random
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experimento.barrido_propuesta1 import (  # noqa: E402
    D_INV_VALS,
    MAX_PASOS,
    SEED_BASE,
    _crear_agente,
    _generar_posiciones_iniciales,
)
from simulacion.grilla_clasica.floor_field import Floor_field  # noqa: E402
from simulacion.pathfinding_propuesta.agent_extendido import (  # noqa: E402
    AgentExtendido,
    mover_agentes_con_conflictos,
)
from simulacion.pathfinding_propuesta.path_selector import PathSelector  # noqa: E402

SCENARIO_CHOICES = ["base", "escenario_base", "sala_de_clases", "avion", "avion_dos_puertas"]


def _mid_d_inv() -> float:
    vals = [float(v) for v in D_INV_VALS]
    return vals[len(vals) // 2]


def load_scenario(name: str) -> dict:
    mod_name = "escenario_base" if name == "base" else name
    esc = importlib.import_module(f"escenarios.{mod_name}")
    return {
        "width": int(esc.width),
        "height": int(esc.height),
        "puertas": list(esc.puertas),
        "obstaculos": list(getattr(esc, "obstaculos", []) or []),
        "name": mod_name,
    }


def generar_historia(
    scenario: str,
    rho: float,
    d_inv: float,
    seed: int,
    max_pasos: int = MAX_PASOS,
) -> list:
    """
    Run one PRU simulation and return dynamics-style history:
      [frame0_list, frame1_list, ..., config_dict]
    where each frame is a list of agent SimpleNamespace snapshots from stores().
    """
    esc = load_scenario(scenario)
    width, height = esc["width"], esc["height"]
    puertas, obstaculos = esc["puertas"], esc["obstaculos"]

    rng = random.Random(seed)
    random.seed(seed)
    np.random.seed(seed)

    ff = Floor_field(width, height, puertas, obstaculos)
    path_selector = PathSelector(ff, umbral_recalculo=0.6, anxiety_thresholds=(30, 70))

    AgentExtendido.instances = []
    AgentExtendido.history = []

    posiciones = _generar_posiciones_iniciales(width, height, obstaculos, rho, rng)
    d = 1.0 / float(d_inv)
    u_i, u_ii = d, 2.0 * d

    ya_todo = False
    for pos in posiciones:
        ya_todo = _crear_agente(ff, pos, u_i, u_ii, path_selector, ya_todo)

    # Initial snapshot (t=0), same convention as dynamics.py
    AgentExtendido.stores()

    for step in range(max_pasos):
        activos = [a for a in AgentExtendido.instances if a.activo]
        if not activos:
            break
        for a in AgentExtendido.instances:
            a._current_simulation_step = step
        mover_agentes_con_conflictos(AgentExtendido.instances)
        AgentExtendido.stores()

    # Trailing config block expected by visualizar_animacion_rutas._construir_visualizador_desde_pkl
    AgentExtendido.history.append(
        {
            "size_x": width,
            "size_y": height,
            "obstacles": list(obstaculos),
            "puertas": list(puertas),
            "meta": {
                "scenario": esc["name"],
                "rho": float(rho),
                "d_inv": float(d_inv),
                "U_I": float(u_i),
                "U_II": float(u_ii),
                "seed": int(seed),
                "n_agentes": len(posiciones),
                "n_frames": sum(1 for f in AgentExtendido.history if isinstance(f, list)),
            },
        }
    )
    return list(AgentExtendido.history)


def verificar_compatible_con_visualizador(ruta_pkl: Path) -> dict:
    """Load via the same helper the GUI uses; no window is opened."""
    from simulacion.nodos.visualizar_animacion_rutas import _construir_visualizador_desde_pkl

    viz = _construir_visualizador_desde_pkl(str(ruta_pkl))
    n_frames = len(viz.historial)
    if n_frames < 1:
        raise ValueError(f"No frames loaded from {ruta_pkl}")
    # Spot-check first frame has positions
    agentes0 = viz.historial[0]["agentes"]
    if not agentes0:
        raise ValueError(f"First frame has no agents in {ruta_pkl}")
    if agentes0[0].get("x") is None or agentes0[0].get("y") is None:
        raise ValueError(f"Missing positions in first frame of {ruta_pkl}")
    return {
        "ruta": str(ruta_pkl),
        "n_frames": n_frames,
        "n_agentes_frame0": len(agentes0),
        "grid_shape_yx": tuple(int(x) for x in viz.ff.valores.shape),
        "sample_agent0": {
            "id": agentes0[0].get("id"),
            "x": agentes0[0].get("x"),
            "y": agentes0[0].get("y"),
            "activo": agentes0[0].get("activo"),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate historia_ref_*.pkl for the route animator.")
    parser.add_argument("--scenario", required=False, choices=SCENARIO_CHOICES)
    parser.add_argument("--rho", type=float, default=1.0)
    parser.add_argument(
        "--d_inv",
        type=float,
        default=None,
        help="1/d value; default = mid value of barrido D_INV_VALS (~0.03981)",
    )
    parser.add_argument("--seed", type=int, default=SEED_BASE)
    parser.add_argument("--max_pasos", type=int, default=MAX_PASOS)
    parser.add_argument(
        "--out",
        type=str,
        default=None,
        help="Output path (default: historia_ref_<scenario>.pkl in repo root)",
    )
    parser.add_argument(
        "--verify-only",
        type=str,
        default=None,
        help="Only verify an existing PKL with the visualizer loader (no simulation)",
    )
    args = parser.parse_args()

    if args.verify_only:
        info = verificar_compatible_con_visualizador(Path(args.verify_only))
        print("VERIFY_OK", info)
        return

    if not args.scenario:
        parser.error("--scenario is required unless --verify-only is set")

    d_inv = float(args.d_inv) if args.d_inv is not None else _mid_d_inv()
    scenario_key = "escenario_base" if args.scenario == "base" else args.scenario
    out = Path(args.out) if args.out else ROOT / f"historia_ref_{scenario_key}.pkl"

    print(
        f"Generating single-run history: scenario={scenario_key} "
        f"rho={args.rho} d_inv={d_inv} seed={args.seed}"
    )
    historia = generar_historia(
        scenario=scenario_key,
        rho=float(args.rho),
        d_inv=d_inv,
        seed=int(args.seed),
        max_pasos=int(args.max_pasos),
    )
    n_frames = sum(1 for f in historia if isinstance(f, list))
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("wb") as f:
        pickle.dump(historia, f)
    print(f"Saved: {out} ({n_frames} frames, {out.stat().st_size} bytes)")

    info = verificar_compatible_con_visualizador(out)
    print("VERIFY_OK", info)


if __name__ == "__main__":
    main()
