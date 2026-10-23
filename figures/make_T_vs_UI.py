"""<T> versus U_I for seeded corrected PFF and pru_fixed PRU.

Reads the existing CSVs. Does not resimulate and does not modify the motors.

Outputs:
  figures/out/T_vs_UI.pdf
  figures/out/T_vs_UI.png
"""

from __future__ import annotations

import csv
import math
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT_DIR = ROOT / "figures" / "out"
N = 100
RHOS = (0.25, 0.5, 0.75, 1.0)
SCENARIOS = (
    ("sala_de_clases", "Classroom"),
    ("avion_dos_puertas", "Aircraft"),
)
PFF_COLOR = "#1f77b4"
PRU_COLOR = "#d62728"


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


def leer(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            rows.append(
                {
                    "rho": float(row["rho"]),
                    "d_inv": float(row["d_inv"]),
                    "U": 1.0 / float(row["d_inv"]),
                    "T": float(row["T_mean"]),
                    "sd": float(row["sigma_T"]),
                    "se": float(row["sigma_T"]) / math.sqrt(N),
                }
            )
    return rows


def grupo(rows: list[dict], rho: float) -> list[dict]:
    return sorted((r for r in rows if abs(r["rho"] - rho) < 1e-9), key=lambda r: r["U"])


def main() -> None:
    apply_style()
    fig, axes = plt.subplots(2, 4, figsize=(11.6, 6.15), sharex=True)
    letters = "abcdefgh"
    for row_i, (scenario, title) in enumerate(SCENARIOS):
        pff = leer(ROOT / f"tabla_{scenario}_pff_ramirez2021_seeded.csv")
        pru = leer(ROOT / f"tabla_{scenario}_pru_fixed.csv")
        for col, rho in enumerate(RHOS):
            ax = axes[row_i, col]
            gp = grupo(pff, rho)
            gr = grupo(pru, rho)
            for series, color, label in (
                (gp, PFF_COLOR, "PFF"),
                (gr, PRU_COLOR, "PRU"),
            ):
                u = np.array([r["U"] for r in series])
                t = np.array([r["T"] for r in series])
                se = np.array([r["se"] for r in series])
                ax.errorbar(
                    u,
                    t,
                    yerr=se,
                    color=color,
                    marker="o",
                    markersize=3.2,
                    linewidth=1.15,
                    capsize=2,
                    elinewidth=0.7,
                    label=label,
                    zorder=3,
                )
                imin = int(np.argmin(t))
                ax.scatter(
                    [u[imin]],
                    [t[imin]],
                    s=46,
                    facecolors="none",
                    edgecolors=color,
                    linewidths=1.4,
                    marker="o",
                    zorder=4,
                )
            ax.set_xscale("log")
            ax.set_xticks([1, 10, 100, 1000])
            ax.set_xticklabels(["1", "10", "100", "1000"])
            letter = letters[row_i * 4 + col]
            ax.text(
                0.03,
                0.97,
                f"({letter})",
                transform=ax.transAxes,
                ha="left",
                va="top",
                fontsize=11,
                fontweight="bold",
            )
            if row_i == 0:
                ax.set_title(rf"$\rho = {rho:g}$")
            if col == 0:
                ax.set_ylabel(rf"{title}" + "\n" + r"$\langle T \rangle$ (steps)")
            if row_i == 1:
                ax.set_xlabel(r"$U_I$")
            ax.grid(True, which="both", linewidth=0.3, alpha=0.45)

    handles, labels = axes[0, 0].get_legend_handles_labels()
    handles.append(
        plt.Line2D(
            [0],
            [0],
            marker="o",
            color="0.2",
            markerfacecolor="none",
            markeredgewidth=1.4,
            markersize=7,
            linewidth=0,
            label="Minimum",
        )
    )
    fig.legend(
        handles=handles,
        loc="lower center",
        ncol=3,
        frameon=False,
        bbox_to_anchor=(0.5, 0.005),
    )
    fig.subplots_adjust(left=0.08, right=0.985, bottom=0.14, top=0.93, wspace=0.32, hspace=0.28)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_DIR / "T_vs_UI.pdf", format="pdf", bbox_inches="tight", pad_inches=0.04)
    fig.savefig(OUT_DIR / "T_vs_UI.png", format="png", dpi=200, bbox_inches="tight", pad_inches=0.04)
    plt.close(fig)
    print("wrote", OUT_DIR / "T_vs_UI.pdf")


if __name__ == "__main__":
    main()
