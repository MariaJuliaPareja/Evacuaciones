"""Occupation maps at rho=1 for three thresholds.

Motors: corrected PFF (ramirez2021=True) and PRU (pru_fixed=True).
Seeds match experimento/barrido_pru_fixed.py. Does not modify the motors
and does not overwrite occupation_classroom.* or occupation_aircraft.*.

Outputs:
  figures/out/occupation_classroom_thresholds.pdf / .png / .npz
  figures/out/occupation_aircraft_thresholds.pdf / .png / .npz
"""

from __future__ import annotations

import csv
import importlib.util
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import random

from escenarios import avion_dos_puertas as aircraft_scenario
from escenarios import sala_de_clases as classroom_scenario
from experimento.barrido_pff import (
    D_INV_VALS,
    MAX_PASOS,
    SEED_BASE,
    _generar_posiciones_iniciales,
)
from experimento.metricas import _desv_estandar_poblacional
def _load_figure_helpers():
    spec = importlib.util.spec_from_file_location(
        "make_paper_figures",
        ROOT / "figures" / "make_paper_figures.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_helpers = _load_figure_helpers()
draw_cells = _helpers.draw_cells
draw_doors = _helpers.draw_doors
interior_seats = _helpers.interior_seats
style_map_axes = _helpers.style_map_axes
wall_cells = _helpers.wall_cells
from simulacion.agent_extendido import AgentExtendido, mover_agentes_con_conflictos
from simulacion.agentes import Agente, mover_agentes
from simulacion.grilla.floor_field import Floor_field
from simulacion.nodos.path_selector import PathSelector

OUT_DIR = ROOT / "figures" / "out"
N_RUNS = 100
RHO = 1.0


def apply_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.labelsize": 11,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "legend.fontsize": 10,
            "axes.linewidth": 0.8,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "savefig.dpi": 200,
        }
    )


def d_inv_de(u_objetivo: float) -> float:
    vals = [float(v) for v in D_INV_VALS]
    return min(vals, key=lambda v: abs((1.0 / v) - u_objetivo))


def optimo_pff(scenario_name: str) -> float:
    path = ROOT / f"tabla_{scenario_name}_pff_ramirez2021_seeded.csv"
    best_u = None
    best_t = None
    with path.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if abs(float(row["rho"]) - RHO) > 1e-9:
                continue
            t = float(row["T_mean"])
            u = 1.0 / float(row["d_inv"])
            if best_t is None or t < best_t:
                best_t = t
                best_u = u
    if best_u is None:
        raise RuntimeError(f"No rho=1 row in {path}")
    return float(best_u)


def semilla_de(d_inv: float, i: int) -> int:
    return SEED_BASE + i + int(1_000_000 * RHO) + int(10_000 * float(d_inv))


def run_pff(ff: Floor_field, posiciones, u_i: float) -> tuple[np.ndarray, int]:
    agentes = [
        Agente(x, y, ff, U_I=u_i, U_II=2.0 * u_i, ramirez2021=True) for x, y in posiciones
    ]
    counts = np.zeros((ff.height, ff.width), dtype=np.int32)
    steps = 0
    while any(a.activo for a in agentes) and steps < MAX_PASOS:
        occupied = {(a.x, a.y) for a in agentes if a.activo}
        for x, y in occupied:
            counts[y, x] += 1
        mover_agentes(agentes)
        steps += 1
    fraction = counts.astype(np.float64) / float(steps) if steps else np.zeros_like(counts, dtype=float)
    return fraction, steps


def run_pru(ff: Floor_field, selector: PathSelector, posiciones, u_i: float) -> tuple[np.ndarray, int]:
    AgentExtendido.instances = []
    AgentExtendido.history = []
    AgentExtendido.ruta_log = []
    selector.anxiety_decisions.clear()
    selector.recalculo_log.clear()
    selector.limpiar_cache()
    agentes = [
        AgentExtendido(
            agent_type="rapido",
            floor_field=ff,
            path_selector=selector,
            x=x,
            y=y,
            U_I=u_i,
            U_II=2.0 * u_i,
            pru_fixed=True,
        )
        for x, y in posiciones
    ]
    counts = np.zeros((ff.height, ff.width), dtype=np.int32)
    steps = 0
    while any(a.activo for a in agentes) and steps < MAX_PASOS:
        occupied = {
            (a.pos_x, a.pos_y) for a in agentes if a.activo and a.pos_x is not None
        }
        for x, y in occupied:
            counts[y, x] += 1
        for agente in agentes:
            if agente.activo:
                agente._current_simulation_step = steps
        mover_agentes_con_conflictos(agentes)
        AgentExtendido.ruta_log.clear()
        steps += 1
    fraction = counts.astype(np.float64) / float(steps) if steps else np.zeros_like(counts, dtype=float)
    return fraction, steps


def ensemble(scenario, motor: str, d_inv: float) -> dict:
    ff = Floor_field(scenario.width, scenario.height, list(scenario.puertas), list(scenario.obstaculos))
    selector = None
    if motor == "pru":
        selector = PathSelector(ff, umbral_recalculo=0.6, anxiety_thresholds=(30, 70), pru_fixed=True)
    u_i = 1.0 / d_inv
    mean = np.zeros((ff.height, ff.width), dtype=np.float64)
    times: list[int] = []
    for i in range(N_RUNS):
        semilla = semilla_de(d_inv, i)
        random.seed(semilla)
        np.random.seed(semilla)
        rng = random.Random(semilla)
        posiciones = _generar_posiciones_iniciales(
            scenario.width, scenario.height, list(scenario.obstaculos), RHO, rng
        )
        if motor == "pru":
            fraction, steps = run_pru(ff, selector, posiciones, u_i)
        else:
            fraction, steps = run_pff(ff, posiciones, u_i)
        mean += fraction
        times.append(steps)
        if (i + 1) % 25 == 0:
            print(f"  {scenario.__name__} {motor} U_I={u_i:.4g}: {i + 1}/{N_RUNS}", flush=True)
    mean /= float(N_RUNS)
    return {
        "mean": mean,
        "T_mean": float(np.mean(times)),
        "T_sd": float(_desv_estandar_poblacional(times)),
        "ff": ff,
        "U_I": u_i,
        "d_inv": d_inv,
    }


def draw_map(ax, mean, ff, panel, star_size):
    walls = wall_cells(ff.width, ff.height, list(ff.puertas))
    seats = interior_seats(ff.obstaculos, ff.width, ff.height)
    masked = np.ma.array(mean, mask=np.zeros(mean.shape, dtype=bool))
    for x, y in walls + seats + [tuple(p) for p in ff.puertas]:
        if 0 <= y < masked.shape[0] and 0 <= x < masked.shape[1]:
            masked[y, x] = np.ma.masked
    cmap = plt.cm.inferno.copy()
    cmap.set_bad("white")
    image = ax.imshow(
        masked,
        origin="lower",
        cmap=cmap,
        vmin=0.0,
        vmax=1.0,
        interpolation="nearest",
        extent=(-0.5, ff.width - 0.5, -0.5, ff.height - 0.5),
        zorder=1,
    )
    draw_cells(ax, seats, "#d9d9d9", "black", 0.4, 2)
    draw_doors(ax, ff.puertas, star_size)
    style_map_axes(ax, ff.width, ff.height, panel)
    return image


def save_figure(stem: str, ff, panels: list[dict], star_size: float, figsize, column_labels: list[str]) -> None:
    fig, axes = plt.subplots(2, 3, figsize=figsize)
    fig.subplots_adjust(left=0.07, right=0.86, bottom=0.08, top=0.90, wspace=0.38, hspace=0.42)
    image = None
    letters = "abcdef"
    row_names = ("PFF", "PRU")
    for index, panel in enumerate(panels):
        r, c = divmod(index, 3)
        ax = axes[r, c]
        image = draw_map(ax, panel["mean"], ff, f"({letters[index]})", star_size)
        if r == 0:
            ax.set_title(column_labels[c], fontsize=10)
            ax.set_xlabel("")
        if c == 0:
            ax.set_ylabel(row_names[r] + "\n" + r"$y$ (cells)")
        else:
            ax.set_ylabel("")
        ax.annotate(
            rf"$\langle T \rangle$ = {panel['T_mean']:.2f} $\pm$ {panel['T_sd']:.2f}",
            xy=(0.5, 0.0),
            xycoords="axes fraction",
            xytext=(0, -32),
            textcoords="offset points",
            ha="center",
            va="top",
            fontsize=8,
            annotation_clip=False,
        )
    fig.canvas.draw()
    box = axes[0, 2].get_position()
    box_b = axes[1, 2].get_position()
    cax = fig.add_axes([box.x1 + 0.03, box_b.y0, 0.018, box.y1 - box_b.y0])
    colorbar = fig.colorbar(image, cax=cax)
    colorbar.set_label("Mean occupation probability")
    fig.legend(
        handles=[
            Line2D(
                [0],
                [0],
                marker="*",
                color="none",
                markerfacecolor="red",
                markeredgecolor="black",
                markersize=12,
                label="Door",
            ),
            Patch(facecolor="#d9d9d9", edgecolor="black", label="Seat/desk"),
        ],
        loc="lower center",
        ncol=2,
        frameon=False,
        bbox_to_anchor=(0.46, 0.005),
    )
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_DIR / f"{stem}.pdf", format="pdf", bbox_inches="tight", pad_inches=0.05)
    fig.savefig(OUT_DIR / f"{stem}.png", format="png", dpi=200, bbox_inches="tight", pad_inches=0.05)
    plt.close(fig)


def run_scenario(scenario, name: str, stem: str, figsize, star_size: float) -> None:
    u_opt = optimo_pff(name)
    thresholds = [
        ("$U_I = 1000$", d_inv_de(1000.0)),
        (rf"$U_I = {u_opt:.3g}$", d_inv_de(u_opt)),
        ("$U_I = 1$", d_inv_de(1.0)),
    ]
    print(f"{name} thresholds", [(lab, d, 1 / d) for lab, d in thresholds], flush=True)
    panels = []
    store = {}
    for motor in ("pff", "pru"):
        for label, d_inv in thresholds:
            result = ensemble(scenario, motor, d_inv)
            result["label"] = label
            result["motor"] = motor
            panels.append(result)
            print(
                f"  done {motor} U_I={result['U_I']:.6g} "
                f"<T>={result['T_mean']:.2f} ± {result['T_sd']:.2f}",
                flush=True,
            )
            key = f"{motor}_{result['U_I']:.6g}"
            store[f"mean_{key}"] = result["mean"]
            store[f"T_{key}"] = np.array([result["T_mean"], result["T_sd"]])
    save_figure(stem, panels[0]["ff"], panels, star_size, figsize, [lab for lab, _ in thresholds])
    np.savez(OUT_DIR / f"{stem}.npz", rho=np.array(RHO), n_runs=np.array(N_RUNS), **store)
    print("wrote", OUT_DIR / f"{stem}.pdf", flush=True)


def main() -> None:
    apply_style()
    run_scenario(classroom_scenario, "sala_de_clases", "occupation_classroom_thresholds", (11.4, 7.4), 120)
    run_scenario(aircraft_scenario, "avion_dos_puertas", "occupation_aircraft_thresholds", (8.6, 11.2), 42)


if __name__ == "__main__":
    main()
