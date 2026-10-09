"""Barrido PFF con el motor de Ramirez et al. 2021.

Mismos escenarios, densidades, umbrales (U_II = 2 U_I), N_SIMS y semillas
que experimento/barrido_pff.py. No modifica ese modulo ni sus CSV.
"""

from __future__ import annotations

import argparse
import csv
import importlib
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from experimento.barrido_pff import (  # noqa: E402
    D_INV_VALS,
    MAX_PASOS,
    N_SIMS,
    RHO_VALS,
    SEED_BASE,
    _generar_posiciones_iniciales,
    guardar_resultados,
)
from experimento.metricas import calcular_metricas, combinar_metricas  # noqa: E402
from simulacion.agentes import Agente, mover_agentes  # noqa: E402
from simulacion.grilla.floor_field import Floor_field  # noqa: E402
import random  # noqa: E402


def load_scenario(name: str) -> dict[str, Any]:
    esc = importlib.import_module(f"escenarios.{name}")
    return {
        "width": int(esc.width),
        "height": int(esc.height),
        "puertas": list(esc.puertas),
        "obstaculos": list(getattr(esc, "obstaculos", []) or []),
    }


def simular_una_historia(esc: dict[str, Any], rho: float, d_inv: float, semilla: int):
    rng = random.Random(semilla)
    np.random.seed(semilla)
    ff = Floor_field(esc["width"], esc["height"], esc["puertas"], esc["obstaculos"])
    posiciones = _generar_posiciones_iniciales(
        esc["width"], esc["height"], esc["obstaculos"], rho, rng
    )
    u_i = 1.0 / d_inv
    u_ii = 2.0 * u_i
    agentes = [
        Agente(x, y, ff, U_I=u_i, U_II=u_ii, ramirez2021=True)
        for (x, y) in posiciones
    ]
    historia = []
    for _ in range(MAX_PASOS):
        if not any(a.activo for a in agentes):
            break
        conflictos = mover_agentes(agentes)
        snapshot = [
            SimpleNamespace(
                activo=a.activo,
                stress=a.stress,
                U_I=a.U_I,
                U_II=a.U_II,
            )
            for a in agentes
        ]
        historia.append({"agentes": snapshot, "conflictos": conflictos})
    if not historia:
        historia.append({"agentes": [], "conflictos": 0})
    return historia


def ejecutar(esc: dict[str, Any], n_sims: int) -> dict[str, Any]:
    resultados: dict[str, Any] = {
        "meta": {
            "rho_vals": RHO_VALS,
            "d_inv_vals": [float(v) for v in D_INV_VALS],
            "n_sims": n_sims,
            "max_pasos": MAX_PASOS,
            "escenario": esc,
            "motor": "PFF",
            "tag": "ramirez2021",
        },
        "resultados": [],
    }
    total = len(RHO_VALS) * len(D_INV_VALS)
    hechas = 0
    for rho in RHO_VALS:
        for d_inv in D_INV_VALS:
            parciales = []
            for i in range(n_sims):
                semilla = SEED_BASE + i + int(1_000_000 * float(rho)) + int(10_000 * float(d_inv))
                historia = simular_una_historia(esc, float(rho), float(d_inv), semilla)
                parciales.append(calcular_metricas(historia))
            resultados["resultados"].append(
                {
                    "rho": float(rho),
                    "d_inv": float(d_inv),
                    "U_I": float(1.0 / d_inv),
                    "U_II": float(2.0 / d_inv),
                    "metricas": combinar_metricas(parciales),
                }
            )
            hechas += 1
            print(f"Progreso PFF ramirez2021: {hechas}/{total}", flush=True)
    return resultados


def escribir_csv(data: dict[str, Any], ruta: Path) -> None:
    n_sims = int(data["meta"]["n_sims"])
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["rho", "d_inv", "T_mean", "sigma_T", "fI", "fII", "fIII", "n_sims"],
        )
        writer.writeheader()
        for e in data["resultados"]:
            m = e["metricas"] or {}
            fr = m.get("fraccion_stress") or {}
            writer.writerow(
                {
                    "rho": e["rho"],
                    "d_inv": e["d_inv"],
                    "T_mean": m.get("T"),
                    "sigma_T": m.get("sigma_T"),
                    "fI": fr.get("mild"),
                    "fII": fr.get("optimal"),
                    "fIII": fr.get("anxiety"),
                    "n_sims": n_sims,
                }
            )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", required=True, choices=["sala_de_clases", "avion_dos_puertas"])
    parser.add_argument("--n_sims", type=int, default=N_SIMS)
    args = parser.parse_args()
    esc = load_scenario(args.scenario)
    print(f"PFF ramirez2021 scenario={args.scenario} N_SIMS={args.n_sims}", flush=True)
    data = ejecutar(esc, args.n_sims)
    pkl = ROOT_DIR / "salidas" / "experimentos" / f"barrido_pff_{args.scenario}_ramirez2021.pkl"
    csv_path = ROOT_DIR / f"tabla_{args.scenario}_ramirez2021.csv"
    guardar_resultados(data, pkl)
    escribir_csv(data, csv_path)
    print(f"Saved: {pkl}")
    print(f"Saved: {csv_path}")


if __name__ == "__main__":
    main()
