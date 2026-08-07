"""Wrapper to run barrido_propuesta1.py for a specific scenario with minimal changes.

Usage:
    python3 scripts/run_barrido_for_scenario.py --scenario base --n_sims 8 --out salidas/experimentos/barrido_propuesta1_base.pkl

This script monkeypatches `experimento.barrido_propuesta1._cargar_escenario_base`
so the rest of the code can run unchanged. It can also override `N_SIMS`.
"""
import argparse
import importlib
import os
import sys
from pathlib import Path
from typing import Any, Dict

# Asegurar que el directorio raíz del proyecto esté en sys.path cuando se ejecuta desde scripts/
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def load_scenario_module(name: str) -> Dict[str, Any]:
    """Try to import escenarios.<name> and return dict{width,height,puertas,obstaculos}.
    Falls back to default if import fails."""
    try:
        esc = importlib.import_module(f"escenarios.{name}")
        return {
            "width": int(getattr(esc, "width")),
            "height": int(getattr(esc, "height")),
            "puertas": list(getattr(esc, "puertas")),
            "obstaculos": list(getattr(esc, "obstaculos", [])),
        }
    except Exception:
        print(f"Warning: could not import escenarios.{name}, using fallback base scenario.")
        # fallback identical to barrido_propuesta1 default
        width, height = 20, 14
        y_mid = height // 2
        puertas = [(0, y_mid - 1), (0, y_mid)]
        return {"width": width, "height": height, "puertas": puertas, "obstaculos": []}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", default="base", choices=["base", "sala_de_clases", "avion", "avion_dos_puertas"], help="Which scenario to run")
    parser.add_argument("--n_sims", type=int, default=None, help="Override N_SIMS (for quick tests)")
    parser.add_argument("--out", type=str, default=None, help="Output PKL path")
    args = parser.parse_args()

    # Import the module
    import experimento.barrido_propuesta1 as bp

    # Monkeypatch loader
    def _loader():
        return load_scenario_module(args.scenario if args.scenario != 'base' else 'escenario_base')

    bp._cargar_escenario_base = _loader

    if args.n_sims is not None:
        print(f"Overriding N_SIMS: {bp.N_SIMS} -> {args.n_sims}")
        bp.N_SIMS = int(args.n_sims)

    salida = Path(args.out) if args.out else Path("salidas") / "experimentos" / f"barrido_propuesta1_{args.scenario}.pkl"
    print(f"Running barrido_propuesta1 for scenario={args.scenario}, N_SIMS={bp.N_SIMS}")
    data = bp.ejecutar_barrido()

    bp.guardar_resultados(data, salida)
    print(f"Saved: {salida}")


if __name__ == '__main__':
    main()
