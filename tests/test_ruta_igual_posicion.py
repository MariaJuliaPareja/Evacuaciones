"""Ruta igual a la posición actual, con una celda que la regla obliga.

La dinámica no se corrige aquí. El test de movimiento muestra el caso.
"""

import os
import sys
from types import SimpleNamespace

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from simulacion.agent_extendido import AgentExtendido
from simulacion.reglas_etapa import etapa_de, proponer_destino


def _grilla():
    valores = np.full((5, 5), 500.0)
    for y in range(1, 4):
        for x in range(1, 4):
            valores[y, x] = float(x)
    return SimpleNamespace(valores=valores, height=5, width=5, puertas=[(0, 2)])


def _agente(campo, ansiedad):
    selector = SimpleNamespace(calculate_unlocked_paths=lambda **_k: 1)
    AgentExtendido.instances = []
    agente = AgentExtendido(
        "rapido",
        campo,
        selector,
        2,
        2,
        U_I=10,
        U_II=20,
        pru_fixed=True,
        reglas_etapa_en_pru=True,
        contar_reemplazos=True,
    )
    agente.elegir_ruta = lambda *_a, **_k: None
    # path_index salta la celda actual y la siguiente de la ruta vuelve a ser (2, 2).
    agente.current_path = [(2, 2), (2, 2)]
    agente.path_index = 0
    agente.ansiedad = ansiedad
    return agente


def _ocupadas_etapa_iii():
    ocupadas = {(2, 2): 1}
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            celda = (2 + dx, 2 + dy)
            if celda != (1, 2):
                ocupadas[celda] = 1
    return ocupadas


def test_contador_ruta_quedarse_no_es_conservada_ni_reemplazada():
    campo = _grilla()
    agente = _agente(campo, 0)
    agente.proponer_movimiento((0, 2), {(2, 2): 1, (1, 1): 1, (1, 3): 1})
    conteo = agente.reemplazos
    assert etapa_de(agente.ansiedad, agente.U_I, agente.U_II) == 1
    assert conteo.ruta_quedarse[1] == 1
    assert conteo.conservada[1] == 0
    assert conteo.reemplazada[1] == 0
    assert conteo.pasos_con_ruta[1] == 1


def test_ruta_igual_posicion_etapa_i_y_iii_siguen_la_regla():
    """Etapa I y etapa III deben ir a la única celda libre que la regla obliga."""
    campo = _grilla()
    phi = campo.valores
    ocupadas_i = {(2, 2), (1, 1), (1, 3)}
    ocupadas_iii = {celda for celda, n in _ocupadas_etapa_iii().items() if n}
    assert proponer_destino(phi, ocupadas_i, 2, 2, 1) == (1, 2)
    assert proponer_destino(phi, ocupadas_iii, 2, 2, 3) == (1, 2)

    agente_i = _agente(campo, 0)
    propuesta_i = agente_i.proponer_movimiento(
        (0, 2), {(2, 2): 1, (1, 1): 1, (1, 3): 1}
    )
    agente_i.mover_a(*propuesta_i)

    agente_iii = _agente(campo, 25)
    propuesta_iii = agente_iii.proponer_movimiento((0, 2), _ocupadas_etapa_iii())
    agente_iii.mover_a(*propuesta_iii)

    vistos = {
        "I": (agente_i.pos_x, agente_i.pos_y),
        "III": (agente_iii.pos_x, agente_iii.pos_y),
    }
    assert vistos == {"I": (1, 2), "III": (1, 2)}, (
        f"ruta == posición actual. La regla obliga (1, 2) en las dos etapas. "
        f"La dinámica terminó en {vistos}."
    )
