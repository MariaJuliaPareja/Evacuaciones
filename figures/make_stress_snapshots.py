"""Classroom snapshots of the real PFF motor at three initial stress levels.

Does not modify any simulation module. Movement, conflicts and stress updates
come from simulacion.agentes. Positions come from the PFF sweep sampler.

Outputs (figures/out/):
  stress_snapshots_actual.pdf / .png
  stress_snapshots_ramirez2021.pdf / .png
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle

from escenarios import sala_de_clases as classroom
from experimento.barrido_pff import SEED_BASE, _generar_posiciones_iniciales
from experimento.metricas import _desv_estandar_poblacional
from simulacion.agentes import Agente, mover_agentes
from simulacion.grilla.floor_field import Floor_field

OUT_DIR = ROOT / "figures" / "out"

RHO = 0.5
U_I = 10
U_II = 20
N_RUNS = 200
MAX_PASOS = 500
POSITION_SEED = SEED_BASE
DYNAMICS_SEED = SEED_BASE
REQUESTED_T = 25

STAGE_COLORS = {
    "I": "#2ca02c",
    "II": "#f1c40f",
    "III": "#d62728",
}
STAGE_LABELS = {
    "I": "Stage I (mild)",
    "II": "Stage II (optimal)",
    "III": "Stage III (anxiety)",
}
CASES = (
    ("(a)", 0, "I"),
    ("(b)", U_I + 1, "II"),
    ("(c)", U_II + 1, "III"),
)


def apply_style() -> None:
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


def save_figure(fig: plt.Figure, stem: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_DIR / f"{stem}.pdf", format="pdf", bbox_inches="tight", pad_inches=0.06)
    fig.savefig(OUT_DIR / f"{stem}.png", format="png", dpi=200, bbox_inches="tight", pad_inches=0.06)
    plt.close(fig)


def stage_of(stress: float) -> str:
    if stress <= U_I:
        return "I"
    if stress <= U_II:
        return "II"
    return "III"


def initial_positions() -> list[tuple[int, int]]:
    rng = random.Random(POSITION_SEED)
    return _generar_posiciones_iniciales(
        classroom.width,
        classroom.height,
        list(classroom.obstaculos),
        RHO,
        rng,
    )


def rollout(posiciones, stress0: int, ramirez2021: bool, dyn_seed: int) -> list[list[tuple]]:
    """One evacuation. Each frame is the state after that step."""
    random.seed(dyn_seed)
    agentes = [
        Agente(
            x,
            y,
            FIELD,
            U_I=U_I,
            U_II=U_II,
            ramirez2021=ramirez2021,
            stress_inicial=stress0,
        )
        for x, y in posiciones
    ]
    frames = []
    for _ in range(MAX_PASOS):
        if not any(a.activo for a in agentes):
            break
        mover_agentes(agentes)
        frames.append([(a.x, a.y, a.stress, a.activo) for a in agentes])
    return frames


def evacuation_time(frames: list) -> int:
    for idx, frame in enumerate(frames):
        if all(not activo for _, _, _, activo in frame):
            return idx + 1
    return len(frames)


def mean_active(histories: list[list], t: int) -> float:
    total = 0
    for frames in histories:
        frame = frames[t - 1]
        total += sum(1 for *_, activo in frame if activo)
    return total / len(histories)


def choose_snapshot_t(histories: list[list], n_agents: int) -> int:
    """t = 25 unless the room is already almost empty; then the t closest to half."""
    longest = min(len(h) for h in histories)
    if REQUESTED_T <= longest and mean_active(histories, REQUESTED_T) >= 0.25 * n_agents:
        return REQUESTED_T
    target = n_agents / 2.0
    best_t = 1
    best_err = float("inf")
    for t in range(1, longest + 1):
        err = abs(mean_active(histories, t) - target)
        if err < best_err:
            best_err = err
            best_t = t
    return best_t


def stage_counts(frame) -> dict[str, int]:
    counts = {"I": 0, "II": 0, "III": 0}
    for _, _, stress, activo in frame:
        if activo:
            counts[stage_of(stress)] += 1
    return counts


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


def draw_panel(ax, frame, panel: str, t_mean: float, t_sd: float) -> None:
    draw_cells(ax, wall_cells(), "black", "black", 0.4, 1)
    draw_cells(ax, list(classroom.obstaculos), "#d9d9d9", "black", 0.6, 2)
    xs, ys, colors = [], [], []
    for x, y, stress, activo in frame:
        if not activo:
            continue
        xs.append(x)
        ys.append(y)
        colors.append(STAGE_COLORS[stage_of(stress)])
    ax.scatter(
        xs,
        ys,
        s=42,
        c=colors,
        edgecolors="black",
        linewidths=0.4,
        zorder=4,
    )
    dx, dy = zip(*classroom.puertas)
    ax.scatter(
        dx,
        dy,
        marker="*",
        s=140,
        c="red",
        edgecolors="black",
        linewidths=0.6,
        zorder=6,
    )
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(-0.8, classroom.width - 0.2)
    ax.set_ylim(-0.8, classroom.height - 0.2)
    ax.set_xlabel(r"$x$ (cells)")
    ax.set_ylabel(r"$y$ (cells)")
    ax.set_xticks(list(range(0, classroom.width, 2)))
    ax.set_yticks(list(range(0, classroom.height, 2)))
    for spine in ax.spines.values():
        spine.set_linewidth(0.8)
    ax.set_title(
        rf"$\langle T \rangle$ = {t_mean:.2f} $\pm$ {t_sd:.2f} steps (full evacuation)",
        fontsize=8,
        pad=4,
    )
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


def evacuation_stats(posiciones, stress0: int, ramirez2021: bool) -> tuple[float, float]:
    times = []
    for i in range(N_RUNS):
        frames = rollout(posiciones, stress0, ramirez2021, DYNAMICS_SEED + i)
        times.append(evacuation_time(frames))
        if (i + 1) % 50 == 0:
            tag = "ramirez2021" if ramirez2021 else "actual"
            print(f"  {tag} s0={stress0}: {i + 1}/{N_RUNS}", flush=True)
    arr = np.asarray(times, dtype=float)
    return float(arr.mean()), float(_desv_estandar_poblacional(times))


def make_figure(ramirez2021: bool, posiciones) -> dict:
    tag = "ramirez2021" if ramirez2021 else "actual"
    print(f"Snapshot trajectories ({tag})", flush=True)
    histories = [
        rollout(posiciones, stress0, ramirez2021, DYNAMICS_SEED) for _, stress0, _ in CASES
    ]
    t_snap = choose_snapshot_t(histories, len(posiciones))
    print(f"  snapshot t={t_snap}", flush=True)

    stats = []
    for (_, stress0, _), frames in zip(CASES, histories):
        mean_t, sd_t = evacuation_stats(posiciones, stress0, ramirez2021)
        counts = stage_counts(frames[t_snap - 1])
        n_left = sum(counts.values())
        stats.append(
            {
                "stress0": stress0,
                "T_mean": mean_t,
                "T_sd": sd_t,
                "counts": counts,
                "n_left": n_left,
            }
        )
        print(
            f"  s0={stress0} <T>={mean_t:.2f} ± {sd_t:.2f}  "
            f"left={n_left} stages={counts}",
            flush=True,
        )

    fig, axes = plt.subplots(1, 3, figsize=(11.0, 3.9))
    fig.subplots_adjust(left=0.05, right=0.99, bottom=0.24, top=0.82, wspace=0.35)
    for ax, (panel, _, _), frames, item in zip(axes, CASES, histories, stats):
        draw_panel(ax, frames[t_snap - 1], panel, item["T_mean"], item["T_sd"])
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
    fig.legend(
        handles=handles,
        loc="lower center",
        bbox_to_anchor=(0.5, 0.01),
        ncol=3,
        frameon=False,
    )
    save_figure(fig, f"stress_snapshots_{tag}")
    return {"t": t_snap, "stats": stats, "tag": tag}


def main() -> None:
    global FIELD
    apply_style()
    FIELD = Floor_field(
        classroom.width,
        classroom.height,
        list(classroom.puertas),
        list(classroom.obstaculos),
    )
    posiciones = initial_positions()
    print(
        f"classroom rho={RHO} U_I={U_I} U_II={U_II} n={len(posiciones)} "
        f"position_seed={POSITION_SEED} dynamics_seed={DYNAMICS_SEED}",
        flush=True,
    )
    actual = make_figure(False, posiciones)
    ramirez = make_figure(True, posiciones)
    print("SNAPSHOT_T", actual["t"], ramirez["t"])
    print("Saved figures/out/stress_snapshots_actual and stress_snapshots_ramirez2021")


if __name__ == "__main__":
    main()
