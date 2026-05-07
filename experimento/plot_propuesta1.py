"""Generacion de figuras para resultados del barrido de la propuesta 1."""

from __future__ import annotations

import pickle
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


RESULTADOS_PKL = Path("salidas") / "experimentos" / "barrido_propuesta1.pkl"
FIGS_DIR = Path("salidas") / "experimentos" / "figuras"


def _cargar_resultados(path: Path) -> dict:
    """Carga el archivo PKL con resultados del barrido."""
    if not path.exists():
        raise FileNotFoundError(f"Results file not found: {path}")
    with path.open("rb") as f:
        return pickle.load(f)


def _extraer_grillas(data: dict) -> tuple[np.ndarray, np.ndarray, dict[str, np.ndarray], int]:
    """
    Construye matrices (rho x log10(1/d)) para T, sigma_T y fracciones de stress.
    """º
    meta = data.get("meta", {})
    entries = data.get("resultados", [])
    if not entries:
        raise ValueError("The results list is empty in barrido_propuesta1.pkl")

    rho_vals = sorted({float(e["rho"]) for e in entries})
    d_inv_vals = sorted({float(e["d_inv"]) for e in entries})

    rho_to_idx = {v: i for i, v in enumerate(rho_vals)}
    d_to_idx = {v: j for j, v in enumerate(d_inv_vals)}

    shape = (len(rho_vals), len(d_inv_vals))
    t_grid = np.full(shape, np.nan, dtype=float)
    sigma_grid = np.full(shape, np.nan, dtype=float)
    mild_grid = np.full(shape, np.nan, dtype=float)
    optimal_grid = np.full(shape, np.nan, dtype=float)
    anxiety_grid = np.full(shape, np.nan, dtype=float)

    for e in entries:
        i = rho_to_idx[float(e["rho"])]
        j = d_to_idx[float(e["d_inv"])]
        m = e.get("metricas") or {}
        fr = m.get("fraccion_stress") or {}

        t_grid[i, j] = float(m.get("T", np.nan))
        sigma_grid[i, j] = float(m.get("sigma_T", np.nan))
        mild_grid[i, j] = float(fr.get("mild", np.nan))
        optimal_grid[i, j] = float(fr.get("optimal", np.nan))
        anxiety_grid[i, j] = float(fr.get("anxiety", np.nan))

    esc = meta.get("escenario", {})
    width = int(esc.get("width", 0))
    height = int(esc.get("height", 0))
    obstaculos = esc.get("obstaculos", []) or []

    # L = numero de celdas libres interiores.
    if width > 2 and height > 2:
        l_celdas_libres = (width - 2) * (height - 2) - len(obstaculos)
    else:
        l_celdas_libres = 1

    stress_grids = {
        "mild": mild_grid,
        "optimal": optimal_grid,
        "anxiety": anxiety_grid,
    }
    return np.array(rho_vals), np.array(d_inv_vals), {"T": t_grid, "sigma_T": sigma_grid, **stress_grids}, l_celdas_libres


def _heatmap(ax, z: np.ndarray, rho_vals: np.ndarray, d_inv_vals: np.ndarray, title: str, cbar_label: str) -> None:
    """Dibuja un heatmap con ejes fisicos."""
    x = np.log10(d_inv_vals)
    y = rho_vals
    im = ax.imshow(
        z,
        origin="lower",
        aspect="auto",
        cmap="plasma",
        extent=[x.min(), x.max(), y.min(), y.max()],
    )
    ax.set_title(title)
    ax.set_xlabel(r"$\log_{10}(1/d)$ [dimensionless]")
    ax.set_ylabel(r"$\rho$ [initial density]")
    cbar = plt.colorbar(im, ax=ax)
    cbar.set_label(cbar_label)


def _guardar_fig1(t_norm: np.ndarray, rho_vals: np.ndarray, d_inv_vals: np.ndarray) -> None:
    """Guarda Figura 1: tiempo de evacuacion normalizado."""
    fig, ax = plt.subplots(figsize=(8, 4.8))
    _heatmap(
        ax,
        t_norm,
        rho_vals,
        d_inv_vals,
        title="Figure 1. Normalized Evacuation Time",
        cbar_label=r"$\langle T \rangle / L$ [steps/cell]",
    )
    fig.tight_layout()
    fig.savefig(FIGS_DIR / "fig1_tiempo_evacuacion.png", dpi=300)
    plt.close(fig)


def _guardar_fig2(sigma_t: np.ndarray, rho_vals: np.ndarray, d_inv_vals: np.ndarray) -> None:
    """Guarda Figura 2: desviacion estandar de evacuacion."""
    fig, ax = plt.subplots(figsize=(8, 4.8))
    _heatmap(
        ax,
        sigma_t,
        rho_vals,
        d_inv_vals,
        title="Figure 2. Evacuation Time Standard Deviation",
        cbar_label=r"$\sigma_T$ [steps]",
    )
    fig.tight_layout()
    fig.savefig(FIGS_DIR / "fig2_std_evacuacion.png", dpi=300)
    plt.close(fig)


def _guardar_fig3(stress_grids: dict[str, np.ndarray], rho_vals: np.ndarray, d_inv_vals: np.ndarray) -> None:
    """Guarda Figura 3: fracciones por regimen de stress."""
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.8), sharex=True, sharey=True)
    order = [("mild", "Mild Stress Fraction"), ("optimal", "Optimal Stress Fraction"), ("anxiety", "Anxiety Stress Fraction")]

    for ax, (key, title) in zip(axes, order):
        _heatmap(
            ax,
            stress_grids[key],
            rho_vals,
            d_inv_vals,
            title=title,
            cbar_label="Average fraction [-]",
        )

    fig.suptitle("Figure 3. Average Stress-Regime Fractions", y=1.02)
    fig.tight_layout()
    fig.savefig(FIGS_DIR / "fig3_fraccion_stress.png", dpi=300)
    plt.close(fig)


def main() -> None:
    """Carga resultados y genera las tres figuras solicitadas."""
    data = _cargar_resultados(RESULTADOS_PKL)
    rho_vals, d_inv_vals, grids, l_celdas_libres = _extraer_grillas(data)
    if l_celdas_libres <= 0:
        l_celdas_libres = 1

    FIGS_DIR.mkdir(parents=True, exist_ok=True)

    t_norm = grids["T"] / float(l_celdas_libres)
    _guardar_fig1(t_norm, rho_vals, d_inv_vals)
    _guardar_fig2(grids["sigma_T"], rho_vals, d_inv_vals)
    _guardar_fig3(
        {
            "mild": grids["mild"],
            "optimal": grids["optimal"],
            "anxiety": grids["anxiety"],
        },
        rho_vals,
        d_inv_vals,
    )
    print(f"Figures saved in: {FIGS_DIR}")


if __name__ == "__main__":
    main()
