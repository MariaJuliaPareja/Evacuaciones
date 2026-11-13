"""Un CSV de experimento sin las columnas de procedencia no se lee."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from experimento.metricas import leer_csv
from experimento.metricas_herd import leer_csv as leer_csv_herd


def test_metricas_aborta_si_falta_procedencia(tmp_path):
    path = tmp_path / "viejo.csv"
    path.write_text("rho,T_mean\n1,10\n", encoding="utf-8")
    try:
        leer_csv(path)
    except SystemExit as exc:
        assert "sin procedencia" in str(exc)
        assert "motor" in str(exc)
        return
    raise AssertionError("leer_csv no abortó")


def test_metricas_herd_usa_el_mismo_rechazo(tmp_path):
    path = tmp_path / "viejo.csv"
    path.write_text("rho,T_mean\n1,10\n", encoding="utf-8")
    try:
        leer_csv_herd(path)
    except SystemExit as exc:
        assert "sin procedencia" in str(exc)
        return
    raise AssertionError("metricas_herd.leer_csv no abortó")
