"""Evacuación completa del aula y del avión con las reglas de etapa.

# [DUDA] la densidad es la lista `agentes` de cada escenario, no el barrido a rho=1.
# [DUDA] U_I=10 y U_II=20. El barrido oficial recorre otros umbrales.
Los agentes que ya salieron quedan sobre la puerta y no se cuentan como ocupación.
"""

import importlib
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from experimento.barrido_pff import MAX_PASOS
from experimento.barrido_pru_fixed import sembrar_corrida
from simulacion.agent_extendido import AgentExtendido, mover_agentes_con_conflictos
from simulacion.agentes import Agente, mover_agentes
from simulacion.grilla.floor_field import Floor_field
from simulacion.nodos.path_selector import PathSelector
from simulacion.reglas_etapa import etapa_de

SEMILLAS = (12345, 12346, 12347, 12348, 12349)
U_I = 10
U_II = 20
ESCENARIOS = ("sala_de_clases", "avion_dos_puertas")
_DIRS = (
    (-1, -1), (0, -1), (1, -1),
    (-1, 0), (1, 0),
    (-1, 1), (0, 1), (1, 1),
)
_ETAPA = {1: "I", 2: "II", 3: "III"}


def _ocupantes(nombre):
    esc = importlib.import_module(f"escenarios.{nombre}")
    gente = []
    for item in esc.agentes:
        if isinstance(item, dict):
            gente.append((tuple(item["pos"]), item.get("tipo", "rapido")))
        else:
            gente.append((tuple(item), "rapido"))
    return esc, gente


def _pos(agente):
    if hasattr(agente, "pos_x"):
        return int(agente.pos_x), int(agente.pos_y)
    return int(agente.x), int(agente.y)


def _estres(agente):
    if hasattr(agente, "ansiedad"):
        return agente.ansiedad
    return agente.stress


def _phi(campo, x, y):
    return float(campo[y, x])


def _minimo_vecindario(campo, x, y):
    alto, ancho = campo.shape
    valores = []
    for dx, dy in _DIRS:
        nx, ny = x + dx, y + dy
        if 0 <= nx < ancho and 0 <= ny < alto:
            valor = float(campo[ny, nx])
            if valor < 500:
                valores.append(valor)
    return min(valores) if valores else None


def _caso(escenario, motor, semilla, paso, agente, etapa, antes, despues, detalle):
    return (
        f"escenario={escenario} motor={motor} semilla={semilla} paso={paso} "
        f"agente={agente} etapa={etapa} celdas={antes}->{despues} {detalle}"
    )


def _revisar_paso(escenario, motor, semilla, paso, campo, previos):
    activos = []
    for indice, antes, etapa, agente in previos:
        if not agente.activo and _pos(agente) == antes and _phi(campo, *antes) == 0:
            continue
        despues = _pos(agente)
        nombre = _ETAPA[etapa]
        assert max(abs(despues[0] - antes[0]), abs(despues[1] - antes[1])) <= 1, _caso(
            escenario, motor, semilla, paso, indice, nombre, antes, despues,
            "el paso no es a una celda vecina",
        )
        assert _phi(campo, *despues) < 500, _caso(
            escenario, motor, semilla, paso, indice, nombre, antes, despues,
            f"pisa una celda con φ={_phi(campo, *despues)}",
        )
        if etapa in (1, 2):
            assert _phi(campo, *despues) <= _phi(campo, *antes), _caso(
                escenario, motor, semilla, paso, indice, nombre, antes, despues,
                f"φ pasó de {_phi(campo, *antes)} a {_phi(campo, *despues)}",
            )
        if etapa == 1 and despues != antes:
            minimo = _minimo_vecindario(campo, *antes)
            assert minimo is not None and _phi(campo, *despues) == minimo, _caso(
                escenario, motor, semilla, paso, indice, nombre, antes, despues,
                f"φ={_phi(campo, *despues)} y el mínimo absoluto era {minimo}",
            )
        if agente.activo:
            activos.append(despues)
    # [DUDA] quien ya salió sigue en la coordenada de la puerta; la ocupación mira solo a los activos
    assert len(activos) == len(set(activos)), _caso(
        escenario, motor, semilla, paso, None, None, None, None,
        f"dos agentes activos en la misma celda: {activos}",
    )


def _correr(escenario, motor, semilla):
    esc, gente = _ocupantes(escenario)
    sembrar_corrida(semilla)
    campo = Floor_field(esc.width, esc.height, list(esc.puertas), list(esc.obstaculos))
    if motor == "pff":
        agentes = [
            Agente(x, y, campo, U_I=U_I, U_II=U_II, ramirez2021=True)
            for (x, y), _tipo in gente
        ]
    else:
        AgentExtendido.instances = []
        AgentExtendido.history = []
        AgentExtendido.ruta_log = []
        selector = PathSelector(campo, pru_fixed=True)
        for (x, y), tipo in gente:
            AgentExtendido(
                tipo, campo, selector, x, y,
                U_I=U_I, U_II=U_II, pru_fixed=True, reglas_etapa_en_pru=True,
            )
        agentes = list(AgentExtendido.instances)
    inicio = [_pos(a) for a in agentes]
    assert len(inicio) == len(set(inicio)), f"{escenario} {motor} posiciones iniciales repetidas"
    tiempo = 0
    for paso in range(MAX_PASOS):
        if not any(a.activo for a in agentes):
            break
        previos = [
            (i, _pos(a), etapa_de(_estres(a), a.U_I, a.U_II), a)
            for i, a in enumerate(agentes)
            if a.activo
        ]
        if motor == "pff":
            mover_agentes(agentes)
        else:
            for agente in agentes:
                if agente.activo:
                    agente._current_simulation_step = paso
            mover_agentes_con_conflictos(agentes)
        tiempo += 1
        _revisar_paso(escenario, motor, semilla, paso, campo.valores, previos)
    quedaron = [
        (i, _pos(a), _ETAPA[etapa_de(_estres(a), a.U_I, a.U_II)])
        for i, a in enumerate(agentes)
        if a.activo
    ]
    assert not quedaron, _caso(
        escenario, motor, semilla, tiempo, quedaron, None, None, None,
        f"siguen dentro al paso {MAX_PASOS}",
    )
    print(f"{escenario} {motor} semilla={semilla} T={tiempo}", flush=True)
    return tiempo


def test_evacuacion_completa_aula_y_avion():
    tiempos = []
    for escenario in ESCENARIOS:
        for motor in ("pff", "pru"):
            for semilla in SEMILLAS:
                tiempos.append((escenario, motor, semilla, _correr(escenario, motor, semilla)))
    assert len(tiempos) == len(ESCENARIOS) * 2 * len(SEMILLAS)
