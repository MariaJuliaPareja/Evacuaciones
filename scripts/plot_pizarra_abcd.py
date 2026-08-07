"""Generate whiteboard figures A-D from full barrido PKLs (N=100 + distribution keys).

Usage:
  PYTHONPATH=. python scripts/plot_pizarra_abcd.py
"""
from __future__ import annotations

import os
import pickle
import sys
from pathlib import Path

import numpy as np

os.environ.setdefault("MPLBACKEND", "Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT_DIR = ROOT / "salidas" / "experimentos" / "figuras_pizarra"

JOBS = [
    {
        "escenario": "avion_dos_puertas",
        "pkl": ROOT / "salidas" / "experimentos" / "barrido_propuesta1_avion_dos_puertas_full.pkl",
        "label": "Airplane (front/rear exits)",
    },
    {
        "escenario": "sala_de_clases",
        "pkl": ROOT / "salidas" / "experimentos" / "barrido_propuesta1_sala_de_clases_full.pkl",
        "label": "Classroom",
    },
]

# Reference cell for A/B/C: high density + mid d_inv (illustrative, same across panels).
RHO_REF = 1.0


def _load(pkl: Path) -> dict:
    with pkl.open("rb") as f:
        return pickle.load(f)


def _entries_by_rho_dinv(data: dict) -> dict[tuple[float, float], dict]:
    out = {}
    for e in data["resultados"]:
        out[(float(e["rho"]), float(e["d_inv"]))] = e
    return out


def _mid_d_inv(d_inv_vals: list[float]) -> float:
    vals = sorted(d_inv_vals)
    return vals[len(vals) // 2]


def _sigma_plus_minus(values: np.ndarray) -> tuple[float, float, float]:
    """Return (sigma_plus, sigma_minus, criterion) relative to the median (RMS)."""
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    if x.size == 0:
        return 0.0, 0.0, 0.0
    med = float(np.median(x))
    above = x[x > med]
    below = x[x < med]
    # RMS deviation from median on each side; if empty side, sigma = 0.
    sig_p = float(np.sqrt(np.mean((above - med) ** 2))) if above.size else 0.0
    sig_m = float(np.sqrt(np.mean((med - below) ** 2))) if below.size else 0.0
    denom = sig_p + sig_m
    crit = abs(sig_p - sig_m) / denom if denom > 0 else 0.0
    return sig_p, sig_m, crit


def _sigma_plus_minus_percentile(
    values: np.ndarray, eps: float = 1e-6
) -> tuple[float, float, float]:
    """
    Gradual one-sided spreads via percentiles (avoids empty-side RMS collapse):
      sigma+ = P90 - P50
      sigma- = P50 - P10
      criterion = |sigma+ - sigma-| / (sigma+ + sigma- + eps)
    """
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    if x.size == 0:
        return 0.0, 0.0, 0.0
    p10, p50, p90 = np.percentile(x, [10, 50, 90])
    sig_p = float(max(0.0, p90 - p50))
    sig_m = float(max(0.0, p50 - p10))
    crit = abs(sig_p - sig_m) / (sig_p + sig_m + eps)
    return sig_p, sig_m, crit


def fig_a(ansiedad: np.ndarray, out: Path, title: str) -> dict:
    med = float(np.median(ansiedad))
    sig_p, sig_m, crit = _sigma_plus_minus(ansiedad)

    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    ax.hist(ansiedad, bins=40, color="#2c5f7c", edgecolor="white", alpha=0.9, density=True)
    ax.axvline(med, color="#c0392b", lw=2, label=f"median = {med:.2f}")
    # Mark one-sided RMS spreads around the median.
    if sig_m > 0:
        ax.axvspan(med - sig_m, med, color="#5dade2", alpha=0.18, label=rf"$\sigma-$ = {sig_m:.2f}")
    if sig_p > 0:
        ax.axvspan(med, med + sig_p, color="#e74c3c", alpha=0.18, label=rf"$\sigma+$ = {sig_p:.2f}")
    ax.set_xlabel("Final anxiety (agent)")
    ax.set_ylabel("Density $P$")
    ax.set_title(title)
    ax.legend(loc="upper right", fontsize=8)
    ax.text(
        0.02,
        0.95,
        r"Asymmetry $|\frac{\sigma_+-\sigma_-}{\sigma_++\sigma_-}|$ = "
        + f"{crit:.3f}",
        transform=ax.transAxes,
        va="top",
        fontsize=9,
        bbox=dict(facecolor="white", alpha=0.85, edgecolor="none"),
    )
    fig.tight_layout()
    fig.savefig(out, dpi=300)
    plt.close(fig)
    return {"median": med, "sigma_plus": sig_p, "sigma_minus": sig_m, "criterion": crit}


def fig_b(cols: np.ndarray, out: Path, title: str) -> None:
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    n_bins = min(20, max(5, int(np.sqrt(len(cols)))))
    ax.hist(cols, bins=n_bins, color="#3d6b4f", edgecolor="white", alpha=0.9)
    ax.axvline(float(np.mean(cols)), color="#c0392b", lw=2, label=f"mean = {np.mean(cols):.1f}")
    ax.axvline(float(np.median(cols)), color="#f39c12", lw=1.5, ls="--", label=f"median = {np.median(cols):.1f}")
    ax.set_xlabel("Number of collisions per run")
    ax.set_ylabel("Count (over 100 sims)")
    ax.set_title(title)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out, dpi=300)
    plt.close(fig)


def fig_c(j_t: np.ndarray, out: Path, title: str) -> None:
    t = np.arange(len(j_t))
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    ax.plot(t, j_t, color="#6c3483", lw=1.8)
    ax.fill_between(t, j_t, color="#6c3483", alpha=0.15)
    ax.set_xlabel("Time step $t$")
    ax.set_ylabel(r"$J(t)$  (agents moving)")
    ax.set_title(title)
    ax.set_xlim(left=0)
    ax.set_ylim(bottom=0)
    fig.tight_layout()
    fig.savefig(out, dpi=300)
    plt.close(fig)


def fig_d(
    d_invs: np.ndarray,
    sig_plus: np.ndarray,
    sig_minus: np.ndarray,
    criteria: np.ndarray,
    out: Path,
    title: str,
) -> None:
    """Plot sigma+/sigma- magnitudes (primary) and regularized ratio (secondary)."""
    order = np.argsort(d_invs)
    x = np.log10(d_invs[order])
    sp = sig_plus[order]
    sm = sig_minus[order]
    y = criteria[order]

    fig, ax = plt.subplots(figsize=(7.5, 4.8))
    ax.plot(x, sp, "o-", color="#c0392b", lw=2, ms=5, label=r"$\sigma+$ $=P_{90}-P_{50}$")
    ax.plot(x, sm, "s-", color="#1a5276", lw=2, ms=5, label=r"$\sigma-$ $=P_{50}-P_{10}$")
    ax.set_xlabel(r"$\log_{10}(1/d)$  [same sweep axis as paper heatmaps]")
    ax.set_ylabel(r"One-sided spread (Stage-III fraction)")
    ax.set_title(title)
    ax.grid(True, alpha=0.3)

    ax2 = ax.twinx()
    ax2.plot(
        x,
        y,
        "^-",
        color="#7d3c98",
        lw=1.5,
        ms=4,
        alpha=0.85,
        label=r"$|\sigma_+-\sigma_-|/(\sigma_++\sigma_-+\varepsilon)$",
    )
    ax2.set_ylabel("Regularized asymmetry ratio", color="#7d3c98")
    ax2.set_ylim(-0.05, 1.05)
    ax2.tick_params(axis="y", labelcolor="#7d3c98")

    # Combined legend
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(out, dpi=300)
    plt.close(fig)


def process_job(job: dict) -> dict:
    data = _load(job["pkl"])
    by = _entries_by_rho_dinv(data)
    d_inv_vals = sorted({k[1] for k in by if abs(k[0] - RHO_REF) < 1e-12})
    d_ref = _mid_d_inv(d_inv_vals)
    entry = by[(RHO_REF, d_ref)]
    m = entry["metricas"]

    ansiedad = np.asarray(m["ansiedad_final_por_agente"], dtype=float)
    cols = np.asarray(m["n_colisiones_por_corrida"], dtype=float)
    j_t = np.asarray(m["moviendose_por_paso"], dtype=float)

    esc = job["escenario"]
    label = job["label"]
    out_dir = OUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    # A: single representative high-density cell (same as B/C) — clearer than pooling
    # mixed U_I/U_II regimes across the anxiety-threshold sweep.
    stats_a = fig_a(
        ansiedad,
        out_dir / f"{esc}_A_cola_larga.png",
        title=f"A. Final-anxiety distribution — {label}\n"
        rf"$\rho={RHO_REF}$, $1/d={d_ref:.4g}$ (N={len(ansiedad)} agents)",
    )
    fig_b(
        cols,
        out_dir / f"{esc}_B_colisiones.png",
        title=f"B. Collisions per run — {label}\n"
        rf"$\rho={RHO_REF}$, $1/d={d_ref:.4g}$ (100 sims)",
    )
    fig_c(
        j_t,
        out_dir / f"{esc}_C_flujo.png",
        title=f"C. Movement flux $J(t)$ — {label}\n"
        rf"$\rho={RHO_REF}$, $1/d={d_ref:.4g}$ (ensemble-averaged)",
    )

    # D: one point per d_inv at rho=RHO_REF.
    # IMPORTANT: ansiedad_final_por_agente is nearly invariant across d_inv (U_I/U_II
    # only change stage labels, not the raw anxiety process), so its asymmetry is flat.
    # Use fraccion_stage_III_por_agente, which does track the threshold sweep.
    # Iterate resultados directly (no float-key lookup) so each point maps to its cell.
    rows_rho = sorted(
        (e for e in data["resultados"] if abs(float(e["rho"]) - RHO_REF) < 1e-12),
        key=lambda e: float(e["d_inv"]),
    )
    dinvs: list[float] = []
    sig_ps: list[float] = []
    sig_ms: list[float] = []
    crits: list[float] = []
    means_iii: list[float] = []
    for e in rows_rho:
        d_inv = float(e["d_inv"])
        frac_iii = np.asarray(e["metricas"]["fraccion_stage_III_por_agente"], dtype=float)
        sp, sm, c = _sigma_plus_minus_percentile(frac_iii, eps=1e-6)
        dinvs.append(d_inv)
        sig_ps.append(sp)
        sig_ms.append(sm)
        crits.append(c)
        means_iii.append(float(np.mean(frac_iii)) if frac_iii.size else 0.0)

    fig_d(
        np.asarray(dinvs),
        np.asarray(sig_ps),
        np.asarray(sig_ms),
        np.asarray(crits),
        out_dir / f"{esc}_D_asimetria.png",
        title=f"D. Asymmetry vs $1/d$ — {label}\n"
        rf"Stage-III fraction percentiles at $\rho={RHO_REF}$ "
        rf"({len(dinvs)} cells)",
    )

    return {
        "escenario": esc,
        "rho_ref": RHO_REF,
        "d_inv_ref": d_ref,
        "n_d_inv_in_D": len(dinvs),
        "d_inv_min": min(dinvs) if dinvs else None,
        "d_inv_max": max(dinvs) if dinvs else None,
        "D_sigma_plus": sig_ps,
        "D_sigma_minus": sig_ms,
        "D_crits": crits,
        "D_mean_stage_III": means_iii,
        "A_stats": stats_a,
        "n_agents_A": int(ansiedad.size),
        "n_runs_B": int(cols.size),
        "n_steps_C": int(j_t.size),
    }


def main() -> None:
    reports = []
    for job in JOBS:
        if not job["pkl"].exists():
            raise FileNotFoundError(job["pkl"])
        reports.append(process_job(job))
        print(f"OK: {job['escenario']}")

    print("\n=== REFERENCE SUMMARY ===")
    for r in reports:
        print(r)
    print(f"\nFigures in: {OUT_DIR}")


if __name__ == "__main__":
    main()
