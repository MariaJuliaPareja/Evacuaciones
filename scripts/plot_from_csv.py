"""Generate fig1-fig3 from barrido CSV tables (N=100 validated metrics).

CSV columns expected:
  rho, T_mean, sigma_T, fI, fII, fIII, n_sims
Optional:
  d_inv  (if missing, reconstructed as nested RHO_VALS x logspace(-3,0,16))

Usage:
  PYTHONPATH=. python scripts/plot_from_csv.py \\
      --csv tabla_escenario_base.csv --scenario escenario_base \\
      --out salidas/experimentos/figuras_base

  # batch (paper set; avion uses frente/atras dos_puertas CSV):
  PYTHONPATH=. python scripts/plot_from_csv.py --batch
"""
from __future__ import annotations

import argparse
import csv
import importlib
import os
import sys
from pathlib import Path

import numpy as np

os.environ.setdefault("MPLBACKEND", "Agg")

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from experimento import plot_propuesta1 as pp  # noqa: E402

RHO_VALS = [0.25, 0.50, 0.75, 1.0]
D_INV_VALS = np.logspace(-3, 0, 16)


def _l_celdas_libres(scenario_module: str) -> int:
    """Free interior cells used for T normalization (same formula as plot_propuesta1)."""
    esc = importlib.import_module(f"escenarios.{scenario_module}")
    width = int(esc.width)
    height = int(esc.height)
    obstaculos = list(getattr(esc, "obstaculos", []) or [])
    if width > 2 and height > 2:
        return max(1, (width - 2) * (height - 2) - len(obstaculos))
    return 1


def _load_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise ValueError(f"Empty CSV: {path}")
    return rows


def _grids_from_rows(rows: list[dict]) -> tuple[np.ndarray, np.ndarray, dict[str, np.ndarray]]:
    """Build (rho x d_inv) grids from CSV rows."""
    has_d_inv = "d_inv" in rows[0]

    parsed: list[tuple[float, float, dict]] = []
    for i, r in enumerate(rows):
        rho = float(r["rho"])
        if has_d_inv:
            d_inv = float(r["d_inv"])
        else:
            # Row order must match barrido_propuesta1: for rho in RHO_VALS for d_inv in D_INV_VALS
            n_d = len(D_INV_VALS)
            rho_idx = i // n_d
            d_idx = i % n_d
            if rho_idx >= len(RHO_VALS):
                raise ValueError(
                    f"CSV has {len(rows)} rows; expected {len(RHO_VALS) * n_d} "
                    f"to reconstruct d_inv without an explicit column."
                )
            expected_rho = RHO_VALS[rho_idx]
            if abs(rho - expected_rho) > 1e-9:
                raise ValueError(
                    f"Row {i}: rho={rho} but reconstructed grid expects {expected_rho}. "
                    "Add a d_inv column or regenerate the CSV from the PKL."
                )
            d_inv = float(D_INV_VALS[d_idx])

        parsed.append(
            (
                rho,
                d_inv,
                {
                    "T": float(r["T_mean"]),
                    "sigma_T": float(r["sigma_T"]),
                    "mild": float(r["fI"]),
                    "optimal": float(r["fII"]),
                    "anxiety": float(r["fIII"]),
                },
            )
        )

    rho_vals = sorted({p[0] for p in parsed})
    d_inv_vals = sorted({p[1] for p in parsed})
    rho_to_i = {v: i for i, v in enumerate(rho_vals)}
    d_to_j = {v: j for j, v in enumerate(d_inv_vals)}

    shape = (len(rho_vals), len(d_inv_vals))
    grids = {
        "T": np.full(shape, np.nan),
        "sigma_T": np.full(shape, np.nan),
        "mild": np.full(shape, np.nan),
        "optimal": np.full(shape, np.nan),
        "anxiety": np.full(shape, np.nan),
    }
    for rho, d_inv, m in parsed:
        i, j = rho_to_i[rho], d_to_j[d_inv]
        for k, v in m.items():
            grids[k][i, j] = v

    return np.array(rho_vals), np.array(d_inv_vals), grids


def plot_from_csv(csv_path: Path, scenario_module: str, out_dir: Path) -> list[Path]:
    """Write fig1/fig2/fig3 into out_dir; return saved paths."""
    rows = _load_csv(csv_path)
    rho_vals, d_inv_vals, grids = _grids_from_rows(rows)
    l_free = _l_celdas_libres(scenario_module)
    t_norm = grids["T"] / float(l_free)

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Temporarily redirect plot_propuesta1 output directory.
    old_figs = pp.FIGS_DIR
    pp.FIGS_DIR = out_dir
    try:
        pp._guardar_fig1(t_norm, rho_vals, d_inv_vals)
        pp._guardar_fig2(grids["sigma_T"], rho_vals, d_inv_vals)
        pp._guardar_fig3(
            {
                "mild": grids["mild"],
                "optimal": grids["optimal"],
                "anxiety": grids["anxiety"],
            },
            rho_vals,
            d_inv_vals,
        )
    finally:
        pp.FIGS_DIR = old_figs

    saved = [
        out_dir / "fig1_tiempo_evacuacion.png",
        out_dir / "fig2_std_evacuacion.png",
        out_dir / "fig3_fraccion_stress.png",
    ]
    for p in saved:
        if not p.exists():
            raise FileNotFoundError(f"Expected figure not written: {p}")
    print(f"Saved figures to: {out_dir}")
    return saved


def export_pkl_to_csv(pkl_path: Path, csv_path: Path) -> None:
    """Export barrido PKL to the CSV schema used by this plotter (includes d_inv)."""
    import pickle

    with pkl_path.open("rb") as f:
        data = pickle.load(f)
    n_sims = int((data.get("meta") or {}).get("n_sims", 0))
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["rho", "d_inv", "T_mean", "sigma_T", "fI", "fII", "fIII", "n_sims"],
        )
        writer.writeheader()
        for e in data.get("resultados", []):
            m = e.get("metricas") or {}
            fr = m.get("fraccion_stress") or {}
            writer.writerow(
                {
                    "rho": e.get("rho"),
                    "d_inv": e.get("d_inv"),
                    "T_mean": m.get("T"),
                    "sigma_T": m.get("sigma_T"),
                    "fI": fr.get("mild"),
                    "fII": fr.get("optimal"),
                    "fIII": fr.get("anxiety"),
                    "n_sims": n_sims,
                }
            )
    print(f"Wrote CSV: {csv_path}")


def run_batch() -> list[Path]:
    """Paper set: base + sala from existing CSVs; avion from dos_puertas PKL→CSV."""
    root = ROOT_DIR
    pkl_avion = root / "salidas" / "experimentos" / "barrido_propuesta1_avion_dos_puertas.pkl"
    csv_avion = root / "tabla_avion_dos_puertas.csv"
    if not pkl_avion.exists():
        raise FileNotFoundError(
            f"Missing {pkl_avion}. Cannot build frente/atras avion figures."
        )
    export_pkl_to_csv(pkl_avion, csv_avion)

    jobs = [
        (
            root / "tabla_escenario_base.csv",
            "escenario_base",
            root / "salidas" / "experimentos" / "figuras_base",
        ),
        (
            root / "tabla_sala_de_clases.csv",
            "sala_de_clases",
            root / "salidas" / "experimentos" / "figuras_sala_de_clases",
        ),
        (
            csv_avion,
            "avion_dos_puertas",
            root / "salidas" / "experimentos" / "figuras_avion_dos_puertas",
        ),
    ]
    saved_all: list[Path] = []
    for csv_path, scenario, out_dir in jobs:
        if not csv_path.exists():
            raise FileNotFoundError(f"Missing CSV: {csv_path}")
        saved_all.extend(plot_from_csv(csv_path, scenario, out_dir))
    return saved_all


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot fig1-fig3 from barrido CSV tables.")
    parser.add_argument("--batch", action="store_true", help="Generate the full 9-figure paper set.")
    parser.add_argument("--csv", type=str, default=None, help="Input CSV path")
    parser.add_argument(
        "--scenario",
        type=str,
        default=None,
        help="escenarios.<name> module used for L normalization",
    )
    parser.add_argument("--out", type=str, default=None, help="Output directory for figures")
    parser.add_argument(
        "--export-pkl",
        type=str,
        default=None,
        help="Optional: export a barrido PKL to CSV (then exit unless --csv also set)",
    )
    parser.add_argument(
        "--export-csv",
        type=str,
        default=None,
        help="Destination CSV when using --export-pkl",
    )
    args = parser.parse_args()

    if args.export_pkl:
        if not args.export_csv:
            raise SystemExit("--export-pkl requires --export-csv")
        export_pkl_to_csv(Path(args.export_pkl), Path(args.export_csv))

    if args.batch:
        saved = run_batch()
        print("Batch complete:")
        for p in saved:
            print(f"  {p}")
        return

    if args.csv and args.scenario and args.out:
        plot_from_csv(Path(args.csv), args.scenario, Path(args.out))
        return

    if not args.export_pkl:
        parser.print_help()
        raise SystemExit(1)


if __name__ == "__main__":
    main()
