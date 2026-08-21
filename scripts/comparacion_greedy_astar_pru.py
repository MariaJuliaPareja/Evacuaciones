"""Comparación Greedy / A* puro / PRU-A* (rho=1.0, umbral óptimo PRU).

Motores — modos YA EXISTENTES del repo, no reimplementaciones nuevas:

  Greedy  AgentExtendido con path_selector=None
          → _movimiento_greedy_floor_field (descenso local de floor field,
            4 vecinos). Mismo resolver de conflictos que PRU-A*.
          No es Greedy Best-First de Wayahdi et al. (2021) Fig. 7; ese
          algoritmo no está en el repositorio. Tampoco es el PFF de
          simulacion.agentes.Agente (8 vecinos + mover_agentes).

  A*      PathSelector + k_paths_max=1
          → find_progressive_paths(num_paths=1) = un solo A* óptimo,
            recálculo bajo demanda (cooldown / should_recalculate).
          Sin desbloqueo 1→3→5. No es un motor aparte: es el stack
          PRU-A* con k_paths_max=1 (parámetro ya cableado).

  PRU-A*  Motor completo actual (k_paths_max=5, default).

Si en el futuro se exige un Greedy/A* literal de Wayahdi Fig. 7, hay que
implementarlo como motor separado; este script no lo inventa.

Usage:
  PYTHONPATH=. python scripts/comparacion_greedy_astar_pru.py
  PYTHONPATH=. python scripts/comparacion_greedy_astar_pru.py --n-sims 2
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
RHO = 1.0
N_RUNS_DEFAULT = 100
TABLA_COMPARACION = ROOT / "tabla_comparacion_pff_pru_fixed.csv"
OUT_DEFAULT = ROOT / "tabla_comparacion_greedy_astar_pru.csv"

# nombre CSV -> (usa PathSelector, k_paths_max)
MOTORES: dict[str, tuple[bool, int]] = {
    "Greedy": (False, 5),
    "A*": (True, 1),
    "PRU-A*": (True, 5),
}


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
                }
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
    usar_path_selector: bool,
    k_paths_max: int,
    max_pasos: int = MAX_PASOS,
) -> dict[str, float]:
    rng = random.Random(semilla)
    random.seed(semilla)
    np.random.seed(semilla)

    ff = Floor_field(esc["width"], esc["height"], esc["puertas"], esc["obstaculos"])
    path_selector = None
    if usar_path_selector:
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
            k_paths_max=k_paths_max,
        )

    door_map = puertas_logicas(esc["puertas"])
    door_cells = set(door_map)
    n_logical = len(set(door_map.values()))
    last_astar: dict[int, tuple[tuple[int, int], ...]] = {}
    route_keys: list[tuple] = []
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
        t_evac += 1

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
    _reset_agentes()
    return {
        "T": float(t_evac),
        "H": h,
        "n_egress": float(len(route_keys)),
        "n_unique_routes": float(len(set(route_keys))),
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
    print("Motores usados (existentes en el repo, no Wayahdi Fig. 7):")
    print("  Greedy = AgentExtendido(path_selector=None)")
    print("  A*     = PathSelector + k_paths_max=1")
    print("  PRU-A* = PathSelector + k_paths_max=5")
    print(f"rho={RHO} fijo; umbral = argmin T_PRU de {tabla_comparacion.name}")
    for escenario in SCENARIOS:
        u = lookup_umbral(umbrales, escenario, RHO)
        print(
            f"  {escenario}: d_inv={u['d_inv']:.6g}  "
            f"U_I={u['U_I']:.6g}  U_II={u['U_II']:.6g}  "
            f"T_PRU_tabla={u['T_PRU']:.2f}"
        )
    print()

    filas: list[dict[str, Any]] = []
    for escenario in SCENARIOS:
        esc = cargar_escenario(escenario)
        u = lookup_umbral(umbrales, escenario, RHO)
        for motor, (usar_ps, k_max) in MOTORES.items():
            ts: list[float] = []
            hs: list[float] = []
            print(
                f"== {escenario} motor={motor}  N={n_runs}  "
                f"U_I={u['U_I']:.6g} U_II={u['U_II']:.6g}",
                flush=True,
            )
            motor_offset = {"Greedy": 0, "A*": 1000, "PRU-A*": 2000}[motor]
            for i in range(n_runs):
                semilla = (
                    SEED_BASE
                    + i
                    + int(1_000_000 * float(RHO))
                    + int(10_000 * float(u["d_inv"]))
                    + motor_offset
                )
                res = simular_una_corrida(
                    esc=esc,
                    rho=float(RHO),
                    u_i=float(u["U_I"]),
                    u_ii=float(u["U_II"]),
                    semilla=semilla,
                    usar_path_selector=usar_ps,
                    k_paths_max=k_max,
                    max_pasos=max_pasos,
                )
                ts.append(res["T"])
                hs.append(res["H"])
                del res
                gc.collect()
                if (i + 1) % 10 == 0 or (i + 1) == n_runs:
                    print(f"   corrida {i + 1}/{n_runs}", flush=True)

            t_mean, t_std = _media_std(ts)
            h_mean, _h_std = _media_std(hs)
            fila = {
                "escenario": escenario,
                "motor": motor,
                "T_mean": t_mean,
                "T_std": t_std,
                "H_mean": h_mean,
            }
            filas.append(fila)
            print(
                f"   T = {t_mean:.2f} +/- {t_std:.2f}   H_mean = {h_mean:.4f}",
                flush=True,
            )

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["escenario", "motor", "T_mean", "T_std", "H_mean"]
        )
        writer.writeheader()
        writer.writerows(filas)
    return filas


def _imprimir_resumen(filas: list[dict[str, Any]], out_csv: Path) -> None:
    print()
    print("=" * 78)
    print("Comparación Greedy / A* / PRU-A*  (rho=1.0)")
    print("=" * 78)
    print(f"{'escenario':22s} {'motor':8s}  {'T_mean':>10s}  {'T_std':>10s}  {'H_mean':>10s}")
    for fila in filas:
        print(
            f"{fila['escenario']:22s} {fila['motor']:8s}  "
            f"{fila['T_mean']:10.3f}  {fila['T_std']:10.3f}  {fila['H_mean']:10.4f}"
        )
    print(f"\nCSV: {out_csv}")
    print(
        "H se mide; no se fuerza a 0 en Greedy/A*. En sala (1 puerta lógica) "
        "Greedy sin A* suele dar H=0 (todas las claves degeneran al mismo "
        "exit); A* puro puede ser >0 si hay varias secuencias A* distintas."
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
        print(f"ERROR en comparacion_greedy_astar_pru: {exc}", file=sys.stderr)
        raise
    _imprimir_resumen(filas, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
