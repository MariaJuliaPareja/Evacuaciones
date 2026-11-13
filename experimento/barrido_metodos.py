"""PRU sin path_selector (greedy_regla) y A* sin desbloqueo, pru_fixed=True.
# [CAMBIO] AgenteGreedy8 retirado: usaba la regla antigua
# [CAMBIO] antes: el método se llamaba greedy4 -> ahora: greedy_regla, PRU sin path_selector y con la regla de 8 vecinos

Same seeds as experimento/barrido_pru_fixed.py. Does not modify the motors
and does not overwrite the existing PFF or PRU tables. Those two methods are
copied into the combined table from the seeded CSVs.

Outputs:
  experimento/out/metodos_{scenario}_{method}.csv
  tabla_metodos_barrido_completo.csv
"""

from __future__ import annotations

import argparse
import csv
import importlib
import random
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experimento.barrido_pff import _generar_posiciones_iniciales  # noqa: E402
from experimento.barrido_pru_fixed import sembrar_corrida, semilla_de  # noqa: E402
from experimento.config import (  # noqa: E402
    D_INV_VALS,
    MAX_PASOS,
    N_RUNS,
    RHO_VALS,
    SEED_BASE,
    fila_procedencia,
)
from experimento.metricas import calcular_metricas, combinar_metricas, leer_csv  # noqa: E402
from simulacion.agent_extendido import AgentExtendido, mover_agentes_con_conflictos  # noqa: E402
from simulacion.grilla.floor_field import Floor_field  # noqa: E402
from simulacion.nodos.path_selector import PathSelector  # noqa: E402

OUT_DIR = ROOT / "experimento" / "out"
# [CAMBIO] AgenteGreedy8 retirado: usaba la regla antigua
# [CAMBIO] antes: AgenteGreedy8 repetía el greedy viejo con 8 vecinos -> ahora: esa clase no existe


def load_scenario(name: str) -> dict[str, Any]:
    esc = importlib.import_module(f"escenarios.{name}")
    return {
        "width": int(esc.width),
        "height": int(esc.height),
        "puertas": list(esc.puertas),
        "obstaculos": list(getattr(esc, "obstaculos", []) or []),
    }


def _frames(agentes, conflictos: int) -> dict[str, Any]:
    snapshot = [
        SimpleNamespace(
            activo=a.activo,
            stress=getattr(a, "stress", None),
            ansiedad=getattr(a, "ansiedad", None),
            U_I=getattr(a, "U_I", None),
            U_II=getattr(a, "U_II", None),
        )
        for a in agentes
    ]
    return {"agentes": snapshot, "conflictos": conflictos}


def simular(esc, rho: float, d_inv: float, semilla: int, method: str) -> list[dict]:
    sembrar_corrida(semilla)
    ff = Floor_field(esc["width"], esc["height"], esc["puertas"], esc["obstaculos"])
    selector = None
    k_paths = 5
    if method == "astar":
        selector = PathSelector(ff, umbral_recalculo=0.6, anxiety_thresholds=(30, 70), pru_fixed=True)
        k_paths = 1
    elif method != "greedy_regla":
        raise ValueError(method)
    AgentExtendido.instances = []
    AgentExtendido.history = []
    AgentExtendido.ruta_log = []
    rng = random.Random(semilla)
    posiciones = _generar_posiciones_iniciales(
        esc["width"], esc["height"], esc["obstaculos"], rho, rng
    )
    u_i = 1.0 / d_inv
    for x, y in posiciones:
        AgentExtendido(
            agent_type="rapido",
            floor_field=ff,
            path_selector=selector,
            x=x,
            y=y,
            U_I=u_i,
            U_II=2.0 * u_i,
            k_paths_max=k_paths,
            pru_fixed=True,
            reglas_etapa_en_pru=True,
        )
    historia = []
    for step in range(MAX_PASOS):
        activos = [a for a in AgentExtendido.instances if a.activo]
        if not activos:
            break
        for agente in activos:
            agente._current_simulation_step = step
        stats = mover_agentes_con_conflictos(AgentExtendido.instances)
        historia.append(_frames(AgentExtendido.instances, stats.get("conflictos", 0)))
        AgentExtendido.ruta_log.clear()
    if not historia:
        historia.append({"agentes": [], "conflictos": 0})
    return historia


def destino_parcial(scenario: str, method: str) -> Path:
    return OUT_DIR / f"metodos_{scenario}_{method}.csv"


def claves_hechas(path: Path) -> set[tuple[float, float]]:
    if not path.exists():
        return set()
    hechas = set()
    with path.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            hechas.add((round(float(row["rho"]), 5), round(float(row["d_inv"]), 8)))
    return hechas


def ejecutar(scenario: str, method: str, n_sims: int) -> None:
    esc = load_scenario(scenario)
    path = destino_parcial(scenario, method)
    path.parent.mkdir(parents=True, exist_ok=True)
    hechas = claves_hechas(path)
    nuevo = not path.exists()
    total = len(RHO_VALS) * len(D_INV_VALS)
    hecha_n = 0
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "rho",
                "d_inv",
                "T_mean",
                "sigma_T",
                "fI",
                "fII",
                "fIII",
                "n_sims",
                "motor",
                "ramirez2021",
                "pru_fixed",
                "reglas_etapa_en_pru",
                "UI",
                "UII",
                "n_runs",
                "semilla_base",
                "commit",
                "fecha",
            ],
        )
        if nuevo:
            writer.writeheader()
        for rho in RHO_VALS:
            for d_inv in D_INV_VALS:
                clave = (round(float(rho), 5), round(float(d_inv), 8))
                hecha_n += 1
                if clave in hechas:
                    print(f"skip {scenario} {method} {hecha_n}/{total}", flush=True)
                    continue
                parciales = []
                for i in range(n_sims):
                    semilla = semilla_de(float(rho), float(d_inv), i)
                    parciales.append(
                        calcular_metricas(simular(esc, float(rho), float(d_inv), semilla, method))
                    )
                metricas = combinar_metricas(parciales) or {}
                fr = metricas.get("fraccion_stress") or {}
                writer.writerow(
                    {
                        "rho": float(rho),
                        "d_inv": float(d_inv),
                        "T_mean": metricas.get("T"),
                        "sigma_T": metricas.get("sigma_T"),
                        "fI": fr.get("mild"),
                        "fII": fr.get("optimal"),
                        "fIII": fr.get("anxiety"),
                        "n_sims": n_sims,
                        # [CAMBIO] antes: el parcial no decía qué motor ni qué semilla lo escribió -> ahora: columnas de procedencia
                        # [DUDA] greedy_regla y astar son PRU sin el flag ramirez2021; esa columna queda False
                        **fila_procedencia(
                            motor="PRU",
                            ramirez2021=False,
                            pru_fixed=True,
                            reglas_etapa_en_pru=True,
                            rho=float(rho),
                            ui=1.0 / float(d_inv),
                            uii=2.0 / float(d_inv),
                            n_runs=n_sims,
                        ),
                    }
                )
                handle.flush()
                print(
                    f"{scenario} {method} {hecha_n}/{total} rho={rho} U_I={1/float(d_inv):.4g} "
                    f"T={float(metricas.get('T')):.2f}",
                    flush=True,
                )
    print(f"Saved {path}", flush=True)


def _leer(path: Path) -> list[dict]:
    return leer_csv(path)


def combinar() -> None:
    filas = []
    for scenario in ("sala_de_clases", "avion_dos_puertas"):
        # [CAMBIO] antes: combinar leía el parcial de greedy8 -> ahora: ese método no entra en la tabla
        fuentes = {
            "greedy_regla": destino_parcial(scenario, "greedy_regla"),
            "astar": destino_parcial(scenario, "astar"),
            # [CAMBIO] antes: --combine leía los CSV de la raíz -> ahora: experimento/out/
            "pru": OUT_DIR / f"tabla_{scenario}_pru_fixed.csv",
            "pff": OUT_DIR / f"tabla_{scenario}_pff_ramirez2021_seeded.csv",
        }
        for method, path in fuentes.items():
            for row in _leer(path):
                sd = float(row["sigma_T"])
                n_runs = int(row["n_runs"])
                filas.append(
                    {
                        "scenario": scenario,
                        "rho": float(row["rho"]),
                        "d_inv": float(row["d_inv"]),
                        "U_I": 1.0 / float(row["d_inv"]),
                        "method": method,
                        "T_mean": float(row["T_mean"]),
                        "sigma_T": sd,
                        "SE": sd / (n_runs ** 0.5),
                        "motor": row["motor"],
                        "ramirez2021": row["ramirez2021"],
                        "pru_fixed": row["pru_fixed"],
                        "reglas_etapa_en_pru": row["reglas_etapa_en_pru"],
                        "UI": row["UI"],
                        "UII": row["UII"],
                        "n_runs": n_runs,
                        "semilla_base": row["semilla_base"],
                        "commit": row["commit"],
                        "fecha": row["fecha"],
                    }
                )
    # [CAMBIO] antes: la tabla combinada se escribía en la raíz -> ahora: experimento/out/
    destino = OUT_DIR / "tabla_metodos_barrido_completo.csv"
    with destino.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(filas[0].keys()))
        writer.writeheader()
        writer.writerows(filas)
    print(f"Saved {destino} rows={len(filas)}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", choices=["sala_de_clases", "avion_dos_puertas"])
    parser.add_argument("--method", choices=["greedy_regla", "astar"])
    parser.add_argument("--n_sims", type=int, default=N_RUNS)
    parser.add_argument("--combine", action="store_true")
    args = parser.parse_args()
    if args.combine:
        combinar()
        return
    if not args.scenario or not args.method:
        parser.error("--scenario and --method are required unless --combine")
    print(
        f"{args.method} {args.scenario} N_RUNS={args.n_sims} SEED_BASE={SEED_BASE}",
        flush=True,
    )
    ejecutar(args.scenario, args.method, args.n_sims)


if __name__ == "__main__":
    main()
