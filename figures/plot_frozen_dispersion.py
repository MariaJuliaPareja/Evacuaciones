"""Dispersion figures from figures/out/frozen_summary.csv. Does not simulate."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT_DIR = ROOT / "figures" / "out"
CSV_PATH = OUT_DIR / "frozen_summary.csv"

RHOS = (0.25, 0.5, 0.75, 1.0)
STAGES = ("I", "II", "III")
MOTORS = ("pff", "pru")
SCENARIOS = (
    ("sala_de_clases", "Classroom"),
    ("avion_dos_puertas", "Aircraft"),
)
STAGE_COLORS = {"I": "#2ca02c", "II": "#f1c40f", "III": "#d62728"}
STAGE_SHORT = {"I": "Stage I", "II": "Stage II", "III": "Stage III"}
STYLES = {"pff": "-", "pru": "--"}
MOTOR_NAME = {"pff": "PFF", "pru": "PRU"}


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


def load_rows() -> list[dict]:
    rows = []
    with CSV_PATH.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            t_mean = float(row["T_mean"])
            sigma = float(row["T_sd"])
            rows.append(
                {
                    "scenario": row["escenario"],
                    "rho": float(row["rho"]),
                    "motor": row["motor"],
                    "stage": row["etapa"],
                    "T_mean": t_mean,
                    "sigma": sigma,
                    "SE": float(row["SE"]),
                    "cv": sigma / t_mean,
                }
            )
    return rows


def serie(rows: list[dict], scenario: str, motor: str, stage: str) -> list[dict]:
    found = [
        row
        for row in rows
        if row["scenario"] == scenario and row["motor"] == motor and row["stage"] == stage
    ]
    return sorted(found, key=lambda row: row["rho"])


def save_figure(fig: plt.Figure, stem: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_DIR / f"{stem}.pdf", format="pdf", bbox_inches="tight", pad_inches=0.06)
    fig.savefig(OUT_DIR / f"{stem}.png", format="png", dpi=200, bbox_inches="tight", pad_inches=0.06)
    plt.close(fig)
    print("wrote", OUT_DIR / f"{stem}.pdf", flush=True)


def draw(rows: list[dict], ykey: str, ylabel: str, stem: str, with_error: bool, linear: bool) -> None:
    apply_style()
    log_axes = []

    def build(log: bool) -> plt.Figure:
        fig, axes = plt.subplots(1, 2, figsize=(7.6, 3.8))
        fig.subplots_adjust(left=0.08, right=0.98, bottom=0.24, top=0.90, wspace=0.28)
        for ax, (nombre, title), letter in zip(axes, SCENARIOS, ("(a)", "(b)")):
            values = []
            for stage in STAGES:
                for motor in MOTORS:
                    points = serie(rows, nombre, motor, stage)
                    ys = [row[ykey] for row in points]
                    values.extend(ys)
                    kwargs = dict(
                        color=STAGE_COLORS[stage],
                        linestyle=STYLES[motor],
                        marker="o",
                        markersize=4.2,
                        markeredgecolor="black",
                        markeredgewidth=0.4,
                        linewidth=1.5,
                        zorder=3,
                    )
                    if with_error:
                        ax.errorbar(
                            [row["rho"] for row in points],
                            ys,
                            yerr=[row["SE"] for row in points],
                            capsize=2.5,
                            elinewidth=0.8,
                            **kwargs,
                        )
                    else:
                        ax.plot([row["rho"] for row in points], ys, **kwargs)
            factor = max(values) / min(values)
            use_log = log and factor > 10.0
            if use_log:
                ax.set_yscale("log")
                log_axes.append(nombre)
            ax.set_xticks(list(RHOS))
            ax.set_xticklabels(["0.25", "0.5", "0.75", "1"])
            ax.set_xlabel(r"$\rho$")
            ax.set_xlim(0.16, 1.09)
            ax.set_title(title)
            ax.set_ylabel(ylabel)
            ax.grid(True, which="both" if use_log else "major", linewidth=0.3, alpha=0.45)
            ax.text(
                0.03,
                0.97,
                letter,
                transform=ax.transAxes,
                ha="left",
                va="top",
                fontsize=12,
                fontweight="bold",
            )
            print(f"{stem} {nombre} {ykey} max/min = {factor:.2f}", flush=True)
        handles = [Line2D([0], [0], color=STAGE_COLORS[key], lw=2.0, label=STAGE_SHORT[key]) for key in STAGES]
        handles.extend(
            [
                Line2D([0], [0], color="black", lw=1.6, linestyle="-", label="PFF"),
                Line2D([0], [0], color="black", lw=1.6, linestyle="--", label="PRU"),
            ]
        )
        fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, 0.01), ncol=5, frameon=False)
        return fig

    if linear:
        save_figure(build(False), stem)
    log_axes.clear()
    fig_log = build(True)
    if log_axes:
        save_figure(fig_log, f"{stem}_log")
    else:
        plt.close(fig_log)
        print(f"{stem}: rango dentro de un factor 10, sin version log", flush=True)


def report(rows: list[dict]) -> None:
    top = max(rows, key=lambda row: row["T_mean"])
    print(
        "MAX_T",
        top["scenario"],
        top["rho"],
        MOTOR_NAME[top["motor"]],
        top["stage"],
        f"{top['T_mean']:.2f}",
        flush=True,
    )
    print("escenario | rho | motor | etapa | sigma_T | sigma_T/<T>")
    order = {"sala_de_clases": 0, "avion_dos_puertas": 1, "pff": 0, "pru": 1, "I": 0, "II": 1, "III": 2}
    ordered = sorted(rows, key=lambda row: (order[row["scenario"]], row["rho"], order[row["motor"]], order[row["stage"]]))
    for row in ordered:
        print(
            f"{row['scenario']} | {row['rho']:g} | {MOTOR_NAME[row['motor']]} | {row['stage']} | "
            f"{row['sigma']:.2f} | {row['cv']:.4f}"
        )
    print("--- menores ---")
    for scenario, _title in SCENARIOS:
        for motor in MOTORS:
            for rho in RHOS:
                group = [
                    row
                    for row in rows
                    if row["scenario"] == scenario and row["motor"] == motor and abs(row["rho"] - rho) < 1e-9
                ]
                by_sigma = min(group, key=lambda row: row["sigma"])
                by_cv = min(group, key=lambda row: row["cv"])
                print(
                    f"{scenario} {MOTOR_NAME[motor]} rho={rho:g}: "
                    f"min sigma etapa {by_sigma['stage']} ({by_sigma['sigma']:.2f})  "
                    f"min CV etapa {by_cv['stage']} ({by_cv['cv']:.4f})"
                )
    print("--- PRU vs PFF sigma ---")
    for scenario, _title in SCENARIOS:
        for stage in STAGES:
            for rho in RHOS:
                pff = next(
                    row
                    for row in rows
                    if row["scenario"] == scenario
                    and row["motor"] == "pff"
                    and row["stage"] == stage
                    and abs(row["rho"] - rho) < 1e-9
                )
                pru = next(
                    row
                    for row in rows
                    if row["scenario"] == scenario
                    and row["motor"] == "pru"
                    and row["stage"] == stage
                    and abs(row["rho"] - rho) < 1e-9
                )
                marca = "PRU menor" if pru["sigma"] < pff["sigma"] else "PFF menor o igual"
                print(
                    f"{scenario} etapa {stage} rho={rho:g}: "
                    f"PFF {pff['sigma']:.2f}  PRU {pru['sigma']:.2f}  {marca}"
                )


def main() -> None:
    rows = load_rows()
    draw(rows, "T_mean", r"$\langle T \rangle$ (steps)", "T_vs_rho_frozen", with_error=True, linear=False)
    draw(rows, "sigma", r"$\sigma_T$ (steps)", "sigma_vs_rho_frozen", with_error=False, linear=True)
    report(rows)


if __name__ == "__main__":
    main()
