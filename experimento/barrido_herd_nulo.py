"""Thundering-herd frequency of pru_fixed PRU against a synchrony null.

Same seeds as experimento/barrido_pru_fixed.py. Does not modify the motors.

nu_TH is the fraction of steps in which more than the threshold of the agents
active at the start of the step recalculate a route. The null keeps each
agent's number of recalculations and moves them uniformly among the steps
in which that agent was active.

Outputs:
  experimento/out/herd_series/{scenario}_rho{rho}_dinv{d_inv}.npz
  tabla_herd_nulo_pru_fixed.csv
"""

from __future__ import annotations

import argparse
import csv
import importlib
import math
import random
import sys
from pathlib import Path
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
from experimento.metricas import leer_csv  # noqa: E402
from simulacion.agent_extendido import AgentExtendido, mover_agentes_con_conflictos  # noqa: E402
from simulacion.grilla.floor_field import Floor_field  # noqa: E402
from simulacion.nodos.path_selector import PathSelector  # noqa: E402

SERIES = ROOT / "experimento" / "out" / "herd_series"
# [CAMBIO] antes: la tabla se escribía en la raíz -> ahora: experimento/out/
TABLA = ROOT / "experimento" / "out" / "tabla_herd_nulo_pru_fixed.csv"
N_SURR = 1000
THRESHOLDS = (0.20, 0.30, 0.40)


def load_scenario(name: str) -> dict[str, Any]:
    esc = importlib.import_module(f"escenarios.{name}")
    return {
        "width": int(esc.width),
        "height": int(esc.height),
        "puertas": list(esc.puertas),
        "obstaculos": list(getattr(esc, "obstaculos", []) or []),
    }


def simular_series(esc, rho: float, d_inv: float, semilla: int) -> tuple[np.ndarray, np.ndarray, int]:
    """Return active[n, T], rec[n, T] and the evacuation time T."""
    sembrar_corrida(semilla)
    ff = Floor_field(esc["width"], esc["height"], esc["puertas"], esc["obstaculos"])
    selector = PathSelector(ff, umbral_recalculo=0.6, anxiety_thresholds=(30, 70), pru_fixed=True)
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
            pru_fixed=True,
            reglas_etapa_en_pru=True,
        )
    n = len(AgentExtendido.instances)
    activos_steps: list[np.ndarray] = []
    recalcs: list[np.ndarray] = []
    for step in range(MAX_PASOS):
        vivos = [a for a in AgentExtendido.instances if a.activo]
        if not vivos:
            break
        activo = np.zeros(n, dtype=bool)
        for agente in vivos:
            activo[agente.id] = True
            agente._current_simulation_step = step
        mover_agentes_con_conflictos(AgentExtendido.instances)
        rec = np.zeros(n, dtype=bool)
        for agente in AgentExtendido.instances:
            if activo[agente.id] and agente.recalculated_this_step:
                rec[agente.id] = True
        activos_steps.append(activo)
        recalcs.append(rec)
        AgentExtendido.ruta_log.clear()
    if not activos_steps:
        return np.zeros((n, 0), dtype=bool), np.zeros((n, 0), dtype=bool), 0
    return np.stack(activos_steps, axis=1), np.stack(recalcs, axis=1), len(activos_steps)


def nu_de(active: np.ndarray, rec: np.ndarray, threshold: float) -> float:
    if active.shape[1] == 0:
        return 0.0
    n_act = active.sum(axis=0)
    n_rec = rec.sum(axis=0)
    return float(np.mean(n_rec / n_act > threshold))


def nulos(
    active: np.ndarray,
    rec: np.ndarray,
    rng: np.random.Generator,
) -> dict[float, np.ndarray]:
    """1000 surrogates for every threshold. Shape (n_surr,) per threshold."""
    n_agents, t_steps = active.shape
    if t_steps == 0:
        return {thr: np.zeros(N_SURR) for thr in THRESHOLDS}
    counts = np.zeros((N_SURR, t_steps), dtype=np.int16)
    for agent in range(n_agents):
        eligible = np.flatnonzero(active[agent])
        total = int(rec[agent, eligible].sum()) if eligible.size else 0
        width = int(eligible.size)
        if total <= 0 or width == 0:
            continue
        if total >= width:
            counts[:, eligible] += 1
            continue
        ranks = rng.random((N_SURR, width))
        chosen = eligible[np.argpartition(ranks, total - 1, axis=1)[:, :total]]
        np.add.at(counts, (np.arange(N_SURR)[:, None], chosen), 1)
    n_act = active.sum(axis=0).astype(np.float64)
    fraction = counts / n_act
    return {thr: np.mean(fraction > thr, axis=1) for thr in THRESHOLDS}


def serie_path(scenario: str, rho: float, d_inv: float) -> Path:
    return SERIES / f"{scenario}_rho{rho:.2f}_dinv{d_inv:.8f}.npz"


def resumir_config(obs: dict[float, np.ndarray], nulls: dict[float, np.ndarray]) -> dict[str, float]:
    """obs[thr] is (n_runs,). nulls[thr] is (n_runs, n_surr)."""
    out: dict[str, float] = {}
    for thr in THRESHOLDS:
        tag = f"{int(thr * 100):02d}"
        observed = obs[thr]
        samples = nulls[thr]
        mean_null_draws = samples.mean(axis=0)
        obs_mean = float(observed.mean())
        null_mean = float(mean_null_draws.mean())
        null_sd = float(mean_null_draws.std(ddof=0))
        if null_sd == 0.0:
            z = 0.0 if obs_mean == null_mean else math.inf
        else:
            z = (obs_mean - null_mean) / null_sd
        p_emp = float(np.mean(mean_null_draws >= obs_mean))
        out[f"nu_{tag}"] = obs_mean
        out[f"null_mean_{tag}"] = null_mean
        out[f"null_sd_{tag}"] = null_sd
        out[f"z_{tag}"] = z
        out[f"p_{tag}"] = p_emp
    return out


def ejecutar(scenario: str, n_sims: int) -> None:
    esc = load_scenario(scenario)
    SERIES.mkdir(parents=True, exist_ok=True)
    total = len(RHO_VALS) * len(D_INV_VALS)
    hecha = 0
    for rho in RHO_VALS:
        for d_inv in D_INV_VALS:
            hecha += 1
            path = serie_path(scenario, float(rho), float(d_inv))
            if path.exists():
                print(f"skip {scenario} {hecha}/{total}", flush=True)
                continue
            obs = {thr: np.empty(n_sims) for thr in THRESHOLDS}
            nulls = {thr: np.empty((n_sims, N_SURR)) for thr in THRESHOLDS}
            times = np.empty(n_sims, dtype=np.int16)
            packed_active = []
            packed_rec = []
            for i in range(n_sims):
                semilla = semilla_de(float(rho), float(d_inv), i)
                active, rec, t_evac = simular_series(esc, float(rho), float(d_inv), semilla)
                times[i] = t_evac
                packed_active.append(active)
                packed_rec.append(rec)
                rng = np.random.default_rng(semilla)
                surr = nulos(active, rec, rng)
                for thr in THRESHOLDS:
                    obs[thr][i] = nu_de(active, rec, thr)
                    nulls[thr][i] = surr[thr]
            n_agents = int(packed_active[0].shape[0]) if packed_active else 0
            tmax = max((a.shape[1] for a in packed_active), default=0)
            active_pad = np.zeros((n_sims, n_agents, tmax), dtype=bool)
            rec_pad = np.zeros((n_sims, n_agents, tmax), dtype=bool)
            for i, (active, rec) in enumerate(zip(packed_active, packed_rec)):
                active_pad[i, :, : active.shape[1]] = active
                rec_pad[i, :, : rec.shape[1]] = rec
            stats = resumir_config(obs, nulls)
            np.savez_compressed(
                path,
                active=active_pad,
                rec=rec_pad,
                T=times,
                rho=np.array(float(rho)),
                d_inv=np.array(float(d_inv)),
                nu20=obs[0.20],
                nu30=obs[0.30],
                nu40=obs[0.40],
                **{key: np.array(value) for key, value in stats.items()},
                n_runs=np.array(n_sims),
                semilla_base=np.array(SEED_BASE),
            )
            print(
                f"{scenario} {hecha}/{total} rho={rho} U_I={1/float(d_inv):.4g} "
                f"nu30={stats['nu_30']:.4f} z={stats['z_30']:.2f} p={stats['p_30']:.3f}",
                flush=True,
            )


def _corr(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    try:
        from scipy.stats import pearsonr, spearmanr

        return float(pearsonr(x, y).statistic), float(spearmanr(x, y).statistic)
    except Exception:
        pearson = float(np.corrcoef(x, y)[0, 1])
        rx = np.argsort(np.argsort(x)).astype(float)
        ry = np.argsort(np.argsort(y)).astype(float)
        return pearson, float(np.corrcoef(rx, ry)[0, 1])


def reportar() -> None:
    campos = [
        "scenario",
        "rho",
        "d_inv",
        "U_I",
        "nu_20",
        "null_mean_20",
        "null_sd_20",
        "z_20",
        "p_20",
        "nu_30",
        "null_mean_30",
        "null_sd_30",
        "z_30",
        "p_30",
        "nu_40",
        "null_mean_40",
        "null_sd_40",
        "z_40",
        "p_40",
    ]
    filas = []
    for scenario in ("sala_de_clases", "avion_dos_puertas"):
        for rho in RHO_VALS:
            for d_inv in D_INV_VALS:
                data = np.load(serie_path(scenario, float(rho), float(d_inv)))
                fila = {
                    "scenario": scenario,
                    "rho": float(rho),
                    "d_inv": float(d_inv),
                    "U_I": 1.0 / float(d_inv),
                }
                for key in campos[4:]:
                    fila[key] = float(np.asarray(data[key]).reshape(-1)[0])
                fila["T_series"] = float(np.mean(data["T"]))
                n_runs = int(np.asarray(data["n_runs"]).reshape(-1)[0]) if "n_runs" in data.files else N_RUNS
                fila.update(
                    fila_procedencia(
                        motor="PRU",
                        ramirez2021=False,
                        pru_fixed=True,
                        reglas_etapa_en_pru=True,
                        rho=float(rho),
                        ui=1.0 / float(d_inv),
                        uii=2.0 / float(d_inv),
                        n_runs=n_runs,
                    )
                )
                filas.append(fila)
    with TABLA.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                *campos,
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
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(filas)
    print(f"Saved {TABLA}", flush=True)

    metodos = {}
    # [CAMBIO] antes: leía la tabla combinada de la raíz -> ahora: experimento/out/, y aborta si no trae procedencia
    for row in leer_csv(ROOT / "experimento" / "out" / "tabla_metodos_barrido_completo.csv"):
        if row["method"] not in ("pru", "astar"):
            continue
        clave = (row["scenario"], round(float(row["rho"]), 5), round(float(row["d_inv"]), 8), row["method"])
        metodos[clave] = row
    nu, sigma, delta = [], [], []
    for fila in filas:
        clave_base = (fila["scenario"], round(fila["rho"], 5), round(fila["d_inv"], 8))
        pru = metodos[clave_base + ("pru",)]
        astar = metodos[clave_base + ("astar",)]
        nu.append(fila["nu_30"])
        sigma.append(float(pru["sigma_T"]))
        delta.append(float(pru["T_mean"]) - float(astar["T_mean"]))
        if abs(fila["T_series"] - float(pru["T_mean"])) > 0.05:
            print(
                f"T mismatch {fila['scenario']} rho={fila['rho']} U_I={fila['U_I']:.4g}: "
                f"series {fila['T_series']:.2f} table {float(pru['T_mean']):.2f}",
                flush=True,
            )
    nu_a = np.asarray(nu)
    for nombre, otro in (("sigma_T", np.asarray(sigma)), ("T_PRU-T_Astar", np.asarray(delta))):
        pearson, spearman = _corr(nu_a, otro)
        print(f"all configs nu_30 vs {nombre}: Pearson={pearson:.4f} Spearman={spearman:.4f}", flush=True)
        for scenario in ("sala_de_clases", "avion_dos_puertas"):
            mask = np.array([f["scenario"] == scenario for f in filas])
            pearson, spearman = _corr(nu_a[mask], otro[mask])
            print(
                f"  {scenario} nu_30 vs {nombre}: Pearson={pearson:.4f} Spearman={spearman:.4f}",
                flush=True,
            )
    for tag in ("20", "30", "40"):
        print(f"--- threshold {tag}% ---", flush=True)
        for scenario in ("sala_de_clases", "avion_dos_puertas"):
            for rho in RHO_VALS:
                grupo = [f for f in filas if f["scenario"] == scenario and abs(f["rho"] - rho) < 1e-9]
                claros = [f for f in grupo if f[f"p_{tag}"] < 0.05 and f[f"z_{tag}"] > 0]
                us = ", ".join(f"{f['U_I']:.3g}" for f in claros)
                print(
                    f"{scenario} rho={rho}: {len(claros)}/{len(grupo)} with p<0.05 and z>0"
                    + (f" at U_I={us}" if us else ""),
                    flush=True,
                )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", choices=["sala_de_clases", "avion_dos_puertas"])
    parser.add_argument("--n_sims", type=int, default=N_RUNS)
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args()
    if args.report:
        reportar()
        return
    if not args.scenario:
        parser.error("--scenario is required")
    print(f"herd {args.scenario} N_SIMS={args.n_sims} N_SURR={N_SURR}", flush=True)
    ejecutar(args.scenario, args.n_sims)


if __name__ == "__main__":
    main()
