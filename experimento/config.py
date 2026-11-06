"""Valores del barrido oficial. Los motores no leen este módulo.

# [CAMBIO] antes: rho, umbrales y N vivían solo en barrido_pff.py -> ahora: este módulo los reexporta para el reporte
# [DUDA] el barrido recorre cuatro densidades; RHO = 1.0 es el default de una sola corrida
"""

from experimento.barrido_pff import D_INV_VALS, MAX_PASOS, N_SIMS, RHO_VALS, SEED_BASE

N_RUNS = N_SIMS
RHO = 1.0


def grilla_umbrales():
    """Pares (U_I, U_II) del barrido. U_I = 1/d_inv y U_II = 2*U_I."""
    return [(float(1.0 / d), float(2.0 / d)) for d in D_INV_VALS]
