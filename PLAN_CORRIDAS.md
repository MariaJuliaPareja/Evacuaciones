# Plan de corridas

Comandos desde la raíz del repo. Sin `--n` / `--n_sims` el default es `N_RUNS=100` de `experimento/config.py` (4 densidades × 16 umbrales). Los tiempos de la tabla mezclan dos cosas: la grilla completa de `sala_de_clases` con 2 corridas, medida, y el avión, extrapolado de una corrida a rho=1 y U_I=10.

`barrido_herd.py`, `barrido_propuesta1.py`, `plot_herd.py` y `plot_propuesta1.py` no entran: están marcados como posible legado.

## Orden

1. `barrido_pff` no alimenta a los demás. Escribe un pkl.
2. `barrido_pru_fixed` escribe los CSV de PFF y PRU. `comparar_pru_fixed` los necesita.
3. `barrido_metodos` puede correr en paralelo con el paso 2. `--combine` espera esos parciales y los CSV del paso 2.
4. `figures.make_metodos_vs_UI` espera la tabla del `--combine`.
5. `barrido_herd_nulo` puede correr en paralelo con 2 y 3. `--report` espera sus series y la tabla del `--combine`.
6. `reporte_reemplazos` y `comparar_regla_en_pru` no leen otros CSV.

## Comandos

Tiempo con 2 corridas por celda de la grilla, salvo donde se dice que el script no barre.

| Orden | Comando | Produce | Tiempo con n=2 |
|---|---|---|---|
| 1 | `python -m experimento.barrido_pff --n 2` | `salidas/experimentos/barrido_pff_base.pkl` | 19 s medidos |
| 2 | `python -m experimento.barrido_pru_fixed --scenario sala_de_clases --motor pff_ramirez --n_sims 2` | `experimento/out/tabla_sala_de_clases_pff_ramirez2021_seeded.csv` | 1 s medido |
| 2 | `python -m experimento.barrido_pru_fixed --scenario avion_dos_puertas --motor pff_ramirez --n_sims 2` | `experimento/out/tabla_avion_dos_puertas_pff_ramirez2021_seeded.csv` | ~15 s |
| 2 | `python -m experimento.barrido_pru_fixed --scenario sala_de_clases --motor pru_fixed --n_sims 2` | `experimento/out/tabla_sala_de_clases_pru_fixed.csv` | 16 s medidos |
| 2 | `python -m experimento.barrido_pru_fixed --scenario avion_dos_puertas --motor pru_fixed --n_sims 2` | `experimento/out/tabla_avion_dos_puertas_pru_fixed.csv` | ~3 min |
| 3 | `python -m experimento.barrido_metodos --scenario sala_de_clases --method greedy_regla --n_sims 2` | `experimento/out/metodos_sala_de_clases_greedy_regla.csv` | 2 s medidos |
| 3 | `python -m experimento.barrido_metodos --scenario sala_de_clases --method astar --n_sims 2` | `experimento/out/metodos_sala_de_clases_astar.csv` | 5 s medidos |
| 3 | `python -m experimento.barrido_metodos --scenario avion_dos_puertas --method greedy_regla --n_sims 2` | `experimento/out/metodos_avion_dos_puertas_greedy_regla.csv` | ~1 min |
| 3 | `python -m experimento.barrido_metodos --scenario avion_dos_puertas --method astar --n_sims 2` | `experimento/out/metodos_avion_dos_puertas_astar.csv` | ~1.5 min |
| 3 | `python -m experimento.barrido_metodos --combine` | `experimento/out/tabla_metodos_barrido_completo.csv` | segundos, después de 2 y 3 |
| 4 | `python -m figures.make_metodos_vs_UI` | `figures/out/metodos_vs_UI.pdf` y `.png` | segundos, después del `--combine`. Aborta si el CSV no trae procedencia |
| 5 | `python -m experimento.comparar_pru_fixed` | `experimento/out/tabla_comparacion_pru_fixed.csv` | segundos, después del paso 2. También imprime la tabla vieja `tabla_comparacion_pff_pru_ramirez2021.csv`, que no tiene procedencia |
| 6 | `python -m experimento.barrido_herd_nulo --scenario sala_de_clases --n_sims 2` | `experimento/out/herd_series/sala_de_clases_rho*_dinv*.npz` | 19 s medidos |
| 6 | `python -m experimento.barrido_herd_nulo --scenario avion_dos_puertas --n_sims 2` | `experimento/out/herd_series/avion_dos_puertas_rho*_dinv*.npz` | ~6–8 min |
| 6 | `python -m experimento.barrido_herd_nulo --report` | `experimento/out/tabla_herd_nulo_pru_fixed.csv` | segundos, después de las series y del `--combine`. Aborta si el npz no trae `n_runs` |
| 7 | `python -m experimento.reporte_reemplazos --n 2` | `experimento/out/tabla_reemplazos.csv` y `experimento/out/tabla_reemplazos_combinaciones.csv` | 8 s medidos. Un solo U_I, el primero de la grilla (1000), no las 16. Con ese umbral no hay etapa II ni III |
| 8 | `python -m experimento.comparar_regla_en_pru --n 2` | `experimento/out/tabla_ablacion_regla_en_pru.csv` | 28 s medidos, ambos escenarios. El default del script es `--n 5`, no `N_RUNS`. Cuatro U_I, no la grilla completa |

`modo_clasico.py` no tiene CLI. Con 2 corridas a rho=1 en el escenario base tarda cerca de 1 s:

```bash
python -c "from escenarios import escenario_base; from experimento.modo_clasico import correr_simulacion_clasica; print(correr_simulacion_clasica(escenario_base, 1.0, 2)['T'])"
```

`metricas.py` y `metricas_herd.py` no se lanzan: los importan los barridos. `leer_csv` aborta si faltan las columnas de procedencia.

Para no marcar como hecha una celda oficial con solo 2 corridas, una prueba usa `--salida` (métodos), `--series` (herd) o `--salida` (pff, pru, reporte, ablación) apuntando a un directorio temporal. `barrido_metodos` no rehace un par rho/d_inv que ya está en el CSV.
