"""Definicion de agentes basicos para simulaciones con floor field."""

from __future__ import annotations

import random
from typing import Iterable

from simulacion.colisiones import anotar


class Agente:
    """Agente basico con dinamica de stress Yerkes-Dodson."""

    def __init__(
        self,
        x,
        y,
        campo,
        U_I: int = 10,
        U_II: int = 20,
        ramirez2021: bool = False,
        stress_inicial: int = 0,
        frozen_stress: bool = False,
    ):
        self.x = x
        self.y = y
        self.campo = campo
        self.activo = True
        self.if_change = False

        # Umbrales de stress por regimen.
        self.U_I: int = U_I
        self.U_II: int = U_II
        self.stress: int = stress_inicial
        self.ramirez2021 = ramirez2021
        # Solo el PFF corregido consulta este flag, al cerrar el paso.
        self.frozen_stress = frozen_stress

    def _vecinas_8(self) -> list[tuple[int, int]]:
        """Retorna vecinas validas (8 direcciones) dentro del mapa."""
        vecinas = []
        for dx, dy in (
            (-1, -1),
            (0, -1),
            (1, -1),
            (-1, 0),
            (1, 0),
            (-1, 1),
            (0, 1),
            (1, 1),
        ):
            nx, ny = self.x + dx, self.y + dy
            if 0 <= nx < self.campo.width and 0 <= ny < self.campo.height:
                vecinas.append((nx, ny))
        return vecinas

    def _es_libre(self, pos: tuple[int, int], ocupadas: set[tuple[int, int]]) -> bool:
        """Retorna True si la celda no esta ocupada ni bloqueada."""
        x, y = pos
        if pos in ocupadas:
            return False
        valor = self.campo.valores[y, x]
        return valor < 500

    def proponer_movimiento(
        self, ocupadas: Iterable[tuple[int, int]]
    ) -> tuple[int, int]:
        """
        Propone un movimiento segun el regimen de stress de Yerkes-Dodson.

        Regimenes:
        - mild (stress <= U_I): mejor vecina libre de menor floor field.
        - optimal (U_I < stress <= U_II): mejor vecina libre entre las que
          mejoran respecto al valor actual.
        - anxiety (stress > U_II): vecina libre aleatoria.

        Actualiza stress:
        - Si se mueve: stress -= 1 (minimo 0).
        - Si no puede moverse: stress += 1.

        Con ramirez2021 el estres no se toca aqui: se actualiza despues
        del conflicto, segun el movimiento que si ocurrio.
        """
        if self.ramirez2021:
            return self._proponer_movimiento_ramirez2021(ocupadas)
        if not self.activo:
            return (self.x, self.y)

        ocupadas_set = set(ocupadas)
        actual = (self.x, self.y)
        valor_actual = self.campo.valores[self.y, self.x]
        vecinas = self._vecinas_8()
        libres = [v for v in vecinas if self._es_libre(v, ocupadas_set)]

        destino = actual

        if self.stress <= self.U_I:
            # Mild: moverse hacia la celda libre con menor floor field.
            if libres:
                destino = min(libres, key=lambda p: self.campo.valores[p[1], p[0]])

        elif self.stress <= self.U_II:
            # Optimal: elegir mejor vecina libre que mejore el valor actual.
            candidatas = [
                v for v in libres if self.campo.valores[v[1], v[0]] < valor_actual
            ]
            if candidatas:
                destino = min(
                    candidatas, key=lambda p: self.campo.valores[p[1], p[0]]
                )

        else:
            # Anxiety: ignorar floor field y elegir una vecina libre al azar.
            if libres:
                destino = random.choice(libres)

        self.if_change = destino != actual
        if self.if_change:
            self.stress = max(0, self.stress - 1)
        else:
            self.stress += 1

        return destino

    def _proponer_movimiento_ramirez2021(
        self, ocupadas: Iterable[tuple[int, int]]
    ) -> tuple[int, int]:
        """Propuesta de Ramirez et al. 2021. No modifica el estres."""
        if not self.activo:
            return (self.x, self.y)

        ocupadas_set = set(ocupadas)
        actual = (self.x, self.y)
        valor_actual = self.campo.valores[self.y, self.x]
        validas = [
            v for v in self._vecinas_8() if self.campo.valores[v[1], v[0]] < 500
        ]

        if self.stress <= self.U_I:
            if not validas:
                return actual
            destino = min(validas, key=lambda p: self.campo.valores[p[1], p[0]])
            if destino in ocupadas_set:
                return actual
            if self.campo.valores[destino[1], destino[0]] > valor_actual:
                return actual
            return destino

        if self.stress <= self.U_II:
            candidatas = [
                v
                for v in validas
                if v not in ocupadas_set and self.campo.valores[v[1], v[0]] < valor_actual
            ]
            if not candidatas:
                return actual
            return min(candidatas, key=lambda p: self.campo.valores[p[1], p[0]])

        libres = [v for v in validas if v not in ocupadas_set]
        if not libres:
            return actual
        return random.choice(libres)

    def mover_a(self, x: int, y: int) -> None:
        """Aplica el movimiento y desactiva al llegar a una puerta."""
        self.x = x
        self.y = y
        if self.campo.valores[self.y, self.x] == 0:  # Si llega a una puerta (valor = 0)
            self.activo = False


def _aplicar_stress_ramirez2021(agente: Agente, x0: int, y0: int) -> None:
    """+1 si no se movio, -1 si se movio. El minimo es 0.

    Con frozen_stress, s_i queda en el valor inicial. if_change sigue
    reflejando si el agente cambio de celda.
    """
    se_movio = (agente.x, agente.y) != (x0, y0)
    agente.if_change = se_movio
    if agente.frozen_stress:
        return
    if se_movio:
        agente.stress = max(0, agente.stress - 1)
    else:
        agente.stress += 1


def _mover_agentes_ramirez2021(agentes, registro=None) -> int:
    """Conflictos al azar. El estres se actualiza con el movimiento real."""
    ocupadas = {(a.x, a.y) for a in agentes if a.activo}
    propuestas = {}

    for agente in agentes:
        if agente.activo:
            propuestas[agente] = agente.proponer_movimiento(ocupadas)

    destinos = {}
    for agente, destino in propuestas.items():
        destinos.setdefault(destino, []).append(agente)

    conflictos = 0
    for destino, candidatos in destinos.items():
        if len(candidatos) == 1:
            ganador = candidatos[0]
        else:
            conflictos += 1
            ganador = random.choice(candidatos)
            anotar(registro, candidatos, ganador, lambda agente: agente.stress)
        for agente in candidatos:
            x0, y0 = agente.x, agente.y
            if agente is ganador:
                agente.mover_a(destino[0], destino[1])
            _aplicar_stress_ramirez2021(agente, x0, y0)
    return conflictos


def mover_agentes(agentes, registro=None) -> int:
    """Mueve agentes activos con resolucion simple de conflictos."""
    if agentes and any(getattr(a, "ramirez2021", False) for a in agentes):
        if not all(getattr(a, "ramirez2021", False) for a in agentes):
            raise ValueError("No mezclar agentes ramirez2021 con el motor PFF anterior")
        return _mover_agentes_ramirez2021(agentes, registro)
    ocupadas = {(a.x, a.y) for a in agentes if a.activo}
    propuestas = {}

    for agente in agentes:
        if agente.activo:
            propuestas[agente] = agente.proponer_movimiento(ocupadas)

    destinos = {}
    for agente, destino in propuestas.items():
        destinos.setdefault(destino, []).append(agente)

    conflictos = 0
    for destino, candidatos in destinos.items():
        if len(candidatos) == 1:
            candidato = candidatos[0]
            candidato.mover_a(destino[0], destino[1])
        else:
            conflictos += 1
            ganador = random.choice(candidatos)
            anotar(registro, candidatos, ganador, lambda agente: agente.stress)
            ganador.mover_a(destino[0], destino[1])
    return conflictos
