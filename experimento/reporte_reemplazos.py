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
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experimento.barrido_pff import (  # noqa: E402
    _generar_posiciones_iniciales,
)
from experimento.barrido_pru_fixed import sembrar_corrida, semilla_de  # noqa: E402
from simulacion.agent_extendido import (  # noqa: E402
    AgentExtendido,
    ContadorReemplazos,
    mover_agentes_con_conflictos,
    sumar_reemplazos,
)
from simulacion.grilla.floor_field import Floor_field  # noqa: E402
from simulacion.nodos.path_selector import PathSelector  # noqa: E402

# [CAMBIO] antes: rho, U_I, U_II y n estaban fijos en  la lista del escenario y U=10/20 -> ahora: salen de config.py o de los argumentos
try:
    from experimento import config as _config
except ImportError:
    from experimento import barrido_pff as _config

    _config.N_RUNS = _config.N_SIMS
    _config.RHO = 1.0

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


def _commit() -> str:
    try:
        salida = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        return salida.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "sin-commit"


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
    for paso in range(_config.MAX_PASOS):
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


def _fila(escenario, etapa, contador, pasos_totales, meta) -> dict:
    pasos = contador.pasos_con_ruta[etapa]
    conservada = contador.conservada[etapa]
    reemplazada = contador.reemplazada[etapa]
    causas = contador.causas[etapa]
    desglose = " ".join(f"{causa}={causas[causa]}" for causa in ContadorReemplazos.CAUSAS)
    return {
        "escenario": escenario,
        "etapa": ETIQUETA[etapa],
        "pasos_con_celda_de_ruta": pasos,
        "pasos_totales": pasos_totales,
        "n_runs": meta["n_runs"],
        "pct_conservada": 0.0 if pasos == 0 else 100.0 * conservada / pasos,
        "pct_reemplazada": 0.0 if pasos == 0 else 100.0 * reemplazada / pasos,
        "desglose": desglose,
        "ocupada": causas["ocupada"],
        "subiria": causas["subiria"],
        "no_minimo_libre": causas["no_minimo_libre"],
        "no_vecina": causas["no_vecina"],
        "no_minimo_absoluto": causas["no_minimo_absoluto"],
        "motor": meta["motor"],
        "pru_fixed": meta["pru_fixed"],
        "reglas_etapa_en_pru": meta["reglas_etapa_en_pru"],
        "contar_reemplazos": meta["contar_reemplazos"],
        "rho": meta["rho"],
        "UI": meta["UI"],
        "UII": meta["UII"],
        "semilla_base": meta["semilla_base"],
        "commit": meta["commit"],
        "fecha": meta["fecha"],
    }


def _meta(rho, u_i, u_ii, n) -> dict:
    return {
        "motor": MOTOR,
        "pru_fixed": PRU_FIXED,
        "reglas_etapa_en_pru": REGLAS_ETAPA_EN_PRU,
        "contar_reemplazos": CONTAR_REEMPLAZOS,
        "rho": rho,
        "UI": u_i,
        "UII": u_ii,
        "n_runs": n,
        "semilla_base": _config.SEED_BASE,
        "commit": _commit(),
        "fecha": date.today().isoformat(),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rho", type=float, default=_config.RHO)
    parser.add_argument("--UI", type=float, default=None)
    parser.add_argument("--UII", type=float, default=None)
    parser.add_argument("--n", type=int, default=_config.N_RUNS)
    parser.add_argument(
        "--salida",
        type=Path,
        default=DESTINO,
        help="CSV de salida. Por defecto experimento/out/tabla_reemplazos.csv",
    )
    args = parser.parse_args()
    # [DUDA] si no se pasa --UI, se usa el primer par de la grilla (U_I=1, U_II=2), no se barre sola
    if args.UI is None:
        u_i, u_ii = _config.grilla_umbrales()[0] if hasattr(_config, "grilla_umbrales") else (1.0, 2.0)
    else:
        u_i = args.UI
        u_ii = args.UII if args.UII is not None else 2.0 * u_i
    d_inv = 1.0 / u_i
    meta = _meta(args.rho, u_i, u_ii, args.n)
    filas = []
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
            print(
                f"  etapa {fila['etapa']}: corridas={fila['n_runs']} "
                f"pasos_totales={fila['pasos_totales']} "
                f"pasos_con_ruta={fila['pasos_con_celda_de_ruta']} "
                f"conservada={fila['pct_conservada']:.1f}% "
                f"reemplazada={fila['pct_reemplazada']:.1f}% {fila['desglose']}",
                flush=True,
            )
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    with args.salida.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(filas[0].keys()))
        writer.writeheader()
        writer.writerows(filas)
    print(f"Saved {args.salida}", flush=True)


if __name__ == "__main__":
    main()
