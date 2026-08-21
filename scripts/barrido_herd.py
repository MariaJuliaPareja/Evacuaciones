"""Route-diversity entropy H and thundering-herd frequency nu_TH.

Runs N=100 PRU-A* simulations for each (escenario, rho) in
{avion_dos_puertas, sala_de_clases} x {0.5, 1.0}, using the (U_I, U_II)
pair that minimises T_PRU in tabla_comparacion_pff_pru_fixed.csv.

Definitions (paper, do not change):
  H = -sum_k p_k ln(p_k)
    p_k = empirical fraction of agents that egress via route k.
    Route k is the logical exit (adjacent door cells = one door). If the
    scenario has a single logical door, k is refined with the last A*
    node sequence (door cells canonicalised).
  nu_TH = fraction of time steps in which more than 30% of the agents
    that were active at the start of the step request a route
    recalculation (AgentExtendido.recalculated_this_step: PathSelector
    invokes A* again after delta_i cooldown / should_recalculate).

Does not modify agent_extendido.py / mover_agentes_con_conflictos.

Usage:
  PYTHONPATH=. python scripts/barrido_herd.py
  PYTHONPATH=. python scripts/barrido_herd.py --n-sims 2
"""
from __future__ import annotations

import argparse
import csv
import gc
import importlib
import math
import random
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experimento.barrido_propuesta1 import (  # noqa: E402
    D_INV_VALS,
    MAX_PASOS,
    SEED_BASE,
    _generar_posiciones_iniciales,
)
from simulacion.grilla_clasica.floor_field import Floor_field  # noqa: E402
from simulacion.pathfinding_propuesta.agent_extendido import (  # noqa: E402
    AgentExtendido,
    mover_agentes_con_conflictos,
)
from simulacion.pathfinding_propuesta.path_selector import PathSelector  # noqa: E402

SCENARIOS = ("avion_dos_puertas", "sala_de_clases")
RHO_VALS = (0.5, 1.0)
N_RUNS_DEFAULT = 100
TABLA_COMPARACION = ROOT / "tabla_comparacion_pff_pru_fixed.csv"
OUT_DEFAULT = ROOT / "tabla_herd_h_nuth.csv"


def cargar_escenario(nombre: str) -> dict[str, Any]:
    esc = importlib.import_module(f"escenarios.{nombre}")
    return {
        "name": nombre,
        "width": int(esc.width),
        "height": int(esc.height),
        "puertas": [tuple(p) for p in esc.puertas],
        "obstaculos": [tuple(o) for o in (getattr(esc, "obstaculos", []) or [])],
    }


def puertas_logicas(puertas: list[tuple[int, int]]) -> dict[tuple[int, int], int]:
    """4-connected clusters of door cells. Adjacent cells share one logical exit."""
    remaining = {tuple(p) for p in puertas}
    cell_to_id: dict[tuple[int, int], int] = {}
    lid = 0
    while remaining:
        start = remaining.pop()
        stack = [start]
        cluster = [start]
        while stack:
            x, y = stack.pop()
            for dx, dy in ((0, 1), (1, 0), (0, -1), (-1, 0)):
                n = (x + dx, y + dy)
                if n in remaining:
                    remaining.remove(n)
                    stack.append(n)
                    cluster.append(n)
        for cell in cluster:
            cell_to_id[cell] = lid
        lid += 1
    return cell_to_id


def shannon_h(keys: list[Any]) -> float:
    if not keys:
        return 0.0
    counts = Counter(keys)
    total = sum(counts.values())
    h = 0.0
    for n in counts.values():
        p = n / total
        if p > 0.0:
            h -= p * math.log(p)
    return h


def clave_ruta(
    logical_id: int | None,
    astar_path: tuple[tuple[int, int], ...],
    n_logical: int,
    door_cells: set[tuple[int, int]],
) -> tuple:
    """Group by logical door; refine with A* node sequence if only one logical door."""
    if logical_id is None:
        return ("unknown",)
    if n_logical > 1:
        return ("door", logical_id)
    if not astar_path:
        return ("door", logical_id, ())
    canon = tuple(
        ("EXIT", logical_id) if node in door_cells else node for node in astar_path
    )
    return ("path", logical_id, canon)


def umbrales_optimos(tabla: Path) -> dict[tuple[str, float], dict[str, float]]:
    """(escenario, rho) -> row with minimum T_PRU, snapped to barrido D_INV_VALS."""
    if not tabla.is_file():
        raise FileNotFoundError(f"No existe la tabla de comparación: {tabla}")

    best: dict[tuple[str, float], dict[str, float]] = {}
    with tabla.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            escenario = str(row["scenario"]).strip()
            if escenario not in SCENARIOS:
                continue
            rho = float(row["rho"])
            t_pru = float(row["T_PRU"])
            key = (escenario, rho)
            prev = best.get(key)
            if prev is None or t_pru < prev["T_PRU"]:
                log10_dinv = float(row["log10(1/d)"])
                target = 10.0 ** log10_dinv
                d_inv = min((float(v) for v in D_INV_VALS), key=lambda v: abs(v - target))
                best[key] = {
                    "T_PRU": t_pru,
                    "d_inv": d_inv,
                    "U_I": 1.0 / d_inv,
                    "U_II": 2.0 / d_inv,
                    "log10_1d": log10_dinv,
                }
    missing = [
        (esc, rho)
        for esc in SCENARIOS
        for rho in RHO_VALS
        if (esc, float(rho)) not in best
        and not any(k[0] == esc and abs(k[1] - rho) < 1e-12 for k in best)
    ]
    if missing:
        raise RuntimeError(f"No hay T_PRU mínimo para: {missing}")
    return best


def lookup_umbral(
    tabla: dict[tuple[str, float], dict[str, float]], escenario: str, rho: float
) -> dict[str, float]:
    for (esc, r), row in tabla.items():
        if esc == escenario and abs(r - rho) < 1e-12:
            return row
    raise KeyError(f"Umbral óptimo ausente para {escenario} rho={rho}")


def _reset_agentes() -> None:
    AgentExtendido.instances = []
    AgentExtendido.history = []
    AgentExtendido.ruta_log.clear()


def simular_una_corrida(
    esc: dict[str, Any],
    rho: float,
    u_i: float,
    u_ii: float,
    semilla: int,
    max_pasos: int = MAX_PASOS,
) -> dict[str, float]:
    """One PRU-A* run. Returns H, nu_TH, T, n_egress, n_unique_routes."""
    rng = random.Random(semilla)
    random.seed(semilla)
    np.random.seed(semilla)

    ff = Floor_field(esc["width"], esc["height"], esc["puertas"], esc["obstaculos"])
    path_selector = PathSelector(ff, umbral_recalculo=0.6, anxiety_thresholds=(30, 70))
    path_selector.reset_log()
    _reset_agentes()

    posiciones = _generar_posiciones_iniciales(
        esc["width"], esc["height"], esc["obstaculos"], rho, rng
    )
    for pos in posiciones:
        AgentExtendido(
            agent_type="rapido",
            floor_field=ff,
            path_selector=path_selector,
            x=pos[0],
            y=pos[1],
            U_I=u_i,
            U_II=u_ii,
        )

    door_map = puertas_logicas(esc["puertas"])
    door_cells = set(door_map)
    n_logical = len(set(door_map.values()))
    last_astar: dict[int, tuple[tuple[int, int], ...]] = {}
    route_keys: list[tuple] = []
    n_th = 0
    n_steps = 0
    t_evac = 0

    for step in range(max_pasos):
        activos = [a for a in AgentExtendido.instances if a.activo]
        if not activos:
            break
        for a in activos:
            a._current_simulation_step = step
            if a.current_path:
                last_astar[a.id] = tuple(a.current_path)

        mover_agentes_con_conflictos(AgentExtendido.instances)

        n_act = len(activos)
        n_rec = sum(1 for a in activos if getattr(a, "recalculated_this_step", False))
        if n_act > 0 and (n_rec / n_act) > 0.30:
            n_th += 1
        n_steps += 1
        t_evac = n_steps

        for a in activos:
            if a.activo:
                if a.current_path:
                    last_astar[a.id] = tuple(a.current_path)
                continue
            cell = (int(a.pos_x), int(a.pos_y))
            lid = door_map.get(cell)
            path = last_astar.get(a.id, ())
            route_keys.append(clave_ruta(lid, path, n_logical, door_cells))

    h = shannon_h(route_keys)
    nu = (n_th / n_steps) if n_steps > 0 else 0.0
    _reset_agentes()
    return {
        "H": h,
        "nu_TH": nu,
        "T": float(t_evac),
        "n_egress": float(len(route_keys)),
        "n_unique_routes": float(len(set(route_keys))),
        "n_steps": float(n_steps),
    }


def _media_std(valores: list[float]) -> tuple[float, float]:
    arr = np.asarray(valores, dtype=float)
    if arr.size == 0:
        return 0.0, 0.0
    return float(np.mean(arr)), float(np.std(arr, ddof=0))


def ejecutar(
    n_runs: int,
    tabla_comparacion: Path,
    out_csv: Path,
    max_pasos: int = MAX_PASOS,
) -> list[dict[str, Any]]:
    umbrales = umbrales_optimos(tabla_comparacion)
    print("Umbrales (U_I, U_II) = argmin T_PRU por (escenario, rho):")
    for esc in SCENARIOS:
        for rho in RHO_VALS:
            u = lookup_umbral(umbrales, esc, rho)
            print(
                f"  {esc:20s} rho={rho:.1f}  d_inv={u['d_inv']:.6g}  "
                f"U_I={u['U_I']:.6g}  U_II={u['U_II']:.6g}  "
                f"T_PRU_tabla={u['T_PRU']:.2f}"
            )
    print()

    filas: list[dict[str, Any]] = []
    for escenario in SCENARIOS:
        esc = cargar_escenario(escenario)
        for rho in RHO_VALS:
            u = lookup_umbral(umbrales, escenario, rho)
            hs: list[float] = []
            nus: list[float] = []
            print(
                f"== {escenario} rho={rho}  N={n_runs}  "
                f"U_I={u['U_I']:.6g} U_II={u['U_II']:.6g}",
                flush=True,
            )
            for i in range(n_runs):
                semilla = (
                    SEED_BASE
                    + i
                    + int(1_000_000 * float(rho))
                    + int(10_000 * float(u["d_inv"]))
                )
                res = simular_una_corrida(
                    esc=esc,
                    rho=float(rho),
                    u_i=float(u["U_I"]),
                    u_ii=float(u["U_II"]),
                    semilla=semilla,
                    max_pasos=max_pasos,
                )
                hs.append(res["H"])
                nus.append(res["nu_TH"])
                del res
                gc.collect()
                if (i + 1) % 10 == 0 or (i + 1) == n_runs:
                    print(f"   corrida {i + 1}/{n_runs}", flush=True)

            h_mean, h_std = _media_std(hs)
            nu_mean, nu_std = _media_std(nus)
            fila = {
                "escenario": escenario,
                "rho": rho,
                "H_mean": h_mean,
                "H_std": h_std,
                "nu_TH_mean": nu_mean,
                "nu_TH_std": nu_std,
            }
            filas.append(fila)
            print(
                f"   H = {h_mean:.4f} +/- {h_std:.4f}   "
                f"nu_TH = {nu_mean:.4f} +/- {nu_std:.4f}",
                flush=True,
            )

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "escenario",
                "rho",
                "H_mean",
                "H_std",
                "nu_TH_mean",
                "nu_TH_std",
            ],
        )
        writer.writeheader()
        writer.writerows(filas)
    return filas


def _imprimir_resumen(filas: list[dict[str, Any]], out_csv: Path) -> None:
    print()
    print("=" * 72)
    print("Resumen H y nu_TH  (media +/- std, N corridas)")
    print("=" * 72)
    print(f"{'escenario':22s} {'rho':>5s}  {'H':>18s}  {'nu_TH':>18s}")
    for fila in filas:
        print(
            f"{fila['escenario']:22s} {fila['rho']:5.1f}  "
            f"{fila['H_mean']:8.4f} +/- {fila['H_std']:<7.4f}  "
            f"{fila['nu_TH_mean']:8.4f} +/- {fila['nu_TH_std']:<7.4f}"
        )
    print(f"\nCSV: {out_csv}")
    avion = [f for f in filas if f["escenario"] == "avion_dos_puertas"]
    if avion and all(f["H_mean"] <= 0.0 for f in avion):
        print(
            "AVISO: H_mean=0 en avión (se esperaba H>0 por diversificación de "
            "puertas/rutas). No se inventan valores; revisar instrumentación."
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n-sims", type=int, default=N_RUNS_DEFAULT)
    parser.add_argument("--tabla", type=Path, default=TABLA_COMPARACION)
    parser.add_argument("--out", type=Path, default=OUT_DEFAULT)
    parser.add_argument("--max-pasos", type=int, default=MAX_PASOS)
    args = parser.parse_args()
    if args.n_sims <= 0:
        raise SystemExit("--n-sims debe ser > 0")
    try:
        filas = ejecutar(
            n_runs=int(args.n_sims),
            tabla_comparacion=args.tabla,
            out_csv=args.out,
            max_pasos=int(args.max_pasos),
        )
    except Exception as exc:
        print(f"ERROR en barrido_herd: {exc}", file=sys.stderr)
        raise
    _imprimir_resumen(filas, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
