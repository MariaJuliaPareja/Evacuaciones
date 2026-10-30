"""Figuras con ansiedad fija en etapa I, II o III.

PFF corregido (ramirez2021=True) y PRU corregido (pru_fixed=True),
frozen_stress=True. U_I=10, U_II=20. s_i = 0, 15 o 25.

Semillas compartidas entre motores y etapas:
- instantaneas: posiciones con random.Random(SEED_BASE); dinamica SEED_BASE+i.
  Aula, rho=0.5, t=15, 200 corridas.
- curvas y ocupacion: SEED_BASE + i + int(1e6*rho), 100 corridas.

Salidas en figures/out/:
  stress_snapshots_frozen.pdf/.png
  stress_snapshots_pru_frozen.pdf/.png
  T_vs_rho_frozen.pdf/.png
  occupation_classroom_frozen.pdf/.png
  occupation_aircraft_frozen.pdf/.png
"""

from __future__ import annotations

import argparse
import csv
import math
import os
import random
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from escenarios import avion_dos_puertas as aircraft
from escenarios import sala_de_clases as classroom
from experimento.barrido_pff import SEED_BASE, _generar_posiciones_iniciales
from experimento.metricas import _desv_estandar_poblacional
from simulacion.agent_extendido import AgentExtendido, mover_agentes_con_conflictos
from simulacion.agentes import Agente, mover_agentes
from simulacion.grilla.floor_field import Floor_field
from simulacion.colisiones import registro_vacio
from simulacion.nodos.path_selector import PathSelector

OUT_DIR = ROOT / "figures" / "out"
CACHE_DIR = OUT_DIR / "frozen_cache"

U_I = 10
U_II = 20
STAGES = (("I", 0), ("II", 15), ("III", 25))
RHOS = (0.25, 0.5, 0.75, 1.0)
N_CURVE = 100
N_SNAP = 200
SNAP_T = 15
SNAP_RHO = 0.5
MAX_PASOS = 20000

STAGE_COLORS = {"I": "#2ca02c", "II": "#f1c40f", "III": "#d62728"}
STAGE_LABELS = {
    "I": "Stage I (mild)",
    "II": "Stage II (optimal)",
    "III": "Stage III (anxiety)",
}
STAGE_SHORT = {"I": "Stage I", "II": "Stage II", "III": "Stage III"}
SCENARIOS = {
    "sala_de_clases": {
        "module": classroom,
        "title": "Classroom",
        "star": 120,
        "figsize": (11.4, 7.4),
        "stem": "occupation_classroom_frozen",
    },
    "avion_dos_puertas": {
        "module": aircraft,
        "title": "Aircraft",
        "star": 42,
        "figsize": (8.6, 11.2),
        "stem": "occupation_aircraft_frozen",
    },
}


def semilla_curva(rho: float, i: int) -> int:
    return SEED_BASE + i + int(1_000_000 * float(rho))


def _campo(scenario) -> Floor_field:
    return Floor_field(
        scenario.width,
        scenario.height,
        list(scenario.puertas),
        list(scenario.obstaculos),
    )


def _posiciones(scenario, rho: float, semilla: int) -> list[tuple[int, int]]:
    rng = random.Random(semilla)
    return _generar_posiciones_iniciales(
        scenario.width,
        scenario.height,
        list(scenario.obstaculos),
        rho,
        rng,
    )


def _limpiar_pru(selector: PathSelector) -> None:
    AgentExtendido.ruta_log.clear()
    selector.anxiety_decisions.clear()
    selector.recalculo_log.clear()
    selector.stats["nodes_explored"].clear()


def run_pff(ff: Floor_field, posiciones, stress0: int, max_pasos: int, want_occ: bool, snap_t: int, cuentas: list | None = None):
    agentes = [
        Agente(
            x,
            y,
            ff,
            U_I=U_I,
            U_II=U_II,
            ramirez2021=True,
            stress_inicial=stress0,
            frozen_stress=True,
        )
        for x, y in posiciones
    ]
    registro = registro_vacio() if cuentas is not None else None
    counts = np.zeros((ff.height, ff.width), dtype=np.int32) if want_occ else None
    frame = None
    steps = 0
    while any(a.activo for a in agentes) and steps < max_pasos:
        if counts is not None:
            for agente in agentes:
                if agente.activo:
                    counts[agente.y, agente.x] += 1
        mover_agentes(agentes, registro)
        steps += 1
        if snap_t and steps == snap_t:
            frame = [(a.x, a.y, a.stress, a.activo) for a in agentes]
    censored = int(any(a.activo for a in agentes))
    if snap_t and frame is None:
        frame = [(a.x, a.y, a.stress, False) for a in agentes]
    fraction = None
    if counts is not None:
        fraction = counts.astype(np.float64) / float(steps) if steps else np.zeros_like(counts, dtype=float)
    if cuentas is not None and registro is not None:
        cuentas.append(registro)
    return steps, censored, frame, fraction


def run_pru(ff, selector, posiciones, stress0: int, max_pasos: int, want_occ: bool, snap_t: int, cuentas: list | None = None):
    AgentExtendido.instances = []
    AgentExtendido.history = []
    AgentExtendido.ruta_log = []
    _limpiar_pru(selector)
    agentes = []
    for x, y in posiciones:
        agente = AgentExtendido(
            agent_type="rapido",
            floor_field=ff,
            path_selector=selector,
            x=x,
            y=y,
            U_I=U_I,
            U_II=U_II,
            pru_fixed=True,
            frozen_stress=True,
        )
        agente.ansiedad = stress0
        agentes.append(agente)
    registro = registro_vacio() if cuentas is not None else None
    counts = np.zeros((ff.height, ff.width), dtype=np.int32) if want_occ else None
    frame = None
    steps = 0
    while any(a.activo for a in agentes) and steps < max_pasos:
        if counts is not None:
            for agente in agentes:
                if agente.activo and agente.pos_x is not None:
                    counts[agente.pos_y, agente.pos_x] += 1
        for agente in agentes:
            if agente.activo:
                agente._current_simulation_step = steps
        mover_agentes_con_conflictos(agentes, registro=registro)
        _limpiar_pru(selector)
        steps += 1
        if snap_t and steps == snap_t:
            frame = [(a.pos_x, a.pos_y, a.ansiedad, a.activo) for a in agentes]
    censored = int(any(a.activo for a in agentes))
    if snap_t and frame is None:
        frame = [(a.pos_x, a.pos_y, a.ansiedad, False) for a in agentes]
    fraction = None
    if counts is not None:
        fraction = counts.astype(np.float64) / float(steps) if steps else np.zeros_like(counts, dtype=float)
    if cuentas is not None and registro is not None:
        cuentas.append(registro)
    return steps, censored, frame, fraction


def _stats(times: list[int]) -> tuple[float, float, float]:
    media = float(np.mean(times))
    sd = float(_desv_estandar_poblacional(times))
    se = sd / math.sqrt(len(times))
    return media, sd, se


def ejecutar_job(spec: dict) -> dict:
    nombre = spec["scenario"]
    escenario = SCENARIOS[nombre]["module"]
    ff = _campo(escenario)
    selector = None
    if spec["motor"] == "pru":
        selector = PathSelector(ff, umbral_recalculo=0.6, anxiety_thresholds=(30, 70), pru_fixed=True)
    n = int(spec["n"])
    rho = float(spec["rho"])
    stress0 = int(spec["stress0"])
    kind = spec["kind"]
    max_pasos = int(spec["max_pasos"])
    want_occ = bool(spec["want_occ"])
    times: list[int] = []
    censored = 0
    occ = None
    frame = None
    t0 = time.perf_counter()
    for i in range(n):
        if kind == "snap":
            semilla = SEED_BASE + i
            random.seed(semilla)
            np.random.seed(semilla)
            posiciones = spec["posiciones"]
            snap_t = SNAP_T if i == 0 else 0
        else:
            semilla = semilla_curva(rho, i)
            random.seed(semilla)
            np.random.seed(semilla)
            posiciones = _posiciones(escenario, rho, semilla)
            snap_t = 0
        if spec["motor"] == "pff":
            steps, flag, got_frame, fraction = run_pff(
                ff, posiciones, stress0, max_pasos, want_occ, snap_t
            )
        else:
            steps, flag, got_frame, fraction = run_pru(
                ff, selector, posiciones, stress0, max_pasos, want_occ, snap_t
            )
        times.append(int(steps))
        censored += int(flag)
        if got_frame is not None:
            frame = got_frame
        if fraction is not None:
            occ = fraction if occ is None else occ + fraction
        if (i + 1) % 25 == 0:
            print(
                f"  {kind} {nombre} {spec['motor']} {spec['stage']} rho={rho:g} {i + 1}/{n}",
                flush=True,
            )
    if occ is not None:
        occ = occ / float(n)
    media, sd, se = _stats(times)
    elapsed = time.perf_counter() - t0
    print(
        f"done {kind} {nombre} {spec['motor']} {spec['stage']} rho={rho:g} "
        f"<T>={media:.2f} ± {sd:.2f} censored={censored} {elapsed:.1f}s",
        flush=True,
    )
    return {
        "kind": kind,
        "scenario": nombre,
        "motor": spec["motor"],
        "stage": spec["stage"],
        "rho": rho,
        "stress0": stress0,
        "times": np.asarray(times, dtype=np.int32),
        "censored": censored,
        "T_mean": media,
        "T_sd": sd,
        "SE": se,
        "occ": occ,
        "frame": frame,
        "elapsed": elapsed,
    }


def cache_path(spec: dict) -> Path:
    rho = float(spec["rho"])
    return CACHE_DIR / (
        f"{spec['kind']}_{spec['scenario']}_{spec['motor']}_{spec['stage']}"
        f"_rho{rho:.2f}_n{spec['n']}_max{spec['max_pasos']}.npz"
    )


def guardar(spec: dict, result: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "times": result["times"],
        "censored": np.array(result["censored"]),
        "T_mean": np.array(result["T_mean"]),
        "T_sd": np.array(result["T_sd"]),
        "SE": np.array(result["SE"]),
        "rho": np.array(result["rho"]),
        "stress0": np.array(result["stress0"]),
    }
    if result["occ"] is not None:
        payload["occ"] = result["occ"]
    if result["frame"] is not None:
        frame = result["frame"]
        payload["fx"] = np.array([p[0] for p in frame], dtype=np.int32)
        payload["fy"] = np.array([p[1] for p in frame], dtype=np.int32)
        payload["fs"] = np.array([p[2] for p in frame], dtype=np.float64)
        payload["fa"] = np.array([p[3] for p in frame], dtype=np.int32)
    np.savez(cache_path(spec), **payload)


def cargar(spec: dict) -> dict | None:
    path = cache_path(spec)
    if not path.exists():
        return None
    data = np.load(path)
    frame = None
    if "fx" in data:
        frame = list(zip(data["fx"].tolist(), data["fy"].tolist(), data["fs"].tolist(), data["fa"].tolist()))
    return {
        "kind": spec["kind"],
        "scenario": spec["scenario"],
        "motor": spec["motor"],
        "stage": spec["stage"],
        "rho": float(spec["rho"]),
        "stress0": int(spec["stress0"]),
        "times": data["times"],
        "censored": int(data["censored"]),
        "T_mean": float(data["T_mean"]),
        "T_sd": float(data["T_sd"]),
        "SE": float(data["SE"]),
        "occ": data["occ"] if "occ" in data else None,
        "frame": frame,
    }


def trabajos(max_pasos: int) -> list[dict]:
    posiciones = _posiciones(classroom, SNAP_RHO, SEED_BASE)
    jobs = []
    for motor in ("pff", "pru"):
        for stage, stress0 in STAGES:
            jobs.append(
                {
                    "kind": "snap",
                    "scenario": "sala_de_clases",
                    "motor": motor,
                    "stage": stage,
                    "stress0": stress0,
                    "rho": SNAP_RHO,
                    "n": N_SNAP,
                    "max_pasos": max_pasos,
                    "want_occ": False,
                    "posiciones": posiciones,
                }
            )
    for nombre in ("sala_de_clases", "avion_dos_puertas"):
        for rho in RHOS:
            for motor in ("pff", "pru"):
                for stage, stress0 in STAGES:
                    jobs.append(
                        {
                            "kind": "curve",
                            "scenario": nombre,
                            "motor": motor,
                            "stage": stage,
                            "stress0": stress0,
                            "rho": float(rho),
                            "n": N_CURVE,
                            "max_pasos": max_pasos,
                            "want_occ": abs(float(rho) - 1.0) < 1e-9,
                            "posiciones": None,
                        }
                    )
    return jobs


def correr(jobs: list[dict], workers: int) -> list[dict]:
    pendientes = []
    listos = []
    for spec in jobs:
        cached = cargar(spec)
        if cached is not None and cached["censored"] == 0:
            listos.append(cached)
        else:
            pendientes.append(spec)
    print(f"cache {len(listos)}  pending {len(pendientes)}  workers {workers}", flush=True)
    if not pendientes:
        return listos
    if workers <= 1:
        for spec in pendientes:
            result = ejecutar_job(spec)
            guardar(spec, result)
            listos.append(result)
        return listos
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(ejecutar_job, spec): spec for spec in pendientes}
        for fut in as_completed(futures):
            spec = futures[fut]
            result = fut.result()
            guardar(spec, result)
            listos.append(result)
    return listos


def apply_style(plt) -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 11,
            "axes.labelsize": 12,
            "xtick.labelsize": 11,
            "ytick.labelsize": 11,
            "legend.fontsize": 11,
            "axes.linewidth": 0.8,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "savefig.dpi": 200,
        }
    )


def save_figure(plt, fig, stem: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_DIR / f"{stem}.pdf", format="pdf", bbox_inches="tight", pad_inches=0.06)
    fig.savefig(OUT_DIR / f"{stem}.png", format="png", dpi=200, bbox_inches="tight", pad_inches=0.06)
    plt.close(fig)
    print("wrote", OUT_DIR / f"{stem}.pdf", flush=True)


def stage_of(stress: float) -> str:
    if stress <= U_I:
        return "I"
    if stress <= U_II:
        return "II"
    return "III"


def wall_cells() -> list[tuple[int, int]]:
    doors = set(classroom.puertas)
    cells = []
    for x in range(classroom.width):
        for y in range(classroom.height):
            if x == 0 or x == classroom.width - 1 or y == 0 or y == classroom.height - 1:
                if (x, y) not in doors:
                    cells.append((x, y))
    return cells


def draw_cells(ax, cells, face, edge, lw, zorder) -> None:
    from matplotlib.patches import Rectangle

    for x, y in cells:
        ax.add_patch(
            Rectangle(
                (x - 0.5, y - 0.5),
                1.0,
                1.0,
                facecolor=face,
                edgecolor=edge,
                linewidth=lw,
                zorder=zorder,
            )
        )


def draw_panel(ax, frame, panel: str, t_mean: float, t_sd: float, colisiones: dict | None = None) -> None:
    draw_cells(ax, wall_cells(), "black", "black", 0.4, 1)
    draw_cells(ax, list(classroom.obstaculos), "#d9d9d9", "black", 0.6, 2)
    xs, ys, colors = [], [], []
    for x, y, stress, activo in frame:
        if not activo:
            continue
        xs.append(x)
        ys.append(y)
        colors.append(STAGE_COLORS[stage_of(stress)])
    if xs:
        ax.scatter(xs, ys, s=42, c=colors, edgecolors="black", linewidths=0.4, zorder=4)
    dx, dy = zip(*classroom.puertas)
    ax.scatter(dx, dy, marker="*", s=140, c="red", edgecolors="black", linewidths=0.6, zorder=6)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(-0.8, classroom.width - 0.2)
    ax.set_ylim(-0.8, classroom.height - 0.2)
    ax.set_xlabel(r"$x$ (cells)")
    ax.set_ylabel(r"$y$ (cells)")
    ax.set_xticks(list(range(0, classroom.width, 2)))
    ax.set_yticks(list(range(0, classroom.height, 2)))
    for spine in ax.spines.values():
        spine.set_linewidth(0.8)
    titulo = rf"$\langle T \rangle$ = {t_mean:.2f} $\pm$ {t_sd:.2f} steps (full evacuation)"
    if colisiones is not None:
        titulo += (
            "\n"
            + rf"conflicts {colisiones['conflictos']:.2f}, "
            + rf"bets {colisiones['apuestas']:.2f}, "
            + rf"wins {colisiones['victorias']:.2f}"
        )
    ax.set_title(titulo, fontsize=8, pad=4)
    ax.text(
        0.02,
        0.98,
        panel,
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=12,
        fontweight="bold",
        zorder=8,
        bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.9),
    )


def plot_snapshots(plt, rows: list[dict]) -> None:
    from matplotlib.lines import Line2D

    apply_style(plt)
    for motor, stem in (("pff", "stress_snapshots_frozen"), ("pru", "stress_snapshots_pru_frozen")):
        chosen = [
            row
            for row in rows
            if row["kind"] == "snap" and row["motor"] == motor
        ]
        chosen.sort(key=lambda row: "III".index(row["stage"]) if row["stage"] != "III" else 2)
        order = {"I": 0, "II": 1, "III": 2}
        chosen.sort(key=lambda row: order[row["stage"]])
        tiene_colisiones = any(row.get("colisiones") for row in chosen)
        alto = 4.35 if tiene_colisiones else 3.9
        techo = 0.78 if tiene_colisiones else 0.82
        fig, axes = plt.subplots(1, 3, figsize=(11.0, alto))
        fig.subplots_adjust(left=0.05, right=0.99, bottom=0.22 if tiene_colisiones else 0.24, top=techo, wspace=0.35)
        for ax, row, panel in zip(axes, chosen, ("(a)", "(b)", "(c)")):
            draw_panel(ax, row["frame"], panel, row["T_mean"], row["T_sd"], row.get("colisiones"))
            n_left = sum(1 for *_, activo in row["frame"] if activo)
            counts = {"I": 0, "II": 0, "III": 0}
            for _, _, stress, activo in row["frame"]:
                if activo:
                    counts[stage_of(stress)] += 1
            print(
                f"snap {motor} {row['stage']} <T>={row['T_mean']:.2f} ± {row['T_sd']:.2f} "
                f"left={n_left} stages={counts}",
                flush=True,
            )
        handles = [
            Line2D(
                [0],
                [0],
                marker="o",
                color="none",
                markerfacecolor=STAGE_COLORS[key],
                markeredgecolor="black",
                markeredgewidth=0.6,
                markersize=8,
                label=STAGE_LABELS[key],
            )
            for key in ("I", "II", "III")
        ]
        fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, 0.01), ncol=3, frameon=False)
        save_figure(plt, fig, stem)


def plot_curves(plt, rows: list[dict]) -> None:
    from matplotlib.lines import Line2D

    apply_style(plt)
    plt.rcParams.update({"font.size": 10, "axes.labelsize": 11, "legend.fontsize": 10})
    fig, axes = plt.subplots(1, 2, figsize=(7.6, 3.8))
    fig.subplots_adjust(left=0.08, right=0.98, bottom=0.24, top=0.90, wspace=0.28)
    styles = {"pff": "-", "pru": "--"}
    for ax, nombre, letter in zip(axes, ("sala_de_clases", "avion_dos_puertas"), ("(a)", "(b)")):
        for stage, _ in STAGES:
            for motor in ("pff", "pru"):
                serie = [
                    row
                    for row in rows
                    if row["kind"] == "curve"
                    and row["scenario"] == nombre
                    and row["motor"] == motor
                    and row["stage"] == stage
                ]
                serie.sort(key=lambda row: row["rho"])
                ax.errorbar(
                    [row["rho"] for row in serie],
                    [row["T_mean"] for row in serie],
                    yerr=[row["SE"] for row in serie],
                    color=STAGE_COLORS[stage],
                    linestyle=styles[motor],
                    marker="o",
                    markersize=4.2,
                    markeredgecolor="black",
                    markeredgewidth=0.4,
                    linewidth=1.5,
                    capsize=2.5,
                    elinewidth=0.8,
                    zorder=3,
                )
        ax.set_xticks(list(RHOS))
        ax.set_xticklabels(["0.25", "0.5", "0.75", "1"])
        ax.set_xlabel(r"$\rho$")
        ax.set_xlim(0.16, 1.09)
        ax.set_title(SCENARIOS[nombre]["title"])
        ax.set_ylabel(r"$\langle T \rangle$ (steps)")
        ax.grid(True, linewidth=0.3, alpha=0.45)
        ax.text(0.03, 0.97, letter, transform=ax.transAxes, ha="left", va="top", fontsize=12, fontweight="bold")
    handles = [
        Line2D([0], [0], color=STAGE_COLORS[key], lw=2.0, label=STAGE_SHORT[key])
        for key in ("I", "II", "III")
    ]
    handles.extend(
        [
            Line2D([0], [0], color="black", lw=1.6, linestyle="-", label="PFF"),
            Line2D([0], [0], color="black", lw=1.6, linestyle="--", label="PRU"),
        ]
    )
    fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, 0.01), ncol=5, frameon=False)
    save_figure(plt, fig, "T_vs_rho_frozen")


def plot_occupation(rows: list[dict]) -> None:
    import importlib.util

    import matplotlib

    matplotlib.use("Agg")
    spec = importlib.util.spec_from_file_location(
        "make_occupation_thresholds",
        ROOT / "figures" / "make_occupation_thresholds.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.apply_style()
    order = {"I": 0, "II": 1, "III": 2}
    for nombre, info in SCENARIOS.items():
        panels = []
        ff = _campo(info["module"])
        for motor in ("pff", "pru"):
            serie = [
                row
                for row in rows
                if row["kind"] == "curve"
                and row["scenario"] == nombre
                and row["motor"] == motor
                and abs(row["rho"] - 1.0) < 1e-9
            ]
            serie.sort(key=lambda row: order[row["stage"]])
            for row in serie:
                panels.append({"mean": row["occ"], "T_mean": row["T_mean"], "T_sd": row["T_sd"]})
        module.save_figure(
            info["stem"],
            ff,
            panels,
            info["star"],
            info["figsize"],
            [STAGE_SHORT[key] for key in ("I", "II", "III")],
        )
        print("wrote", OUT_DIR / f"{info['stem']}.pdf", flush=True)


def escribir_tabla(rows: list[dict]) -> list[dict]:
    curvas = [row for row in rows if row["kind"] == "curve"]
    curvas.sort(key=lambda row: (row["scenario"], row["rho"], row["motor"], "III".find(row["stage"])))
    order = {"I": 0, "II": 1, "III": 2, "pff": 0, "pru": 1}
    curvas.sort(key=lambda row: (row["scenario"], row["rho"], order[row["motor"]], order[row["stage"]]))
    path = OUT_DIR / "frozen_summary.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["escenario", "rho", "motor", "etapa", "T_mean", "T_sd", "SE", "n", "censored"],
        )
        writer.writeheader()
        for row in curvas:
            writer.writerow(
                {
                    "escenario": row["scenario"],
                    "rho": row["rho"],
                    "motor": row["motor"],
                    "etapa": row["stage"],
                    "T_mean": f"{row['T_mean']:.6f}",
                    "T_sd": f"{row['T_sd']:.6f}",
                    "SE": f"{row['SE']:.6f}",
                    "n": len(row["times"]),
                    "censored": row["censored"],
                }
            )
    return curvas


def reportar(curvas: list[dict]) -> None:
    print("escenario | rho | motor | etapa | <T> ± sd | SE")
    for row in curvas:
        motor = "PFF" if row["motor"] == "pff" else "PRU"
        print(
            f"{row['scenario']} | {row['rho']:g} | {motor} | {row['stage']} | "
            f"{row['T_mean']:.2f} ± {row['T_sd']:.2f} | {row['SE']:.3f}"
        )
    print("--- comparacion ---")
    grupos: dict[tuple, list] = {}
    for row in curvas:
        grupos.setdefault((row["scenario"], row["motor"], row["rho"]), []).append(row)
    for key in sorted(grupos):
        serie = {row["stage"]: row for row in grupos[key]}
        ganador = min(serie.values(), key=lambda row: row["T_mean"])
        escenario, motor, rho = key
        nombre_motor = "PFF" if motor == "pff" else "PRU"
        print(f"{escenario} {nombre_motor} rho={rho:g}: menor <T> en etapa {ganador['stage']}")
        for a, b in (("I", "II"), ("I", "III"), ("II", "III")):
            da = abs(serie[a]["T_mean"] - serie[b]["T_mean"])
            se = math.sqrt(serie[a]["SE"] ** 2 + serie[b]["SE"] ** 2)
            marca = "SI" if da > 2.0 * se else "no"
            print(
                f"  {a}-{b}: |dT|={da:.3f}  2 SE={2.0 * se:.3f}  supera={marca}"
            )


def plot_all(rows: list[dict]) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plot_snapshots(plt, rows)
    plot_curves(plt, rows)
    plot_occupation(rows)


def pilot(max_pasos: int) -> None:
    casos = [
        ("sala_de_clases", "pff", "III", 25, 1.0),
        ("sala_de_clases", "pru", "I", 0, 0.5),
        ("avion_dos_puertas", "pru", "III", 25, 1.0),
        ("avion_dos_puertas", "pff", "III", 25, 1.0),
    ]
    for nombre, motor, stage, stress0, rho in casos:
        spec = {
            "kind": "pilot",
            "scenario": nombre,
            "motor": motor,
            "stage": stage,
            "stress0": stress0,
            "rho": rho,
            "n": 1,
            "max_pasos": max_pasos,
            "want_occ": False,
            "posiciones": _posiciones(SCENARIOS[nombre]["module"], SNAP_RHO, SEED_BASE)
            if nombre == "sala_de_clases"
            else None,
        }
        if spec["posiciones"] is None:
            spec["kind"] = "curve"
        t0 = time.perf_counter()
        result = ejecutar_job(spec)
        print(
            f"PILOT {nombre} {motor} {stage} rho={rho:g} T={result['times'][0]} "
            f"censored={result['censored']} {time.perf_counter() - t0:.2f}s",
            flush=True,
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pilot", action="store_true")
    parser.add_argument("--plot-only", action="store_true")
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--max-pasos", type=int, default=MAX_PASOS)
    args = parser.parse_args()
    if args.pilot:
        pilot(args.max_pasos)
        return
    jobs = trabajos(args.max_pasos)
    if args.plot_only:
        rows = []
        for spec in jobs:
            loaded = cargar(spec)
            if loaded is None:
                raise SystemExit(f"falta cache {cache_path(spec)}")
            rows.append(loaded)
    else:
        workers = args.workers or max(1, (os.cpu_count() or 2) - 0)
        rows = correr(jobs, workers)
    malos = [row for row in rows if row["censored"]]
    if malos:
        for row in malos:
            print(
                f"CENSURADO {row['scenario']} {row['motor']} {row['stage']} rho={row['rho']} "
                f"n={row['censored']}",
                flush=True,
            )
        raise SystemExit("hay corridas que no terminaron")
    curvas = escribir_tabla(rows)
    reportar(curvas)
    plot_all(rows)


if __name__ == "__main__":
    main()
