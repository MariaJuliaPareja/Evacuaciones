"""Barrido de parametros con instrumentacion de comportamiento herd."""

from __future__ import annotations

import inspect
import pickle
import random
import sys
from pathlib import Path
from typing import Any

import numpy as np

try:
    from simulacion.floor_field import Floor_field
except ImportError:
    from simulacion.grilla.floor_field import Floor_field

from experimento.metricas_herd import resumen_herd
from simulacion.agent_extendido import AgentExtendido, mover_agentes_con_conflictos

try:
    from simulacion.nodos.path_selector import PathSelector
except ImportError:
    from simulacion.path_selector import PathSelector  # type: ignore


RHO_VALS = [0.25, 0.50, 0.75, 1.0]
D_INV_VALS = [1e-2, 1e-1, 1.0]
K_PATHS_VALS = [1, 3, 5]
N_SIMS = 50
MAX_PASOS = 500
SEED_BASE = 12345


def _cargar_escenario_base() -> dict[str, Any]:
    """Carga escenario base desde modulo si existe, o crea fallback."""
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
    """Genera posiciones iniciales segun densidad rho sobre celdas libres interiores."""
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
    path_selector: PathSelector,
    posicion: tuple[int, int],
    u_i: float,
    u_ii: float,
    k_paths_max: int,
    ya_reportado_todo: bool,
) -> bool:
    """
    Crea un AgentExtendido intentando inyectar U_I/U_II y k_paths_max si la clase lo soporta.

    Retorna True si ya se reporto el TODO de compatibilidad.
    """
    firma = inspect.signature(AgentExtendido.__init__)
    params = firma.parameters
    kwargs: dict[str, Any] = {
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
            "para modelar umbrales de ansiedad."
        )
        ya_reportado_todo = True

    if "k_paths_max" in params:
        kwargs["k_paths_max"] = int(k_paths_max)
    elif "max_unlocked_paths" in params:
        kwargs["max_unlocked_paths"] = int(k_paths_max)
    elif not ya_reportado_todo:
        print(
            "TODO: AgentExtendido no soporta parametro k_paths_max (o equivalente) "
            "para limitar rutas desbloqueables; barrido_herd registra este faltante."
        )
        ya_reportado_todo = True

    AgentExtendido(**kwargs)
    return ya_reportado_todo


def _simular_una_corrida(
    width: int,
    height: int,
    puertas: list[tuple[int, int]],
    obstaculos: list[tuple[int, int]],
    rho: float,
    d_inv: float,
    k_paths_max: int,
    semilla: int,
    ya_reportado_todo: bool,
) -> tuple[dict[str, Any], bool]:
    """
    Ejecuta una corrida y retorna resumen herd + bandera de TODO reportado.
    """
    rng = random.Random(semilla)
    np.random.seed(semilla)

    ff = Floor_field(width, height, puertas, obstaculos)
    path_selector = PathSelector(ff)

    # Requisito de instrumentacion por simulacion
    AgentExtendido.instances = []
    AgentExtendido.history = []
    AgentExtendido.ruta_log.clear()
    path_selector.reset_log()

    posiciones = _generar_posiciones_iniciales(width, height, obstaculos, rho, rng)
    d = 1.0 / d_inv
    u_i = d
    u_ii = 2.0 * d

    for pos in posiciones:
        ya_reportado_todo = _crear_agente(
            floor_field=ff,
            path_selector=path_selector,
            posicion=pos,
            u_i=u_i,
            u_ii=u_ii,
            k_paths_max=k_paths_max,
            ya_reportado_todo=ya_reportado_todo,
        )

    for step in range(MAX_PASOS):
        activos = [a for a in AgentExtendido.instances if a.activo]
        if not activos:
            break

        # Exponer step actual a los agentes para loggear ruta_log
        for a in activos:
            a._current_simulation_step = step

        mover_agentes_con_conflictos(AgentExtendido.instances)

    # Ansiedad media final de agentes (como proxy agregado de corrida)
    ansiedades = [getattr(a, "ansiedad", 0) for a in AgentExtendido.instances]
    ansiedad_media = float(np.mean(ansiedades)) if ansiedades else 0.0

    resumen = resumen_herd(
        recalculo_log=path_selector.recalculo_log,
        ruta_log=AgentExtendido.ruta_log,
        n_rutas_posibles=int(k_paths_max),
        rho=float(rho),
        ansiedad_media=ansiedad_media,
    )

    return resumen, ya_reportado_todo


def ejecutar_barrido_herd() -> dict[str, Any]:
    """Ejecuta barrido (rho, d_inv, k_paths_max) y agrega metricas herd."""
    esc = _cargar_escenario_base()
    width = esc["width"]
    height = esc["height"]
    puertas = esc["puertas"]
    obstaculos = esc["obstaculos"]

    resultados: dict[str, Any] = {
        "meta": {
            "rho_vals": RHO_VALS,
            "d_inv_vals": D_INV_VALS,
            "k_paths_vals": K_PATHS_VALS,
            "n_sims": N_SIMS,
            "max_pasos": MAX_PASOS,
            "escenario": {
                "width": width,
                "height": height,
                "puertas": puertas,
                "obstaculos": obstaculos,
            },
            "notas": [
                "k_paths_max se intenta inyectar en AgentExtendido si la firma lo permite.",
                "Si AgentExtendido no expone ese parametro, se imprime TODO en consola.",
            ],
        },
        "resultados": [],
    }

    total_combinaciones = len(RHO_VALS) * len(D_INV_VALS) * len(K_PATHS_VALS)
    procesadas = 0
    todo_reportado = False

    for rho in RHO_VALS:
        for d_inv in D_INV_VALS:
            for k_paths_max in K_PATHS_VALS:
                resumenes_corridas: list[dict[str, Any]] = []

                for i in range(N_SIMS):
                    semilla = (
                        SEED_BASE
                        + i
                        + int(1_000_000 * float(rho))
                        + int(10_000 * float(d_inv))
                        + int(100 * int(k_paths_max))
                    )

                    resumen, todo_reportado = _simular_una_corrida(
                        width=width,
                        height=height,
                        puertas=puertas,
                        obstaculos=obstaculos,
                        rho=float(rho),
                        d_inv=float(d_inv),
                        k_paths_max=int(k_paths_max),
                        semilla=semilla,
                        ya_reportado_todo=todo_reportado,
                    )
                    resumenes_corridas.append(resumen)

                # Agregado por combinacion
                frec = [r["frecuencia_cascadas"] for r in resumenes_corridas]
                dur = [r["duracion_media_cascada"] for r in resumenes_corridas]
                h_mean = [r["entropia_media"] for r in resumenes_corridas]
                h_min = [r["entropia_min"] for r in resumenes_corridas]
                h_std = [r["entropia_std"] for r in resumenes_corridas]
                ans = [r["ansiedad_media"] for r in resumenes_corridas]

                resultados["resultados"].append(
                    {
                        "rho": float(rho),
                        "d_inv": float(d_inv),
                        "k_paths_max": int(k_paths_max),
                        "U_I": float(1.0 / d_inv),
                        "U_II": float(2.0 / d_inv),
                        "metricas_herd": {
                            "frecuencia_cascadas_media": float(np.mean(frec)) if frec else 0.0,
                            "duracion_media_cascada_media": float(np.mean(dur)) if dur else 0.0,
                            "entropia_media_media": float(np.mean(h_mean)) if h_mean else 0.0,
                            "entropia_min_media": float(np.mean(h_min)) if h_min else 0.0,
                            "entropia_std_media": float(np.mean(h_std)) if h_std else 0.0,
                            "ansiedad_media_media": float(np.mean(ans)) if ans else 0.0,
                        },
                        "corridas": resumenes_corridas,
                    }
                )

                procesadas += 1
                print(
                    f"Progreso herd: {procesadas}/{total_combinaciones} combinaciones "
                    f"(rho={rho}, d_inv={d_inv}, k_paths_max={k_paths_max})"
                )

    return resultados


def guardar_resultados(resultados: dict[str, Any], ruta_salida: Path) -> None:
    """Guarda resultados del barrido herd en archivo PKL."""
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    with ruta_salida.open("wb") as f:
        pickle.dump(resultados, f)


if __name__ == "__main__":
    try:
        salida = Path("resultados") / "barrido_herd.pkl"
        data = ejecutar_barrido_herd()
        guardar_resultados(data, salida)
        print(f"Barrido herd finalizado. Archivo guardado en: {salida}")
    except KeyboardInterrupt:
        print("Ejecucion interrumpida por el usuario.")
        sys.exit(1)
    except Exception as exc:
        print(f"Error durante el barrido herd: {exc}")
        raise
