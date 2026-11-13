"""La causa única no cambia de orden. Las combinaciones se cuentan aparte."""

import os
import sys
from types import SimpleNamespace

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from simulacion.agent_extendido import AgentExtendido
from simulacion.reglas_etapa import candidatas, causas_simultaneas, clasificar_rechazo


def _grilla():
    valores = np.full((5, 5), 500.0)
    for y in range(1, 4):
        for x in range(1, 4):
            valores[y, x] = float(x)
    return valores


def test_la_primera_causa_simultanea_es_la_unica():
    phi = _grilla()
    celdas = [(x, y) for x in range(5) for y in range(5)]
    bloqueos = [set(), {(1, 2)}, {(1, 1), (1, 3), (3, 2)}]
    for etapa in (1, 2, 3):
        for ocupadas in bloqueos:
            for celda in celdas:
                if celda == (2, 2) or celda in candidatas(phi, ocupadas, 2, 2, etapa):
                    continue
                juntas = causas_simultaneas(phi, ocupadas, 2, 2, etapa, celda)
                unica = clasificar_rechazo(phi, ocupadas, 2, 2, etapa, celda)
                assert juntas, (etapa, celda, ocupadas, unica)
                assert juntas[0] == unica


def test_ocupada_y_cuesta_arriba_cuentan_como_combinacion_sin_cambiar_la_unica():
    phi = _grilla()
    ocupadas = {(3, 2)}
    celda = (3, 2)
    unica = clasificar_rechazo(phi, ocupadas, 2, 2, 1, celda)
    juntas = causas_simultaneas(phi, ocupadas, 2, 2, 1, celda)
    assert unica == "ocupada"
    assert juntas[0] == "ocupada"
    assert "subiria" in juntas
    assert len(juntas) > 1

    selector = SimpleNamespace(calculate_unlocked_paths=lambda **_k: 1)
    AgentExtendido.instances = []
    agente = AgentExtendido(
        "rapido",
        SimpleNamespace(valores=phi, height=5, width=5, puertas=[(0, 2)]),
        selector,
        2,
        2,
        U_I=10,
        U_II=20,
        pru_fixed=True,
        reglas_etapa_en_pru=True,
    )
    agente.elegir_ruta = lambda *_a, **_k: None
    agente.current_path = [(2, 2), (3, 2)]
    agente.proponer_movimiento((0, 2), {(2, 2): 1, (3, 2): 1})
    assert agente.reemplazos.causas[1]["ocupada"] == 1
    assert agente.reemplazos.multicausa[1] == 1
    assert agente.reemplazos.combinaciones[1]["ocupada+subiria+no_minimo_absoluto"] == 1
