"""Utilidades para calcular metricas agregadas de simulaciones."""

from __future__ import annotations

import math
import numpy as np
from typing import Any


def _es_frame(obj: Any) -> bool:
    """Retorna True si el objeto tiene forma de frame del simulador."""
    return isinstance(obj, dict) and "agentes" in obj


def _normalizar_historias(historia: list[dict]) -> list[list[dict]]:
    """
    Normaliza la entrada para trabajar siempre como lista de historias.

    Permite dos formatos:
    - Historia unica: [frame_0, frame_1, ...]
    - Ensemble: [[frame_0, ...], [frame_0, ...], ...]
    """
    if not historia:
        return []
    if _es_frame(historia[0]):
        return [historia]
    return [h for h in historia if isinstance(h, list)]


def _calcular_t(historia_unica: list[dict]) -> int:
    """Calcula T como el numero de pasos hasta que no queden agentes activos."""
    for idx, frame in enumerate(historia_unica):
        agentes = frame.get("agentes", [])
        if all(not getattr(agente, "activo", False) for agente in agentes):
            return idx + 1
    return len(historia_unica)


def _valor_ansiedad(agente: Any) -> float | None:
    """Extrae el valor de ansiedad del agente, si existe."""
    valor = getattr(agente, "ansiedad", None)
    if valor is None:
        return None
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def _etapa_ansiedad(valor: float, u_i: float, u_ii: float) -> str:
    """Clasifica ansiedad en mild, optimal o anxiety usando U_I/U_II."""
    if valor <= u_i:
        return "mild"
    if valor <= u_ii:
        return "optimal"
    return "anxiety"


def _obtener_valor_numerico(frame: dict, claves: tuple[str, ...], default: int | None = None) -> int | None:
    """Lee un valor numérico desde el frame o su sub-dict stats, si existe."""
    for clave in claves:
        if clave in frame:
            try:
                return int(frame[clave])
            except (TypeError, ValueError):
                return default

    stats = frame.get("stats")
    if isinstance(stats, dict):
        for clave in claves:
            if clave in stats:
                try:
                    return int(stats[clave])
                except (TypeError, ValueError):
                    return default
    return default


def _sumar_agentes_activos(frame: dict) -> int:
    """Cuenta agentes activos desde el frame, o desde la lista de agentes si no se indicó explícitamente."""
    valor = _obtener_valor_numerico(frame, ("n_agentes_activos", "agentes_activos", "n_activos"), default=None)
    if valor is not None:
        return valor

    agentes = frame.get("agentes", [])
    return int(sum(1 for agente in agentes if getattr(agente, "activo", False)))


def _sumar_agentes_movidos(frame: dict) -> int:
    """Cuenta agentes que se movieron en el paso, o deriva desde if_change si no se indicó explícitamente."""
    valor = _obtener_valor_numerico(frame, ("n_agentes_movidos", "agentes_movidos", "n_movidos"), default=None)
    if valor is not None:
        return valor

    agentes = frame.get("agentes", [])
    return int(sum(1 for agente in agentes if getattr(agente, "activo", False) and getattr(agente, "if_change", False)))


def _sumar_recalculos_ruta(frame: dict) -> int:
    """Cuenta recálculos de ruta solicitados en el frame, si el frame lo expone."""
    valor = _obtener_valor_numerico(frame, ("n_recalculos_ruta", "recalculos_ruta", "n_recalculos"), default=None)
    if valor is not None:
        return valor
    return 0


def _sumar_colisiones(frame: dict) -> int | None:
    """
    Obtiene colisiones del frame.

    Retorna None cuando no existe informacion de colisiones.
    """
    claves = (
        "n_colisiones",
        "colisiones",
        "conflictos_movimiento",
        "conflictos_totales",
        "conflictos",
    )
    for clave in claves:
        if clave in frame:
            try:
                return int(frame[clave])
            except (TypeError, ValueError):
                return 0

    stats = frame.get("stats")
    if isinstance(stats, dict):
        for clave in claves:
            if clave in stats:
                try:
                    return int(stats[clave])
                except (TypeError, ValueError):
                    return 0
    return None


def _desv_estandar_poblacional(valores: list[int]) -> float:
    """Calcula desviacion estandar poblacional para una lista numerica."""
    if not valores:
        return 0.0
    media = sum(valores) / len(valores)
    varianza = sum((v - media) ** 2 for v in valores) / len(valores)
    return math.sqrt(varianza)


def calcular_metricas(historia: list[dict]) -> dict | None:
    """
    Calcula metricas agregadas de una simulacion o de un ensemble.

    Parametros
    ----------
    historia : list[dict]

    Retorna
    -------
    dict | None
        Si la historia esta vacia retorna ``None``.
        En caso contrario retorna un diccionario con:
        - ``T``: pasos de la primera historia hasta que no queden activos.
        - ``sigma_T``: desviacion estandar de T entre historias del ensemble.
        - ``fraccion_stress``: fraccion promedio por etapa
          (``mild``, ``optimal``, ``anxiety``) a lo largo de todos los frames.
        - ``n_colisiones``: total de colisiones/conflictos detectados; ``None``
          si la historia no provee esa metrica.
    """
    historias = _normalizar_historias(historia)
    if not historias:
        return None

    ts: list[int] = []
    conteo_stress = {"mild": 0, "optimal": 0, "anxiety": 0}
    agentes_con_stress = 0
    total_colisiones = 0
    hay_colisiones = False
    agentes_activos_por_paso: list[int] = []
    agentes_movidos_por_paso: list[int] = []
    total_recalculos_ruta = 0

    for historia_unica in historias:
        if not historia_unica:
            ts.append(0)
            continue

        ts.append(_calcular_t(historia_unica))

        for frame in historia_unica:
            agentes = frame.get("agentes", [])
            for agente in agentes:
                valor = _valor_ansiedad(agente)
                if valor is None:
                    continue
                u_i = getattr(agente, "U_I", 30)
                u_ii = getattr(agente, "U_II", 70)
                try:
                    u_i = float(u_i)
                    u_ii = float(u_ii)
                except (TypeError, ValueError):
                    u_i, u_ii = 30.0, 70.0
                conteo_stress[_etapa_ansiedad(valor, u_i, u_ii)] += 1
                agentes_con_stress += 1

            colisiones_frame = _sumar_colisiones(frame)
            if colisiones_frame is not None:
                hay_colisiones = True
                total_colisiones += colisiones_frame

            agentes_activos_por_paso.append(_sumar_agentes_activos(frame))
            agentes_movidos_por_paso.append(_sumar_agentes_movidos(frame))
            total_recalculos_ruta += _sumar_recalculos_ruta(frame)

    if agentes_con_stress > 0:
        fraccion_stress = {
            etapa: conteo / agentes_con_stress
            for etapa, conteo in conteo_stress.items()
        }
    else:
        fraccion_stress = {"mild": 0.0, "optimal": 0.0, "anxiety": 0.0}

    return {
        "T": float(np.mean(ts)),
        "sigma_T": _desv_estandar_poblacional(ts),
        "fraccion_stress": fraccion_stress,
        "n_colisiones": total_colisiones if hay_colisiones else None,
        "n_agentes_activos_promedio": float(np.mean(agentes_activos_por_paso)) if agentes_activos_por_paso else 0.0,
        "n_agentes_activos_max": int(max(agentes_activos_por_paso)) if agentes_activos_por_paso else 0,
        "n_agentes_activos_por_paso": agentes_activos_por_paso,
        "n_agentes_movidos_por_paso": agentes_movidos_por_paso,
        "n_recalculos_ruta": int(total_recalculos_ruta),
    }
