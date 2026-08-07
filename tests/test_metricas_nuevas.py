from types import SimpleNamespace

from experimento.metricas import calcular_metricas


def test_calcular_metricas_agrega_metricas_por_paso_y_recalculo():
    historia = [
        {
            "agentes": [
                SimpleNamespace(activo=True, ansiedad=20, U_I=10, U_II=40),
                SimpleNamespace(activo=True, ansiedad=80, U_I=10, U_II=40),
                SimpleNamespace(activo=False, ansiedad=10, U_I=10, U_II=40),
            ],
            "conflictos": 3,
            "n_agentes_activos": 2,
            "n_agentes_movidos": 1,
            "n_recalculos_ruta": 2,
        },
        {
            "agentes": [
                SimpleNamespace(activo=False, ansiedad=10, U_I=10, U_II=40),
                SimpleNamespace(activo=False, ansiedad=90, U_I=10, U_II=40),
            ],
            "conflictos": 0,
            "n_agentes_activos": 0,
            "n_agentes_movidos": 0,
            "n_recalculos_ruta": 1,
        },
    ]

    metricas = calcular_metricas([historia])

    assert metricas is not None
    assert metricas["n_colisiones"] == 3
    assert metricas["n_agentes_activos_promedio"] == 1.0
    assert metricas["n_agentes_activos_max"] == 2
    assert metricas["n_agentes_activos_por_paso"] == [2, 0]
    assert metricas["n_agentes_movidos_por_paso"] == [1, 0]
    assert metricas["n_recalculos_ruta"] == 3
