"""Convert barrido_propuesta1 PKL to CSV table with columns:
rho, T_mean, sigma_T, fI, fII, fIII, n_sims

Usage:
    PYTHONPATH=. python3 scripts/pkl_to_csv.py salidas/experimentos/barrido_propuesta1_base_quick.pkl tabla_escenario_base_quick.csv
"""
import sys
import pickle
import numpy as np
import csv
from pathlib import Path


def pkl_to_csv(pkl_path: Path, out_path: Path):
    with pkl_path.open('rb') as f:
        data = pickle.load(f)

    rows = []
    meta = data.get('meta', {})
    n_sims = int(meta.get('n_sims', 0))

    for entry in data.get('resultados', []):
        rho = entry.get('rho')
        metricas = entry.get('metricas') or {}
        fr = metricas.get('fraccion_stress') or {}
        rows.append({
            'ρ': rho,
            'T': metricas.get('T'),
            'σT': metricas.get('sigma_T'),
            'fI': fr.get('mild'),
            'fII': fr.get('optimal'),
            'fIII': fr.get('anxiety'),
        })

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open('w', newline='') as csvfile:
        fieldnames = ['ρ','T','σT','fI','fII','fIII']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    print(f"Wrote CSV: {out_path}")


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: scripts/pkl_to_csv.py <input.pkl> <output.csv>")
        sys.exit(1)
    pkl_to_csv(Path(sys.argv[1]), Path(sys.argv[2]))
