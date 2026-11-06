"""Una prueba por corrección del motor PRU con pru_fixed=True."""

import os
import random
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from simulacion.agent_extendido import AgentExtendido
from simulacion.grilla.floor_field import Floor_field
from simulacion.nodos.path_selector import PathSelector


def _campo():
    return Floor_field(8, 8, [(0, 4)], [])


def _agente(ff, x, y, fijo=True, selector=None):
    return AgentExtendido(
        agent_type="rapido",
        floor_field=ff,
        path_selector=selector,
        x=x,
        y=y,
        U_I=10,
        U_II=20,
        pru_fixed=fijo,
    )


def _silenciar_recalculo(agente):
    agente.last_recalculation_step = 0
    agente._current_simulation_step = 0
    agente.current_path = [(2, 2), (1, 3), (0, 4)]
    agente.path_index = 0


def test_ruido_solo_si_es_vecina_de_ambos_extremos(monkeypatch):
    ff = _campo()
    selector = PathSelector(ff, pru_fixed=True)
    ruta = [(2, 2), (3, 2), (4, 2)]
    monkeypatch.setattr("simulacion.nodos.path_selector.random.random", lambda: 0.0)
    monkeypatch.setattr(
        "simulacion.nodos.path_selector.random.choice",
        lambda opciones: (2, 0),
    )
    assert selector._add_path_noise(ruta) == ruta

    monkeypatch.setattr(
        "simulacion.nodos.path_selector.random.choice",
        lambda opciones: (0, 1),
    )
    ruidosa = selector._add_path_noise(ruta)
    assert ruidosa == [(2, 2), (3, 3), (4, 2)]
    for a, b in zip(ruidosa, ruidosa[1:]):
        assert max(abs(a[0] - b[0]), abs(a[1] - b[1])) == 1


def test_mover_a_no_aplica_un_salto():
    ff = _campo()
    fijo = _agente(ff, 2, 2)
    fijo.current_path = [(2, 2), (5, 2)]
    fijo.mover_a(5, 2)
    assert (fijo.pos_x, fijo.pos_y) == (2, 2)
    assert fijo.current_path is None
    assert fijo.steps_without_moving == 1
    assert fijo.ansiedad == 1
    assert fijo.if_change is False

    anterior = _agente(ff, 2, 2, fijo=False)
    anterior.mover_a(5, 2)
    assert (anterior.pos_x, anterior.pos_y) == (5, 2)


def test_path_index_avanza_solo_tras_el_movimiento_real():
    ff = _campo()
    selector = PathSelector(ff, pru_fixed=True)
    agente = _agente(ff, 2, 2, selector=selector)
    _silenciar_recalculo(agente)

    assert agente.proponer_movimiento((0, 4), {}) == (1, 3)
    assert agente.path_index == 0
    agente.mover_a(1, 3)
    assert (agente.pos_x, agente.pos_y) == (1, 3)
    assert agente.path_index == 2

    agente._current_simulation_step = 1
    agente.last_recalculation_step = 1
    assert agente.proponer_movimiento((0, 4), {}) == (0, 4)
    agente.mover_a(1, 3)
    assert agente.path_index == 2
    assert (agente.pos_x, agente.pos_y) == (1, 3)

    agente._current_simulation_step = 2
    agente.last_recalculation_step = 2
    assert agente.proponer_movimiento((0, 4), {}) == (0, 4)


def test_recalculo_mira_la_celda_que_intenta_pisar():
    ff = _campo()
    selector = PathSelector(ff, pru_fixed=True)
    ruta = [(2, 2), (3, 2), (4, 2), (5, 2)]
    ocupada = {(4, 2): 2}
    assert selector.should_recalculate(
        (3, 2), ruta, 2, ocupada, 0, siguiente_celda=(4, 2)
    )
    assert selector.should_recalculate((3, 2), ruta, 2, ocupada, 0) is False

    agente = _agente(ff, 3, 2, selector=selector)
    agente.current_path = ruta
    agente.path_index = 2
    agente.last_recalculation_step = -10
    agente._current_simulation_step = 0
    visto = {}
    original = selector.should_recalculate

    def _ver(*args, **kwargs):
        visto["celda"] = kwargs.get("siguiente_celda")
        return False

    selector.should_recalculate = _ver
    agente.elegir_ruta((5, 2), ocupada)
    assert visto["celda"] == (4, 2)
    selector.should_recalculate = original


def test_ansiedad_sin_tope_de_100():
    ff = _campo()
    fijo = _agente(ff, 2, 2)
    fijo.ansiedad = 100
    fijo.mover_a(2, 2)
    assert fijo.ansiedad == 101

    anterior = _agente(ff, 2, 2, fijo=False)
    anterior.ansiedad = 100
    anterior.mover_a(2, 2)
    assert anterior.ansiedad == 100

    rutas = [[(2, 2), (3, 2)], [(2, 2), (3, 3)], [(2, 2), (2, 3)]]
    con_tope = PathSelector(ff, pru_fixed=False)
    sin_tope = PathSelector(ff, pru_fixed=True)
    assert con_tope.select_path_by_anxiety(rutas, 180, anxiety_thresholds=(150, 300)) == rutas[0]

    original = random.choices
    random.choices = lambda opciones, weights=None: [opciones[1]]
    try:
        elegida = sin_tope.select_path_by_anxiety(
            rutas, 180, anxiety_thresholds=(150, 300)
        )
    finally:
        random.choices = original
    assert elegida == rutas[1]


def test_barrido_siembra_el_modulo_random():
    from experimento.barrido_pru_fixed import sembrar_corrida

    sembrar_corrida(12345)
    primera = [random.random() for _ in range(3)]
    sembrar_corrida(12345)
    assert [random.random() for _ in range(3)] == primera
    np.random.seed(12345)
    sembrar_corrida(12345)
    assert np.random.random() == np.random.RandomState(12345).random()


def test_docstring_desbloqueo_coincide_con_la_funcion():
    texto = AgentExtendido.__doc__
    assert "3-4" in texto
    assert "5 o más" in texto
    selector = PathSelector(_campo())
    assert selector.calculate_unlocked_paths(5) == 5
    assert selector.calculate_unlocked_paths(3) == 3


def test_docstring_estancamiento_es_8_pasos():
    assert ">= 8" in PathSelector.should_recalculate.__doc__


def test_docstring_de_seleccion_no_promete_30_30_40():
    texto = PathSelector.select_path_by_anxiety.__doc__
    assert "inverso de la" in texto
    assert "30% óptima, 30% media, 40%" not in texto


def test_docstring_de_heuristica_es_euclidiana():
    texto = PathSelector.calculate_heuristic.__doc__
    assert "sqrt" in texto
    assert "No aplica los pesos" in texto


def test_docstring_debe_recalcular_ruta_avisa_que_no_corre_en_el_barrido():
    assert "No la usa" in PathSelector.debe_recalcular_ruta.__doc__


def test_docstring_de_conflictos_describe_floor_field_y_tipo():
    import simulacion.agent_extendido as modulo

    texto = modulo.mover_agentes_con_conflictos.__doc__
    assert "floor field" in texto
    assert "rapido" in texto
