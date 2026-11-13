"""Utilidades para calcular metricas agregadas de simulaciones."""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any

import numpy as np

from experimento.config import N_RUNS, RHO_VALS, SEED_BASE, exigir_procedencia, grilla_umbrales

# [DUDA] N_RUNS, SEED_BASE, RHO_VALS y la grilla no entran en el cálculo de T; se importan porque config.py es la única fuente
_ = (N_RUNS, SEED_BASE, RHO_VALS, grilla_umbrales)


def leer_csv(path) -> list[dict]:
    """Lee un CSV de experimento. Si falta la procedencia, aborta con un mensaje."""
    path = Path(path)
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        exigir_procedencia(reader.fieldnames, path)
        return list(reader)


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

        Agregados (compatibles con barridos/plotters existentes):
        - ``T``: media de tiempos de evacuacion del ensemble.
        - ``sigma_T``: desviacion estandar de T entre historias del ensemble.
        - ``fraccion_stress``: fraccion promedio por etapa
          (``mild``, ``optimal``, ``anxiety``) a lo largo de todos los frames.
        - ``n_colisiones``: suma total de colisiones/conflictos del ensemble;
          ``None`` si la historia no provee esa metrica.
        - ``activos_por_paso``, ``moviendose_por_paso``, ``recalculos_por_paso``:
          series temporales promediadas entre corridas.

        Distribuciones por corrida / agente (claves nuevas, aditivas):
        - ``T_por_corrida``: T de cada historia (largo = N).
        - ``n_colisiones_por_corrida``: colisiones por historia (largo = N);
          ``None`` si ninguna historia reporta colisiones.
        - ``ansiedad_final_por_agente``: ansiedad en el ultimo frame por agente,
          apilada across corridas.
        - ``fraccion_stage_III_por_agente``: fraccion de frames en Stage III
          (anxiety) por agente, apilada across corridas.
    """
    historias = _normalizar_historias(historia)
    if not historias:
        return None

    ts: list[int] = []
    conteo_stress = {"mild": 0, "optimal": 0, "anxiety": 0}
    agentes_con_stress = 0
    total_colisiones = 0
    hay_colisiones = False
    n_colisiones_por_corrida: list[int] = []
    ansiedad_final_por_agente: list[float] = []
    fraccion_stage_III_por_agente: list[float] = []

    for historia_unica in historias:
        if not historia_unica:
            ts.append(0)
            n_colisiones_por_corrida.append(0)
            continue

        ts.append(_calcular_t(historia_unica))

        colisiones_corrida = 0
        # agent_id -> (frames_con_ansiedad, frames_stage_III, ultima_ansiedad)
        por_agente: dict[Any, list[Any]] = {}

        for frame in historia_unica:
            agentes = frame.get("agentes", [])
            for idx_agente, agente in enumerate(agentes):
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
                etapa = _etapa_ansiedad(valor, u_i, u_ii)
                conteo_stress[etapa] += 1
                agentes_con_stress += 1

                agent_key = getattr(agente, "id", None)
                if agent_key is None:
                    agent_key = idx_agente
                stats = por_agente.get(agent_key)
                if stats is None:
                    stats = [0, 0, valor]
                    por_agente[agent_key] = stats
                stats[0] += 1
                if etapa == "anxiety":
                    stats[1] += 1
                stats[2] = valor

            colisiones_frame = _sumar_colisiones(frame)
            if colisiones_frame is not None:
                hay_colisiones = True
                colisiones_corrida += colisiones_frame
                total_colisiones += colisiones_frame

        n_colisiones_por_corrida.append(colisiones_corrida)

        for n_obs, n_iii, ans_final in por_agente.values():
            ansiedad_final_por_agente.append(float(ans_final))
            fraccion_stage_III_por_agente.append(
                float(n_iii) / float(n_obs) if n_obs > 0 else 0.0
            )

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
        "T_por_corrida": list(ts),
        "n_colisiones_por_corrida": n_colisiones_por_corrida if hay_colisiones else None,
        "ansiedad_final_por_agente": ansiedad_final_por_agente,
        "fraccion_stage_III_por_agente": fraccion_stage_III_por_agente,
        # Para fusionar corridas sin retener historias completas en RAM:
        "conteo_stress": dict(conteo_stress),
        "n_obs_stress": int(agentes_con_stress),
    }


def combinar_metricas(parciales: list[dict]) -> dict | None:
    """Combina metricas por-corrida (salida de ``calcular_metricas`` en 1 historia).

    Permite barridos N grandes sin acumular el ensemble de frames en memoria.
    El resultado es equivalente a ``calcular_metricas(ensemble)``.
    """
    parciales = [p for p in parciales if isinstance(p, dict)]
    if not parciales:
        return None

    ts: list[int] = []
    n_colisiones_por_corrida: list[int] = []
    hay_colisiones = False
    ansiedad_final_por_agente: list[float] = []
    fraccion_stage_III_por_agente: list[float] = []
    conteo_stress = {"mild": 0, "optimal": 0, "anxiety": 0}
    n_obs_stress = 0
    series_activos: list[list[int]] = []
    series_mov: list[list[int]] = []
    series_rec: list[list[int]] = []

    for p in parciales:
        ts.extend(int(t) for t in p.get("T_por_corrida", []))
        cols = p.get("n_colisiones_por_corrida")
        if cols is not None:
            hay_colisiones = True
            n_colisiones_por_corrida.extend(int(c) for c in cols)
        ansiedad_final_por_agente.extend(
            float(v) for v in (p.get("ansiedad_final_por_agente") or [])
        )
        fraccion_stage_III_por_agente.extend(
            float(v) for v in (p.get("fraccion_stage_III_por_agente") or [])
        )
        raw = p.get("conteo_stress") or {}
        for etapa in conteo_stress:
            conteo_stress[etapa] += int(raw.get(etapa, 0))
        n_obs_stress += int(p.get("n_obs_stress", 0))
        series_activos.append(list(p.get("activos_por_paso") or []))
        series_mov.append(list(p.get("moviendose_por_paso") or []))
        series_rec.append(list(p.get("recalculos_por_paso") or []))

    if n_obs_stress > 0:
        fraccion_stress = {
            etapa: conteo / n_obs_stress for etapa, conteo in conteo_stress.items()
        }
    else:
        fraccion_stress = {"mild": 0.0, "optimal": 0.0, "anxiety": 0.0}

    n = len(parciales)
    max_len = max((len(s) for s in series_activos), default=0)
    activos_por_paso: list[int] = []
    moviendose_por_paso: list[int] = []
    recalculos_por_paso: list[int] = []
    for paso in range(max_len):
        a_sum = sum(s[paso] if paso < len(s) else 0 for s in series_activos)
        m_sum = sum(s[paso] if paso < len(s) else 0 for s in series_mov)
        r_sum = sum(s[paso] if paso < len(s) else 0 for s in series_rec)
        activos_por_paso.append(int(round(a_sum / n)))
        moviendose_por_paso.append(int(round(m_sum / n)))
        recalculos_por_paso.append(int(round(r_sum / n)))

    total_colisiones = sum(n_colisiones_por_corrida) if hay_colisiones else None

    return {
        "T": float(np.mean(ts)) if ts else 0.0,
        "sigma_T": _desv_estandar_poblacional(ts),
        "fraccion_stress": fraccion_stress,
        "n_colisiones": total_colisiones,
        "activos_por_paso": activos_por_paso,
        "moviendose_por_paso": moviendose_por_paso,
        "recalculos_por_paso": recalculos_por_paso,
        "T_por_corrida": list(ts),
        "n_colisiones_por_corrida": n_colisiones_por_corrida if hay_colisiones else None,
        "ansiedad_final_por_agente": ansiedad_final_por_agente,
        "fraccion_stage_III_por_agente": fraccion_stage_III_por_agente,
        "conteo_stress": dict(conteo_stress),
        "n_obs_stress": int(n_obs_stress),
    }
