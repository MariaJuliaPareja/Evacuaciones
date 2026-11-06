"""Una prueba por regla de Ramirez et al. 2021 (PRE 104, 024312)."""

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from simulacion.agentes import Agente, mover_agentes
from simulacion.grilla.floor_field import Floor_field


class CampoFijo:
    def __init__(self, valores):
        self.valores = np.array(valores, dtype=float)
        self.height, self.width = self.valores.shape


def _agente(campo, x, y, stress, u_i=10, u_ii=20, ramirez=True):
    return Agente(
        x,
        y,
        campo,
        U_I=u_i,
        U_II=u_ii,
        ramirez2021=ramirez,
        stress_inicial=stress,
    )


def test_regla_1_estres_despues_del_movimiento_real():
    """Empieza en el valor inicial. +1 si no se movio, -1 si se movio, minimo 0."""
    campo = CampoFijo(
        [
            [500, 500, 500, 500],
            [500, 2, 1, 500],
            [500, 500, 500, 500],
            [500, 500, 500, 500],
        ]
    )
    se_mueve = _agente(campo, 1, 1, stress=4)
    propuesta = se_mueve.proponer_movimiento({(1, 1)})
    assert propuesta == (2, 1)
    assert se_mueve.stress == 4
    assert se_mueve.x == 1

    mover_agentes([se_mueve])
    assert (se_mueve.x, se_mueve.y) == (2, 1)
    assert se_mueve.stress == 3

    en_cero = _agente(campo, 1, 1, stress=0)
    mover_agentes([en_cero])
    assert (en_cero.x, en_cero.y) == (2, 1)
    assert en_cero.stress == 0

    paredes = CampoFijo(
        [
            [500, 500, 500],
            [500, 4, 500],
            [500, 500, 500],
        ]
    )
    quieto = _agente(paredes, 1, 1, stress=2)
    assert quieto.proponer_movimiento({(1, 1)}) == (1, 1)
    assert quieto.stress == 2
    mover_agentes([quieto])
    assert (quieto.x, quieto.y) == (1, 1)
    assert quieto.stress == 3


def test_regla_2_etapa_i_solo_la_vecina_de_menor_phi_si_esta_vacia():
    """Etapa I apunta a la menor phi y no se mueve si esta ocupada o es mayor."""
    campo = CampoFijo(
            [
                [500, 500, 500, 500],
                [500, 5, 1, 500],
                [500, 3, 2, 500],
                [500, 500, 500, 500],
            ]
        )
    agente = _agente(campo, 1, 1, stress=0, u_i=10)
    assert agente.proponer_movimiento({(1, 1), (2, 1)}) == (1, 1)

    libre = _agente(campo, 1, 1, stress=10, u_i=10)
    assert libre.proponer_movimiento({(1, 1)}) == (2, 1)

    mayor = CampoFijo(
        [
            [500, 500, 500, 500],
            [500, 1, 3, 500],
            [500, 2, 4, 500],
            [500, 500, 500, 500],
        ]
    )
    no_sube = _agente(mayor, 1, 1, stress=0, u_i=10)
    assert no_sube.proponer_movimiento({(1, 1)}) == (1, 1)


def test_regla_3_etapa_ii_menor_phi_entre_las_libres_que_mejoran():
    """En esta grilla la etapa II tiene una sola libre con φ <= actual: (2, 1)."""
    campo = CampoFijo(
        [
            [500, 500, 500, 500],
            [500, 5, 4, 500],
            [500, 0, 6, 500],
            [500, 500, 500, 500],
        ]
    )
    agente = _agente(campo, 1, 1, stress=5, u_i=2, u_ii=10)
    assert agente.proponer_movimiento({(1, 1), (1, 2)}) == (2, 1)
    assert agente.stress == 5


def test_regla_4_etapa_iii_minimo_entre_las_libres():
    """Etapa III va al mínimo libre, aquí (2, 2) con φ = 0, aunque (2, 1) también esté libre."""
    campo = CampoFijo(
        [
            [500, 500, 500, 500],
            [500, 5, 9, 500],
            [500, 1, 0, 500],
            [500, 500, 500, 500],
        ]
    )
    agente = _agente(campo, 1, 1, stress=11, u_i=2, u_ii=10)
    assert agente.proponer_movimiento({(1, 1)}) == (2, 2)
    assert agente.stress == 11


def test_regla_5_ocho_vecinos_y_diagonal_1_5():
    campo = Floor_field(5, 5, [(0, 2)], [])
    agente = _agente(campo, 2, 2, stress=0)
    assert len(agente._vecinas_8()) == 8
    assert campo.valores[2, 1] == 1.0
    assert campo.valores[3, 1] == 1.5


def test_regla_6_el_perdedor_del_conflicto_sube_su_estres(monkeypatch):
    campo = CampoFijo(
        [
            [500, 500, 500, 500],
            [500, 3, 0, 500],
            [500, 3, 5, 500],
            [500, 500, 500, 500],
        ]
    )
    primero = _agente(campo, 1, 1, stress=5)
    segundo = _agente(campo, 1, 2, stress=5)
    monkeypatch.setattr(
        "simulacion.agentes.random.choice",
        lambda opciones: opciones[-1],
    )
    mover_agentes([primero, segundo])
    assert (segundo.x, segundo.y) == (2, 1)
    assert segundo.stress == 4
    assert (primero.x, primero.y) == (1, 1)
    assert primero.stress == 6


def test_el_motor_anterior_sigue_actualizando_el_estres_al_proponer():
    """El motor anterior cambia el estrés al proponer. En un mínimo local se queda y sube."""
    campo = CampoFijo(
        [
            [500, 500, 500, 500],
            [500, 1, 3, 500],
            [500, 2, 4, 500],
            [500, 500, 500, 500],
        ]
    )
    agente = _agente(campo, 1, 1, stress=3, ramirez=False)
    assert agente.proponer_movimiento({(1, 1)}) == (1, 1)
    assert agente.stress == 4
    assert agente.x == 1

    bajada = CampoFijo(
        [
            [500, 500, 500, 500],
            [500, 4, 1, 500],
            [500, 3, 2, 500],
            [500, 500, 500, 500],
        ]
    )
    baja = _agente(bajada, 1, 1, stress=3, ramirez=False)
    assert baja.proponer_movimiento({(1, 1)}) == (2, 1)
    assert baja.stress == 2
    assert baja.x == 1
