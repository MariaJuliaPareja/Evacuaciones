"""Barrido paramétrico para el baseline PFF puro.

Usa el agente clásico de floor field (`simulacion.agentes.Agente`) con
estrés Yerkes-Dodson y sin PathSelector ni AgentExtendido.
"""

from __future__ import annotations

import argparse
import inspect
import pickle
import random
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np

from experimento.config import D_INV_VALS, MAX_PASOS, N_RUNS, RHO_VALS, SEED_BASE
from experimento.metricas import calcular_metricas, combinar_metricas
import gc

# [CAMBIO] antes: N_SIMS = 100 se definía en este archivo -> ahora: alias de N_RUNS para scripts fuera de experimento/ que asignan barrido_pff.N_SIMS
N_SIMS = N_RUNS

try:
    from simulacion.grilla_clasica.floor_field import Floor_field
except ImportError:
    from simulacion.grilla.floor_field import Floor_field

try:
    from simulacion.agentes import Agente, mover_agentes
except ImportError:
    from simulacion.agentes import Agente, mover_agentes


def _cargar_escenario_base() -> dict[str, Any]:
    """Carga escenario base desde el módulo o usa fallback estándar."""
    try:
        from escenarios import escenario_base as esc

        return {
            "width": int(getattr(esc, "width")),
            "height": int(getattr(esc, "height")),
            "puertas": list(getattr(esc, "puertas")),
            "obstaculos": list(getattr(esc, "obstaculos", [])),
        }
    except Exception:
        width, height = 20, 14
        y_mid = height // 2
        puertas = [(0, y_mid - 1), (0, y_mid)]
        return {"width": width, "height": height, "puertas": puertas, "obstaculos": []}


def _generar_posiciones_iniciales(
    width: int, height: int, obstaculos: list[tuple[int, int]], rho: float, rng: random.Random
) -> list[tuple[int, int]]:
    """Genera posiciones iniciales libres en función de density rho."""
    libres = [
        (x, y)
        for x in range(1, width - 1)
        for y in range(1, height - 1)
        if (x, y) not in obstaculos
    ]
    n_agentes = max(1, int(round(rho * len(libres))))
    n_agentes = min(n_agentes, len(libres))
    return rng.sample(libres, n_agentes)


def _simular_una_historia(
    width: int,
    height: int,
    puertas: list[tuple[int, int]],
    obstaculos: list[tuple[int, int]],
    rho: float,
    d_inv: float,
    semilla: int,
) -> list[dict[str, Any]]:
    """Ejecuta una simulación PFF pura y retorna la historia de frames."""
    rng = random.Random(semilla)
    np.random.seed(semilla)

    ff = Floor_field(width, height, puertas, obstaculos)
    posiciones = _generar_posiciones_iniciales(width, height, obstaculos, rho, rng)

    d = 1.0 / d_inv
    u_i = d
    u_ii = 2.0 * d

    # [CAMBIO] antes: Agente() sin ramirez2021, el motor PFF anterior -> ahora: ramirez2021=True explícito
    agentes = [Agente(x, y, ff, U_I=u_i, U_II=u_ii, ramirez2021=True) for (x, y) in posiciones]

    historia_frames: list[dict[str, Any]] = []
    for _ in range(MAX_PASOS):
        activos = [a for a in agentes if a.activo]
        if not activos:
            break

        conflictos = mover_agentes(agentes)
        snapshot = [
            SimpleNamespace(
                activo=a.activo,
                stress=getattr(a, "stress", None),
                U_I=getattr(a, "U_I", None),
                U_II=getattr(a, "U_II", None),
            )
            for a in agentes
        ]
        historia_frames.append({"agentes": snapshot, "conflictos": conflictos})

    if not historia_frames:
        historia_frames.append({"agentes": [], "conflictos": 0})

    return historia_frames


def ejecutar_barrido(n_sims: int | None = None) -> dict[str, Any]:
    """Ejecuta el barrido PFF con ramirez2021=True y retorna un dict con los resultados."""
    if n_sims is None:
        n_sims = N_SIMS
    esc = _cargar_escenario_base()
    width = esc["width"]
    height = esc["height"]
    puertas = esc["puertas"]
    obstaculos = esc["obstaculos"]

    resultados: dict[str, Any] = {
        "meta": {
            "rho_vals": RHO_VALS,
            "d_inv_vals": [float(v) for v in D_INV_VALS],
            "n_sims": n_sims,
            "max_pasos": MAX_PASOS,
            "escenario": esc,
        },
        "resultados": [],
    }

    total_combinaciones = len(RHO_VALS) * len(D_INV_VALS)
    procesadas = 0

    for rho in RHO_VALS:
        for d_inv in D_INV_VALS:
            parciales: list[dict[str, Any]] = []
            for i in range(n_sims):
                semilla = SEED_BASE + i + int(1_000_000 * float(rho)) + int(10_000 * float(d_inv))
                historia = _simular_una_historia(
                    width=width,
                    height=height,
                    puertas=puertas,
                    obstaculos=obstaculos,
                    rho=float(rho),
                    d_inv=float(d_inv),
                    semilla=semilla,
                )
                parciales.append(calcular_metricas(historia))
                del historia
                gc.collect()

            metricas = combinar_metricas(parciales)
            resultados["resultados"].append(
                {
                    "rho": float(rho),
                    "d_inv": float(d_inv),
                    "U_I": float(1.0 / d_inv),
                    "U_II": float(2.0 / d_inv),
                    "metricas": metricas,
                }
            )
            procesadas += 1
            if procesadas % 10 == 0 or procesadas == total_combinaciones:
                print(
                    f"Progreso PFF: {procesadas}/{total_combinaciones} combinaciones completadas",
                    flush=True,
                )

    return resultados


def guardar_resultados(resultados: dict[str, Any], ruta_salida: Path) -> None:
    """Guarda resultados del barrido en archivo PKL."""
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    with ruta_salida.open("wb") as f:
        pickle.dump(resultados, f)


if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument("--n", type=int, default=N_RUNS)
        parser.add_argument(
            "--salida",
            type=Path,
            default=Path("salidas") / "experimentos" / "barrido_pff_base.pkl",
        )
        args = parser.parse_args()
        # [DUDA] el pkl no es un CSV: no lleva las columnas de procedencia
        data = ejecutar_barrido(args.n)
        guardar_resultados(data, args.salida)
        print(f"Barrido PFF completo. Archivo guardado en: {args.salida}")
    except KeyboardInterrupt:
        print("Ejecución interrumpida por el usuario.")
        sys.exit(1)
    except Exception as exc:
        print(f"Error durante el barrido PFF: {exc}")
        raise
