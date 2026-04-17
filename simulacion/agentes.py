"""Definicion de agentes basicos para simulaciones con floor field."""

from __future__ import annotations

import random
from typing import Iterable


class Agente:
    """Agente basico con dinamica de stress Yerkes-Dodson."""

    def __init__(self, x, y, campo, U_I: int = 10, U_II: int = 20):
        self.x = x
        self.y = y
        self.campo = campo
        self.activo = True
        self.if_change = False

        # Umbrales de stress por regimen.
        self.U_I: int = U_I
        self.U_II: int = U_II
        self.stress: int = 0

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
        """
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

    def mover_a(self, x: int, y: int) -> None:
        """Aplica el movimiento y desactiva al llegar a una puerta."""
        self.x = x
        self.y = y
        if self.campo.valores[self.y, self.x] == 0:
            self.activo = False


def mover_agentes(agentes):
    """Mueve agentes activos con resolucion simple de conflictos."""
    ocupadas = {(a.x, a.y) for a in agentes if a.activo}
    propuestas = {}

    for agente in agentes:
        if agente.activo:
            propuestas[agente] = agente.proponer_movimiento(ocupadas)

    destinos = {}
    for agente, destino in propuestas.items():
        destinos.setdefault(destino, []).append(agente)

    for destino, candidatos in destinos.items():
        if len(candidatos) == 1:
            candidato = candidatos[0]
            candidato.mover_a(destino[0], destino[1])
        else:
            ganador = random.choice(candidatos)
            ganador.mover_a(destino[0], destino[1])
