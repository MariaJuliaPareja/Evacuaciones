"""Forced-proposal baseline: same-dest conflict + indirect cell reuse."""
from __future__ import annotations

import pickle
import random
from collections import defaultdict
from pathlib import Path

import numpy as np

from escenarios import sala_de_clases as esc
from simulacion.grilla_clasica.floor_field import Floor_field
from simulacion.pathfinding_propuesta.agent_extendido import AgentExtendido, mover_agentes_con_conflictos
from simulacion.pathfinding_propuesta.path_selector import PathSelector

# Forced proposals that reproduce the diagnosed bug pattern under buggy resolver:
# agent0 at (8,3) and agent14 at (8,5) both want (7,4); agent13 at (8,2) wants (8,3).
FORCED = {
    0: (7, 4),
    13: (8, 3),
    14: (7, 4),
}


def _overlaps(agentes):
    by = defaultdict(list)
    for a in agentes:
        if a.activo and a.pos_x is not None:
            by[(a.pos_x, a.pos_y)].append(a.id)
    return [(p, ids) for p, ids in by.items() if len(ids) >= 2]


def run_forced(seed: int = 0) -> dict:
    random.seed(seed)
    np.random.seed(seed)
    ff = Floor_field(esc.width, esc.height, esc.puertas, esc.obstaculos)
    ps = PathSelector(ff, umbral_recalculo=0.6, anxiety_thresholds=(30, 70))
    AgentExtendido.instances = []
    AgentExtendido.history = []
    AgentExtendido.ruta_log = []

    starts = [(8, 3, "rapido"), (8, 2, "lento"), (8, 5, "lento")]
    # ids will be 0,1,2 — remap forced keys to these ids
    forced_local = {0: (7, 4), 1: (8, 3), 2: (7, 4)}

    for x, y, tipo in starts:
        AgentExtendido(
            agent_type=tipo,
            floor_field=ff,
            path_selector=ps,
            x=x,
            y=y,
            U_I=25.0,
            U_II=50.0,
        )

    agentes = list(AgentExtendido.instances)

    def _forced_propose(self, goal=None, agent_positions=None):
        return forced_local[self.id]

    # Patch instance method for this run only
    for a in agentes:
        a.proponer_movimiento = _forced_propose.__get__(a, AgentExtendido)

    before = {a.id: (a.pos_x, a.pos_y) for a in agentes}
    stats = mover_agentes_con_conflictos(agentes)
    after = {a.id: (a.pos_x, a.pos_y) for a in agentes}
    ov = _overlaps(agentes)
    return {
        "seed": seed,
        "stats": dict(stats),
        "before": before,
        "after": after,
        "overlaps": ov,
        "n_overlap_events": len(ov),
        "same_dest_conflict_recorded": int(stats.get("conflictos", 0)),
        "n_moved": sum(1 for i in before if before[i] != after[i]),
    }


if __name__ == "__main__":
    import sys

    mode = sys.argv[1] if len(sys.argv) > 1 else "before"
    out = Path(f"salidas/experimentos/smoke/conflict_baseline_{mode}.pkl")
    out.parent.mkdir(parents=True, exist_ok=True)
    data = run_forced(0)
    with out.open("wb") as f:
        pickle.dump(data, f)
    print(f"[{mode}] {data}")
    print("SAVED", out)
