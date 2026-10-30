"""Conteo de conflictos. No participa en la decision ni llama al azar."""

from __future__ import annotations


def registro_vacio() -> dict:
    return {"conflictos": 0, "apuestas": 0, "victorias": 0}


def etapa_de(valor: float, u_i: float, u_ii: float) -> str:
    if valor <= u_i:
        return "I"
    if valor <= u_ii:
        return "II"
    return "III"


def anotar(registro: dict | None, participantes, ganador, estres_de) -> None:
    """Un conflicto: 2 o mas agentes piden la misma celda.

    Apuesta es cada participante. Victoria es el agente que se queda
    con la celda. Si nadie es elegible, la victoria no se cuenta.
    """
    if registro is None or len(participantes) < 2:
        return
    registro["conflictos"] += 1
    registro["apuestas"] += len(participantes)
    etapas = []
    for agente in participantes:
        etapa = etapa_de(estres_de(agente), agente.U_I, agente.U_II)
        etapas.append(etapa)
        por_etapa = registro.setdefault("apuestas_etapa", {"I": 0, "II": 0, "III": 0})
        por_etapa[etapa] += 1
    if ganador is not None:
        etapa_g = etapa_de(estres_de(ganador), ganador.U_I, ganador.U_II)
        registro["victorias"] += 1
        por_v = registro.setdefault("victorias_etapa", {"I": 0, "II": 0, "III": 0})
        por_v[etapa_g] += 1
    if len(set(etapas)) == 1:
        por_c = registro.setdefault("conflictos_etapa", {"I": 0, "II": 0, "III": 0})
        por_c[etapas[0]] += 1
