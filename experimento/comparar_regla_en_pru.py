"""PRU con reglas_etapa_en_pru True contra False, mismas semillas.

rho=1. U_I en {10, 39.8 y los dos más altos de la grilla oficial}, U_II=2*U_I.
T_normalizado = T_medio / L, con L las celdas libres interiores, como plot_propuesta1.
"""

from __future__ import annotations

import argparse
import csv
import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experimento.barrido_pru_fixed import (  # noqa: E402
    load_scenario,
    semilla_de,
    simular_pru,
)
from experimento.config import N_RUNS, RHO_VALS, SEED_BASE, fila_procedencia, grilla_umbrales  # noqa: E402
from experimento.metricas import calcular_metricas, combinar_metricas  # noqa: E402

ESCENARIOS = ("sala_de_clases", "avion_dos_puertas")
DESTINO = ROOT / "experimento" / "out" / "tabla_ablacion_regla_en_pru.csv"
COLUMNAS = [
    "escenario",
    "UI",
    "UII",
    "flag",
    "T_medio",
    "T_std",
    "T_normalizado",
    "motor",
    "ramirez2021",
    "pru_fixed",
    "reglas_etapa_en_pru",
    "rho",
    "n_runs",
    "semilla_base",
    "commit",
    "fecha",
]


def umbrales_ablacion() -> list[tuple[float, float]]:
    """10, 39.8 y los dos U_I más altos. U_II = 2*U_I sale de la grilla."""
    pares = list(grilla_umbrales())
    altos = sorted(pares, key=lambda par: par[0], reverse=True)[:2]

    def el_de(objetivo: float) -> tuple[float, float]:
        return min(pares, key=lambda par: abs(par[0] - objetivo))

    elegidos: list[tuple[float, float]] = []
    for par in (el_de(10.0), el_de(39.8), *altos):
        if not any(abs(par[0] - previo[0]) < 1e-8 for previo in elegidos):
            elegidos.append(par)
    return sorted(elegidos, key=lambda par: par[0])


def celdas_libres(escenario: str) -> int:
    # [CAMBIO] antes: esta corrida no normalizaba T -> ahora: T/L con L = (ancho-2)*(alto-2) - obstáculos, como plot_propuesta1
    esc = importlib.import_module(f"escenarios.{escenario}")
    ancho = int(esc.width)
    alto = int(esc.height)
    obstaculos = list(getattr(esc, "obstaculos", []) or [])
    if ancho > 2 and alto > 2:
        return max(1, (ancho - 2) * (alto - 2) - len(obstaculos))
    return 1


# [DUDA] N_RUNS y RHO_VALS se importan de config.py; esta ablación fija rho=1 y --n default 5, no N_RUNS
_ = (N_RUNS, RHO_VALS, SEED_BASE)


def correr(n: int) -> list[dict]:
    filas = []
    rho = 1.0
    for escenario in ESCENARIOS:
        esc = load_scenario(escenario)
        libre = celdas_libres(escenario)
        for u_i, u_ii in umbrales_ablacion():
            d_inv = 1.0 / u_i
            for flag in (True, False):
                parciales = []
                for i in range(n):
                    semilla = semilla_de(rho, d_inv, i)
                    historia = simular_pru(esc, rho, d_inv, semilla, reglas_etapa_en_pru=flag)
                    parciales.append(calcular_metricas(historia))
                metricas = combinar_metricas(parciales) or {}
                t_medio = float(metricas.get("T"))
                fila = {
                    "escenario": escenario,
                    "UI": u_i,
                    "UII": u_ii,
                    "flag": flag,
                    "T_medio": t_medio,
                    "T_std": float(metricas.get("sigma_T")),
                    "T_normalizado": t_medio / libre,
                }
                fila.update(
                    fila_procedencia(
                        motor="PRU",
                        ramirez2021=False,
                        pru_fixed=True,
                        reglas_etapa_en_pru=flag,
                        rho=rho,
                        ui=u_i,
                        uii=u_ii,
                        n_runs=n,
                    )
                )
                filas.append(fila)
                print(
                    f"{escenario} UI={u_i:.6g} flag={flag} T={t_medio:.2f}",
                    flush=True,
                )
    return filas


def imprimir_diferencia(filas: list[dict]) -> None:
    print("escenario UI T_true T_false dT(True-False) dT_normalizado")
    index = {(f["escenario"], round(float(f["UI"]), 8), f["flag"]): f for f in filas}
    for escenario in ESCENARIOS:
        uis = sorted({round(float(f["UI"]), 8) for f in filas if f["escenario"] == escenario})
        for ui in uis:
            cierto = index[(escenario, ui, True)]
            falso = index[(escenario, ui, False)]
            d_t = float(cierto["T_medio"]) - float(falso["T_medio"])
            d_n = float(cierto["T_normalizado"]) - float(falso["T_normalizado"])
            print(
                f"{escenario} {float(cierto['UI']):.6g} "
                f"{float(cierto['T_medio']):.3f} {float(falso['T_medio']):.3f} "
                f"{d_t:.3f} {d_n:.4f}"
            )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=5)
    parser.add_argument("--salida", type=Path, default=DESTINO)
    args = parser.parse_args()
    filas = correr(args.n)
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    with args.salida.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNAS)
        writer.writeheader()
        writer.writerows(filas)
    print(f"Saved {args.salida}", flush=True)
    imprimir_diferencia(filas)


if __name__ == "__main__":
    main()
