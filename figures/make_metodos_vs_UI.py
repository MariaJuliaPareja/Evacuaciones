"""<T> versus U_I for PFF, Greedy-4, Greedy-8, A* and PRU.

Reads tabla_metodos_barrido_completo.csv. Does not resimulate.

Outputs:
  figures/out/metodos_vs_UI.pdf
  figures/out/metodos_vs_UI.png
"""

from __future__ import annotations

import csv
import math
import sys
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "figures" / "out"
N = 100
RHOS = (0.25, 0.5, 0.75, 1.0)
ORDER = ("pff", "greedy4", "greedy8", "astar", "pru")
LABELS = {
    "pff": "PFF",
    "greedy4": "Greedy-4",
    "greedy8": "Greedy-8",
    "astar": "A*",
    "pru": "PRU",
}
COLORS = {
    "pff": "#1f77b4",
    "greedy4": "#2ca02c",
    "greedy8": "#98df8a",
    "astar": "#9467bd",
    "pru": "#d62728",
}
COMPARE = ("astar", "greedy4", "greedy8", "pff")


def apply_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.labelsize": 11,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "legend.fontsize": 9,
            "axes.linewidth": 0.8,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "savefig.dpi": 200,
        }
    )


def leer() -> list[dict]:
    rows = []
    with (ROOT / "tabla_metodos_barrido_completo.csv").open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            rows.append(
                {
                    "scenario": row["scenario"],
                    "rho": float(row["rho"]),
                    "d_inv": round(float(row["d_inv"]), 8),
                    "U": float(row["U_I"]),
                    "method": row["method"],
                    "T": float(row["T_mean"]),
                    "sd": float(row["sigma_T"]),
                    "se": float(row["SE"]),
                }
            )
    return rows


def clase(pru: dict, other: dict) -> str:
    se = math.sqrt((pru["sd"] ** 2 + other["sd"] ** 2) / N)
    diff = pru["T"] - other["T"]
    if abs(diff) <= 2.0 * se:
        return "indistinguible"
    return "mejor" if diff < 0 else "peor"


def resumir(rows: list[dict]) -> None:
    index = {(r["scenario"], r["rho"], r["d_inv"], r["method"]): r for r in rows}
    for scenario in ("sala_de_clases", "avion_dos_puertas"):
        for rho in RHOS:
            keys = sorted(
                {
                    d
                    for (s, r, d, _m) in index
                    if s == scenario and abs(r - rho) < 1e-9
                }
            )
            for other in COMPARE:
                conteo = Counter()
                for d_inv in keys:
                    pru = index[(scenario, rho, d_inv, "pru")]
                    alt = index[(scenario, rho, d_inv, other)]
                    conteo[clase(pru, alt)] += 1
                print(
                    f"{scenario} rho={rho} PRU vs {other}: "
                    f"mejor={conteo['mejor']} peor={conteo['peor']} "
                    f"indistinguible={conteo['indistinguible']}",
                    flush=True,
                )


def main() -> None:
    apply_style()
    rows = leer()
    resumir(rows)
    fig, axes = plt.subplots(2, 4, figsize=(11.8, 6.3), sharex=True)
    letters = "abcdefgh"
    names = {"sala_de_clases": "Classroom", "avion_dos_puertas": "Aircraft"}
    for row_i, scenario in enumerate(("sala_de_clases", "avion_dos_puertas")):
        for col, rho in enumerate(RHOS):
            ax = axes[row_i, col]
            for method in ORDER:
                series = sorted(
                    (
                        r
                        for r in rows
                        if r["scenario"] == scenario
                        and r["method"] == method
                        and abs(r["rho"] - rho) < 1e-9
                    ),
                    key=lambda r: r["U"],
                )
                u = np.array([r["U"] for r in series])
                t = np.array([r["T"] for r in series])
                se = np.array([r["se"] for r in series])
                ax.errorbar(
                    u,
                    t,
                    yerr=se,
                    color=COLORS[method],
                    marker="o",
                    markersize=2.6,
                    linewidth=1.05,
                    capsize=1.5,
                    elinewidth=0.6,
                    label=LABELS[method],
                )
            ax.set_xscale("log")
            ax.set_xticks([1, 10, 100, 1000])
            ax.set_xticklabels(["1", "10", "100", "1000"])
            ax.text(
                0.03,
                0.97,
                f"({letters[row_i * 4 + col]})",
                transform=ax.transAxes,
                ha="left",
                va="top",
                fontsize=11,
                fontweight="bold",
            )
            if row_i == 0:
                ax.set_title(rf"$\rho = {rho:g}$")
            if col == 0:
                ax.set_ylabel(names[scenario] + "\n" + r"$\langle T \rangle$ (steps)")
            if row_i == 1:
                ax.set_xlabel(r"$U_I$")
            ax.grid(True, which="both", linewidth=0.3, alpha=0.4)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        loc="lower center",
        ncol=5,
        frameon=False,
        bbox_to_anchor=(0.5, 0.005),
    )
    fig.subplots_adjust(left=0.08, right=0.985, bottom=0.14, top=0.93, wspace=0.32, hspace=0.28)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_DIR / "metodos_vs_UI.pdf", format="pdf", bbox_inches="tight", pad_inches=0.04)
    fig.savefig(OUT_DIR / "metodos_vs_UI.png", format="png", dpi=200, bbox_inches="tight", pad_inches=0.04)
    plt.close(fig)
    print("wrote", OUT_DIR / "metodos_vs_UI.pdf", flush=True)


if __name__ == "__main__":
    main()
