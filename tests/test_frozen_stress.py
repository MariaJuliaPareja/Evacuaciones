"""frozen_stress deja s_i quieto. En PRU, delta_i y el desbloqueo siguen."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from simulacion.agent_extendido import AgentExtendido, mover_agentes_con_conflictos
from simulacion.agentes import Agente, mover_agentes
from simulacion.grilla.floor_field import Floor_field
from simulacion.nodos.path_selector import PathSelector


class CampoFijo:
    def __init__(self, valores):
        self.valores = __import__("numpy").array(valores, dtype=float)
        self.height, self.width = self.valores.shape


def test_pff_frozen_stress_no_cambia_durante_la_simulacion():
    """El PFF corregido corre de verdad: s_i no se mueve ni al avanzar ni al atascarse."""
    corredor = CampoFijo(
        [
            [500, 500, 500, 500, 500, 500],
            [500, 5, 4, 3, 2, 1],
            [500, 500, 500, 500, 500, 500],
        ]
    )
    libre = Agente(1, 1, corredor, U_I=10, U_II=20, ramirez2021=True, stress_inicial=15, frozen_stress=True)
    assert libre.frozen_stress is True
    assert Agente(1, 1, corredor, ramirez2021=True).frozen_stress is False

    for _ in range(4):
        mover_agentes([libre])
        assert libre.stress == 15
    assert (libre.x, libre.y) != (1, 1)

    caja = CampoFijo(
        [
            [500, 500, 500],
            [500, 4, 500],
            [500, 500, 500],
        ]
    )
    quieto = Agente(1, 1, caja, U_I=10, U_II=20, ramirez2021=True, stress_inicial=25, frozen_stress=True)
    for _ in range(6):
        mover_agentes([quieto])
        assert quieto.stress == 25
        assert (quieto.x, quieto.y) == (1, 1)

    suelto = Agente(1, 1, caja, ramirez2021=True, stress_inicial=25, frozen_stress=False)
    mover_agentes([suelto])
    assert suelto.stress == 26


def test_pru_frozen_stress_no_cambia_y_el_desbloqueo_sigue():
    """La simulación PRU corregida conserva s_i. delta_i sigue y abre 1, 3 y 5 rutas."""
    ff = Floor_field(8, 8, [(0, 4)], [])
    selector = PathSelector(ff, pru_fixed=True)
    AgentExtendido.instances = []
    agente = AgentExtendido(
        agent_type="rapido",
        floor_field=ff,
        path_selector=selector,
        x=5,
        y=4,
        U_I=10,
        U_II=20,
        pru_fixed=True,
        frozen_stress=True,
    )
    assert agente.frozen_stress is True
    assert AgentExtendido("rapido", ff, None, 1, 1).frozen_stress is False
    agente.ansiedad = 15

    for step in range(10):
        agente._current_simulation_step = step
        mover_agentes_con_conflictos([agente])
        assert agente.ansiedad == 15
    assert agente.pos_x != 5 or not agente.activo

    for delta, rutas in ((0, 1), (3, 3), (5, 5)):
        agente.activo = True
        agente.pos_x, agente.pos_y = 5, 4
        agente.ansiedad = 15
        agente.steps_without_moving = delta
        agente.current_path = None
        agente.last_recalculation_step = -10
        agente._current_simulation_step = 0
        mover_agentes_con_conflictos([agente])
        assert agente.ansiedad == 15
        assert agente.unlocked_paths_count == rutas
        assert selector.calculate_unlocked_paths(delta) == rutas

    caja = Floor_field(
        5,
        5,
        [(0, 2)],
        [(1, 1), (2, 1), (3, 1), (1, 2), (3, 2), (1, 3), (2, 3), (3, 3)],
    )
    selector_caja = PathSelector(caja, pru_fixed=True)
    AgentExtendido.instances = []
    atascado = AgentExtendido(
        agent_type="rapido",
        floor_field=caja,
        path_selector=selector_caja,
        x=2,
        y=2,
        U_I=10,
        U_II=20,
        pru_fixed=True,
        frozen_stress=True,
    )
    atascado.ansiedad = 25
    for step in range(6):
        atascado._current_simulation_step = step
        mover_agentes_con_conflictos([atascado])
        assert atascado.ansiedad == 25
        assert (atascado.pos_x, atascado.pos_y) == (2, 2)
    assert atascado.steps_without_moving == 6
    assert selector_caja.calculate_unlocked_paths(atascado.steps_without_moving) == 5
    AgentExtendido.instances = []
