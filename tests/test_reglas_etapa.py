"""Reglas de etapa sobre una grilla con φ = columna x y la salida a la izquierda."""

import os
import random
import sys
from types import SimpleNamespace

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from simulacion.agent_extendido import AgentExtendido, mover_agentes_con_conflictos
from simulacion.agentes import Agente, mover_agentes
from simulacion.grilla.floor_field import Floor_field
from simulacion.nodos.path_selector import PathSelector
from simulacion.reglas_etapa import candidatas, proponer_destino


def _grilla():
    valores = np.full((5, 5), 500.0)
    for y in range(1, 4):
        for x in range(1, 4):
            valores[y, x] = float(x)
    campo = SimpleNamespace(valores=valores, height=5, width=5, puertas=[])
    return campo


def _phi(campo, x, y):
    return float(campo.valores[y, x])


def test_e1_espera_si_el_minimo_absoluto_esta_ocupado():
    campo = _grilla()
    ocupadas = {(2, 2), (1, 1), (1, 2), (1, 3)}
    assert proponer_destino(campo.valores, ocupadas, 2, 2, 1) == (2, 2)
    assert candidatas(campo.valores, ocupadas, 2, 2, 1) == []

    for ramirez in (True, False):
        agente = Agente(2, 2, campo, U_I=10, U_II=20, ramirez2021=ramirez, stress_inicial=0)
        assert agente.proponer_movimiento(ocupadas) == (2, 2)


def test_e1_no_hace_nada_en_un_minimo_local():
    campo = _grilla()
    assert proponer_destino(campo.valores, {(1, 2)}, 1, 2, 1) == (1, 2)
    agente = Agente(1, 2, campo, U_I=10, ramirez2021=True, stress_inicial=0)
    assert agente.proponer_movimiento({(1, 2)}) == (1, 2)


def test_e1_empate_solo_entre_las_libres_del_minimo(monkeypatch):
    campo = _grilla()
    ocupadas = {(2, 2), (1, 2)}
    opciones = candidatas(campo.valores, ocupadas, 2, 2, 1)
    assert set(opciones) == {(1, 1), (1, 3)}
    monkeypatch.setattr("simulacion.reglas_etapa.random.choice", lambda opts: opts[-1])
    assert proponer_destino(campo.valores, ocupadas, 2, 2, 1) == opciones[-1]


def test_e2_nunca_sube_y_se_queda_si_no_hay_candidata():
    campo = _grilla()
    random.seed(7)
    for _ in range(40):
        destino = proponer_destino(campo.valores, {(2, 2)}, 2, 2, 2)
        assert _phi(campo, *destino) <= 2
    bloqueadas = {(2, 2), (1, 1), (1, 2), (1, 3), (2, 1), (2, 3)}
    assert candidatas(campo.valores, bloqueadas, 2, 2, 2) == []
    assert proponer_destino(campo.valores, bloqueadas, 2, 2, 2) == (2, 2)
    agente = Agente(2, 2, campo, U_I=1, U_II=10, ramirez2021=True, stress_inicial=5)
    assert agente.proponer_movimiento(bloqueadas) == (2, 2)


def test_e3_sube_al_minimo_libre_cuando_las_demas_estan_ocupadas():
    campo = _grilla()
    ocupadas = {(2, 2), (1, 1), (1, 2), (1, 3), (2, 1), (2, 3)}
    opciones = candidatas(campo.valores, ocupadas, 2, 2, 3)
    assert set(opciones) == {(3, 1), (3, 2), (3, 3)}
    destino = proponer_destino(campo.valores, ocupadas, 2, 2, 3)
    assert destino in opciones
    assert _phi(campo, *destino) == 3
    agente = Agente(2, 2, campo, U_I=1, U_II=4, ramirez2021=True, stress_inicial=5)
    assert agente.proponer_movimiento(ocupadas) in opciones


def test_e3_se_queda_si_esta_rodeado():
    campo = _grilla()
    rodeado = {
        (2, 2),
        (1, 1), (2, 1), (3, 1),
        (1, 2), (3, 2),
        (1, 3), (2, 3), (3, 3),
    }
    assert candidatas(campo.valores, rodeado, 2, 2, 3) == []
    assert proponer_destino(campo.valores, rodeado, 2, 2, 3) == (2, 2)


def _pru(campo, x, y, ansiedad, ruta, posiciones):
    selector = SimpleNamespace(calculate_unlocked_paths=lambda **_k: 1)
    AgentExtendido.instances = []
    agente = AgentExtendido(
        "rapido", campo, selector, x, y, U_I=10, U_II=20, pru_fixed=True
    )
    agente.elegir_ruta = lambda *_a, **_k: None
    agente.current_path = ruta
    agente.path_index = 0
    agente.ansiedad = ansiedad
    return agente.proponer_movimiento((0, 2), posiciones)


def test_pru_etapa_i_espera_si_la_celda_de_la_ruta_es_el_minimo_ocupado():
    campo = _grilla()
    ocupadas = {(1, 1): 1, (1, 2): 1, (1, 3): 1, (2, 2): 1}
    destino = _pru(campo, 2, 2, 0, [(2, 2), (1, 2), (1, 1), (0, 1)], ocupadas)
    assert destino == (2, 2)


def test_pru_etapa_ii_conserva_la_celda_legal_de_la_ruta():
    campo = _grilla()
    destino = _pru(campo, 2, 2, 15, [(2, 2), (2, 3), (2, 4)], {(2, 2): 1})
    assert destino == (2, 3)
    assert _phi(campo, *destino) == 2


def test_pru_etapa_iii_no_sigue_una_celda_que_no_es_el_minimo_libre():
    campo = _grilla()
    destino = _pru(campo, 2, 2, 25, [(2, 2), (3, 2), (3, 3)], {(2, 2): 1})
    assert destino in {(1, 1), (1, 2), (1, 3)}


def test_simulacion_corta_pff_y_pru():
    ff = Floor_field(7, 7, [(0, 3)], [])
    random.seed(1)
    np.random.seed(1)
    pff = [
        Agente(3, 3, ff, U_I=2, U_II=4, ramirez2021=True, stress_inicial=0),
        Agente(4, 3, ff, U_I=2, U_II=4, ramirez2021=True, stress_inicial=5),
        Agente(3, 4, ff, U_I=2, U_II=4, ramirez2021=True, stress_inicial=8),
    ]
    for _ in range(20):
        if not any(agente.activo for agente in pff):
            break
        mover_agentes(pff)
        vivos = [(agente.x, agente.y) for agente in pff if agente.activo]
        assert len(vivos) == len(set(vivos))

    AgentExtendido.instances = []
    selector = PathSelector(ff, pru_fixed=True)
    pru = []
    for x, y, ansiedad in ((3, 3, 0), (4, 3, 5), (3, 4, 9)):
        agente = AgentExtendido("rapido", ff, selector, x, y, U_I=2, U_II=4, pru_fixed=True)
        agente.ansiedad = ansiedad
        pru.append(agente)
    for paso in range(20):
        if not any(agente.activo for agente in pru):
            break
        for agente in pru:
            agente._current_simulation_step = paso
        mover_agentes_con_conflictos(pru)
        vivos = [(agente.pos_x, agente.pos_y) for agente in pru if agente.activo]
        assert len(vivos) == len(set(vivos))
