"""Destino de un paso según la etapa de estrés. La usan PFF y PRU.

φ se indexa como valores[y, x]. Una celda con φ >= 500 es pared u obstáculo
y no entra al vecindario. El vecindario es de 8 celdas.
"""

from __future__ import annotations

import random

_DIRS = (
    (-1, -1),
    (0, -1),
    (1, -1),
    (-1, 0),
    (1, 0),
    (-1, 1),
    (0, 1),
    (1, 1),
)


def etapa_de(estres: float, u1: float, u2: float) -> int:
    """1 si estrés <= U1, 2 si U1 < estrés <= U2, 3 si estrés > U2."""
    if estres <= u1:
        return 1
    if estres <= u2:
        return 2
    return 3


def _vecinos(phi, x: int, y: int) -> list[tuple[int, int, float]]:
    height, width = phi.shape
    vecinos = []
    for dx, dy in _DIRS:
        nx, ny = x + dx, y + dy
        if not (0 <= nx < width and 0 <= ny < height):
            continue
        valor = float(phi[ny, nx])
        if valor >= 500:
            continue
        vecinos.append((nx, ny, valor))
    return vecinos


def candidatas(phi, ocupadas, x: int, y: int, etapa: int) -> list[tuple[int, int]]:
    """Celdas a las que la etapa puede moverse. Vacío significa quedarse.

    # [DUDA] (a) etapa II: al azar entre las libres con φ <= φ actual, no la de menor φ.
    # [DUDA] (b) etapa III: mínimo de φ entre las libres, aunque suba; no un salto aleatorio.
    """
    if etapa not in (1, 2, 3):
        raise ValueError(f"etapa debe ser 1, 2 o 3, no {etapa}")
    ocupadas = set(ocupadas)
    actual = float(phi[y, x])
    vecinos = _vecinos(phi, x, y)
    if etapa == 1:
        # [AUDITORÍA REGLAS PFF] CORREGIDO — regla 1: solo el mínimo absoluto, ocupadas incluidas
        if not vecinos:
            return []
        minimo = min(valor for _, _, valor in vecinos)
        if minimo >= actual:
            return []
        return [
            (nx, ny)
            for nx, ny, valor in vecinos
            if valor == minimo and (nx, ny) not in ocupadas
        ]
    if etapa == 2:
        # [AUDITORÍA REGLAS PFF] CORREGIDO — regla 2: libre y φ <= actual
        return [
            (nx, ny)
            for nx, ny, valor in vecinos
            if valor <= actual and (nx, ny) not in ocupadas
        ]
    libres = [(nx, ny, valor) for nx, ny, valor in vecinos if (nx, ny) not in ocupadas]
    if not libres:
        return []
    minimo = min(valor for _, _, valor in libres)
    # [AUDITORÍA REGLAS PFF] CORREGIDO — regla 3: mínimo entre libres, aunque sea mayor que φ actual
    return [(nx, ny) for nx, ny, valor in libres if valor == minimo]


def clasificar_rechazo(phi, ocupadas, x: int, y: int, etapa: int, celda) -> str:
    """Por qué la celda de la ruta no es candidata. No usa el azar.

    # [DUDA] una celda puede caer en varias causas. Se guarda una sola, en este orden:
    # no_vecina, ocupada, subiria, no_minimo_absoluto, no_minimo_libre.
    # [DUDA] la etapa I también rechaza una libre que no es el mínimo absoluto, aunque φ baje o se quede igual.
    # Esa causa no estaba en la lista pedida; se anota como no_minimo_absoluto para que el desglose sume.
    # [DUDA] una celda con φ >= 500 o fuera del mapa se anota como no_vecina.
    """
    sx, sy = int(celda[0]), int(celda[1])
    height, width = phi.shape
    if max(abs(sx - x), abs(sy - y)) != 1 or not (0 <= sx < width and 0 <= sy < height):
        return "no_vecina"
    valor = float(phi[sy, sx])
    if valor >= 500:
        return "no_vecina"
    if (sx, sy) in set(ocupadas):
        return "ocupada"
    actual = float(phi[y, x])
    if etapa in (1, 2) and valor > actual:
        return "subiria"
    if etapa == 1:
        return "no_minimo_absoluto"
    if etapa == 3:
        return "no_minimo_libre"
    return "subiria"


def proponer_destino(phi, ocupadas, x: int, y: int, etapa: int) -> tuple[int, int]:
    """Elige la celda del paso. Si no hay candidata, devuelve (x, y)."""
    opciones = candidatas(phi, ocupadas, x, y, etapa)
    if not opciones:
        return (x, y)
    if len(opciones) == 1:
        return opciones[0]
    return random.choice(opciones)
