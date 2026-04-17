"""Generacion de figuras para analisis de comportamiento herd."""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


RUTA_INPUT = Path("resultados") / "barrido_herd.pkl"
RUTA_FIGURAS = Path("resultados") / "figuras"


def _cargar_resultados(path: Path) -> dict[str, Any]:
    """Carga resultados del barrido herd desde archivo PKL."""
    with path.open("rb") as f:
        data = pickle.load(f)
    if not isinstance(data, dict) or "resultados" not in data:
        raise ValueError("Formato invalido: se esperaba dict con clave 'resultados'.")
    return data


def _armar_dataframe(data: dict[str, Any]) -> pd.DataFrame:
    """Convierte la lista de resultados en un DataFrame plano."""
    rows: list[dict[str, Any]] = []
    for item in data.get("resultados", []):
        metricas = item.get("metricas_herd", {})
        rows.append(
            {
                "rho": float(item.get("rho", np.nan)),
                "d_inv": float(item.get("d_inv", np.nan)),
                "k_paths_max": int(item.get("k_paths_max", 0)),
                "frecuencia_cascadas_media": float(metricas.get("frecuencia_cascadas_media", 0.0)),
                "duracion_media_cascada_media": float(metricas.get("duracion_media_cascada_media", 0.0)),
                "entropia_media_media": float(metricas.get("entropia_media_media", 0.0)),
                "entropia_min_media": float(metricas.get("entropia_min_media", 0.0)),
                "entropia_std_media": float(metricas.get("entropia_std_media", 0.0)),
                "ansiedad_media_media": float(metricas.get("ansiedad_media_media", np.nan)),
            }
        )
    df = pd.DataFrame(rows)
    if df.empty:
        raise ValueError("No se encontraron filas en 'resultados'.")
    return df


def _figura_4_frecuencia_cascadas(df: pd.DataFrame, out_path: Path) -> None:
    """
    Figura 4:
    - 3 subplots por k_paths_max
    - x: rho
    - y: frecuencia_cascadas por paso de simulacion (aproximada con media por combinacion)
    - lineas por d_inv
    """
    ks = sorted(df["k_paths_max"].unique())
    d_vals = sorted(df["d_inv"].unique())
    cmap = plt.get_cmap("viridis", len(d_vals))

    fig, axes = plt.subplots(1, len(ks), figsize=(16, 4.8), sharey=True)
    if len(ks) == 1:
        axes = [axes]

    for ax, k in zip(axes, ks):
        dfx = df[df["k_paths_max"] == k].sort_values(["d_inv", "rho"])
        for i, d_inv in enumerate(d_vals):
            sub = dfx[dfx["d_inv"] == d_inv].sort_values("rho")
            if sub.empty:
                continue
            ax.plot(
                sub["rho"],
                sub["frecuencia_cascadas_media"],
                marker="o",
                linewidth=2.0,
                color=cmap(i),
                label=f"d_inv={d_inv:g}",
            )
        ax.set_title(f"k_paths_max = {k}")
        ax.set_xlabel("rho")
        ax.grid(True, alpha=0.3)

    axes[0].set_ylabel("Cascade Frequency (per simulation step)")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=max(1, len(d_vals)), frameon=False)
    fig.suptitle("Figure 4: Cascade Frequency vs Density", y=1.04)
    fig.tight_layout()
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)


def _figura_5_heatmaps_entropia(df: pd.DataFrame, out_dir: Path) -> None:
    """
    Figura 5:
    - Un heatmap por d_inv
    - x: rho
    - y: k_paths_max
    - color: entropia_media
    """
    d_vals = sorted(df["d_inv"].unique())

    for d_inv in d_vals:
        sub = df[df["d_inv"] == d_inv].copy()
        if sub.empty:
            continue

        pivot = sub.pivot_table(
            index="k_paths_max",
            columns="rho",
            values="entropia_media_media",
            aggfunc="mean",
        )
        pivot = pivot.sort_index().sort_index(axis=1)

        fig, ax = plt.subplots(figsize=(7.0, 4.8))
        im = ax.imshow(pivot.values, aspect="auto", cmap="magma", origin="lower")

        ax.set_xticks(np.arange(len(pivot.columns)))
        ax.set_xticklabels([f"{x:g}" for x in pivot.columns])
        ax.set_yticks(np.arange(len(pivot.index)))
        ax.set_yticklabels([str(y) for y in pivot.index])
        ax.set_xlabel("rho")
        ax.set_ylabel("k_paths_max")
        ax.set_title(f"Figure 5: Route Entropy Heatmap (d_inv = {d_inv:g})")

        cbar = fig.colorbar(im, ax=ax)
        cbar.set_label("Mean Route Entropy")

        fig.tight_layout()
        out_path = out_dir / f"fig5_entropia_rutas_dinv_{d_inv:g}.png"
        fig.savefig(out_path, dpi=300, bbox_inches="tight")
        plt.close(fig)


def _figura_6_entropia_vs_ansiedad(df: pd.DataFrame, out_path: Path) -> None:
    """
    Figura 6:
    - scatter x: ansiedad_media_media
    - y: entropia_media_media
    - color por rho
    - una curva por k_paths_max
    """
    ks = sorted(df["k_paths_max"].unique())
    rho_vals = sorted(df["rho"].unique())
    color_map = {rho: plt.cm.plasma(i / max(1, len(rho_vals) - 1)) for i, rho in enumerate(rho_vals)}

    fig, ax = plt.subplots(figsize=(8.0, 6.0))

    # Scatter points colored by rho
    for rho in rho_vals:
        sub = df[df["rho"] == rho]
        ax.scatter(
            sub["ansiedad_media_media"],
            sub["entropia_media_media"],
            s=48,
            alpha=0.85,
            color=color_map[rho],
            label=f"rho={rho:g}",
            edgecolors="white",
            linewidths=0.4,
        )

    # Curves by k_paths_max using centroids by anxiety
    for k in ks:
        subk = df[df["k_paths_max"] == k].sort_values("ansiedad_media_media")
        if subk.empty:
            continue
        ax.plot(
            subk["ansiedad_media_media"],
            subk["entropia_media_media"],
            linewidth=1.8,
            alpha=0.8,
            label=f"k_paths_max={k}",
        )

    ax.set_xlabel("Mean Anxiety (ensemble average)")
    ax.set_ylabel("Mean Route Entropy")
    ax.set_title("Figure 6: Route Entropy vs Anxiety")
    ax.grid(True, alpha=0.3)

    # Leyenda combinada (rho y curvas k)
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles, labels, loc="best", frameon=True)
    fig.tight_layout()
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    """Carga datos herd y genera figuras 4, 5 y 6."""
    if not RUTA_INPUT.exists():
        raise FileNotFoundError(f"No existe archivo de entrada: {RUTA_INPUT}")

    RUTA_FIGURAS.mkdir(parents=True, exist_ok=True)

    data = _cargar_resultados(RUTA_INPUT)
    df = _armar_dataframe(data)

    out_fig4 = RUTA_FIGURAS / "fig4_frecuencia_cascadas.png"
    out_fig6 = RUTA_FIGURAS / "fig6_entropia_vs_ansiedad.png"

    _figura_4_frecuencia_cascadas(df, out_fig4)
    _figura_5_heatmaps_entropia(df, RUTA_FIGURAS)
    _figura_6_entropia_vs_ansiedad(df, out_fig6)

    # Crear alias principal para Figura 5 solicitado
    # (el contenido detallado se guarda por d_inv con sufijo).
    fig5_alias = RUTA_FIGURAS / "fig5_entropia_rutas.png"
    d_vals = sorted(df["d_inv"].unique())
    if d_vals:
        source = RUTA_FIGURAS / f"fig5_entropia_rutas_dinv_{d_vals[0]:g}.png"
        if source.exists():
            fig5_alias.write_bytes(source.read_bytes())

    print(f"Figura 4 guardada en: {out_fig4}")
    print(f"Figura 5 guardada en: {RUTA_FIGURAS} (una por d_inv y alias fig5_entropia_rutas.png)")
    print(f"Figura 6 guardada en: {out_fig6}")


if __name__ == "__main__":
    main()
