"""Barrido de parametros para la propuesta 1 de evacuacion."""

from __future__ import annotations

import importlib
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
from simulacion.pathfinding_propuesta.path_selector import PathSelector
from experimento.metricas import calcular_metricas


RHO_VALS = [0.25, 0.50, 0.75, 1.0]
D_INV_VALS = np.logspace(-3, 0, 16)
N_SIMS = 100
MAX_PASOS = 500
SEED_BASE = 12345


def _cargar_escenario_base(scenario_name: str = "escenario_base", d: float | None = None) -> dict[str, Any]:
    """
    Carga un escenario desde el paquete escenarios o usa fallback.

    El parámetro ``d`` permite configurar la distancia entre puertas cuando el
    módulo del escenario expone una función ``get_config``.
    """
    try:
        if scenario_name in {"base", "escenario_base"}:
            module_name = "escenario_base"
        else:
            module_name = scenario_name

        esc_module = importlib.import_module(f"escenarios.{module_name}")
        if hasattr(esc_module, "get_config"):
            config = esc_module.get_config(d=d)
            return {
                "width": int(config.get("width", getattr(esc_module, "width", 0))),
                "height": int(config.get("height", getattr(esc_module, "height", 0))),
                "puertas": list(config.get("puertas", [])),
                "obstaculos": list(config.get("obstaculos", [])),
                "door_distance": config.get("door_distance", None),
            }

        return {
            "width": int(getattr(esc_module, "width")),
            "height": int(getattr(esc_module, "height")),
            "puertas": list(getattr(esc_module, "puertas")),
            "obstaculos": list(getattr(esc_module, "obstaculos", [])),
            "door_distance": getattr(esc_module, "door_distance", None),
        }
    except Exception:
        width, height = 20, 14
        y_mid = height // 2
        puertas = [(0, y_mid - 1), (0, y_mid)]
        return {"width": width, "height": height, "puertas": puertas, "obstaculos": [], "door_distance": None}


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
    path_selector: PathSelector | None,
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
        "path_selector": path_selector,
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
    path_selector = PathSelector(ff)
    AgentExtendido.instances = []
    AgentExtendido.history = []
    AgentExtendido.ruta_log.clear()
    path_selector.reset_log()

    posiciones = _generar_posiciones_iniciales(width, height, obstaculos, rho, rng)
    d = 1.0 / d_inv
    u_i = d
    u_ii = 2.0 * d

    for pos in posiciones:
        ya_reportado_todo = _crear_agente(ff, path_selector, pos, u_i, u_ii, ya_reportado_todo)

    historia_frames: list[dict[str, Any]] = []

    for step in range(MAX_PASOS):
        activos = [a for a in AgentExtendido.instances if a.activo]
        if not activos:
            break

        for agente in activos:
            agente._current_simulation_step = step

        prev_recalculos = len(path_selector.recalculo_log)
        stats = mover_agentes_con_conflictos(AgentExtendido.instances)
        n_recalculos_step = max(0, len(path_selector.recalculo_log) - prev_recalculos)

        snapshot = [
            SimpleNamespace(
                activo=a.activo,
                if_change=getattr(a, "if_change", False),
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
                "n_agentes_activos": len(activos),
                "n_agentes_movidos": int(stats.get("movidos", 0)),
                "n_recalculos_ruta": int(n_recalculos_step),
            }
        )

    if not historia_frames:
        historia_frames.append({"agentes": [], "conflictos": 0, "n_agentes_activos": 0, "n_agentes_movidos": 0, "n_recalculos_ruta": 0})

    return historia_frames, ya_reportado_todo


def ejecutar_barrido(scenario_name: str = "escenario_base", d: float | None = None) -> dict[str, Any]:
    """
    Ejecuta barrido sobre (rho, 1/d) y calcula metricas por combinacion.
    """
    esc = _cargar_escenario_base(scenario_name=scenario_name, d=d)
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
                "door_distance": esc.get("door_distance"),
            },
            "scenario_name": scenario_name,
            "door_distance": esc.get("door_distance"),
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
