"""Run PFF barrido for a named scenario (mirrors run_barrido_for_scenario.py).

Usage:
  PYTHONPATH=. python scripts/run_barrido_pff_for_scenario.py --scenario sala_de_clases --n_sims 100 \\
      --out salidas/experimentos/barrido_pff_sala_de_clases_fixed.pkl
"""
from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path
from typing import Any, Dict

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def load_scenario_module(name: str) -> Dict[str, Any]:
    try:
        esc = importlib.import_module(f"escenarios.{name}")
        return {
            "width": int(getattr(esc, "width")),
            "height": int(getattr(esc, "height")),
            "puertas": list(getattr(esc, "puertas")),
            "obstaculos": list(getattr(esc, "obstaculos", []) or []),
        }
    except Exception:
        width, height = 20, 14
        y_mid = height // 2
        return {
            "width": width,
            "height": height,
            "puertas": [(0, y_mid - 1), (0, y_mid)],
            "obstaculos": [],
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scenario",
        default="base",
        choices=["base", "sala_de_clases", "avion", "avion_dos_puertas"],
    )
    parser.add_argument("--n_sims", type=int, default=None)
    parser.add_argument("--out", type=str, default=None)
    args = parser.parse_args()

    import experimento.barrido_pff as bp

    def _loader():
        return load_scenario_module("escenario_base" if args.scenario == "base" else args.scenario)

    bp._cargar_escenario_base = _loader
    if args.n_sims is not None:
        print(f"Overriding N_SIMS: {bp.N_SIMS} -> {args.n_sims}")
        bp.N_SIMS = int(args.n_sims)

    salida = (
        Path(args.out)
        if args.out
        else Path("salidas") / "experimentos" / f"barrido_pff_{args.scenario}_fixed.pkl"
    )
    print(f"Running barrido_pff for scenario={args.scenario}, N_SIMS={bp.N_SIMS}")
    data = bp.ejecutar_barrido()
    # Tag meta so files are self-describing
    data.setdefault("meta", {})
    data["meta"]["motor"] = "PFF"
    data["meta"]["tag"] = "fixed_post_occupation_bug"
    data["meta"]["scenario"] = args.scenario
    bp.guardar_resultados(data, salida)
    print(f"Saved: {salida}")


if __name__ == "__main__":
    main()
