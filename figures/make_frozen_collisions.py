"""Medias de conflictos, apuestas y victorias con estres fijo.

No cambia quien se mueve. Rehace las mismas semillas de los instantaneos
(200 corridas, posiciones fijas) y de frozen_summary.csv (100 corridas).
Comprueba que <T> coincide antes de escribir.
"""

from __future__ import annotations

import csv
import os
import random
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import make_frozen_stress as frozen
from experimento.barrido_pff import SEED_BASE

SUMMARY = frozen.OUT_DIR / "frozen_summary.csv"
RHOS = frozen.RHOS


def _trabajo(kind: str, scenario: str, motor: str, stage: str, stress0: int, rho: float, n: int, posiciones) -> dict:
    return {
        "kind": kind,
        "scenario": scenario,
        "motor": motor,
        "stage": stage,
        "stress0": stress0,
        "rho": float(rho),
        "n": n,
        "max_pasos": frozen.MAX_PASOS,
        "posiciones": posiciones,
    }


def trabajos(posiciones) -> list[dict]:
    jobs = []
    for motor in ("pff", "pru"):
        for stage, stress0 in frozen.STAGES:
            jobs.append(_trabajo("snap", "sala_de_clases", motor, stage, stress0, frozen.SNAP_RHO, frozen.N_SNAP, posiciones))
    for scenario in ("sala_de_clases", "avion_dos_puertas"):
        for rho in RHOS:
            for motor in ("pff", "pru"):
                for stage, stress0 in frozen.STAGES:
                    jobs.append(_trabajo("curve", scenario, motor, stage, stress0, rho, frozen.N_CURVE, None))
    return jobs


def ejecutar(spec: dict) -> dict:
    escenario = frozen.SCENARIOS[spec["scenario"]]["module"]
    ff = frozen._campo(escenario)
    selector = None
    if spec["motor"] == "pru":
        from simulacion.nodos.path_selector import PathSelector

        selector = PathSelector(ff, umbral_recalculo=0.6, anxiety_thresholds=(30, 70), pru_fixed=True)
    times = []
    censored = 0
    conflictos = []
    apuestas = []
    victorias = []
    for i in range(int(spec["n"])):
        if spec["kind"] == "snap":
            semilla = SEED_BASE + i
            random.seed(semilla)
            np.random.seed(semilla)
            posiciones = spec["posiciones"]
        else:
            semilla = frozen.semilla_curva(spec["rho"], i)
            random.seed(semilla)
            np.random.seed(semilla)
            posiciones = frozen._posiciones(escenario, spec["rho"], semilla)
        una: list[dict] = []
        if spec["motor"] == "pff":
            steps, flag, _, _ = frozen.run_pff(ff, posiciones, spec["stress0"], spec["max_pasos"], False, 0, una)
        else:
            steps, flag, _, _ = frozen.run_pru(
                ff, selector, posiciones, spec["stress0"], spec["max_pasos"], False, 0, una
            )
        times.append(int(steps))
        censored += int(flag)
        cuenta = una[0]
        etapa = spec["stage"]
        if cuenta.get("conflictos_etapa", {}).get(etapa, 0) != cuenta["conflictos"]:
            raise RuntimeError(f"conflicto de otra etapa en {spec}")
        if cuenta.get("apuestas_etapa", {}).get(etapa, 0) != cuenta["apuestas"]:
            raise RuntimeError(f"apuesta de otra etapa en {spec}")
        conflictos.append(cuenta["conflictos"])
        apuestas.append(cuenta["apuestas"])
        victorias.append(cuenta["victorias"])
        if (i + 1) % 50 == 0:
            print(f"  {spec['kind']} {spec['scenario']} {spec['motor']} {spec['stage']} rho={spec['rho']:g} {i + 1}/{spec['n']}", flush=True)
    media, sd, _se = frozen._stats(times)
    print(
        f"done {spec['kind']} {spec['scenario']} {spec['motor']} {spec['stage']} rho={spec['rho']:g} "
        f"<T>={media:.2f} conflicts={float(np.mean(conflictos)):.2f}",
        flush=True,
    )
    return {
        "kind": spec["kind"],
        "scenario": spec["scenario"],
        "motor": spec["motor"],
        "stage": spec["stage"],
        "rho": float(spec["rho"]),
        "T_mean": media,
        "T_sd": sd,
        "censored": censored,
        "conflictos": float(np.mean(conflictos)),
        "apuestas": float(np.mean(apuestas)),
        "victorias": float(np.mean(victorias)),
    }


def _esperados_curva() -> dict[tuple, dict]:
    out = {}
    with SUMMARY.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            key = (row["escenario"], row["motor"], row["etapa"], round(float(row["rho"]), 2))
            out[key] = row
    return out


def _esperados_snap() -> dict[tuple, tuple[float, float]]:
    out = {}
    for motor in ("pff", "pru"):
        for stage, stress0 in frozen.STAGES:
            spec = {
                "kind": "snap",
                "scenario": "sala_de_clases",
                "motor": motor,
                "stage": stage,
                "stress0": stress0,
                "rho": frozen.SNAP_RHO,
                "n": frozen.N_SNAP,
                "max_pasos": frozen.MAX_PASOS,
            }
            loaded = frozen.cargar(spec)
            if loaded is None:
                raise SystemExit(f"falta cache de instantanea {motor} {stage}")
            out[(motor, stage)] = (loaded["T_mean"], loaded["T_sd"], loaded)
    return out


def comprobar(filas: list[dict], curvas: dict, snaps: dict) -> None:
    for fila in filas:
        if fila["censored"]:
            raise SystemExit(f"censurado {fila}")
        if fila["kind"] == "curve":
            key = (fila["scenario"], fila["motor"], fila["stage"], round(fila["rho"], 2))
            previo = curvas[key]
            if abs(fila["T_mean"] - float(previo["T_mean"])) > 1e-4 or abs(fila["T_sd"] - float(previo["T_sd"])) > 1e-4:
                raise SystemExit(f"<T> distinto del CSV en {key}: {fila['T_mean']} vs {previo['T_mean']}")
        else:
            media, sd, _loaded = snaps[(fila["motor"], fila["stage"])]
            if abs(fila["T_mean"] - media) > 1e-4 or abs(fila["T_sd"] - sd) > 1e-4:
                raise SystemExit(
                    f"<T> distinto del instantaneo {fila['motor']} {fila['stage']}: {fila['T_mean']} vs {media}"
                )


def escribir_tabla(filas: list[dict]) -> None:
    por_clave = {
        (fila["scenario"], fila["motor"], fila["stage"], round(fila["rho"], 2)): fila
        for fila in filas
        if fila["kind"] == "curve"
    }
    with SUMMARY.open(encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        previos = list(reader)
        campos = list(reader.fieldnames or [])
    for extra in ("conflictos", "apuestas", "victorias"):
        if extra not in campos:
            campos.append(extra)
    with SUMMARY.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=campos)
        writer.writeheader()
        for row in previos:
            key = (row["escenario"], row["motor"], row["etapa"], round(float(row["rho"]), 2))
            nuevo = por_clave[key]
            row["conflictos"] = f"{nuevo['conflictos']:.6f}"
            row["apuestas"] = f"{nuevo['apuestas']:.6f}"
            row["victorias"] = f"{nuevo['victorias']:.6f}"
            writer.writerow(row)
    print("wrote", SUMMARY, flush=True)


def figuras(filas: list[dict], snaps: dict) -> None:
    rows = []
    for fila in filas:
        if fila["kind"] != "snap":
            continue
        _media, _sd, loaded = snaps[(fila["motor"], fila["stage"])]
        loaded["colisiones"] = {
            "conflictos": fila["conflictos"],
            "apuestas": fila["apuestas"],
            "victorias": fila["victorias"],
        }
        rows.append(loaded)
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    frozen.plot_snapshots(plt, rows)


def main() -> None:
    posiciones = frozen._posiciones(frozen.classroom, frozen.SNAP_RHO, SEED_BASE)
    curvas = _esperados_curva()
    snaps = _esperados_snap()
    jobs = trabajos(posiciones)
    workers = max(1, os.cpu_count() or 2)
    print(f"jobs {len(jobs)} workers {workers}", flush=True)
    filas = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(ejecutar, spec) for spec in jobs]
        for fut in as_completed(futures):
            filas.append(fut.result())
    comprobar(filas, curvas, snaps)
    escribir_tabla(filas)
    figuras(filas, snaps)
    for fila in sorted(filas, key=lambda row: (row["kind"], row["scenario"], row["rho"], row["motor"], row["stage"])):
        print(
            f"{fila['kind']} {fila['scenario']} {fila['motor']} {fila['stage']} rho={fila['rho']:g} "
            f"conflicts={fila['conflictos']:.2f} bets={fila['apuestas']:.2f} wins={fila['victorias']:.2f}",
            flush=True,
        )


if __name__ == "__main__":
    main()
