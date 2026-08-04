"""Barrido de parametros para la propuesta 1 de evacuacion."""

from __future__ import annotations

import inspect
import pickle
import random
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np


from simulacion.grilla_clasica.floor_field import Floor_field
from simulacion.pathfinding_propuesta.agent_extendido import AgentExtendido, mover_agentes_con_conflictos
from experimento.metricas import calcular_metricas


RHO_VALS = [0.25, 0.50, 0.75, 1.0]
D_INV_VALS = np.logspace(-3, 0, 16)
N_SIMS = 100
MAX_PASOS = 500
SEED_BASE = 12345


def _cargar_escenario_base() -> dict[str, Any]:
    """
    Carga escenario base desde modulo si existe, o crea fallback.

    Fallback: sala de 20x14 con una salida central de ancho 2 en el borde izquierdo.
    """
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
    """
    Genera posiciones iniciales segun densidad rho sobre celdas libres interiores.
    """
    libres = [
        (x, y)
        for x in range(1, width - 1)
        for y in range(1, height - 1)
        if (x, y) not in obstaculos
    ]
    n_agentes = max(1, int(round(rho * len(libres))))
    n_agentes = min(n_agentes, len(libres))
    return rng.sample(libres, n_agentes)


def _crear_agente(
    floor_field: Floor_field,
    posicion: tuple[int, int],
    u_i: float,
    u_ii: float,
    ya_reportado_todo: bool,
) -> bool:
    """
    Crea un AgentExtendido intentando inyectar U_I/U_II si la clase lo soporta.

    Retorna True si ya se reporto el TODO de compatibilidad.
    """
    firma = inspect.signature(AgentExtendido.__init__)
    params = firma.parameters
    kwargs = {
        "agent_type": "rapido",
        "floor_field": floor_field,
        "path_selector": None,
        "x": posicion[0],
        "y": posicion[1],
    }

    if "U_I" in params and "U_II" in params:
        kwargs["U_I"] = u_i
        kwargs["U_II"] = u_ii
    elif not ya_reportado_todo:
        print(
            "TODO: agregar soporte de parametros U_I y U_II en AgentExtendido "
            "para modelar umbrales de ansiedad de la propuesta 1."
        )
        ya_reportado_todo = True

    AgentExtendido(**kwargs)
    return ya_reportado_todo


def _simular_una_historia(
    width: int,
    height: int,
    puertas: list[tuple[int, int]],
    obstaculos: list[tuple[int, int]],
    rho: float,
    d_inv: float,
    semilla: int,
    ya_reportado_todo: bool,
) -> tuple[list[dict[str, Any]], bool]:
    """
    Ejecuta una simulacion y retorna historia en formato de frames para metricas.
    """
    rng = random.Random(semilla)
    np.random.seed(semilla)

    ff = Floor_field(width, height, puertas, obstaculos)
    AgentExtendido.instances = []
    AgentExtendido.history = []

    posiciones = _generar_posiciones_iniciales(width, height, obstaculos, rho, rng)
    d = 1.0 / d_inv
    u_i = d
    u_ii = 2.0 * d

    for pos in posiciones:
        ya_reportado_todo = _crear_agente(ff, pos, u_i, u_ii, ya_reportado_todo)

    historia_frames: list[dict[str, Any]] = []

    for _ in range(MAX_PASOS):
        activos = [a for a in AgentExtendido.instances if a.activo]
        if not activos:
            break

        stats = mover_agentes_con_conflictos(AgentExtendido.instances)

        snapshot = [
            SimpleNamespace(
                activo=a.activo,
                ansiedad=getattr(a, "ansiedad", None),
                U_I=getattr(a, "U_I", None),
                U_II=getattr(a, "U_II", None),
            )
            for a in AgentExtendido.instances
        ]
        historia_frames.append(
            {
                "agentes": snapshot,
                "conflictos": stats.get("conflictos", 0),
            }
        )

    if not historia_frames:
        historia_frames.append({"agentes": [], "conflictos": 0})

    return historia_frames, ya_reportado_todo


def ejecutar_barrido() -> dict[str, Any]:
    """
    Ejecuta barrido sobre (rho, 1/d) y calcula metricas por combinacion.
    """
    esc = _cargar_escenario_base()
    width = esc["width"]
    height = esc["height"]
    puertas = esc["puertas"]
    obstaculos = esc["obstaculos"]

    resultados: dict[str, Any] = {
        "meta": {
            "rho_vals": RHO_VALS,
            "d_inv_vals": [float(v) for v in D_INV_VALS],
            "n_sims": N_SIMS,
            "max_pasos": MAX_PASOS,
            "escenario": {
                "width": width,
                "height": height,
                "puertas": puertas,
                "obstaculos": obstaculos,
            },
        },
        "resultados": [],
    }

    total_combinaciones = len(RHO_VALS) * len(D_INV_VALS)
    procesadas = 0
    todo_reportado = False

    for rho in RHO_VALS:
        for d_inv in D_INV_VALS:
            ensemble: list[list[dict[str, Any]]] = []

            for i in range(N_SIMS):
                semilla = SEED_BASE + i + int(1_000_000 * float(rho)) + int(10_000 * float(d_inv))
                historia, todo_reportado = _simular_una_historia(
                    width=width,
                    height=height,
                    puertas=puertas,
                    obstaculos=obstaculos,
                    rho=float(rho),
                    d_inv=float(d_inv),
                    semilla=semilla,
                    ya_reportado_todo=todo_reportado,
                )
                ensemble.append(historia)

            metricas = calcular_metricas(ensemble)

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
            if procesadas % 10 == 0:
                print(f"Progreso: {procesadas}/{total_combinaciones} combinaciones completadas")

    return resultados


def guardar_resultados(resultados: dict[str, Any], ruta_salida: Path) -> None:
    """Guarda resultados del barrido en archivo PKL."""
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    with ruta_salida.open("wb") as f:
        pickle.dump(resultados, f)


if __name__ == "__main__":
    try:
        salida = Path("salidas") / "experimentos" / "barrido_propuesta1.pkl"
        data = ejecutar_barrido()
        guardar_resultados(data, salida)
        print(f"Barrido finalizado. Archivo guardado en: {salida}")
    except KeyboardInterrupt:
        print("Ejecucion interrumpida por el usuario.")
        sys.exit(1)
    except Exception as exc:
        print(f"Error durante el barrido: {exc}")
        raise
