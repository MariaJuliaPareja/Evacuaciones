"""Build tabla_comparacion_pff_pru.csv from PFF and PRU barrido PKLs.

Usage:
  PYTHONPATH=. python scripts/build_comparacion_pff_pru.py \\
      --pff salidas/experimentos/barrido_pff_base.pkl \\
      --pru salidas/experimentos/barrido_propuesta1_base_full.pkl \\
      --out tabla_comparacion_pff_pru.csv
"""
from __future__ import annotations

import argparse
import csv
import math
import pickle
from pathlib import Path


def _load_grid(pkl: Path) -> dict[tuple[float, float], dict]:
    with pkl.open("rb") as f:
        data = pickle.load(f)
    out = {}
    for e in data.get("resultados", []):
        m = e.get("metricas") or {}
        out[(float(e["rho"]), float(e["d_inv"]))] = {
            "T": float(m.get("T", float("nan"))),
            "sigma_T": float(m.get("sigma_T", float("nan"))),
        }
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pff", type=Path, required=True)
    parser.add_argument("--pru", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("tabla_comparacion_pff_pru.csv"))
    args = parser.parse_args()

    pff = _load_grid(args.pff)
    pru = _load_grid(args.pru)
    keys = sorted(set(pff) & set(pru), key=lambda k: (k[0], k[1]))
    if not keys:
        raise SystemExit("No overlapping (rho, d_inv) cells between PFF and PRU PKLs")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["rho", "log10(1/d)", "T_PFF", "sigma_T_PFF", "T_PRU", "sigma_T_PRU", "ΔT (%)"])
        for rho, d_inv in keys:
            tp, sp = pff[(rho, d_inv)]["T"], pff[(rho, d_inv)]["sigma_T"]
            tr, sr = pru[(rho, d_inv)]["T"], pru[(rho, d_inv)]["sigma_T"]
            dtpct = ((tr - tp) / tp * 100.0) if tp else float("nan")
            w.writerow([rho, math.log10(d_inv), tp, sp, tr, sr, dtpct])
    print(f"Wrote {args.out} ({len(keys)} rows)")


if __name__ == "__main__":
    main()
