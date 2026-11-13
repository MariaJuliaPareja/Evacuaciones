"""Cuántas celdas de ruta A* conserva o reemplaza PRU, por etapa.

Los defaults salen de experimento/config.py si ese módulo existe.
Si no, se usan los de experimento/barrido_pff.py.

# [DUDA] el desglose guarda una sola causa por paso, en el orden de clasificar_rechazo.
# [DUDA] con --rho las posiciones se sortean como en el barrido y todos los agentes son rapidos.
"""

from __future__ import annotations

import argparse
import csv
import importlib
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experimento.barrido_pff import _generar_posiciones_iniciales  # noqa: E402
from experimento.barrido_pru_fixed import sembrar_corrida, semilla_de  # noqa: E402
from experimento.config import (  # noqa: E402
    MAX_PASOS,
    N_RUNS,
    RHO,
    SEED_BASE,
    fila_procedencia,
    grilla_umbrales,
)
from simulacion.agent_extendido import (  # noqa: E402
    AgentExtendido,
    ContadorReemplazos,
    mover_agentes_con_conflictos,
    sumar_reemplazos,
)
from simulacion.grilla.floor_field import Floor_field  # noqa: E402
from simulacion.nodos.path_selector import PathSelector  # noqa: E402

ESCENARIOS = ("sala_de_clases", "avion_dos_puertas")
ETIQUETA = {1: "I", 2: "II", 3: "III"}
DESTINO = ROOT / "experimento" / "out" / "tabla_reemplazos.csv"
MOTOR = "PRU"
PRU_FIXED = True
REGLAS_ETAPA_EN_PRU = True
CONTAR_REEMPLAZOS = True


def _escenario(nombre):
    esc = importlib.import_module(f"escenarios.{nombre}")
    return {
        "width": int(esc.width),
        "height": int(esc.height),
        "puertas": list(esc.puertas),
        "obstaculos": list(getattr(esc, "obstaculos", []) or []),
    }


def correr(nombre: str, semilla: int, rho: float, u_i: float, u_ii: float):
    esc = _escenario(nombre)
    sembrar_corrida(semilla)
    campo = Floor_field(esc["width"], esc["height"], esc["puertas"], esc["obstaculos"])
    AgentExtendido.instances = []
    AgentExtendido.history = []
    AgentExtendido.ruta_log = []
    selector = PathSelector(campo, pru_fixed=PRU_FIXED)
    rng = random.Random(semilla)
    posiciones = _generar_posiciones_iniciales(
        esc["width"], esc["height"], esc["obstaculos"], rho, rng
    )
    for x, y in posiciones:
        AgentExtendido(
            "rapido",
            campo,
            selector,
            x,
            y,
            U_I=u_i,
            U_II=u_ii,
            pru_fixed=PRU_FIXED,
            reglas_etapa_en_pru=REGLAS_ETAPA_EN_PRU,
            contar_reemplazos=CONTAR_REEMPLAZOS,
        )
    tiempo = 0
    max_ansiedad = 0.0
    for paso in range(MAX_PASOS):
        activos = [a for a in AgentExtendido.instances if a.activo]
        if not activos:
            break
        for agente in activos:
            agente._current_simulation_step = paso
            if agente.ansiedad > max_ansiedad:
                max_ansiedad = agente.ansiedad
        mover_agentes_con_conflictos(AgentExtendido.instances)
        tiempo += 1
    return tiempo, sumar_reemplazos(AgentExtendido.instances), max_ansiedad


def _pct(cuenta: int, pasos: int) -> float:
    return 0.0 if pasos == 0 else 100.0 * cuenta / pasos


def _fila(escenario, etapa, contador, pasos_totales, meta) -> dict:
    pasos = contador.pasos_con_ruta[etapa]
    causas = contador.causas[etapa]
    # [CAMBIO] antes: pct_reemplazada agrupaba todas las causas -> ahora: un % por causa única, y con conservada y ruta_quedarse suman 100
    # [DUDA] el orden de la causa única no se toca; una celda con varias causas solo entra en la primera
    fila = {
        "escenario": escenario,
        "etapa": ETIQUETA[etapa],
        "pasos_con_celda_de_ruta": pasos,
        "pasos_totales": pasos_totales,
        "n_runs": meta["n_runs"],
        "pct_conservada": _pct(contador.conservada[etapa], pasos),
        "pct_ruta_quedarse": _pct(contador.ruta_quedarse[etapa], pasos),
        "pct_ocupada": _pct(causas["ocupada"], pasos),
        "pct_subiria": _pct(causas["subiria"], pasos),
        "pct_no_minimo_absoluto": _pct(causas["no_minimo_absoluto"], pasos),
        "pct_no_minimo_libre": _pct(causas["no_minimo_libre"], pasos),
        "pct_no_vecina": _pct(causas["no_vecina"], pasos),
        "pasos_mas_de_una_causa": contador.multicausa[etapa],
    }
    fila.update(meta)
    return fila


def _filas_combinaciones(escenario, etapa, contador, meta) -> list[dict]:
    pasos = contador.pasos_con_ruta[etapa]
    filas = []
    for combinacion, cuenta in sorted(contador.combinaciones[etapa].items()):
        fila = {
            "escenario": escenario,
            "etapa": ETIQUETA[etapa],
            "combinacion": combinacion,
            "pasos": cuenta,
            "pct_de_pasos_con_ruta": _pct(cuenta, pasos),
            "pasos_mas_de_una_causa": contador.multicausa[etapa],
            "pasos_con_celda_de_ruta": pasos,
        }
        fila.update(meta)
        filas.append(fila)
    return filas


def _meta(rho, u_i, u_ii, n) -> dict:
    # [DUDA] PRU no construye Agente; ramirez2021 queda False
    meta = fila_procedencia(
        motor=MOTOR,
        ramirez2021=False,
        pru_fixed=PRU_FIXED,
        reglas_etapa_en_pru=REGLAS_ETAPA_EN_PRU,
        rho=rho,
        ui=u_i,
        uii=u_ii,
        n_runs=n,
    )
    meta["contar_reemplazos"] = CONTAR_REEMPLAZOS
    meta["semilla_base"] = SEED_BASE
    return meta


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rho", type=float, default=RHO)
    parser.add_argument("--UI", type=float, default=None)
    parser.add_argument("--UII", type=float, default=None)
    parser.add_argument("--n", type=int, default=N_RUNS)
    parser.add_argument(
        "--salida",
        type=Path,
        default=DESTINO,
        help="CSV de salida. Por defecto experimento/out/tabla_reemplazos.csv",
    )
    args = parser.parse_args()
    # [DUDA] si no se pasa --UI, se usa el primer par de la grilla (d_inv mínimo, U_I=1000, U_II=2000), no se barre sola. Con ese umbral estas corridas no salen de la etapa I.
    if args.UI is None:
        u_i, u_ii = grilla_umbrales()[0]
    else:
        u_i = args.UI
        u_ii = args.UII if args.UII is not None else 2.0 * u_i
    d_inv = 1.0 / u_i
    meta = _meta(args.rho, u_i, u_ii, args.n)
    filas = []
    combinaciones = []
    for escenario in ESCENARIOS:
        total = ContadorReemplazos()
        pasos_totales = 0
        llego_iii = False
        for i in range(args.n):
            semilla = semilla_de(args.rho, d_inv, i)
            tiempo, contador, max_ansiedad = correr(escenario, semilla, args.rho, u_i, u_ii)
            total.sumar(contador)
            pasos_totales += tiempo
            if max_ansiedad > u_ii:
                llego_iii = True
            print(
                f"{escenario} semilla={semilla} T={tiempo} max_ansiedad={max_ansiedad}",
                flush=True,
            )
        print(
            f"{escenario} etapa III={'sí' if llego_iii else 'no'} "
            f"corridas={args.n} pasos_totales={pasos_totales}",
            flush=True,
        )
        for etapa in (1, 2, 3):
            fila = _fila(escenario, etapa, total, pasos_totales, meta)
            filas.append(fila)
            combinaciones.extend(_filas_combinaciones(escenario, etapa, total, meta))
            print(
                f"  etapa {fila['etapa']}: corridas={fila['n_runs']} "
                f"pasos_totales={fila['pasos_totales']} "
                f"pasos_con_ruta={fila['pasos_con_celda_de_ruta']} "
                f"conservada={fila['pct_conservada']:.1f}% "
                f"ruta_quedarse={fila['pct_ruta_quedarse']:.1f}% "
                f"ocupada={fila['pct_ocupada']:.1f}% "
                f"subiria={fila['pct_subiria']:.1f}% "
                f"no_minimo_absoluto={fila['pct_no_minimo_absoluto']:.1f}% "
                f"no_minimo_libre={fila['pct_no_minimo_libre']:.1f}% "
                f"no_vecina={fila['pct_no_vecina']:.1f}% "
                f"mas_de_una={fila['pasos_mas_de_una_causa']}",
                flush=True,
            )
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    with args.salida.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(filas[0].keys()))
        writer.writeheader()
        writer.writerows(filas)
    print(f"Saved {args.salida}", flush=True)
    destino_comb = args.salida.with_name(args.salida.stem + "_combinaciones.csv")
    campos_comb = [
        "escenario",
        "etapa",
        "combinacion",
        "pasos",
        "pct_de_pasos_con_ruta",
        "pasos_mas_de_una_causa",
        "pasos_con_celda_de_ruta",
        *meta.keys(),
    ]
    with destino_comb.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=campos_comb)
        writer.writeheader()
        writer.writerows(combinaciones)
    print(f"Saved {destino_comb} filas={len(combinaciones)}", flush=True)


if __name__ == "__main__":
    main()
