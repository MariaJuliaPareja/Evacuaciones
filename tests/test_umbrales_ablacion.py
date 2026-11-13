"""La ablación toma 10, 39.8 y los dos U_I más altos de la grilla."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from experimento.comparar_regla_en_pru import umbrales_ablacion
from experimento.config import grilla_umbrales


def test_cuatro_umbrales_con_los_dos_mas_altos():
    pares = umbrales_ablacion()
    assert len(pares) == 4
    uis = [par[0] for par in pares]
    assert uis == sorted(uis)
    assert all(abs(u_ii - 2.0 * u_i) < 1e-9 for u_i, u_ii in pares)
    oficial = [par[0] for par in grilla_umbrales()]
    assert min(uis, key=lambda u: abs(u - 10.0)) in oficial
    assert abs(min(uis, key=lambda u: abs(u - 10.0)) - 10.0) < 1e-6
    assert abs(min(uis, key=lambda u: abs(u - 39.8)) - 39.810717055349734) < 1e-6
    assert uis[-2:] == sorted(oficial, reverse=True)[:2][::-1]
