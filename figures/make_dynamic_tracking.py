"""Seguimiento vs d del barrido dinamico ya publicado.

<T> se lee de las tablas seeded. Conflictos, apuestas, victorias y la
fraccion de etapas se miden con las mismas semillas y el mismo tope de
pasos (500). No reescribe T_vs_UI ni las figuras congeladas.
"""

from __future__ import annotations

import csv
import os
import random
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experimento.barrido_pff import D_INV_VALS, MAX_PASOS, N_SIMS, RHO_VALS, SEED_BASE, _generar_posiciones_iniciales
from experimento.barrido_pru_fixed import semilla_de
from experimento.metricas import _desv_estandar_poblacional
from simulacion.agent_extendido import AgentExtendido, mover_agentes_con_conflictos
from simulacion.agentes import Agente, mover_agentes
from simulacion.colisiones import etapa_de, registro_vacio
from simulacion.grilla.floor_field import Floor_field
from simulacion.nodos.path_selector import PathSelector

OUT = ROOT / "figures" / "out"
CACHE = OUT / "dynamic_cache"
TABLAS = {
    ("sala_de_clases", "pff"): ROOT / "tabla_sala_de_clases_pff_ramirez2021_seeded.csv",
    ("sala_de_clases", "pru"): ROOT / "tabla_sala_de_clases_pru_fixed.csv",
    ("avion_dos_puertas", "pff"): ROOT / "tabla_avion_dos_puertas_pff_ramirez2021_seeded.csv",
    ("avion_dos_puertas", "pru"): ROOT / "tabla_avion_dos_puertas_pru_fixed.csv",
}
SCENARIOS = (
    ("sala_de_clases", "Classroom"),
    ("avion_dos_puertas", "Aircraft"),
)
STAGE_COLORS = {"I": "#2ca02c", "II": "#f1c40f", "III": "#d62728"}
ETAPAS = ("I", "II", "III")
METRICAS = ("conflictos", "apuestas", "victorias")


def _escenario(nombre: str):
    if nombre == "sala_de_clases":
        from escenarios import sala_de_clases as esc
    else:
        from escenarios import avion_dos_puertas as esc
    return esc


def _cache(spec: dict) -> Path:
    return CACHE / (
        f"{spec['scenario']}_{spec['motor']}_rho{spec['rho']:.2f}_i{spec['d_index']:02d}_n{spec['n']}.npz"
    )


def _leer_tablas() -> list[dict]:
    filas = []
    for (scenario, motor), path in TABLAS.items():
        with path.open(encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                filas.append(
                    {
                        "scenario": scenario,
                        "motor": motor,
                        "rho": float(row["rho"]),
                        "d_inv": float(row["d_inv"]),
                        "d": 1.0 / float(row["d_inv"]),
                        "T": float(row["T_mean"]),
                        "sd": float(row["sigma_T"]),
                        "fI": float(row["fI"]),
                        "fII": float(row["fII"]),
                        "fIII": float(row["fIII"]),
                    }
                )
    return filas


def _optimo(filas: list[dict], scenario: str, motor: str, rho: float) -> dict:
    grupo = [
        row
        for row in filas
        if row["scenario"] == scenario and row["motor"] == motor and abs(row["rho"] - rho) < 1e-9
    ]
    return min(grupo, key=lambda row: row["T"])


def _indice(d_inv: float) -> int:
    return int(np.argmin(np.abs(np.asarray(D_INV_VALS, dtype=float) - d_inv)))


def _fraccion_activa(agentes, motor: str) -> tuple[int, int, int, int]:
    conteo = {"I": 0, "II": 0, "III": 0}
    total = 0
    for agente in agentes:
        if not getattr(agente, "activo", False):
            continue
        valor = agente.stress if motor == "pff" else agente.ansiedad
        conteo[etapa_de(float(valor), float(agente.U_I), float(agente.U_II))] += 1
        total += 1
    return conteo["I"], conteo["II"], conteo["III"], total


def _acumular(registro: dict, destino: dict) -> None:
    destino["conflictos"] += registro["conflictos"]
    destino["apuestas"] += registro["apuestas"]
    destino["victorias"] += registro["victorias"]
    for etapa in ETAPAS:
        destino["conflictos_etapa"][etapa] += registro.get("conflictos_etapa", {}).get(etapa, 0)
        destino["apuestas_etapa"][etapa] += registro.get("apuestas_etapa", {}).get(etapa, 0)
        destino["victorias_etapa"][etapa] += registro.get("victorias_etapa", {}).get(etapa, 0)


def _vacio() -> dict:
    return {
        "conflictos": 0,
        "apuestas": 0,
        "victorias": 0,
        "conflictos_etapa": {etapa: 0 for etapa in ETAPAS},
        "apuestas_etapa": {etapa: 0 for etapa in ETAPAS},
        "victorias_etapa": {etapa: 0 for etapa in ETAPAS},
    }


def _simular_una(esc, motor: str, rho: float, d_inv: float, semilla: int, serie: bool) -> dict:
    random.seed(semilla)
    np.random.seed(semilla)
    ff = Floor_field(esc.width, esc.height, list(esc.puertas), list(esc.obstaculos))
    rng = random.Random(semilla)
    posiciones = _generar_posiciones_iniciales(esc.width, esc.height, list(esc.obstaculos), rho, rng)
    u_i = 1.0 / d_inv
    registro = registro_vacio()
    suma = np.zeros(3, dtype=np.float64)
    pasos_frac = 0
    pasos_t = 0
    serie_i = []
    serie_ii = []
    serie_iii = []
    if motor == "pff":
        agentes = [
            Agente(x, y, ff, U_I=u_i, U_II=2.0 * u_i, ramirez2021=True) for x, y in posiciones
        ]
        for _ in range(MAX_PASOS):
            if not any(agente.activo for agente in agentes):
                break
            mover_agentes(agentes, registro)
            pasos_t += 1
            c1, c2, c3, total = _fraccion_activa(agentes, motor)
            if total:
                suma += (c1 / total, c2 / total, c3 / total)
                pasos_frac += 1
                if serie:
                    serie_i.append(c1 / total)
                    serie_ii.append(c2 / total)
                    serie_iii.append(c3 / total)
    else:
        AgentExtendido.instances = []
        AgentExtendido.history = []
        AgentExtendido.ruta_log = []
        selector = PathSelector(ff, umbral_recalculo=0.6, anxiety_thresholds=(30, 70), pru_fixed=True)
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
            )
        for step in range(MAX_PASOS):
            activos = [agente for agente in AgentExtendido.instances if agente.activo]
            if not activos:
                break
            for agente in activos:
                agente._current_simulation_step = step
            mover_agentes_con_conflictos(AgentExtendido.instances, registro=registro)
            pasos_t += 1
            c1, c2, c3, total = _fraccion_activa(AgentExtendido.instances, motor)
            if total:
                suma += (c1 / total, c2 / total, c3 / total)
                pasos_frac += 1
                if serie:
                    serie_i.append(c1 / total)
                    serie_ii.append(c2 / total)
                    serie_iii.append(c3 / total)
        AgentExtendido.instances = []
    return {
        "T": pasos_t,
        "registro": registro,
        "fraccion": suma / pasos_frac if pasos_frac else suma,
        "serie": (serie_i, serie_ii, serie_iii) if serie else None,
    }


def ejecutar(spec: dict) -> dict:
    path = _cache(spec)
    if path.exists():
        return {"cache": str(path), "spec": spec}
    esc = _escenario(spec["scenario"])
    tiempos = []
    total = _vacio()
    fraccion = np.zeros(3, dtype=np.float64)
    largo = MAX_PASOS
    acc = np.zeros((3, largo), dtype=np.float64)
    cuenta = np.zeros(largo, dtype=np.int32)
    for i in range(int(spec["n"])):
        semilla = semilla_de(spec["rho"], spec["d_inv"], i)
        corrida = _simular_una(esc, spec["motor"], spec["rho"], spec["d_inv"], semilla, spec["serie"])
        tiempos.append(corrida["T"])
        _acumular(corrida["registro"], total)
        fraccion += corrida["fraccion"]
        if spec["serie"] and corrida["serie"] is not None:
            for k, serie in enumerate(corrida["serie"]):
                n = min(len(serie), largo)
                acc[k, :n] += np.asarray(serie[:n], dtype=np.float64)
                if k == 0:
                    cuenta[:n] += 1
    n = float(spec["n"])
    payload = {
        "T_mean": np.array(float(np.mean(tiempos))),
        "T_sd": np.array(float(_desv_estandar_poblacional(tiempos))),
        "conflictos": np.array(total["conflictos"] / n),
        "apuestas": np.array(total["apuestas"] / n),
        "victorias": np.array(total["victorias"] / n),
        "conflictos_etapa": np.array([total["conflictos_etapa"][e] / n for e in ETAPAS]),
        "apuestas_etapa": np.array([total["apuestas_etapa"][e] / n for e in ETAPAS]),
        "victorias_etapa": np.array([total["victorias_etapa"][e] / n for e in ETAPAS]),
        "fraccion": fraccion / n,
        "time_n": cuenta,
        "time_frac": acc,
    }
    CACHE.mkdir(parents=True, exist_ok=True)
    np.savez(path, **payload)
    print(
        f"done {spec['scenario']} {spec['motor']} rho={spec['rho']:g} d={spec['d']:.4g} "
        f"T={payload['T_mean']:.2f} C={payload['conflictos']:.2f}",
        flush=True,
    )
    return {"cache": str(path), "spec": spec}


def _trabajos(filas: list[dict]) -> list[dict]:
    optimos = {}
    for scenario, _titulo in SCENARIOS:
        optimos[scenario] = _indice(_optimo(filas, scenario, "pff", 1.0)["d_inv"])
    jobs = []
    for scenario, _titulo in SCENARIOS:
        for rho in RHO_VALS:
            for indice, d_inv in enumerate(D_INV_VALS):
                d = 1.0 / float(d_inv)
                serie = abs(float(rho) - 1.0) < 1e-9 and (
                    indice in (0, 15) or indice == optimos[scenario]
                )
                for motor in ("pff", "pru"):
                    jobs.append(
                        {
                            "scenario": scenario,
                            "motor": motor,
                            "rho": float(rho),
                            "d_inv": float(d_inv),
                            "d": float(d),
                            "d_index": indice,
                            "n": N_SIMS,
                            "serie": serie,
                        }
                    )
    return jobs


def _cargar(spec: dict) -> dict:
    data = np.load(_cache(spec))
    return {clave: data[clave] for clave in data.files}


def _comprobar(filas: list[dict], jobs: list[dict]) -> None:
    peor = 0.0
    for spec in jobs:
        data = _cargar(spec)
        tabla = min(
            filas,
            key=lambda row: abs(row["rho"] - spec["rho"])
            + abs(np.log(row["d_inv"]) - np.log(spec["d_inv"]))
            + (0 if row["scenario"] == spec["scenario"] and row["motor"] == spec["motor"] else 10),
        )
        peor = max(peor, abs(float(data["T_mean"]) - tabla["T"]))
    print(f"max |T medido - T tabla| = {peor:.4f}", flush=True)
    if peor > 0.05:
        raise SystemExit("el T medido no coincide con la tabla del barrido")


def _filas_medidas(jobs: list[dict]) -> list[dict]:
    salida = []
    for spec in jobs:
        data = _cargar(spec)
        fila = dict(spec)
        fila["T_mean"] = float(data["T_mean"])
        fila["T_sd"] = float(data["T_sd"])
        for clave in METRICAS:
            fila[clave] = float(data[clave])
            fila[f"{clave}_etapa"] = data[f"{clave}_etapa"].astype(float)
        fila["fraccion"] = data["fraccion"].astype(float)
        fila["time_n"] = data["time_n"].astype(int)
        fila["time_frac"] = data["time_frac"].astype(float)
        salida.append(fila)
    return salida


def _maximos(filas: list[dict]) -> dict[str, float]:
    return {clave: max(fila[clave] for fila in filas) for clave in METRICAS}


def apply_style(plt) -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.labelsize": 11,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "legend.fontsize": 9,
            "axes.linewidth": 0.8,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "savefig.dpi": 200,
        }
    )


def _guardar(plt, fig, stem: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f"{stem}.pdf", format="pdf", bbox_inches="tight", pad_inches=0.04)
    fig.savefig(OUT / f"{stem}.png", format="png", dpi=200, bbox_inches="tight", pad_inches=0.04)
    plt.close(fig)
    print("wrote", OUT / f"{stem}.pdf", flush=True)


def _ejes_d(ax) -> None:
    ax.set_xscale("log")
    ax.set_xticks([1, 10, 100, 1000])
    ax.set_xticklabels(["1", "10", "100", "1000"])
    ax.set_xlabel(r"$d$")
    ax.grid(True, which="both", linewidth=0.3, alpha=0.45)


def figura_colisiones(plt, filas: list[dict], maximos: dict[str, float]) -> None:
    from matplotlib.lines import Line2D

    apply_style(plt)
    fig, axes = plt.subplots(2, 4, figsize=(11.6, 6.3), sharex=True)
    letras = "abcdefgh"
    colores = {"conflictos": "#333333", "apuestas": "#1f77b4", "victorias": "#ff7f0e"}
    for fila_i, (scenario, titulo) in enumerate(SCENARIOS):
        for col, rho in enumerate(RHO_VALS):
            ax = axes[fila_i, col]
            for motor, estilo in (("pff", "-"), ("pru", "--")):
                grupo = sorted(
                    (
                        row
                        for row in filas
                        if row["scenario"] == scenario and row["motor"] == motor and abs(row["rho"] - rho) < 1e-9
                    ),
                    key=lambda row: row["d"],
                )
                d = np.array([row["d"] for row in grupo])
                for clave, color in colores.items():
                    y = np.array([row[clave] / maximos[clave] for row in grupo])
                    ax.plot(d, y, color=color, linestyle=estilo, linewidth=1.2, marker="o", markersize=2.6)
                for etapa_i, etapa in enumerate(ETAPAS):
                    y = np.array([row["conflictos_etapa"][etapa_i] / maximos["conflictos"] for row in grupo])
                    ax.plot(
                        d,
                        y,
                        color=STAGE_COLORS[etapa],
                        linestyle=estilo,
                        linewidth=1.0,
                        alpha=0.95,
                    )
            _ejes_d(ax)
            ax.set_ylim(-0.02, 1.05)
            letra = letras[fila_i * 4 + col]
            ax.text(0.03, 0.97, f"({letra})", transform=ax.transAxes, ha="left", va="top", fontsize=11, fontweight="bold")
            if fila_i == 0:
                ax.set_title(rf"$\rho = {rho:g}$")
            if col == 0:
                ax.set_ylabel(titulo + "\ncount / maximum")
    handles = [
        Line2D([0], [0], color=colores["conflictos"], lw=1.6, label="Conflicts"),
        Line2D([0], [0], color=colores["apuestas"], lw=1.6, label="Bets"),
        Line2D([0], [0], color=colores["victorias"], lw=1.6, label="Wins"),
        Line2D([0], [0], color=STAGE_COLORS["I"], lw=1.6, label="Conflicts I"),
        Line2D([0], [0], color=STAGE_COLORS["II"], lw=1.6, label="Conflicts II"),
        Line2D([0], [0], color=STAGE_COLORS["III"], lw=1.6, label="Conflicts III"),
        Line2D([0], [0], color="0.2", lw=1.4, linestyle="-", label="PFF"),
        Line2D([0], [0], color="0.2", lw=1.4, linestyle="--", label="PRU"),
    ]
    fig.legend(handles=handles, loc="lower center", ncol=4, frameon=False, bbox_to_anchor=(0.5, 0.0))
    fig.subplots_adjust(left=0.07, right=0.985, bottom=0.16, top=0.93, wspace=0.28, hspace=0.28)
    _guardar(plt, fig, "collisions_vs_d")


def figura_fraccion(plt, filas: list[dict]) -> None:
    from matplotlib.lines import Line2D

    apply_style(plt)
    fig, axes = plt.subplots(2, 4, figsize=(11.6, 6.15), sharex=True, sharey=True)
    letras = "abcdefgh"
    for fila_i, (scenario, titulo) in enumerate(SCENARIOS):
        for col, rho in enumerate(RHO_VALS):
            ax = axes[fila_i, col]
            for motor, estilo in (("pff", "-"), ("pru", "--")):
                grupo = sorted(
                    (
                        row
                        for row in filas
                        if row["scenario"] == scenario and row["motor"] == motor and abs(row["rho"] - rho) < 1e-9
                    ),
                    key=lambda row: row["d"],
                )
                d = np.array([row["d"] for row in grupo])
                for etapa_i, etapa in enumerate(ETAPAS):
                    y = np.array([row["fraccion"][etapa_i] for row in grupo])
                    ax.plot(
                        d,
                        y,
                        color=STAGE_COLORS[etapa],
                        linestyle=estilo,
                        linewidth=1.25,
                        marker="o",
                        markersize=2.6,
                    )
            _ejes_d(ax)
            ax.set_ylim(-0.02, 1.05)
            letra = letras[fila_i * 4 + col]
            ax.text(0.03, 0.97, f"({letra})", transform=ax.transAxes, ha="left", va="top", fontsize=11, fontweight="bold")
            if fila_i == 0:
                ax.set_title(rf"$\rho = {rho:g}$")
            if col == 0:
                ax.set_ylabel(titulo + "\nmean stage fraction")
    handles = [
        Line2D([0], [0], color=STAGE_COLORS[etapa], lw=1.8, label=f"Stage {etapa}") for etapa in ETAPAS
    ]
    handles.extend(
        [
            Line2D([0], [0], color="0.2", lw=1.4, linestyle="-", label="PFF"),
            Line2D([0], [0], color="0.2", lw=1.4, linestyle="--", label="PRU"),
        ]
    )
    fig.legend(handles=handles, loc="lower center", ncol=5, frameon=False, bbox_to_anchor=(0.5, 0.005))
    fig.subplots_adjust(left=0.07, right=0.985, bottom=0.14, top=0.93, wspace=0.22, hspace=0.28)
    _guardar(plt, fig, "stage_fraction_vs_d")


def figura_tiempo(plt, filas: list[dict], tablas: list[dict]) -> None:
    from matplotlib.lines import Line2D

    apply_style(plt)
    fig, axes = plt.subplots(2, 3, figsize=(10.2, 6.0), sharey=True)
    columnas = ("endpoint", "optimum", "calm")
    for fila_i, (scenario, titulo) in enumerate(SCENARIOS):
        opt = _optimo(tablas, scenario, "pff", 1.0)
        indice_opt = _indice(opt["d_inv"])
        elegidos = {
            "endpoint": 15,
            "optimum": indice_opt,
            "calm": 0,
        }
        titulos = {
            "endpoint": r"$d = 1$",
            "optimum": rf"PFF optimum, $d = {opt['d']:.3g}$",
            "calm": r"$d = 1000$",
        }
        for col, clave in enumerate(columnas):
            ax = axes[fila_i, col]
            indice = elegidos[clave]
            for motor, estilo in (("pff", "-"), ("pru", "--")):
                fila = next(
                    row
                    for row in filas
                    if row["scenario"] == scenario
                    and row["motor"] == motor
                    and abs(row["rho"] - 1.0) < 1e-9
                    and row["d_index"] == indice
                )
                n = fila["time_n"]
                validos = np.where(n >= 20)[0]
                if len(validos) == 0:
                    continue
                t = validos
                for etapa_i, etapa in enumerate(ETAPAS):
                    y = fila["time_frac"][etapa_i, t] / np.maximum(n[t], 1)
                    ax.plot(t + 1, y, color=STAGE_COLORS[etapa], linestyle=estilo, linewidth=1.2)
            ax.set_ylim(-0.02, 1.05)
            ax.grid(True, linewidth=0.3, alpha=0.45)
            ax.set_title(titulos[clave] if fila_i == 0 else titulos[clave])
            if fila_i == 1:
                ax.set_xlabel("step")
            if col == 0:
                ax.set_ylabel(titulo + "\nstage fraction")
            ax.text(
                0.03,
                0.97,
                f"({chr(ord('a') + fila_i * 3 + col)})",
                transform=ax.transAxes,
                ha="left",
                va="top",
                fontsize=11,
                fontweight="bold",
            )
    handles = [Line2D([0], [0], color=STAGE_COLORS[etapa], lw=1.8, label=f"Stage {etapa}") for etapa in ETAPAS]
    handles.extend(
        [
            Line2D([0], [0], color="0.2", lw=1.4, linestyle="-", label="PFF"),
            Line2D([0], [0], color="0.2", lw=1.4, linestyle="--", label="PRU"),
        ]
    )
    fig.legend(handles=handles, loc="lower center", ncol=5, frameon=False, bbox_to_anchor=(0.5, 0.0))
    fig.subplots_adjust(left=0.08, right=0.985, bottom=0.14, top=0.92, wspace=0.22, hspace=0.32)
    _guardar(plt, fig, "stage_fraction_time_rho1")


def _resumen(filas: list[dict], tablas: list[dict], maximos: dict[str, float]) -> None:
    print("maximos del barrido", {k: round(v, 2) for k, v in maximos.items()}, flush=True)
    for scenario, _titulo in SCENARIOS:
        for motor in ("pff", "pru"):
            opt = _optimo(tablas, scenario, motor, 1.0)
            print(
                f"optimo rho=1 {scenario} {motor} d={opt['d']:.4g} T={opt['T']:.2f} ± {opt['sd']:.2f}",
                flush=True,
            )
    print("scenario motor rho d conflictos apuestas victorias C_I C_II C_III fI fII fIII", flush=True)
    for fila in filas:
        if abs(fila["rho"] - 1.0) > 1e-9 and abs(fila["d"] - 1.0) > 0.05 and abs(fila["d"] - 1000) > 1:
            continue
        c = fila["conflictos_etapa"]
        f = fila["fraccion"]
        print(
            f"{fila['scenario']} {fila['motor']} {fila['rho']:.2f} {fila['d']:.4g} "
            f"{fila['conflictos']:.2f} {fila['apuestas']:.2f} {fila['victorias']:.2f} "
            f"{c[0]:.2f} {c[1]:.2f} {c[2]:.2f} {f[0]:.3f} {f[1]:.3f} {f[2]:.3f}",
            flush=True,
        )


def main() -> None:
    tablas = _leer_tablas()
    jobs = _trabajos(tablas)
    pendientes = [spec for spec in jobs if not _cache(spec).exists()]
    print(f"jobs {len(jobs)} pending {len(pendientes)}", flush=True)
    if pendientes and "--plot-only" not in sys.argv:
        workers = max(1, (os.cpu_count() or 2) - 0)
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(ejecutar, spec) for spec in pendientes]
            for fut in as_completed(futures):
                fut.result()
    _comprobar(tablas, jobs)
    medidos = _filas_medidas(jobs)
    maximos = _maximos(medidos)
    _resumen(medidos, tablas, maximos)
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figura_colisiones(plt, medidos, maximos)
    figura_fraccion(plt, medidos)
    figura_tiempo(plt, medidos, tablas)


if __name__ == "__main__":
    main()
