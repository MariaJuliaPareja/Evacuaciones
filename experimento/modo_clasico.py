"""Baseline de simulacion clasica con floor field y Agente base."""

from __future__ import annotations

import random
from types import SimpleNamespace
from typing import Any

import numpy as np

from experimento.config import MAX_PASOS, N_RUNS, RHO_VALS, SEED_BASE, grilla_umbrales
from experimento.metricas import calcular_metricas

try:
    from simulacion.floor_field import Floor_field  
except ImportError:
    from simulacion.grilla.floor_field import Floor_field  

from simulacion.agentes import Agente, mover_agentes

# [DUDA] N_RUNS, RHO_VALS, SEED_BASE y la grilla se importan de config.py; esta función recibe rho y n_sims por argumento y la semilla sigue en 2026+i
_ = (N_RUNS, RHO_VALS, SEED_BASE, grilla_umbrales)


def _normalizar_escenario(escenario: Any) -> dict[str, Any]:
    """
    Convierte `escenario` a un diccionario con campos necesarios.

    Acepta:
    - Modulo/objeto con atributos: width, height, puertas, obstaculos.
    - Diccionario con esas mismas claves.
    """
    if isinstance(escenario, dict):
        width = int(escenario["width"])
        height = int(escenario["height"])
        puertas = list(escenario["puertas"])
        obstaculos = list(escenario.get("obstaculos", []))
    else:
        width = int(getattr(escenario, "width"))
        height = int(getattr(escenario, "height"))
        puertas = list(getattr(escenario, "puertas"))
        obstaculos = list(getattr(escenario, "obstaculos", []))

    return {
        "width": width,
        "height": height,
        "puertas": puertas,
        "obstaculos": obstaculos,
    }


def _posiciones_iniciales(
    width: int, height: int, obstaculos: list[tuple[int, int]], rho: float, rng: random.Random
) -> list[tuple[int, int]]:
    """Genera posiciones interiores libres en funcion de la densidad inicial rho."""
    libres = [
        (x, y)
        for x in range(1, width - 1)
        for y in range(1, height - 1)
        if (x, y) not in obstaculos
    ]
    n_agentes = max(1, int(round(rho * len(libres))))
    n_agentes = min(n_agentes, len(libres))
    return rng.sample(libres, n_agentes)


def _simular_una_corrida(
    width: int,
    height: int,
    puertas: list[tuple[int, int]],
    obstaculos: list[tuple[int, int]],
    rho: float,
    semilla: int,
) -> list[dict]:
    """
    Ejecuta una simulacion clasica (sin stress efectivo) y retorna historia por frames.
    """
    rng = random.Random(semilla)
    np.random.seed(semilla)

    campo = Floor_field(width, height, puertas, obstaculos)
    posiciones = _posiciones_iniciales(width, height, obstaculos, rho, rng)

    # [CAMBIO] antes: Agente() sin ramirez2021, el motor PFF anterior -> ahora: ramirez2021=True explícito
    # [DUDA] con U=1e9 todos están en etapa I y la regla 1 espera el mínimo absoluto (ya no es el greedy de Varas al mínimo libre)
    agentes = [
        Agente(x, y, campo, U_I=10**9, U_II=10**9, ramirez2021=True) for (x, y) in posiciones
    ]

    historia: list[dict] = []
    for _ in range(MAX_PASOS):
        if not any(a.activo for a in agentes):
            break

        mover_agentes(agentes)
        historia.append(
            {
                "agentes": [SimpleNamespace(activo=a.activo) for a in agentes],
            }
        )

    if not historia:
        historia.append({"agentes": []})
    return historia


def correr_simulacion_clasica(escenario, rho, n_sims) -> dict:
    """
    Corre un ensemble del modelo clasico floor field usando solo `Agente` base.

    Parametros
    ----------
    escenario : module | object | dict
        Escenario con `width`, `height`, `puertas` y opcional `obstaculos`.
    rho : float
        Densidad inicial de agentes (0, 1] sobre celdas interiores libres.
    n_sims : int
        Cantidad de simulaciones del ensemble.

    Retorna
    -------
    dict
        Mismo formato de `metricas.calcular_metricas`:
        - `T`: int
        - `sigma_T`: float
        - `fraccion_stress`: None (baseline clasico sin stress)
        - `n_colisiones`: None
    """
    if n_sims <= 0:
        return None

    esc = _normalizar_escenario(escenario)
    ensemble: list[list[dict]] = []

    for i in range(int(n_sims)):
        semilla = 2026 + i
        historia = _simular_una_corrida(
            width=esc["width"],
            height=esc["height"],
            puertas=esc["puertas"],
            obstaculos=esc["obstaculos"],
            rho=float(rho),
            semilla=semilla,
        )
        ensemble.append(historia)

    metricas = calcular_metricas(ensemble)
    if metricas is None:
        return None

    metricas["fraccion_stress"] = None
    metricas["n_colisiones"] = None
    return metricas
