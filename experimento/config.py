"""Única fuente de la grilla oficial. Los motores no leen este módulo.

# [CAMBIO] antes: este módulo reexportaba barrido_pff.py -> ahora: los números se definen aquí y barrido_pff los importa
# [DUDA] el barrido recorre cuatro densidades; RHO = 1.0 es el default de una sola corrida
"""

from __future__ import annotations

import subprocess
from datetime import date
from functools import lru_cache
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent

RHO_VALS = [0.25, 0.50, 0.75, 1.0]
D_INV_VALS = np.logspace(-3, 0, 16)
N_RUNS = 100
MAX_PASOS = 500
SEED_BASE = 12345
RHO = 1.0

COLUMNAS_PROCEDENCIA = (
    "motor",
    "ramirez2021",
    "pru_fixed",
    "reglas_etapa_en_pru",
    "rho",
    "UI",
    "UII",
    "n_runs",
    "semilla_base",
    "commit",
    "fecha",
)


def grilla_umbrales():
    """Pares (U_I, U_II) del barrido. U_I = 1/d_inv y U_II = 2*U_I."""
    return [(float(1.0 / d), float(2.0 / d)) for d in D_INV_VALS]


@lru_cache(maxsize=1)
def commit_corto() -> str:
    try:
        salida = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        return salida.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "sin-commit"


def fila_procedencia(
    *,
    motor: str,
    ramirez2021: bool,
    pru_fixed: bool,
    reglas_etapa_en_pru: bool,
    rho: float,
    ui: float,
    uii: float,
    n_runs: int,
) -> dict:
    return {
        "motor": motor,
        "ramirez2021": bool(ramirez2021),
        "pru_fixed": bool(pru_fixed),
        "reglas_etapa_en_pru": bool(reglas_etapa_en_pru),
        "rho": rho,
        "UI": ui,
        "UII": uii,
        "n_runs": n_runs,
        "semilla_base": SEED_BASE,
        "commit": commit_corto(),
        "fecha": date.today().isoformat(),
    }


def exigir_procedencia(fieldnames, origen) -> None:
    """Aborta si el CSV no trae la procedencia de la corrida."""
    presentes = set(fieldnames or [])
    faltan = [columna for columna in COLUMNAS_PROCEDENCIA if columna not in presentes]
    if faltan:
        raise SystemExit(
            f"CSV sin procedencia: {origen}\n"
            f"Faltan columnas: {', '.join(faltan)}.\n"
            "Regenera el barrido. Los CSV anteriores a la regla de etapa no se leen."
        )
