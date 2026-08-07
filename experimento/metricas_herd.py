"""
Métricas para analizar comportamiento tipo "thundering herd" en simulaciones.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from statistics import mean, pstdev
from typing import Any


def detectar_cascadas(recalculo_log: list[dict], ventana: int = 5) -> list[dict]:
    """
    Detecta cascadas de recálculo en base al `recalculo_log`.

    Una cascada se define como un tramo de pasos consecutivos donde, por al menos
    `ventana` pasos seguidos, la fracción de agentes recalculando supera o iguala
    el 30% del total activo estimado.

    La función agrupa entradas por `step`, estima el total activo y retorna una
    lista de eventos de cascada con:
    - `step_inicio`
    - `duracion`
    - `n_agentes_pico`
    - `fraccion_pico`

    Parámetros
    ----------
    recalculo_log : list[dict]
        Lista de eventos de recálculo (idealmente uno por agente que recalcula).
    ventana : int, opcional
        Cantidad mínima de pasos consecutivos para considerar cascada.

    Returns
    -------
    list[dict]
        Lista de cascadas detectadas.
    """
    if not recalculo_log or ventana <= 0:
        return []

    # Conteo por paso
    recalculos_por_step: dict[int, int] = defaultdict(int)
    n_recalc_externo_por_step: dict[int, int] = {}
    unique_agents = set()

    for entry in recalculo_log:
        step = int(entry.get("step", 0))
        recalculos_por_step[step] += 1

        agent_id = entry.get("agent_id")
        if agent_id is not None:
            unique_agents.add(agent_id)

        # Si está disponible, priorizamos esta métrica externa por paso
        n_ext = entry.get("n_agents_recalculating")
        if isinstance(n_ext, (int, float)):
            n_recalc_externo_por_step[step] = max(n_recalc_externo_por_step.get(step, 0), int(n_ext))

    if not recalculos_por_step:
        return []

    # Total activo estimado (fallback robusto sin depender de otros logs)
    total_activo = max(len(unique_agents), max(recalculos_por_step.values()), 1)
    umbral_fraccion = 0.30

    steps_sorted = sorted(recalculos_por_step.keys())
    step_min, step_max = steps_sorted[0], steps_sorted[-1]

    pasos_sobre_umbral: list[tuple[int, int, float]] = []
    for step in range(step_min, step_max + 1):
        n_recalc = n_recalc_externo_por_step.get(step, recalculos_por_step.get(step, 0))
        fraccion = n_recalc / total_activo
        if fraccion >= umbral_fraccion:
            pasos_sobre_umbral.append((step, n_recalc, fraccion))

    if not pasos_sobre_umbral:
        return []

    cascadas: list[dict] = []
    tramo_actual: list[tuple[int, int, float]] = [pasos_sobre_umbral[0]]

    for step, n_recalc, fraccion in pasos_sobre_umbral[1:]:
        prev_step = tramo_actual[-1][0]
        if step == prev_step + 1:
            tramo_actual.append((step, n_recalc, fraccion))
        else:
            if len(tramo_actual) >= ventana:
                n_pico = max(x[1] for x in tramo_actual)
                f_pico = max(x[2] for x in tramo_actual)
                cascadas.append(
                    {
                        "step_inicio": tramo_actual[0][0],
                        "duracion": len(tramo_actual),
                        "n_agentes_pico": n_pico,
                        "fraccion_pico": f_pico,
                    }
                )
            tramo_actual = [(step, n_recalc, fraccion)]

    # Cerrar último tramo
    if len(tramo_actual) >= ventana:
        n_pico = max(x[1] for x in tramo_actual)
        f_pico = max(x[2] for x in tramo_actual)
        cascadas.append(
            {
                "step_inicio": tramo_actual[0][0],
                "duracion": len(tramo_actual),
                "n_agentes_pico": n_pico,
                "fraccion_pico": f_pico,
            }
        )

    return cascadas


def calcular_nu_th(recalculo_log: list[dict], ruta_log: list[dict]) -> float:
    """
    Calcula la fracción de pasos con al menos 30% de agentes recalculando.

    Si `ruta_log` tiene pasos, se usa su paso máximo para estimar la duración
    total de la simulación. En caso contrario, se usa el paso máximo de
    `recalculo_log`.
    """
    if not recalculo_log:
        return 0.0

    recalculos_por_step: dict[int, int] = defaultdict(int)
    n_recalc_externo_por_step: dict[int, int] = {}
    unique_agents = set()

    for entry in recalculo_log:
        step = int(entry.get("step", 0))
        recalculos_por_step[step] += 1

        agent_id = entry.get("agent_id")
        if agent_id is not None:
            unique_agents.add(agent_id)

        n_ext = entry.get("n_agents_recalculating")
        if isinstance(n_ext, (int, float)):
            n_recalc_externo_por_step[step] = max(n_recalc_externo_por_step.get(step, 0), int(n_ext))

    if not recalculos_por_step:
        return 0.0

    total_activo = max(len(unique_agents), max(recalculos_por_step.values()), 1)

    if ruta_log:
        total_steps = max(int(entry.get("step", 0)) for entry in ruta_log) + 1
    else:
        total_steps = max(recalculos_por_step.keys()) + 1

    umbral_fraccion = 0.30
    pasos_sobre_umbral = 0
    for step, count in recalculos_por_step.items():
        n_recalc = n_recalc_externo_por_step.get(step, count)
        fraccion = n_recalc / total_activo
        if fraccion >= umbral_fraccion:
            pasos_sobre_umbral += 1

    return pasos_sobre_umbral / total_steps if total_steps > 0 else 0.0


def entropia_rutas(ruta_log: list[dict], n_rutas_posibles: int) -> list[float]:
    """
    Calcula la entropía de Shannon por paso para la selección de rutas.

    Para cada `step`, se toma la distribución de `ruta_idx` y se calcula:
    H = -sum(p_i * ln(p_i))

    Interpretación:
    - H = 0: todos eligieron la misma ruta (thundering herd puro)
    - H = ln(n_rutas_posibles): distribución uniforme (diversidad máxima)

    Parámetros
    ----------
    ruta_log : list[dict]
        Lista de eventos con al menos `step` y `ruta_idx`.
    n_rutas_posibles : int
        Número de rutas posibles consideradas.

    Returns
    -------
    list[float]
        Lista de entropías ordenadas por step ascendente.
    """
    if not ruta_log or n_rutas_posibles <= 0:
        return []

    rutas_por_step: dict[int, list[int]] = defaultdict(list)
    for entry in ruta_log:
        if "step" not in entry or "ruta_idx" not in entry:
            continue
        step = int(entry["step"])
        ruta_idx = int(entry["ruta_idx"])
        if ruta_idx < 0:
            continue
        rutas_por_step[step].append(ruta_idx)

    entropias: list[float] = []
    for step in sorted(rutas_por_step):
        conteo = Counter(rutas_por_step[step])
        total = sum(conteo.values())
        if total == 0:
            entropias.append(0.0)
            continue

        h = 0.0
        for n in conteo.values():
            p_i = n / total
            h -= p_i * math.log(p_i)
        entropias.append(h)

    return entropias


def resumen_herd(
    recalculo_log: list[dict],
    ruta_log: list[dict],
    n_rutas_posibles: int,
    rho: Any,
    ansiedad_media: Any,
) -> dict:
    """
    Construye un resumen agregado de métricas de comportamiento herd.

    El resumen incluye:
    - frecuencia_cascadas
    - duracion_media_cascada
    - entropia_media
    - entropia_min
    - entropia_std

    Además conserva `rho` y `ansiedad_media` en la salida para facilitar análisis
    comparativos entre escenarios.

    Parámetros
    ----------
    recalculo_log : list[dict]
        Log de recálculos por agente.
    ruta_log : list[dict]
        Log de selección de rutas por agente.
    n_rutas_posibles : int
        Número de rutas disponibles en el experimento.
    rho : Any
        Densidad del escenario (u otro descriptor de condición experimental).
    ansiedad_media : Any
        Valor agregado de ansiedad para el escenario/corrida.

    Returns
    -------
    dict
        Diccionario con métricas agregadas de herd.
    """
    cascadas = detectar_cascadas(recalculo_log)
    entropias = entropia_rutas(ruta_log, n_rutas_posibles=n_rutas_posibles)

    frecuencia_cascadas = len(cascadas)
    pasos = sorted(c["step"] for c in cascadas)
    duraciones: list[int] = []
    if pasos:
        tramo_actual = [pasos[0]]
        for step in pasos[1:]:
            if step == tramo_actual[-1] + 1:
                tramo_actual.append(step)
            else:
                duraciones.append(len(tramo_actual))
                tramo_actual = [step]
        duraciones.append(len(tramo_actual))

    duracion_media_cascada = mean(duraciones) if duraciones else 0.0

    nu_th = calcular_nu_th(recalculo_log, ruta_log)

    entropia_media = mean(entropias) if entropias else 0.0
    entropia_min = min(entropias) if entropias else 0.0
    entropia_std = pstdev(entropias) if len(entropias) > 1 else 0.0

    return {
        "rho": rho,
        "ansiedad_media": ansiedad_media,
        "frecuencia_cascadas": frecuencia_cascadas,
        "duracion_media_cascada": duracion_media_cascada,
        "nu_th": nu_th,
        "entropia_media": entropia_media,
        "entropia_min": entropia_min,
        "entropia_std": entropia_std,
    }
