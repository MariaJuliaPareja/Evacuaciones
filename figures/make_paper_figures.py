"""Paper figures for the PRU-A* evacuation model (Physica A / elsarticle).

Reads the real simulation classes. Does not modify any simulation module.

Outputs (figures/out/):
  model_overview.pdf / .png
  model_overview_info.txt
  occupation_classroom.pdf / .png
  occupation_aircraft.pdf / .png
  occupation_classroom.npz
  occupation_aircraft.npz
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle

from escenarios import avion_dos_puertas as aircraft_scenario
from escenarios import sala_de_clases as classroom_scenario
from experimento.barrido_pff import (
    _generar_posiciones_iniciales as posiciones_pff,
)
from experimento.barrido_propuesta1 import (
    D_INV_VALS,
    SEED_BASE,
    _generar_posiciones_iniciales as posiciones_pru,
)
from experimento.metricas import _desv_estandar_poblacional
from simulacion.agent_extendido import AgentExtendido, mover_agentes_con_conflictos
from simulacion.agentes import Agente, mover_agentes
from simulacion.grilla.floor_field import Floor_field
from simulacion.nodos.path_selector import PathSelector

OUT_DIR = ROOT / "figures" / "out"

# Reference cell of the published sweep: rho = 1 (plot_pizarra_abcd.RHO_REF)
# and the middle 1/d of D_INV_VALS (index len//2), which is log10(1/d) = -1.4
# in tabla_comparacion_pff_pru_fixed.csv.
RHO = 1.0
N_RUNS = 100
MAX_PASOS = 500
AGENT_START = (10, 2)  # behind desk (9, 2), far from the left-wall doors

SEAT_GRAPH = "#e0e0e0"
SEAT_EDGE = "#4a4a4a"
ROUTE_BLUE = "#1f77b4"
ROUTE_ORANGE = "#ff7f0e"
AGENT_GREEN = "#2ca02c"


def _paper_thresholds() -> tuple[float, float, float]:
    d_inv_vals = sorted(float(v) for v in D_INV_VALS)
    d_inv = d_inv_vals[len(d_inv_vals) // 2]
    return d_inv, 1.0 / d_inv, 2.0 / d_inv


def _seed(run_index: int, d_inv: float) -> int:
    """Same formula as experimento/barrido_propuesta1.py and barrido_pff.py."""
    return SEED_BASE + run_index + int(1_000_000 * RHO) + int(10_000 * float(d_inv))


def apply_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 11,
            "axes.labelsize": 12,
            "xtick.labelsize": 11,
            "ytick.labelsize": 11,
            "legend.fontsize": 11,
            "axes.linewidth": 0.8,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "savefig.dpi": 200,
        }
    )


def save_figure(fig: plt.Figure, stem: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_DIR / f"{stem}.pdf", format="pdf", bbox_inches="tight", pad_inches=0.06)
    fig.savefig(OUT_DIR / f"{stem}.png", format="png", dpi=200, bbox_inches="tight", pad_inches=0.06)
    plt.close(fig)


def wall_cells(width: int, height: int, puertas: list[tuple[int, int]]) -> list[tuple[int, int]]:
    doors = set(map(tuple, puertas))
    cells = []
    for x in range(width):
        for y in range(height):
            if x == 0 or x == width - 1 or y == 0 or y == height - 1:
                if (x, y) not in doors:
                    cells.append((x, y))
    return cells


def interior_seats(obstaculos, width: int, height: int) -> list[tuple[int, int]]:
    seats = []
    for x, y in obstaculos:
        if 0 < x < width - 1 and 0 < y < height - 1:
            seats.append((int(x), int(y)))
    return seats


def draw_cells(
    ax: plt.Axes,
    cells: list[tuple[int, int]],
    face: str,
    edge: str,
    lw: float,
    zorder: int,
) -> None:
    for x, y in cells:
        ax.add_patch(
            Rectangle(
                (x - 0.5, y - 0.5),
                1.0,
                1.0,
                facecolor=face,
                edgecolor=edge,
                linewidth=lw,
                zorder=zorder,
            )
        )


def draw_doors(ax: plt.Axes, puertas, size: float) -> None:
    if not puertas:
        return
    xs, ys = zip(*puertas)
    ax.scatter(
        xs,
        ys,
        marker="*",
        s=size,
        c="red",
        edgecolors="black",
        linewidths=0.6,
        zorder=6,
    )


def style_map_axes(ax: plt.Axes, width: int, height: int, panel: str) -> None:
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(-0.8, width - 0.2)
    ax.set_ylim(-0.8, height - 0.2)
    ax.set_xlabel(r"$x$ (cells)")
    ax.set_ylabel(r"$y$ (cells)")
    ax.set_xticks(_ticks(width))
    ax.set_yticks(_ticks(height))
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_linewidth(0.8)
    ax.text(
        0.02,
        0.98,
        panel,
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=12,
        fontweight="bold",
        color="black",
        zorder=8,
        bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.9),
    )


def _ticks(n: int) -> list[int]:
    if n <= 16:
        step = 2
    else:
        step = 5
    return list(range(0, n, step))


def undirected_segments(graph) -> list[list[tuple[float, float]]]:
    seen: set[tuple[tuple[int, int], tuple[int, int]]] = set()
    segments = []
    for u, v in graph.edges():
        key = (u, v) if u <= v else (v, u)
        if key in seen:
            continue
        seen.add(key)
        segments.append([(u[0], u[1]), (v[0], v[1])])
    return segments


def degree_report(graph) -> dict[str, int]:
    degrees = [graph.out_degree(n) for n in graph.nodes]
    n8 = sum(1 for d in degrees if d == 8)
    return {
        "min": int(min(degrees) if degrees else 0),
        "max": int(max(degrees) if degrees else 0),
        "n_with_8": int(n8),
        "n_nodes": int(graph.number_of_nodes()),
        "n_directed_edges": int(graph.number_of_edges()),
        "n_undirected": len(undirected_segments(graph)),
    }


def draw_navigation_graph(
    ax: plt.Axes,
    ff: Floor_field,
    selector: PathSelector,
    norm,
    panel: str,
    node_size: float,
    star_size: float,
) -> None:
    seats = interior_seats(ff.obstaculos, ff.width, ff.height)
    walls = wall_cells(ff.width, ff.height, list(ff.puertas))
    draw_cells(ax, walls, SEAT_GRAPH, SEAT_EDGE, 0.35, 1)
    draw_cells(ax, seats, SEAT_GRAPH, SEAT_EDGE, 0.45, 1)

    segments = undirected_segments(selector.grafo)
    if segments:
        ax.add_collection(
            LineCollection(
                segments,
                colors="#6b6b6b",
                linewidths=0.35,
                alpha=0.75,
                zorder=2,
            )
        )

    xs, ys, phi = [], [], []
    for x, y in selector.grafo.nodes:
        xs.append(x)
        ys.append(y)
        phi.append(float(ff.valores[y, x]))
    ax.scatter(
        xs,
        ys,
        c=phi,
        cmap="viridis",
        norm=norm,
        s=node_size,
        marker="s",
        linewidths=0,
        zorder=3,
    )
    draw_doors(ax, ff.puertas, star_size)
    style_map_axes(ax, ff.width, ff.height, panel)

    n_nodes = selector.grafo.number_of_nodes()
    n_edges = selector.grafo.number_of_edges()
    # Above the frame so the box does not cover a door or the seat graph.
    ax.text(
        0.5,
        1.03,
        f"Nodes: {n_nodes}, edges: {n_edges}",
        transform=ax.transAxes,
        ha="center",
        va="bottom",
        fontsize=8,
        zorder=8,
        clip_on=False,
        bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="0.4", alpha=0.95),
    )


def measure_unlock_thresholds(selector: PathSelector, calmness: int) -> dict[str, int]:
    """Read the 1 -> 3 -> 5 cuts from calculate_unlocked_paths."""
    levels = {
        s: int(selector.calculate_unlocked_paths(s, calmness_threshold=calmness))
        for s in range(0, 12)
    }
    to_3 = next(s for s, n in levels.items() if n >= 3)
    to_5 = next(s for s, n in levels.items() if n >= 5)
    return {"calmness": calmness, "to_3": to_3, "to_5": to_5, "levels": levels}


def offset_polyline(path: list[tuple[int, int]], delta: float) -> np.ndarray:
    pts = np.asarray(path, dtype=float)
    if abs(delta) < 1e-12 or len(pts) < 2:
        return pts
    out = np.empty_like(pts)
    for i in range(len(pts)):
        if i == 0:
            direction = pts[1] - pts[0]
        elif i == len(pts) - 1:
            direction = pts[-1] - pts[-2]
        else:
            direction = pts[i + 1] - pts[i - 1]
        normal = np.array([-direction[1], direction[0]], dtype=float)
        norm = float(np.linalg.norm(normal))
        if norm == 0.0:
            out[i] = pts[i]
        else:
            out[i] = pts[i] + delta * normal / norm
    out[0] = pts[0]
    out[-1] = pts[-1]
    return out


def route_offsets(paths: list[list[tuple[int, int]]]) -> list[float]:
    """Separate overlapping routes by multiples of 0.08 cells. Route 1 stays put."""
    cell_sets = [set(map(tuple, path)) for path in paths]
    offsets = [0.0] * len(paths)
    for i in range(1, len(paths)):
        used = {0.0}
        for j in range(i):
            if cell_sets[i] & cell_sets[j]:
                used.add(offsets[j])
        if not (cell_sets[i] & set().union(*(cell_sets[j] for j in range(i)))):
            continue
        k = 1
        chosen = 0.0
        while True:
            for sign in (1.0, -1.0):
                candidate = sign * 0.08 * k
                if candidate not in used:
                    chosen = candidate
                    break
            else:
                k += 1
                continue
            break
        offsets[i] = chosen
    return offsets


def nearest_door_manhattan(origin: tuple[int, int], puertas) -> tuple[int, int]:
    """Same rule as AgentExtendido._encontrar_puerta_mas_cercana."""
    return min(puertas, key=lambda door: abs(origin[0] - door[0]) + abs(origin[1] - door[1]))


def build_classroom_routes(ff: Floor_field, selector: PathSelector):
    """Five routes in the order PathSelector.find_progressive_paths returns them."""
    AgentExtendido.instances = []
    AgentExtendido.history = []
    AgentExtendido.ruta_log = []
    agent = AgentExtendido(
        agent_type="rapido",
        floor_field=ff,
        path_selector=selector,
        x=AGENT_START[0],
        y=AGENT_START[1],
        U_I=10,
        U_II=20,
    )
    goal = agent._encontrar_puerta_mas_cercana()
    paths = selector.find_progressive_paths(AGENT_START, goal, num_paths=agent.k_paths_max)
    costs = [float(selector._calculate_base_path_cost(path)) for path in paths]
    return agent, goal, paths, costs


def draw_route_panel(
    ax: plt.Axes,
    ff: Floor_field,
    paths: list[list[tuple[int, int]]],
    start: tuple[int, int],
) -> None:
    seats = interior_seats(ff.obstaculos, ff.width, ff.height)
    walls = wall_cells(ff.width, ff.height, list(ff.puertas))
    draw_cells(ax, walls, SEAT_GRAPH, SEAT_EDGE, 0.35, 1)
    draw_cells(ax, seats, SEAT_GRAPH, SEAT_EDGE, 0.45, 1)

    styles = [
        dict(color="black", lw=2.4, ls="-", zorder=5),
        dict(color=ROUTE_BLUE, lw=1.7, ls=(0, (4, 1.6)), zorder=4),
        dict(color=ROUTE_BLUE, lw=1.7, ls=(0, (4, 1.6)), zorder=4),
        dict(color=ROUTE_ORANGE, lw=1.8, ls=(0, (1, 1.1)), zorder=3),
        dict(color=ROUTE_ORANGE, lw=1.8, ls=(0, (1, 1.1)), zorder=3),
    ]
    offsets = route_offsets(paths)
    order = list(range(len(paths) - 1, -1, -1))
    for index in order:
        style = styles[min(index, len(styles) - 1)]
        shifted = offset_polyline(paths[index], offsets[index])
        ax.plot(shifted[:, 0], shifted[:, 1], solid_capstyle="round", **style)

    draw_doors(ax, ff.puertas, 160)
    ax.scatter(
        [start[0]],
        [start[1]],
        s=90,
        c=AGENT_GREEN,
        marker="o",
        edgecolors="black",
        linewidths=0.7,
        zorder=7,
    )
    style_map_axes(ax, ff.width, ff.height, "(c)")


def make_model_overview(d_inv: float, u_i: float, u_ii: float) -> dict:
    classroom_ff = Floor_field(
        classroom_scenario.width,
        classroom_scenario.height,
        classroom_scenario.puertas,
        classroom_scenario.obstaculos,
    )
    aircraft_ff = Floor_field(
        aircraft_scenario.width,
        aircraft_scenario.height,
        aircraft_scenario.puertas,
        aircraft_scenario.obstaculos,
    )
    classroom_ps = PathSelector(classroom_ff, umbral_recalculo=0.6, anxiety_thresholds=(30, 70))
    aircraft_ps = PathSelector(aircraft_ff, umbral_recalculo=0.6, anxiety_thresholds=(30, 70))

    phi_values = []
    for ff, ps in ((classroom_ff, classroom_ps), (aircraft_ff, aircraft_ps)):
        for x, y in ps.grafo.nodes:
            phi_values.append(float(ff.valores[y, x]))
    norm = plt.Normalize(vmin=min(phi_values), vmax=max(phi_values))

    unlock = measure_unlock_thresholds(classroom_ps, calmness=3)
    _agent, goal, paths, costs = build_classroom_routes(classroom_ff, classroom_ps)
    unique_paths = len({tuple(path) for path in paths})

    fig = plt.figure(figsize=(14.0, 5.35))
    grid = fig.add_gridspec(
        1,
        3,
        width_ratios=(1.15, 0.85, 1.15),
        left=0.045,
        right=0.90,
        bottom=0.22,
        top=0.90,
        wspace=0.32,
    )
    ax_a = fig.add_subplot(grid[0, 0])
    ax_b = fig.add_subplot(grid[0, 1])
    ax_c = fig.add_subplot(grid[0, 2])

    draw_navigation_graph(ax_a, classroom_ff, classroom_ps, norm, "(a)", node_size=11, star_size=150)
    draw_navigation_graph(ax_b, aircraft_ff, aircraft_ps, norm, "(b)", node_size=7, star_size=70)
    draw_route_panel(ax_c, classroom_ff, paths, AGENT_START)

    mappable = plt.cm.ScalarMappable(norm=norm, cmap="viridis")
    colorbar = fig.colorbar(mappable, ax=[ax_a, ax_b], fraction=0.046, pad=0.03)
    colorbar.set_label(r"Distance to nearest door, $\phi$")

    t3, t5 = unlock["to_3"], unlock["to_5"]
    handles = [
        Line2D([0], [0], color="black", lw=2.4, label=rf"Route 1 ($\delta_i < {t3}$)"),
        Line2D(
            [0],
            [0],
            color=ROUTE_BLUE,
            lw=1.7,
            ls=(0, (4, 1.6)),
            label=rf"Routes 2–3 (${t3} \leq \delta_i < {t5}$)",
        ),
        Line2D(
            [0],
            [0],
            color=ROUTE_ORANGE,
            lw=1.8,
            ls=(0, (1, 1.1)),
            label=rf"Routes 4–5 ($\delta_i \geq {t5}$)",
        ),
        Line2D(
            [0],
            [0],
            marker="o",
            color="none",
            markerfacecolor=AGENT_GREEN,
            markeredgecolor="black",
            markersize=8,
            label="Agent",
        ),
        Line2D(
            [0],
            [0],
            marker="*",
            color="none",
            markerfacecolor="red",
            markeredgecolor="black",
            markersize=13,
            label="Door",
        ),
        Patch(facecolor=SEAT_GRAPH, edgecolor=SEAT_EDGE, label="Seat"),
    ]
    fig.legend(
        handles=handles,
        loc="lower center",
        bbox_to_anchor=(0.48, 0.005),
        ncol=3,
        frameon=False,
    )
    save_figure(fig, "model_overview")

    class_deg = degree_report(classroom_ps.grafo)
    air_deg = degree_report(aircraft_ps.grafo)
    weights = sorted({round(data["weight"], 4) for *_edge, data in classroom_ps.grafo.edges(data=True)})
    air_weights = sorted({round(data["weight"], 4) for *_edge, data in aircraft_ps.grafo.edges(data=True)})

    info = {
        "classroom_degree": class_deg,
        "aircraft_degree": air_deg,
        "weights_classroom": weights,
        "weights_aircraft": air_weights,
        "unlock": unlock,
        "start": AGENT_START,
        "goal": tuple(goal),
        "n_paths": len(paths),
        "n_unique": unique_paths,
        "costs": costs,
        "lengths": [len(path) for path in paths],
        "offsets": route_offsets(paths),
        "phi_vmin": float(norm.vmin),
        "phi_vmax": float(norm.vmax),
        "d_inv": d_inv,
        "U_I": u_i,
        "U_II": u_ii,
        "k_paths_max": int(_agent.k_paths_max),
        "calmness": int(_agent.calmness_threshold),
    }
    write_overview_info(info)
    return info


def write_overview_info(info: dict) -> None:
    unlock = info["unlock"]
    lines = [
        "model_overview — values taken from the running code",
        "",
        "Scenarios",
        "  (a) escenarios/sala_de_clases.py",
        "  (b) escenarios/avion_dos_puertas.py",
        "      (front/rear doors; this is the aircraft in the published tables,",
        "       not escenarios/avion.py, which has side doors).",
        "",
        "Graph neighborhood",
        "  PathSelector._construir_grafo_nodos_impl builds a DiGraph with 8",
        "  directions (4 orthogonal weight 1.0, 4 diagonal weight 1.5):",
        "  simulacion/nodos/path_selector.py lines 90-99 and 128-130.",
        "  A node has fewer than 8 edges wherever a neighbor is a wall or a seat.",
        f"  Classroom: nodes={info['classroom_degree']['n_nodes']}, "
        f"directed edges={info['classroom_degree']['n_directed_edges']}, "
        f"undirected links drawn={info['classroom_degree']['n_undirected']}, "
        f"out-degree min/max={info['classroom_degree']['min']}/{info['classroom_degree']['max']}, "
        f"nodes with 8 neighbors={info['classroom_degree']['n_with_8']}.",
        f"  Aircraft: nodes={info['aircraft_degree']['n_nodes']}, "
        f"directed edges={info['aircraft_degree']['n_directed_edges']}, "
        f"undirected links drawn={info['aircraft_degree']['n_undirected']}, "
        f"out-degree min/max={info['aircraft_degree']['min']}/{info['aircraft_degree']['max']}, "
        f"nodes with 8 neighbors={info['aircraft_degree']['n_with_8']}.",
        "  The box on panels (a) and (b) reports DiGraph.number_of_nodes() and",
        "  number_of_edges() (both directions). The drawing shows each link once.",
        "",
        "How alternative routes are generated",
        "  Not a k-shortest-path library. find_progressive_paths (path_selector.py",
        "  lines 393-430) calls find_k_paths (lines 440-537):",
        "    path 1: plain A* (line 472);",
        "    paths 2..k: A* with peso_penalizado = peso_base + penalty_factor * veces_usada",
        "    (line 537), penalty_factor=0.5 (line 441);",
        "    a candidate is kept only if its cell-set difference from every",
        "    accepted path is >= 0.30 (line 518);",
        "    if that fails, one retry uses penalty_factor * 2 (line 555).",
        "  The returned order is the unlock order, not a sort by cost.",
        "",
        "Progressive unlocking (checked by calling calculate_unlocked_paths)",
        f"  AgentExtendido.calmness_threshold = {info['calmness']} "
        "(agent_extendido.py line 93).",
        "  path_selector.py lines 1371-1376:",
        "    steps < calmness            -> 1 route",
        "    steps < calmness + 2        -> 3 routes",
        "    otherwise                   -> 5 routes",
        f"  Measured cuts: 3 routes from delta={unlock['to_3']}, "
        f"5 routes from delta={unlock['to_5']}.",
        f"  levels by delta 0..11: {unlock['levels']}",
        "  These are the thresholds 3 and 5 used in the figure legend.",
        "  The class docstring in agent_extendido.py lines 25-28 says 3-5 -> 3",
        "  and 6+ -> 5. That docstring disagrees with the function that runs.",
        "",
        "Panel (c) agent",
        f"  Start {info['start']}, in the seat column immediately behind desk (9, 2),",
        "  on the side of the room opposite the doors. This cell is also one of",
        "  the seats listed in escenarios/sala_de_clases.py.",
        f"  Goal chosen by AgentExtendido._encontrar_puerta_mas_cercana "
        f"(Manhattan): {info['goal']}.",
        f"  find_progressive_paths returned {info['n_paths']} routes, "
        f"{info['n_unique']} distinct.",
        "  Graph cost of each route (sum of current edge weights via",
        "  PathSelector._calculate_base_path_cost, lines 789-822).",
        "  Weights were not updated, so this is 1.0 per orthogonal step and",
        "  1.5 per diagonal step:",
    ]
    for index, (cost, length, offset) in enumerate(
        zip(info["costs"], info["lengths"], info["offsets"]), start=1
    ):
        lines.append(
            f"    route {index}: cost={cost:.2f}, cells={length}, "
            f"display offset={offset:+.2f}"
        )
    lines.extend(
        [
            "",
            "Edge weights",
            f"  Classroom unique weights at construction: {info['weights_classroom']}.",
            f"  Aircraft unique weights at construction: {info['weights_aircraft']}.",
            "  Orthogonal edges are initialized at 1.0 and diagonal edges at 1.5",
            "  (path_selector.py lines 91-99). They are not proportional to phi.",
            "  actualizar_pesos_grafo (lines 197-231) can multiply those weights",
            "  by occupancy, but the parameter sweep never calls it.",
            "  The only call sites are simulacion/grilla/dynamics.py lines 467 and",
            "  629-631. experimento/barrido_propuesta1.py does not update weights,",
            "  so during the runs behind the tables the edges stay at 1.0 / 1.5.",
            "  Figure 2 uses that same sweep path: weights are not updated.",
            "",
            "Shared floor-field scale on panels (a) and (b)",
            f"  vmin={info['phi_vmin']:.2f}, vmax={info['phi_vmax']:.2f}.",
            "",
            "Paper parameters recorded here for figure 2 (not used to draw routes)",
            f"  rho={RHO}, d_inv={info['d_inv']:.16g}, U_I={info['U_I']:.10g}, "
            f"U_II={info['U_II']:.10g}.",
            "  rho=1 is RHO_REF in scripts/plot_pizarra_abcd.py.",
            "  d_inv is D_INV_VALS[len//2] from experimento/barrido_propuesta1.py",
            "  (log10(1/d) = -1.4 in tabla_comparacion_pff_pru_fixed.csv).",
            "  U_I = 1/d_inv, U_II = 2/d_inv, as in that sweep.",
            "",
        ]
    )
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "model_overview_info.txt").write_text("\n".join(lines), encoding="utf-8")


def _fraction_and_diagnostics(counts: np.ndarray, steps: int) -> np.ndarray:
    if steps <= 0:
        return np.zeros_like(counts, dtype=np.float64)
    return counts.astype(np.float64) / float(steps)


def run_pff_once(ff: Floor_field, posiciones, u_i: float, u_ii: float) -> dict:
    agentes = [Agente(x, y, ff, U_I=u_i, U_II=u_ii) for x, y in posiciones]
    counts = np.zeros((ff.height, ff.width), dtype=np.int32)
    jumps: list[tuple[tuple[int, int], tuple[int, int]]] = []
    jump_total = 0
    overlap_steps = 0
    steps = 0
    while any(agente.activo for agente in agentes) and steps < MAX_PASOS:
        occupied = {(agente.x, agente.y) for agente in agentes if agente.activo}
        for x, y in occupied:
            counts[y, x] += 1
        before = [(agente, agente.x, agente.y) for agente in agentes if agente.activo]
        mover_agentes(agentes)
        seen: dict[tuple[int, int], int] = {}
        for agente, ox, oy in before:
            nxt = (agente.x, agente.y)
            if max(abs(nxt[0] - ox), abs(nxt[1] - oy)) > 1:
                jump_total += 1
                if len(jumps) < 6:
                    jumps.append(((ox, oy), nxt))
            if agente.activo:
                seen[nxt] = seen.get(nxt, 0) + 1
        if any(value > 1 for value in seen.values()):
            overlap_steps += 1
        steps += 1
    censored = any(agente.activo for agente in agentes)
    return {
        "fraction": _fraction_and_diagnostics(counts, steps),
        "T": steps,
        "jumps": jumps,
        "jump_total": jump_total,
        "overlap_steps": overlap_steps,
        "censored": censored,
    }


def run_pru_once(ff: Floor_field, selector: PathSelector, posiciones, u_i: float, u_ii: float) -> dict:
    AgentExtendido.instances = []
    AgentExtendido.history = []
    AgentExtendido.ruta_log = []
    selector.anxiety_decisions.clear()
    selector.recalculo_log.clear()
    selector.limpiar_cache()
    agentes = [
        AgentExtendido(
            agent_type="rapido",
            floor_field=ff,
            path_selector=selector,
            x=x,
            y=y,
            U_I=u_i,
            U_II=u_ii,
        )
        for x, y in posiciones
    ]
    counts = np.zeros((ff.height, ff.width), dtype=np.int32)
    jumps: list[tuple[tuple[int, int], tuple[int, int]]] = []
    jump_total = 0
    overlap_steps = 0
    steps = 0
    while any(agente.activo for agente in agentes) and steps < MAX_PASOS:
        occupied = {
            (agente.pos_x, agente.pos_y)
            for agente in agentes
            if agente.activo and agente.pos_x is not None
        }
        for x, y in occupied:
            counts[y, x] += 1
        for agente in agentes:
            if agente.activo:
                agente._current_simulation_step = steps
        before = [
            (agente, agente.pos_x, agente.pos_y)
            for agente in agentes
            if agente.activo
        ]
        mover_agentes_con_conflictos(agentes)
        AgentExtendido.ruta_log.clear()
        seen: dict[tuple[int, int], int] = {}
        for agente, ox, oy in before:
            nxt = (agente.pos_x, agente.pos_y)
            if max(abs(nxt[0] - ox), abs(nxt[1] - oy)) > 1:
                jump_total += 1
                if len(jumps) < 6:
                    jumps.append(((ox, oy), nxt))
            if agente.activo:
                seen[nxt] = seen.get(nxt, 0) + 1
        if any(value > 1 for value in seen.values()):
            overlap_steps += 1
        steps += 1
    censored = any(agente.activo for agente in agentes)
    return {
        "fraction": _fraction_and_diagnostics(counts, steps),
        "T": steps,
        "jumps": jumps,
        "jump_total": jump_total,
        "overlap_steps": overlap_steps,
        "censored": censored,
    }


def ensemble_occupation(scenario, motor: str, d_inv: float, u_i: float, u_ii: float) -> dict:
    ff = Floor_field(scenario.width, scenario.height, scenario.puertas, scenario.obstaculos)
    selector = None
    if motor == "pru":
        selector = PathSelector(ff, umbral_recalculo=0.6, anxiety_thresholds=(30, 70))
    mean = np.zeros((ff.height, ff.width), dtype=np.float64)
    times: list[int] = []
    jump_examples: list[tuple] = []
    jump_total = 0
    overlap_steps = 0
    censored = 0
    n_agents = None
    position_fn = posiciones_pru if motor == "pru" else posiciones_pff

    for run_index in range(N_RUNS):
        semilla = _seed(run_index, d_inv)
        rng = random.Random(semilla)
        random.seed(semilla)
        np.random.seed(semilla)
        posiciones = position_fn(
            scenario.width,
            scenario.height,
            list(scenario.obstaculos),
            RHO,
            rng,
        )
        n_agents = len(posiciones)
        if motor == "pru":
            result = run_pru_once(ff, selector, posiciones, u_i, u_ii)
        else:
            result = run_pff_once(ff, posiciones, u_i, u_ii)
        jump_total += int(result["jump_total"])
        mean += result["fraction"]
        times.append(int(result["T"]))
        overlap_steps += int(result["overlap_steps"])
        censored += int(bool(result["censored"]))
        if len(jump_examples) < 6:
            jump_examples.extend(result["jumps"][: 6 - len(jump_examples)])
        if (run_index + 1) % 20 == 0:
            print(f"  {scenario.__name__} {motor}: {run_index + 1}/{N_RUNS}", flush=True)

    mean /= float(N_RUNS)
    t_arr = np.asarray(times, dtype=float)
    return {
        "mean": mean,
        "T": t_arr,
        "T_mean": float(np.mean(t_arr)),
        "T_sd": float(_desv_estandar_poblacional([int(t) for t in times])),
        "jump_total": jump_total,
        "jump_examples": jump_examples,
        "overlap_steps": overlap_steps,
        "censored": censored,
        "n_agents": n_agents,
        "ff": ff,
    }


def draw_occupation(ax: plt.Axes, mean: np.ndarray, ff: Floor_field, panel: str, star_size: float):
    walls = wall_cells(ff.width, ff.height, list(ff.puertas))
    seats = interior_seats(ff.obstaculos, ff.width, ff.height)
    masked = np.ma.array(mean, mask=np.zeros(mean.shape, dtype=bool))
    for x, y in walls:
        masked[y, x] = np.ma.masked
    for x, y in seats:
        masked[y, x] = np.ma.masked
    # Door cells have occupation 0 in this counting (agents are removed on
    # arrival). Mask them so the star sits on the wall instead of a black tile.
    for x, y in ff.puertas:
        if 0 <= y < masked.shape[0] and 0 <= x < masked.shape[1]:
            masked[y, x] = np.ma.masked
    cmap = plt.cm.inferno.copy()
    cmap.set_bad("white")
    image = ax.imshow(
        masked,
        origin="lower",
        cmap=cmap,
        vmin=0.0,
        vmax=1.0,
        interpolation="nearest",
        extent=(-0.5, ff.width - 0.5, -0.5, ff.height - 0.5),
        zorder=1,
    )
    draw_cells(ax, seats, "#d9d9d9", "black", 0.45, 2)
    draw_doors(ax, ff.puertas, star_size)
    style_map_axes(ax, ff.width, ff.height, panel)
    return image


def annotate_evacuation_time(ax: plt.Axes, t_mean: float, t_sd: float) -> None:
    # Offset in points, so a tall cabin does not push this line into the legend.
    ax.annotate(
        rf"$\langle T \rangle$ = {t_mean:.2f} $\pm$ {t_sd:.2f} steps",
        xy=(0.5, 0.0),
        xycoords="axes fraction",
        xytext=(0, -46),
        textcoords="offset points",
        ha="center",
        va="top",
        fontsize=8,
        annotation_clip=False,
    )


def make_occupation_figure(stem: str, ff: Floor_field, pff: dict, pru: dict, figsize: tuple[float, float], star_size: float) -> None:
    fig, axes = plt.subplots(1, 2, figsize=figsize)
    # Leave a clear strip on the right. The colorbar is placed after aspect='equal'
    # has shrunk the panels, so it sits next to panel (b) instead of on top of it.
    fig.subplots_adjust(left=0.08, right=0.82, bottom=0.14, top=0.97, wspace=0.32)
    image = draw_occupation(axes[0], pff["mean"], ff, "(a)", star_size)
    draw_occupation(axes[1], pru["mean"], ff, "(b)", star_size)
    annotate_evacuation_time(axes[0], pff["T_mean"], pff["T_sd"])
    annotate_evacuation_time(axes[1], pru["T_mean"], pru["T_sd"])
    fig.canvas.draw()
    panel_box = axes[1].get_position()
    colorbar_ax = fig.add_axes([panel_box.x1 + 0.045, panel_box.y0, 0.022, panel_box.height])
    colorbar = fig.colorbar(image, cax=colorbar_ax)
    colorbar.set_label("Mean occupation probability")
    handles = [
        Line2D(
            [0],
            [0],
            marker="*",
            color="none",
            markerfacecolor="red",
            markeredgecolor="black",
            markersize=12,
            label="Door",
        ),
        Patch(facecolor="#d9d9d9", edgecolor="black", label="Seat"),
    ]
    fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.42, 0.005), ncol=2, frameon=False)
    save_figure(fig, stem)


def save_occupation_npz(stem: str, pff: dict, pru: dict, d_inv: float, u_i: float, u_ii: float) -> None:
    np.savez(
        OUT_DIR / f"{stem}.npz",
        mean_pff=pff["mean"],
        mean_pru=pru["mean"],
        T_pff=pff["T"],
        T_pru=pru["T"],
        rho=np.array(RHO),
        d_inv=np.array(d_inv),
        U_I=np.array(u_i),
        U_II=np.array(u_ii),
        n_runs=np.array(N_RUNS),
        n_agents=np.array(pff["n_agents"]),
    )


def main() -> None:
    apply_style()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    d_inv, u_i, u_ii = _paper_thresholds()
    print(
        f"Parameters: rho={RHO}, d_inv={d_inv:.6g}, U_I={u_i:.6g}, U_II={u_ii:.6g}, N_runs={N_RUNS}",
        flush=True,
    )
    info = make_model_overview(d_inv, u_i, u_ii)
    print(
        f"Figure 1 routes: start={info['start']} goal={info['goal']} "
        f"n={info['n_paths']} unique={info['n_unique']} costs={info['costs']}",
        flush=True,
    )

    print("Occupation: classroom", flush=True)
    class_pff = ensemble_occupation(classroom_scenario, "pff", d_inv, u_i, u_ii)
    class_pru = ensemble_occupation(classroom_scenario, "pru", d_inv, u_i, u_ii)
    make_occupation_figure(
        "occupation_classroom",
        class_pff["ff"],
        class_pff,
        class_pru,
        figsize=(8.4, 4.5),
        star_size=140,
    )
    save_occupation_npz("occupation_classroom", class_pff, class_pru, d_inv, u_i, u_ii)

    print("Occupation: aircraft", flush=True)
    air_pff = ensemble_occupation(aircraft_scenario, "pff", d_inv, u_i, u_ii)
    air_pru = ensemble_occupation(aircraft_scenario, "pru", d_inv, u_i, u_ii)
    make_occupation_figure(
        "occupation_aircraft",
        air_pff["ff"],
        air_pff,
        air_pru,
        figsize=(7.4, 9.6),
        star_size=55,
    )
    save_occupation_npz("occupation_aircraft", air_pff, air_pru, d_inv, u_i, u_ii)

    print("--- summary ---", flush=True)
    for name, pff, pru in (
        ("classroom", class_pff, class_pru),
        ("aircraft", air_pff, air_pru),
    ):
        print(
            f"{name}: agents={pff['n_agents']} "
            f"PFF <T>={pff['T_mean']:.4f} ± {pff['T_sd']:.4f} "
            f"jumps~{pff['jump_total']} overlap_steps={pff['overlap_steps']} censored={pff['censored']} "
            f"examples={pff['jump_examples']}",
            flush=True,
        )
        print(
            f"{name}: PRU <T>={pru['T_mean']:.4f} ± {pru['T_sd']:.4f} "
            f"jumps={pru['jump_total']} overlap_steps={pru['overlap_steps']} censored={pru['censored']} "
            f"examples={pru['jump_examples']}",
            flush=True,
        )


if __name__ == "__main__":
    main()
