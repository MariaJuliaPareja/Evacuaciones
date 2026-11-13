"""El contador de reemplazos no cambia la trayectoria de PRU."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from experimento.barrido_pru_fixed import sembrar_corrida
from simulacion.agent_extendido import (
    AgentExtendido,
    mover_agentes_con_conflictos,
    sumar_reemplazos,
)
from simulacion.grilla.floor_field import Floor_field
from simulacion.nodos.path_selector import PathSelector
from simulacion.reglas_etapa import etapa_de


def _traza(contar, semilla, reglas=True):
    sembrar_corrida(semilla)
    campo = Floor_field(8, 8, [(0, 4)], [])
    AgentExtendido.instances = []
    AgentExtendido.history = []
    AgentExtendido.ruta_log = []
    selector = PathSelector(campo, pru_fixed=True)
    for x, y in ((2, 2), (3, 3), (4, 5), (5, 3)):
        AgentExtendido(
            "rapido", campo, selector, x, y,
            U_I=4, U_II=8, pru_fixed=True,
            reglas_etapa_en_pru=reglas, contar_reemplazos=contar,
        )
    traza = []
    for paso in range(40):
        activos = [a for a in AgentExtendido.instances if a.activo]
        if not activos:
            break
        for agente in activos:
            agente._current_simulation_step = paso
        mover_agentes_con_conflictos(AgentExtendido.instances)
        traza.append([
            (a.activo, a.pos_x, a.pos_y, a.ansiedad, a.steps_without_moving)
            for a in AgentExtendido.instances
        ])
    return traza, sumar_reemplazos(AgentExtendido.instances)


def test_misma_semilla_con_y_sin_contador():
    con, contador = _traza(True, 99)
    sin, vacio = _traza(False, 99)
    assert con == sin
    assert sum(vacio.pasos_con_ruta.values()) == 0
    assert sum(contador.pasos_con_ruta.values()) > 0
    for etapa in (1, 2, 3):
        assert (
            contador.conservada[etapa]
            + contador.ruta_quedarse[etapa]
            + contador.reemplazada[etapa]
            == contador.pasos_con_ruta[etapa]
        )
        assert sum(contador.causas[etapa].values()) == contador.reemplazada[etapa]


def test_flag_false_vuelve_a_pisar_la_celda_de_la_ruta():
    """Sin la regla, una celda de ruta cuesta arriba se conserva."""
    from types import SimpleNamespace

    import numpy as np

    valores = np.full((5, 5), 500.0)
    for y in range(1, 4):
        for x in range(1, 4):
            valores[y, x] = float(x)
    campo = SimpleNamespace(valores=valores, height=5, width=5, puertas=[(0, 2)])
    selector = SimpleNamespace(calculate_unlocked_paths=lambda **_k: 1)
    AgentExtendido.instances = []
    apagado = AgentExtendido(
        "rapido", campo, selector, 2, 2, U_I=10, U_II=20,
        pru_fixed=True, reglas_etapa_en_pru=False,
    )
    apagado.elegir_ruta = lambda *_a, **_k: None
    apagado.current_path = [(2, 2), (3, 2), (3, 3)]
    assert apagado.proponer_movimiento((0, 2), {(2, 2): 1}) == (3, 2)
    assert etapa_de(apagado.ansiedad, apagado.U_I, apagado.U_II) == 1

    AgentExtendido.instances = []
    encendido = AgentExtendido(
        "rapido", campo, selector, 2, 2, U_I=10, U_II=20,
        pru_fixed=True, reglas_etapa_en_pru=True,
    )
    encendido.elegir_ruta = lambda *_a, **_k: None
    encendido.current_path = [(2, 2), (3, 2), (3, 3)]
    destino = encendido.proponer_movimiento((0, 2), {(2, 2): 1})
    assert destino in {(1, 1), (1, 2), (1, 3)}
    assert encendido.reemplazos.reemplazada[1] == 1
    assert encendido.reemplazos.causas[1]["subiria"] == 1
