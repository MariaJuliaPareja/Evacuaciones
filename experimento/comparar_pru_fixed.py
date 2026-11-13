"""dT de PRU pru_fixed contra el PFF corregido sembrado con la misma semilla."""

from __future__ import annotations

import csv
import math
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experimento.config import N_RUNS, RHO_VALS, SEED_BASE, grilla_umbrales  # noqa: E402
from experimento.metricas import leer_csv  # noqa: E402

# [DUDA] la grilla y SEED_BASE no se usan para re-simular; N de la comparación sale de n_runs del CSV
_ = (SEED_BASE, grilla_umbrales)
OUT = ROOT / "experimento" / "out"


def leer(path: Path) -> dict[tuple[float, float], dict]:
    out = {}
    for row in leer_csv(path):
        clave = (round(float(row["rho"]), 5), round(float(row["d_inv"]), 8))
        out[clave] = row
    return out


def clase(
    t_pru: float,
    sd_pru: float,
    n_pru: int,
    t_pff: float,
    sd_pff: float,
    n_pff: int,
) -> str:
    # [CAMBIO] antes: N=100 fijo en el error estándar -> ahora: n_runs de cada CSV
    se = math.sqrt((sd_pru ** 2) / n_pru + (sd_pff ** 2) / n_pff)
    diff = t_pru - t_pff
    if abs(diff) <= 2.0 * se:
        return "indistinguible"
    return "mejor" if diff < 0 else "peor"


def main() -> None:
    # [DUDA] tabla_comparacion_pff_pru_ramirez2021.csv es anterior a la regla y no trae procedencia; solo se imprime
    anterior = list(
        csv.DictReader((ROOT / "tabla_comparacion_pff_pru_ramirez2021.csv").open(encoding="utf-8"))
    )
    filas = []
    for escenario in ("sala_de_clases", "avion_dos_puertas"):
        pru = leer(OUT / f"tabla_{escenario}_pru_fixed.csv")
        pff = leer(OUT / f"tabla_{escenario}_pff_ramirez2021_seeded.csv")
        for clave in sorted(set(pru) & set(pff)):
            rho, d_inv = clave
            t_pru = float(pru[clave]["T_mean"])
            sd_pru = float(pru[clave]["sigma_T"])
            n_pru = int(pru[clave]["n_runs"])
            t_pff = float(pff[clave]["T_mean"])
            sd_pff = float(pff[clave]["sigma_T"])
            n_pff = int(pff[clave]["n_runs"])
            dtp = (t_pru - t_pff) / t_pff * 100.0
            filas.append(
                {
                    "scenario": escenario,
                    "rho": rho,
                    "d_inv": d_inv,
                    "U_I": 1.0 / d_inv,
                    "T_PFF": t_pff,
                    "sigma_T_PFF": sd_pff,
                    "SE_PFF": sd_pff / math.sqrt(n_pff),
                    "T_PRU_fixed": t_pru,
                    "sigma_T_PRU_fixed": sd_pru,
                    "SE_PRU_fixed": sd_pru / math.sqrt(n_pru),
                    "dT_pct": dtp,
                    "clase": clase(t_pru, sd_pru, n_pru, t_pff, sd_pff, n_pff),
                    "motor": "PRU-PFF",
                    "ramirez2021": pff[clave]["ramirez2021"],
                    "pru_fixed": pru[clave]["pru_fixed"],
                    "reglas_etapa_en_pru": pru[clave]["reglas_etapa_en_pru"],
                    "UI": pru[clave]["UI"],
                    "UII": pru[clave]["UII"],
                    "n_runs": n_pru,
                    "semilla_base": pru[clave]["semilla_base"],
                    "commit": pru[clave]["commit"],
                    "fecha": pru[clave]["fecha"],
                }
            )
    # [CAMBIO] antes: tabla_comparacion_pru_fixed.csv se escribía en la raíz -> ahora: experimento/out/
    destino = OUT / "tabla_comparacion_pru_fixed.csv"
    with destino.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(filas[0].keys()))
        writer.writeheader()
        writer.writerows(filas)

    print("NUEVO pru_fixed vs PFF sembrado")
    for escenario in ("sala_de_clases", "avion_dos_puertas"):
        for rho in RHO_VALS:
            grupo = [f for f in filas if f["scenario"] == escenario and abs(f["rho"] - rho) < 1e-9]
            conteo = Counter(f["clase"] for f in grupo)
            dts = [f["dT_pct"] for f in grupo]
            print(
                f"{escenario} rho={rho} mejor={conteo['mejor']} peor={conteo['peor']} "
                f"indistinguible={conteo['indistinguible']} "
                f"dT {min(dts):.2f} a {max(dts):.2f}"
            )

    print("ANTERIOR PRU vs PFF ramirez sin semilla global")
    viejo = []
    for row in anterior:
        viejo.append(
            (
                row["scenario"],
                float(row["rho"]),
                clase(
                    float(row["T_PRU"]),
                    float(row["sigma_T_PRU"]),
                    N_RUNS,
                    float(row["T_PFF_ramirez2021"]),
                    float(row["sigma_T_PFF_ramirez2021"]),
                    N_RUNS,
                ),
            )
        )
    for escenario in ("sala_de_clases", "avion_dos_puertas"):
        for rho in RHO_VALS:
            grupo = [c for e, r, c in viejo if e == escenario and abs(r - rho) < 1e-9]
            conteo = Counter(grupo)
            print(
                f"{escenario} rho={rho} mejor={conteo['mejor']} peor={conteo['peor']} "
                f"indistinguible={conteo['indistinguible']}"
            )
    print("Wrote", destino)


if __name__ == "__main__":
    main()
