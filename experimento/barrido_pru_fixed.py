"""Barrido con la misma semilla global en PFF corregido y PRU pru_fixed.

No modifica los barridos anteriores. Cada corrida llama random.seed(semilla)
y np.random.seed(semilla) antes de mover agentes.
"""

from __future__ import annotations

import argparse
import csv
import importlib
import random
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experimento.barrido_pff import (  # noqa: E402
    D_INV_VALS,
    MAX_PASOS,
    N_SIMS,
    RHO_VALS,
    SEED_BASE,
    _generar_posiciones_iniciales,
)
from experimento.metricas import calcular_metricas, combinar_metricas  # noqa: E402
from simulacion.agent_extendido import AgentExtendido, mover_agentes_con_conflictos  # noqa: E402
from simulacion.agentes import Agente, mover_agentes  # noqa: E402
from simulacion.grilla.floor_field import Floor_field  # noqa: E402
from simulacion.nodos.path_selector import PathSelector  # noqa: E402


def sembrar_corrida(semilla: int) -> None:
    """Misma semilla para el módulo random y para numpy."""
    random.seed(semilla)
    np.random.seed(semilla)


def semilla_de(rho: float, d_inv: float, i: int) -> int:
    return SEED_BASE + i + int(1_000_000 * float(rho)) + int(10_000 * float(d_inv))


def load_scenario(name: str) -> dict[str, Any]:
    esc = importlib.import_module(f"escenarios.{name}")
    return {
        "width": int(esc.width),
        "height": int(esc.height),
        "puertas": list(esc.puertas),
        "obstaculos": list(getattr(esc, "obstaculos", []) or []),
    }


def _frames_desde_agentes(agentes, conflictos: int) -> dict[str, Any]:
    snapshot = [
        SimpleNamespace(
            activo=a.activo,
            stress=getattr(a, "stress", None),
            ansiedad=getattr(a, "ansiedad", None),
            U_I=getattr(a, "U_I", None),
            U_II=getattr(a, "U_II", None),
        )
        for a in agentes
    ]
    return {"agentes": snapshot, "conflictos": conflictos}


def simular_pff(esc, rho: float, d_inv: float, semilla: int) -> list[dict]:
    sembrar_corrida(semilla)
    ff = Floor_field(esc["width"], esc["height"], esc["puertas"], esc["obstaculos"])
    rng = random.Random(semilla)
    posiciones = _generar_posiciones_iniciales(
        esc["width"], esc["height"], esc["obstaculos"], rho, rng
    )
    u_i = 1.0 / d_inv
    agentes = [
        Agente(x, y, ff, U_I=u_i, U_II=2.0 * u_i, ramirez2021=True) for x, y in posiciones
    ]
    historia = []
    for _ in range(MAX_PASOS):
        if not any(a.activo for a in agentes):
            break
        conflictos = mover_agentes(agentes)
        historia.append(_frames_desde_agentes(agentes, conflictos))
    if not historia:
        historia.append({"agentes": [], "conflictos": 0})
    return historia


def simular_pru(esc, rho: float, d_inv: float, semilla: int) -> list[dict]:
    sembrar_corrida(semilla)
    ff = Floor_field(esc["width"], esc["height"], esc["puertas"], esc["obstaculos"])
    selector = PathSelector(ff, umbral_recalculo=0.6, anxiety_thresholds=(30, 70), pru_fixed=True)
    AgentExtendido.instances = []
    AgentExtendido.history = []
    AgentExtendido.ruta_log = []
    rng = random.Random(semilla)
    posiciones = _generar_posiciones_iniciales(
        esc["width"], esc["height"], esc["obstaculos"], rho, rng
    )
    u_i = 1.0 / d_inv
    for x, y in posiciones:
        AgentExtendido(
            agent_type="rapido",
            floor_field=ff,
            path_selector=selector,
            x=x,
            y=y,
            U_I=u_i,
            U_II=2.0 * u_i,
            pru_fixed=True,
        )
    historia = []
    for step in range(MAX_PASOS):
        activos = [a for a in AgentExtendido.instances if a.activo]
        if not activos:
            break
        for a in activos:
            a._current_simulation_step = step
        stats = mover_agentes_con_conflictos(AgentExtendido.instances)
        historia.append(_frames_desde_agentes(AgentExtendido.instances, stats.get("conflictos", 0)))
    if not historia:
        historia.append({"agentes": [], "conflictos": 0})
    return historia


def ejecutar(esc, motor: str, n_sims: int) -> dict[str, Any]:
    simular = simular_pru if motor == "pru_fixed" else simular_pff
    resultados = []
    total = len(RHO_VALS) * len(D_INV_VALS)
    hechas = 0
    for rho in RHO_VALS:
        for d_inv in D_INV_VALS:
            parciales = []
            for i in range(n_sims):
                semilla = semilla_de(float(rho), float(d_inv), i)
                parciales.append(calcular_metricas(simular(esc, float(rho), float(d_inv), semilla)))
            resultados.append(
                {
                    "rho": float(rho),
                    "d_inv": float(d_inv),
                    "U_I": float(1.0 / d_inv),
                    "U_II": float(2.0 / d_inv),
                    "metricas": combinar_metricas(parciales),
                }
            )
            hechas += 1
            print(f"Progreso {motor}: {hechas}/{total}", flush=True)
    return {"meta": {"n_sims": n_sims, "motor": motor}, "resultados": resultados}


def escribir_csv(data: dict[str, Any], ruta: Path) -> None:
    n_sims = int(data["meta"]["n_sims"])
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["rho", "d_inv", "T_mean", "sigma_T", "fI", "fII", "fIII", "n_sims"],
        )
        writer.writeheader()
        for entrada in data["resultados"]:
            metricas = entrada["metricas"] or {}
            fr = metricas.get("fraccion_stress") or {}
            writer.writerow(
                {
                    "rho": entrada["rho"],
                    "d_inv": entrada["d_inv"],
                    "T_mean": metricas.get("T"),
                    "sigma_T": metricas.get("sigma_T"),
                    "fI": fr.get("mild"),
                    "fII": fr.get("optimal"),
                    "fIII": fr.get("anxiety"),
                    "n_sims": n_sims,
                }
            )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", required=True, choices=["sala_de_clases", "avion_dos_puertas"])
    parser.add_argument("--motor", required=True, choices=["pru_fixed", "pff_ramirez"])
    parser.add_argument("--n_sims", type=int, default=N_SIMS)
    args = parser.parse_args()
    esc = load_scenario(args.scenario)
    print(f"{args.motor} {args.scenario} N_SIMS={args.n_sims}", flush=True)
    data = ejecutar(esc, args.motor, args.n_sims)
    if args.motor == "pru_fixed":
        nombre = f"tabla_{args.scenario}_pru_fixed.csv"
    else:
        nombre = f"tabla_{args.scenario}_pff_ramirez2021_seeded.csv"
    destino = ROOT / nombre
    escribir_csv(data, destino)
    print(f"Saved {destino}")


if __name__ == "__main__":
    main()
