"""Barrido fino de rho con estres fijo. No reescribe figuras ni el CSV previos.

Reutiliza rho = 0.5 y 1.0 de figures/out/frozen_summary.csv.
Simula rho = 0.1, 0.2, 0.3, 0.4, 0.6, 0.7, 0.8, 0.9.
Semilla de cada corrida: SEED_BASE + i + int(1e6 * rho), compartida
entre etapas y motores.
"""

from __future__ import annotations

import csv
import math
import os
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import make_frozen_stress as frozen

OUT_DIR = frozen.OUT_DIR
SUMMARY_IN = OUT_DIR / "frozen_summary.csv"
SUMMARY_OUT = OUT_DIR / "frozen_yd_summary.csv"
RHOS = tuple(k / 10 for k in range(1, 11))
REUSE = (0.5, 1.0)
N = frozen.N_CURVE
MAX_PASOS = frozen.MAX_PASOS
PAIRS = (("I", "II"), ("I", "III"), ("II", "III"))


def rho_nuevo(rho: float) -> bool:
    return not any(abs(rho - viejo) < 1e-9 for viejo in REUSE)


def trabajos() -> list[dict]:
    jobs = []
    for nombre in ("sala_de_clases", "avion_dos_puertas"):
        for rho in RHOS:
            if not rho_nuevo(rho):
                continue
            for motor in ("pff", "pru"):
                for stage, stress0 in frozen.STAGES:
                    jobs.append(
                        {
                            "kind": "curve",
                            "scenario": nombre,
                            "motor": motor,
                            "stage": stage,
                            "stress0": stress0,
                            "rho": float(rho),
                            "n": N,
                            "max_pasos": MAX_PASOS,
                            "want_occ": False,
                            "posiciones": None,
                        }
                    )
    return jobs


def leer_reutilizados() -> list[dict]:
    rows = []
    with SUMMARY_IN.open(encoding="utf-8") as handle:
        for raw in csv.DictReader(handle):
            rho = float(raw["rho"])
            if not any(abs(rho - viejo) < 1e-9 for viejo in REUSE):
                continue
            if int(raw["n"]) != N or int(raw["censored"]) != 0:
                raise SystemExit(f"fila reutilizada no valida: {raw}")
            rows.append(
                {
                    "scenario": raw["escenario"],
                    "rho": rho,
                    "motor": raw["motor"],
                    "stage": raw["etapa"],
                    "T_mean": float(raw["T_mean"]),
                    "T_sd": float(raw["T_sd"]),
                    "SE": float(raw["SE"]),
                    "n": int(raw["n"]),
                    "censored": int(raw["censored"]),
                }
            )
    esperados = 2 * 2 * 2 * 3
    if len(rows) != esperados:
        raise SystemExit(f"se esperaban {esperados} filas reutilizadas, hay {len(rows)}")
    return rows


def filas_nuevas(results: list[dict]) -> list[dict]:
    rows = []
    for row in results:
        if int(row["censored"]) != 0:
            raise SystemExit(
                f"CENSURADO {row['scenario']} {row['motor']} {row['stage']} rho={row['rho']}"
            )
        rows.append(
            {
                "scenario": row["scenario"],
                "rho": float(row["rho"]),
                "motor": row["motor"],
                "stage": row["stage"],
                "T_mean": float(row["T_mean"]),
                "T_sd": float(row["T_sd"]),
                "SE": float(row["SE"]),
                "n": N,
                "censored": 0,
            }
        )
    return rows


def guardar_tabla(rows: list[dict]) -> None:
    order = {"I": 0, "II": 1, "III": 2, "pff": 0, "pru": 1}
    rows = sorted(rows, key=lambda row: (row["scenario"], row["rho"], order[row["motor"]], order[row["stage"]]))
    with SUMMARY_OUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["escenario", "rho", "motor", "etapa", "T_mean", "T_sd", "SE", "n", "censored"],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "escenario": row["scenario"],
                    "rho": f"{row['rho']:.1f}",
                    "motor": row["motor"],
                    "etapa": row["stage"],
                    "T_mean": f"{row['T_mean']:.6f}",
                    "T_sd": f"{row['T_sd']:.6f}",
                    "SE": f"{row['SE']:.6f}",
                    "n": row["n"],
                    "censored": row["censored"],
                }
            )
    print("wrote", SUMMARY_OUT, flush=True)


def grupos(rows: list[dict]) -> dict[tuple, dict]:
    out: dict[tuple, dict] = {}
    for row in rows:
        out.setdefault((row["scenario"], row["motor"], round(row["rho"], 1)), {})[row["stage"]] = row
    return out


def supera(a: dict, b: dict) -> tuple[bool, float, float]:
    delta = abs(a["T_mean"] - b["T_mean"])
    umbral = 2.0 * math.sqrt(a["SE"] ** 2 + b["SE"] ** 2)
    return delta > umbral, delta, umbral


def orden_de(serie: dict) -> str:
    etapas = sorted(("I", "II", "III"), key=lambda stage: (serie[stage]["T_mean"], stage))
    return " < ".join(etapas)


def reportar(rows: list[dict]) -> None:
    print("escenario | motor | rho | I | II | III | orden | I-II | I-III | II-III")
    for key in sorted(grupos(rows)):
        serie = grupos(rows)[key]
        escenario, motor, rho = key
        nombre = "PFF" if motor == "pff" else "PRU"
        marcas = []
        for a, b in PAIRS:
            claro, delta, umbral = supera(serie[a], serie[b])
            marcas.append("si" if claro else "no")
            print(
                f"  par {a}-{b} |dT|={delta:.3f} 2SE={umbral:.3f} supera={'SI' if claro else 'no'}",
                flush=True,
            )
        texto = " | ".join(
            f"{stage} {serie[stage]['T_mean']:.2f} ± {serie[stage]['T_sd']:.2f}"
            for stage in ("I", "II", "III")
        )
        print(
            f"{escenario} | {nombre} | {rho:.1f} | {texto} | {orden_de(serie)} | "
            + " ".join(f"{par[0]}-{par[1]}:{marca}" for par, marca in zip(PAIRS, marcas)),
            flush=True,
        )


def figura(rows: list[dict], motor: str, stem: str) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch

    frozen.apply_style(plt)
    plt.rcParams.update({"font.size": 10, "axes.labelsize": 11, "xtick.labelsize": 9, "legend.fontsize": 10})
    fig, axes = plt.subplots(1, 2, figsize=(8.6, 4.05))
    fig.subplots_adjust(left=0.08, right=0.98, bottom=0.22, top=0.88, wspace=0.28)
    for ax, nombre, letter in zip(axes, ("sala_de_clases", "avion_dos_puertas"), ("(a)", "(b)")):
        for stage, _stress in frozen.STAGES:
            serie = [
                row
                for row in rows
                if row["scenario"] == nombre and row["motor"] == motor and row["stage"] == stage
            ]
            serie.sort(key=lambda row: row["rho"])
            rho = np.array([row["rho"] for row in serie])
            media = np.array([row["T_mean"] for row in serie])
            sd = np.array([row["T_sd"] for row in serie])
            bajo = media - sd
            if np.any(bajo <= 0):
                raise SystemExit(f"banda no positiva en {nombre} {motor} etapa {stage}")
            color = frozen.STAGE_COLORS[stage]
            ax.fill_between(rho, bajo, media + sd, color=color, alpha=0.22, linewidth=0, zorder=2)
            ax.plot(
                rho,
                media,
                color=color,
                marker="o",
                markersize=4.2,
                markeredgecolor="black",
                markeredgewidth=0.4,
                linewidth=1.5,
                zorder=3,
            )
        ax.set_yscale("log")
        ax.set_xticks(list(RHOS))
        ax.set_xticklabels(["0.1", "0.2", "0.3", "0.4", "0.5", "0.6", "0.7", "0.8", "0.9", "1"])
        ax.set_xlim(0.05, 1.05)
        ax.set_xlabel(r"$\rho$")
        ax.set_ylabel(r"$\langle T \rangle$ (steps)")
        ax.set_title(frozen.SCENARIOS[nombre]["title"])
        ax.grid(True, which="both", linewidth=0.3, alpha=0.45)
        ax.text(0.03, 0.97, letter, transform=ax.transAxes, ha="left", va="top", fontsize=12, fontweight="bold")
    handles = [
        Line2D([0], [0], color=frozen.STAGE_COLORS[key], lw=2.0, marker="o", markersize=4.5, label=frozen.STAGE_SHORT[key])
        for key in ("I", "II", "III")
    ]
    handles.append(Patch(facecolor="0.45", alpha=0.22, label=r"$\pm\,\sigma_T$"))
    fig.legend(handles=handles, loc="lower center", ncol=4, frameon=False, bbox_to_anchor=(0.5, 0.01))
    frozen.save_figure(plt, fig, stem)


def main() -> None:
    if "--plot-only" in sys.argv:
        rows = []
        with SUMMARY_OUT.open(encoding="utf-8") as handle:
            for raw in csv.DictReader(handle):
                rows.append(
                    {
                        "scenario": raw["escenario"],
                        "rho": float(raw["rho"]),
                        "motor": raw["motor"],
                        "stage": raw["etapa"],
                        "T_mean": float(raw["T_mean"]),
                        "T_sd": float(raw["T_sd"]),
                        "SE": float(raw["SE"]),
                        "n": int(raw["n"]),
                        "censored": int(raw["censored"]),
                    }
                )
    else:
        for rho in RHOS:
            print(f"seed offset rho={rho:.1f} -> {frozen.semilla_curva(rho, 0)}", flush=True)
        workers = max(1, os.cpu_count() or 2)
        results = frozen.correr(trabajos(), workers)
        rows = filas_nuevas(results) + leer_reutilizados()
        if len(rows) != 2 * 2 * len(RHOS) * 3:
            raise SystemExit(f"filas inesperadas: {len(rows)}")
        guardar_tabla(rows)
    reportar(rows)
    figura(rows, "pff", "T_vs_rho_frozen_YD")
    figura(rows, "pru", "T_vs_rho_frozen_YD_pru")


if __name__ == "__main__":
    main()
