"""Mide el efecto de PathSelector._add_path_noise sin editar el motor.

20 corridas, rho=1, aula y avion_dos_puertas, U_II = 2 U_I.
U_I: 1000, el optimo del PFF corregido (aula 15.8489, avion 63.0957) y 1.
Cada corrida usa random.seed(semilla) ademas del generador de posiciones.
"""

from __future__ import annotations

import csv
import importlib
import random
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experimento.barrido_propuesta1 import (  # noqa: E402
    MAX_PASOS,
    SEED_BASE,
    _generar_posiciones_iniciales,
)
from simulacion.agent_extendido import AgentExtendido, mover_agentes_con_conflictos  # noqa: E402
from simulacion.grilla.floor_field import Floor_field  # noqa: E402
from simulacion.nodos.path_selector import PathSelector  # noqa: E402

OUT = ROOT / "diagnostics" / "out"
N_RUNS = 20
RHO = 1.0

# Valores exactos de np.logspace(-3, 0, 16): indices 0, 9, 6 y 15.
U_I_BY_SCENARIO = {
    "sala_de_clases": (1000.0, 10 ** 1.2, 1.0),
    "avion_dos_puertas": (1000.0, 10 ** 1.8, 1.0),
}


def load_scenario(name: str) -> dict:
    esc = importlib.import_module(f"escenarios.{name}")
    return {
        "width": int(esc.width),
        "height": int(esc.height),
        "puertas": list(esc.puertas),
        "obstaculos": list(getattr(esc, "obstaculos", []) or []),
    }


def stage_of(ansiedad: float, u_i: float, u_ii: float) -> str:
    if ansiedad <= u_i:
        return "I"
    if ansiedad <= u_ii:
        return "II"
    return "III"


def chebyshev(a: tuple[int, int], b: tuple[int, int]) -> int:
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def segment_cells(a: tuple[int, int], b: tuple[int, int]) -> list[tuple[int, int]]:
    x0, y0 = a
    x1, y1 = b
    n = max(abs(x1 - x0), abs(y1 - y0))
    if n == 0:
        return [a]
    cells = []
    for i in range(n + 1):
        cells.append((int(round(x0 + (x1 - x0) * i / n)), int(round(y0 + (y1 - y0) * i / n))))
    return cells


def step_flags(a: tuple[int, int], b: tuple[int, int], ff: Floor_field) -> tuple[bool, bool]:
    """(no es vecina de Chebyshev 1, el segmento toca pared u obstaculo)."""
    non_neighbor = chebyshev(a, b) > 1
    crosses = False
    for x, y in segment_cells(a, b):
        if not (0 <= x < ff.width and 0 <= y < ff.height) or ff.valores[y, x] >= 500:
            crosses = True
            break
    return non_neighbor, crosses


class Recorder:
    def __init__(self, ff: Floor_field):
        self.ff = ff
        self.n_routes = 0
        self.n_routes_noise = 0
        self.n_routes_non_neighbor = 0
        self.n_routes_cross = 0
        self.n_routes_bad = 0
        self.n_plan_steps = 0
        self.n_plan_non_neighbor = 0
        self.n_plan_cross = 0
        self.n_moves = 0
        self.n_moves_far = 0
        self.n_moves_wall = 0
        self.n_moves_occupied = 0
        self.n_moves_bad = 0
        self.bad_by_stage = {"I": 0, "II": 0, "III": 0}
        self.far_by_stage = {"I": 0, "II": 0, "III": 0}
        self.examples: list[str] = []

    def add_route(self, path: list[tuple[int, int]], noise: bool) -> None:
        self.n_routes += 1
        if noise:
            self.n_routes_noise += 1
        route_non = False
        route_cross = False
        if path:
            for a, b in zip(path, path[1:]):
                self.n_plan_steps += 1
                non_neighbor, crosses = step_flags(a, b, self.ff)
                if non_neighbor:
                    self.n_plan_non_neighbor += 1
                    route_non = True
                if crosses:
                    self.n_plan_cross += 1
                    route_cross = True
        if route_non:
            self.n_routes_non_neighbor += 1
        if route_cross:
            self.n_routes_cross += 1
        if route_non or route_cross:
            self.n_routes_bad += 1

    def add_move(self, old, new, stage: str, occupied_before: dict) -> None:
        if old == new or old[0] is None:
            return
        self.n_moves += 1
        far = chebyshev(old, new) > 1
        wall = (
            not (0 <= new[0] < self.ff.width and 0 <= new[1] < self.ff.height)
            or self.ff.valores[new[1], new[0]] >= 500
        )
        occupied = occupied_before.get(new, 0) > 0
        if far:
            self.n_moves_far += 1
            self.far_by_stage[stage] += 1
        if wall:
            self.n_moves_wall += 1
        if occupied:
            self.n_moves_occupied += 1
        if far or wall or occupied:
            self.n_moves_bad += 1
            self.bad_by_stage[stage] += 1
            if len(self.examples) < 8:
                self.examples.append(f"{old}->{new} stage={stage} far={far} wall={wall} occ={occupied}")


def install_patches(rec: Recorder, u_i: float, u_ii: float):
    orig_select = PathSelector.select_path_by_anxiety
    orig_move = mover_agentes_con_conflictos

    def select(self, *args, **kwargs):
        path = orig_select(self, *args, **kwargs)
        noise = bool(self.anxiety_decisions and self.anxiety_decisions[-1].get("noise_added"))
        rec.add_route(list(path) if path else [], noise)
        return path

    def move(agentes, goals=None):
        before = {}
        occupied: dict[tuple[int, int], int] = {}
        for agente in agentes:
            if not agente.activo or agente.pos_x is None:
                continue
            pos = (agente.pos_x, agente.pos_y)
            before[agente.id] = (pos, stage_of(agente.ansiedad, u_i, u_ii))
            occupied[pos] = occupied.get(pos, 0) + 1
        stats = orig_move(agentes, goals)
        for agente in agentes:
            if agente.id not in before:
                continue
            old, stage = before[agente.id]
            new = (agente.pos_x, agente.pos_y)
            rec.add_move(old, new, stage, occupied)
        return stats

    PathSelector.select_path_by_anxiety = select
    return move, orig_select


def restore_select(orig_select) -> None:
    PathSelector.select_path_by_anxiety = orig_select


def run_once(esc: dict, u_i: float, semilla: int, move_fn) -> None:
    random.seed(semilla)
    np.random.seed(semilla)
    ff = Floor_field(esc["width"], esc["height"], esc["puertas"], esc["obstaculos"])
    # El barrido construye el selector con (30, 70); la eleccion usa U_I, U_II del agente.
    selector = PathSelector(ff, umbral_recalculo=0.6, anxiety_thresholds=(30, 70))
    AgentExtendido.instances = []
    AgentExtendido.history = []
    AgentExtendido.ruta_log = []
    rng = random.Random(semilla)
    posiciones = _generar_posiciones_iniciales(
        esc["width"], esc["height"], esc["obstaculos"], RHO, rng
    )
    for x, y in posiciones:
        AgentExtendido(
            agent_type="rapido",
            floor_field=ff,
            path_selector=selector,
            x=x,
            y=y,
            U_I=u_i,
            U_II=2.0 * u_i,
        )
    for step in range(MAX_PASOS):
        activos = [a for a in AgentExtendido.instances if a.activo]
        if not activos:
            break
        for a in activos:
            a._current_simulation_step = step
        move_fn(AgentExtendido.instances)


def pct(num: int, den: int) -> float:
    return 100.0 * num / den if den else 0.0


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for scenario, u_values in U_I_BY_SCENARIO.items():
        esc = load_scenario(scenario)
        for u_i in u_values:
            rec = Recorder(
                Floor_field(esc["width"], esc["height"], esc["puertas"], esc["obstaculos"])
            )
            move_fn, orig_select = install_patches(rec, u_i, 2.0 * u_i)
            try:
                for i in range(N_RUNS):
                    semilla = SEED_BASE + i + int(1_000_000 * RHO) + int(10_000 * (1.0 / u_i))
                    run_once(esc, u_i, semilla, move_fn)
                    print(
                        f"{scenario} U_I={u_i:.4g} {i + 1}/{N_RUNS} "
                        f"routes_bad={rec.n_routes_bad}/{rec.n_routes} "
                        f"moves_bad={rec.n_moves_bad}/{rec.n_moves}",
                        flush=True,
                    )
            finally:
                restore_select(orig_select)
            rows.append(
                {
                    "scenario": scenario,
                    "rho": RHO,
                    "U_I": u_i,
                    "U_II": 2.0 * u_i,
                    "n_runs": N_RUNS,
                    "n_routes": rec.n_routes,
                    "n_routes_noise": rec.n_routes_noise,
                    "pct_routes_noise": pct(rec.n_routes_noise, rec.n_routes),
                    "pct_routes_non_neighbor": pct(rec.n_routes_non_neighbor, rec.n_routes),
                    "pct_routes_cross_wall": pct(rec.n_routes_cross, rec.n_routes),
                    "pct_routes_bad": pct(rec.n_routes_bad, rec.n_routes),
                    "n_plan_steps": rec.n_plan_steps,
                    "pct_plan_steps_non_neighbor": pct(rec.n_plan_non_neighbor, rec.n_plan_steps),
                    "n_moves": rec.n_moves,
                    "n_moves_far": rec.n_moves_far,
                    "n_moves_wall": rec.n_moves_wall,
                    "n_moves_occupied": rec.n_moves_occupied,
                    "n_moves_bad": rec.n_moves_bad,
                    "pct_moves_bad": pct(rec.n_moves_bad, rec.n_moves),
                    "pct_moves_far": pct(rec.n_moves_far, rec.n_moves),
                    "bad_stage_I": rec.bad_by_stage["I"],
                    "bad_stage_II": rec.bad_by_stage["II"],
                    "bad_stage_III": rec.bad_by_stage["III"],
                    "far_stage_I": rec.far_by_stage["I"],
                    "far_stage_II": rec.far_by_stage["II"],
                    "far_stage_III": rec.far_by_stage["III"],
                    "examples": " | ".join(rec.examples),
                }
            )
    dest = OUT / "path_noise_resumen.csv"
    with dest.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {dest}")


if __name__ == "__main__":
    main()
