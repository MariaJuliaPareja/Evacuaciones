"""Plot fig1-fig3 from a barrido_propuesta1 PKL into a target directory.

Usage:
  PYTHONPATH=. python3 scripts/plot_pkl_propuesta1.py salidas/experimentos/barrido_propuesta1_base_quick.pkl salidas/experimentos/figuras_base_quick
"""
import sys
from pathlib import Path
import pickle
import numpy as np

# Force non-interactive backend before importing plotting utilities
import os
os.environ.setdefault('MPLBACKEND', 'Agg')
# reuse functions from experimento.plot_propuesta1
from experimento import plot_propuesta1 as pp


def plot_from_pkl(pkl_path: Path, out_dir: Path):
    with pkl_path.open('rb') as f:
        data = pickle.load(f)

    rho_vals, d_inv_vals, grids, l_celdas_libres = pp._extraer_grillas(data)
    if l_celdas_libres <= 0:
        l_celdas_libres = 1

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    t_norm = grids['T'] / float(l_celdas_libres)

    # Save figs in out_dir
    fig1 = out_dir / 'fig1_tiempo_evacuacion.png'
    fig2 = out_dir / 'fig2_std_evacuacion.png'
    fig3 = out_dir / 'fig3_fraccion_stress.png'

    default_dir = pp.FIGS_DIR
    default_dir.mkdir(parents=True, exist_ok=True)
    pp._guardar_fig1(t_norm, rho_vals, d_inv_vals)
    pp._guardar_fig2(grids['sigma_T'], rho_vals, d_inv_vals)
    pp._guardar_fig3(
        {
            'mild': grids['mild'],
            'optimal': grids['optimal'],
            'anxiety': grids['anxiety'],
        },
        rho_vals,
        d_inv_vals,
    )
    # move generated files from default FIGS_DIR to out_dir

    # The helper functions write to pp.FIGS_DIR. To keep out_dir separation, copy bytes.
    import shutil
    shutil.copyfile(default_dir / 'fig1_tiempo_evacuacion.png', fig1)
    shutil.copyfile(default_dir / 'fig2_std_evacuacion.png', fig2)
    shutil.copyfile(default_dir / 'fig3_fraccion_stress.png', fig3)

    print(f"Saved figures to: {out_dir}")


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: scripts/plot_pkl_propuesta1.py <input.pkl> <out_dir>")
        sys.exit(1)
    plot_from_pkl(Path(sys.argv[1]), Path(sys.argv[2]))
