"""Wrapper para ejecutar el barrido de la propuesta 1 sobre un escenario concreto."""
import argparse
import importlib
import sys
from pathlib import Path
from typing import Any, Dict

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def load_scenario_module(name: str, d: float | None = None) -> Dict[str, Any]:
    """Carga un escenario desde escenarios.<name> o usa fallback."""
    try:
        if name in {"base", "escenario_base"}:
            module_name = "escenario_base"
        else:
            module_name = name

        esc = importlib.import_module(f"escenarios.{module_name}")
        if hasattr(esc, "get_config"):
            config = esc.get_config(d=d)
            return {
                "width": int(config.get("width", getattr(esc, "width", 0))),
                "height": int(config.get("height", getattr(esc, "height", 0))),
                "puertas": list(config.get("puertas", [])),
                "obstaculos": list(config.get("obstaculos", [])),
                "door_distance": config.get("door_distance", None),
            }

        return {
            "width": int(getattr(esc, "width")),
            "height": int(getattr(esc, "height")),
            "puertas": list(getattr(esc, "puertas")),
            "obstaculos": list(getattr(esc, "obstaculos", [])),
            "door_distance": getattr(esc, "door_distance", None),
        }
    except Exception:
        print(f"Warning: could not import escenarios.{name}, using fallback base scenario.")
        width, height = 20, 14
        y_mid = height // 2
        puertas = [(0, y_mid - 1), (0, y_mid)]
        return {"width": width, "height": height, "puertas": puertas, "obstaculos": [], "door_distance": None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scenario",
        default="base",
        choices=["base", "escenario_base", "sala_de_clases", "avion", "sala_de_clases_dos_puertas", "avion_dos_puertas"],
        help="Which scenario to run",
    )
    parser.add_argument("--distance", type=float, default=None, help="Door separation distance for configurable two-door scenarios")
    parser.add_argument("--n_sims", type=int, default=None, help="Override N_SIMS (for quick tests)")
    parser.add_argument("--out", type=str, default=None, help="Output PKL path")
    args = parser.parse_args()

    import experimento.barrido_propuesta1 as bp

    if args.n_sims is not None:
        print(f"Overriding N_SIMS: {bp.N_SIMS} -> {args.n_sims}")
        bp.N_SIMS = int(args.n_sims)

    salida = Path(args.out) if args.out else Path("salidas") / "experimentos" / f"barrido_propuesta1_{args.scenario}.pkl"
    print(f"Running barrido_propuesta1 for scenario={args.scenario}, distance={args.distance}, N_SIMS={bp.N_SIMS}")
    data = bp.ejecutar_barrido(scenario_name=args.scenario if args.scenario != "base" else "escenario_base", d=args.distance)

    bp.guardar_resultados(data, salida)
    print(f"Saved: {salida}")


if __name__ == "__main__":
    main()
