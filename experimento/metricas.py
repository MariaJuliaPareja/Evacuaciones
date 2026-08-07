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

    if agentes_con_stress > 0:
        fraccion_stress = {
            etapa: conteo / agentes_con_stress
            for etapa, conteo in conteo_stress.items()
        }
    else:
        fraccion_stress = {"mild": 0.0, "optimal": 0.0, "anxiety": 0.0}

    # Normalizar por longitud de la primera historia si hay ensemble y pad con ceros en historias cortas.
    activos_por_paso: list[int] = []
    moviendose_por_paso: list[int] = []
    recalculos_por_paso: list[int] = []
    if historias:
        max_len = max(len(h) for h in historias)
        for paso in range(max_len):
            activos_sum = 0
            movidos_sum = 0
            recalculos_sum = 0
            for historia_unica in historias:
                if paso < len(historia_unica):
                    frame = historia_unica[paso]
                    activos_sum += int(frame.get("n_activos", 0))
                    movidos_sum += int(frame.get("n_moviendose", 0))
                    recalculos_sum += int(frame.get("n_recalculos_pathselector", 0))
            n = len(historias)
            activos_por_paso.append(int(round(activos_sum / n)))
            moviendose_por_paso.append(int(round(movidos_sum / n)))
            recalculos_por_paso.append(int(round(recalculos_sum / n)))

    return {
        "T": float(np.mean(ts)),
        "sigma_T": _desv_estandar_poblacional(ts),
        "fraccion_stress": fraccion_stress,
        "n_colisiones": total_colisiones if hay_colisiones else None,
        "activos_por_paso": activos_por_paso,
        "moviendose_por_paso": moviendose_por_paso,
        "recalculos_por_paso": recalculos_por_paso,
    }
