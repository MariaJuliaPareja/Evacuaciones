"""sigma_T versus U_I from the seeded dynamic-stress CSVs. Does not simulate."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import f as f_dist

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT_DIR = ROOT / "figures" / "out"
N = 100
DF = N - 1
ALPHA = 0.05
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
                    "n": int(float(row["n_sims"])),
                }
            )
    return rows


def emparejar(pff: list[dict], pru: list[dict]) -> list[dict]:
    pares = []
    for a in pff:
        b = min(pru, key=lambda r: abs(r["rho"] - a["rho"]) + abs(np.log(r["d_inv"]) - np.log(a["d_inv"])))
        if abs(b["rho"] - a["rho"]) > 1e-9 or abs(np.log(b["d_inv"]) - np.log(a["d_inv"])) > 1e-6:
            raise RuntimeError(f"sin par para rho={a['rho']} d_inv={a['d_inv']}")
        sa, sb = a["sd"], b["sd"]
        if sa == 0 and sb == 0:
            pval, relacion = 1.0, "indistinguible"
        elif sa == 0 or sb == 0:
            pval, relacion = 0.0, ("PRU menor" if sb < sa else "PRU mayor")
        else:
            estadistico = (sb ** 2) / (sa ** 2)
            if estadistico >= 1:
                pval = 2.0 * float(f_dist.sf(estadistico, DF, DF))
            else:
                pval = 2.0 * float(f_dist.cdf(estadistico, DF, DF))
            pval = min(pval, 1.0)
            if pval >= ALPHA:
                relacion = "indistinguible"
            elif sb < sa:
                relacion = "PRU menor"
            else:
                relacion = "PRU mayor"
        pares.append(
            {
                "rho": a["rho"],
                "U": a["U"],
                "d_inv": a["d_inv"],
                "T_pff": a["T"],
                "T_pru": b["T"],
                "sd_pff": sa,
                "sd_pru": sb,
                "cv_pff": sa / a["T"],
                "cv_pru": sb / b["T"],
                "p": pval,
                "relacion": relacion,
                "n": a["n"],
            }
        )
    return pares


def reportar(nombre: str, pares: list[dict]) -> None:
    print(f"=== {nombre} n={pares[0]['n']} F bilateral alpha={ALPHA} gl={DF},{DF} ===")
    orden = sorted(pares, key=lambda r: (r["rho"], r["U"]))
    print("escenario | rho | U_I | sigma_PFF | sigma_PRU | CV_PFF | CV_PRU | relacion | p")
    for r in orden:
        print(
            f"{nombre} | {r['rho']:g} | {r['U']:.6g} | {r['sd_pff']:.4f} | {r['sd_pru']:.4f} | "
            f"{r['cv_pff']:.4f} | {r['cv_pru']:.4f} | {r['relacion']} | {r['p']:.4g}"
        )
    print("--- conteo ---")
    for rho in RHOS:
        sub = [r for r in pares if abs(r["rho"] - rho) < 1e-9]
        conteo = {k: sum(1 for r in sub if r["relacion"] == k) for k in ("PRU menor", "PRU mayor", "indistinguible")}
        print(f"{nombre} rho={rho:g} n={len(sub)} {conteo}")
    total = {k: sum(1 for r in pares if r["relacion"] == k) for k in ("PRU menor", "PRU mayor", "indistinguible")}
    print(f"{nombre} total {len(pares)} {total}")
    print("--- min sigma vs min T del PFF ---")
    for rho in RHOS:
        sub = [r for r in pares if abs(r["rho"] - rho) < 1e-9]
        por_t = min(sub, key=lambda r: r["T_pff"])
        por_s = min(sub, key=lambda r: r["sd_pff"])
        mismo = abs(por_t["d_inv"] - por_s["d_inv"]) < 1e-12
        print(
            f"{nombre} rho={rho:g} minT U_I={por_t['U']:.6g} T={por_t['T_pff']:.2f} sigma={por_t['sd_pff']:.4f} | "
            f"minSigma U_I={por_s['U']:.6g} sigma={por_s['sd_pff']:.4f} T={por_s['T_pff']:.2f} | coincide={mismo}"
        )


def figura(datos: dict[str, list[dict]]) -> None:
    apply_style()
    fig, axes = plt.subplots(2, 4, figsize=(11.6, 6.15), sharex=True)
    letters = "abcdefgh"
    for row_i, (scenario, title) in enumerate(SCENARIOS):
        pares = datos[scenario]
        for col, rho in enumerate(RHOS):
            ax = axes[row_i, col]
            sub = sorted((r for r in pares if abs(r["rho"] - rho) < 1e-9), key=lambda r: r["U"])
            for key, color, label in (("sd_pff", PFF_COLOR, "PFF"), ("sd_pru", PRU_COLOR, "PRU")):
                u = np.array([r["U"] for r in sub])
                y = np.array([r[key] for r in sub])
                ax.plot(
                    u,
                    y,
                    color=color,
                    marker="o",
                    markersize=3.2,
                    linewidth=1.15,
                    label=label,
                    zorder=3,
                )
                imin = int(np.argmin(y))
                ax.scatter(
                    [u[imin]],
                    [y[imin]],
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
                ax.set_ylabel(title + "\n" + r"$\sigma_T$ (steps)")
            if row_i == 1:
                ax.set_xlabel(r"$U_I$")
            ax.grid(True, which="both", linewidth=0.3, alpha=0.45)
    handles, _labels = axes[0, 0].get_legend_handles_labels()
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
    fig.legend(handles=handles, loc="lower center", ncol=3, frameon=False, bbox_to_anchor=(0.5, 0.005))
    fig.subplots_adjust(left=0.08, right=0.985, bottom=0.14, top=0.93, wspace=0.32, hspace=0.28)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_DIR / "sigma_vs_UI.pdf", format="pdf", bbox_inches="tight", pad_inches=0.04)
    fig.savefig(OUT_DIR / "sigma_vs_UI.png", format="png", dpi=200, bbox_inches="tight", pad_inches=0.04)
    plt.close(fig)
    print("wrote", OUT_DIR / "sigma_vs_UI.pdf")


def main() -> None:
    datos = {}
    for scenario, _title in SCENARIOS:
        pff = leer(ROOT / f"tabla_{scenario}_pff_ramirez2021_seeded.csv")
        pru = leer(ROOT / f"tabla_{scenario}_pru_fixed.csv")
        pares = emparejar(pff, pru)
        for row in pares:
            row["scenario"] = scenario
        datos[scenario] = pares
        reportar(scenario, pares)
    todos = [r for pares in datos.values() for r in pares]
    total = {k: sum(1 for r in todos if r["relacion"] == k) for k in ("PRU menor", "PRU mayor", "indistinguible")}
    print("GLOBAL", len(todos), total)
    global_s = min(todos, key=lambda r: r["sd_pff"])
    print(
        "GLOBAL min sigma PFF",
        global_s["scenario"],
        f"rho={global_s['rho']:g} U_I={global_s['U']:.6g} sigma={global_s['sd_pff']:.4f} T={global_s['T_pff']:.2f}",
    )
    figura(datos)


if __name__ == "__main__":
    main()
