"""Model overview, version 2: classroom and aircraft, one agent and its routes.

Reads the real PathSelector (pru_fixed=True). Does not modify any simulation
module and does not overwrite figures/out/model_overview.pdf or .png.

Outputs:
  figures/out/model_overview_v2.pdf
  figures/out/model_overview_v2.png
"""

from __future__ import annotations

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
from matplotlib.colors import Normalize
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

from escenarios import avion_dos_puertas as aircraft_scenario
from escenarios import sala_de_clases as classroom_scenario
from simulacion.agent_extendido import AgentExtendido
from simulacion.grilla.floor_field import Floor_field
from simulacion.nodos.path_selector import PathSelector

OUT_DIR = ROOT / "figures" / "out"

CLASSROOM_START = (10, 2)
# Seat-row cells flanking the mid-cabin gap (seats at y=13 and y=17).
# The search below picks among these; (7, 16) wins on route distinctness.
AIRCRAFT_MID_Y = 15

SEAT_FACE = "#e4e4e4"
SEAT_EDGE = "#b0b0b0"
ROUTE_BLUE = "#1f77b4"
ROUTE_ORANGE = "#ff7f0e"
AGENT_GREEN = "#2ca02c"
EDGE_COLOR = "#d0d0d0"


def apply_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 11,
            "axes.labelsize": 12,
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
            "legend.fontsize": 10,
            "axes.linewidth": 0.8,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "savefig.dpi": 200,
        }
    )


def wall_cells(width: int, height: int, puertas) -> list[tuple[int, int]]:
    doors = set(map(tuple, puertas))
    cells = []
    for x in range(width):
        for y in range(height):
            if x == 0 or x == width - 1 or y == 0 or y == height - 1:
                if (x, y) not in doors:
                    cells.append((x, y))
    return cells


def interior_seats(obstaculos, width: int, height: int) -> list[tuple[int, int]]:
    return [
        (int(x), int(y))
        for x, y in obstaculos
        if 0 < int(x) < width - 1 and 0 < int(y) < height - 1
    ]


def draw_cells(ax, cells, face, edge, lw, zorder) -> None:
    from matplotlib.patches import Rectangle

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


def undirected_segments(graph) -> list[list[tuple[float, float]]]:
    seen: set[tuple] = set()
    segments = []
    for u, v in graph.edges():
        key = (u, v) if u <= v else (v, u)
        if key in seen:
            continue
        seen.add(key)
        segments.append([(float(u[0]), float(u[1])), (float(v[0]), float(v[1]))])
    return segments


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
    """Separate overlapping routes by ±0.08 cells. Route 1 stays put."""
    cell_sets = [set(map(tuple, path)) for path in paths]
    offsets = [0.0] * len(paths)
    for i in range(1, len(paths)):
        used = {0.0}
        overlaps = False
        for j in range(i):
            if cell_sets[i] & cell_sets[j]:
                used.add(offsets[j])
                overlaps = True
        if not overlaps:
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


def nearest_door(origin: tuple[int, int], puertas) -> tuple[int, int]:
    """Same rule as AgentExtendido._encontrar_puerta_mas_cercana (Manhattan)."""
    return min(
        (tuple(door) for door in puertas),
        key=lambda door: abs(origin[0] - door[0]) + abs(origin[1] - door[1]),
    )


def build_field(scenario) -> tuple[Floor_field, PathSelector]:
    field = Floor_field(
        scenario.width,
        scenario.height,
        list(scenario.puertas),
        list(scenario.obstaculos),
    )
    selector = PathSelector(field, pru_fixed=True)
    return field, selector


def agent_routes(
    field: Floor_field,
    selector: PathSelector,
    start: tuple[int, int],
) -> tuple[tuple[int, int], list[list[tuple[int, int]]], list[float]]:
    """Five unlock-order routes from the real PathSelector, plus base costs."""
    AgentExtendido.instances = []
    AgentExtendido.history = []
    AgentExtendido.ruta_log = []
    agent = AgentExtendido(
        agent_type="rapido",
        floor_field=field,
        path_selector=selector,
        x=start[0],
        y=start[1],
        U_I=10,
        U_II=20,
        pru_fixed=True,
    )
    goal = tuple(agent._encontrar_puerta_mas_cercana())
    paths = selector.find_progressive_paths(start, goal, num_paths=agent.k_paths_max)
    costs = [float(selector._calculate_base_path_cost(path)) for path in paths]
    return goal, paths, costs


def pairwise_distinctness(paths: list[list[tuple[int, int]]]) -> float:
    sets = [set(map(tuple, path)) for path in paths]
    total = 0.0
    count = 0
    for i in range(len(sets)):
        for j in range(i + 1, len(sets)):
            union = sets[i] | sets[j]
            if not union:
                continue
            total += 1.0 - len(sets[i] & sets[j]) / len(union)
            count += 1
    return total / count if count else 0.0


def choose_aircraft_start(
    field: Floor_field,
    selector: PathSelector,
) -> tuple[tuple[int, int], dict]:
    """Seat-row cell near mid-cabin whose real routes are most distinct.

    find_progressive_paths takes one goal, so every route of one call ends at
    the same door. The search still checks the set of terminal doors. Among
    walkable cells next to a seat and within two rows of the cabin midpoint,
    it keeps the set with the largest mean pairwise Jaccard distance.
    """
    seats = set(map(tuple, field.obstaculos))
    best: tuple | None = None
    notes = []
    for node in selector.grafo.nodes:
        x, y = int(node[0]), int(node[1])
        if abs(y - AIRCRAFT_MID_Y) > 2:
            continue
        beside_seat = any(
            (x + dx, y + dy) in seats
            for dx in (-1, 0, 1)
            for dy in (-1, 0, 1)
            if dx or dy
        )
        if not beside_seat:
            continue
        start = (x, y)
        goal, paths, costs = agent_routes(field, selector, start)
        ends = sorted({tuple(path[-1]) for path in paths})
        score = pairwise_distinctness(paths)
        record = {
            "start": start,
            "goal": goal,
            "n_paths": len(paths),
            "ends": ends,
            "score": score,
            "costs": costs,
        }
        notes.append(record)
        rank = (score, len(paths), -abs(y - AIRCRAFT_MID_Y), x)
        if best is None or rank > best[0]:
            best = (rank, record, paths)
    if best is None:
        raise RuntimeError("No seat-row cell near the middle of the cabin")
    both = [item for item in notes if len(item["ends"]) > 1]
    return best[1]["start"], {
        "chosen": best[1],
        "n_candidates": len(notes),
        "n_reaching_both_doors": len(both),
        "max_paths": max(item["n_paths"] for item in notes),
    }


def ticks(n: int) -> list[int]:
    step = 2 if n <= 16 else 5
    return list(range(0, n, step))


def draw_panel(
    ax: plt.Axes,
    field: Floor_field,
    selector: PathSelector,
    start: tuple[int, int],
    paths: list[list[tuple[int, int]]],
    norm: Normalize,
    panel: str,
    node_size: float,
    star_size: float,
    agent_size: float,
    route_scale: float,
) -> None:
    seats = interior_seats(field.obstaculos, field.width, field.height)
    walls = wall_cells(field.width, field.height, list(field.puertas))
    draw_cells(ax, walls, SEAT_FACE, SEAT_EDGE, 0.3, 1)
    draw_cells(ax, seats, SEAT_FACE, SEAT_EDGE, 0.35, 1)

    segments = undirected_segments(selector.grafo)
    if segments:
        ax.add_collection(
            LineCollection(
                segments,
                colors=EDGE_COLOR,
                linewidths=0.4 * route_scale,
                alpha=0.95,
                zorder=2,
            )
        )

    xs, ys, phi = [], [], []
    for x, y in selector.grafo.nodes:
        xs.append(x)
        ys.append(y)
        phi.append(float(field.valores[y, x]))
    nodes = ax.scatter(
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

    styles = [
        dict(color="black", lw=2.4 * route_scale, ls="-", zorder=5),
        dict(color=ROUTE_BLUE, lw=1.7 * route_scale, ls=(0, (4, 1.6)), zorder=4),
        dict(color=ROUTE_BLUE, lw=1.7 * route_scale, ls=(0, (4, 1.6)), zorder=4),
        dict(color=ROUTE_ORANGE, lw=1.8 * route_scale, ls=(0, (1, 1.1)), zorder=4),
        dict(color=ROUTE_ORANGE, lw=1.8 * route_scale, ls=(0, (1, 1.1)), zorder=4),
    ]
    offsets = route_offsets(paths)
    for index in range(len(paths) - 1, -1, -1):
        shifted = offset_polyline(paths[index], offsets[index])
        ax.plot(
            shifted[:, 0],
            shifted[:, 1],
            solid_capstyle="round",
            **styles[index],
        )

    ax.scatter(
        [door[0] for door in field.puertas],
        [door[1] for door in field.puertas],
        marker="*",
        s=star_size,
        c="red",
        edgecolors="black",
        linewidths=0.45,
        zorder=6,
    )
    ax.scatter(
        [start[0]],
        [start[1]],
        s=agent_size,
        c=AGENT_GREEN,
        marker="o",
        edgecolors="black",
        linewidths=0.6,
        zorder=7,
    )

    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(-0.7, field.width - 0.3)
    ax.set_ylim(-0.7, field.height - 0.3)
    ax.set_xlabel(r"$x$ (cells)")
    ax.set_ylabel(r"$y$ (cells)")
    ax.set_xticks(ticks(field.width))
    ax.set_yticks(ticks(field.height))
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
        bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.92),
    )
    n_nodes = selector.grafo.number_of_nodes()
    n_edges = selector.grafo.number_of_edges()
    ax.text(
        0.5,
        1.02,
        f"Nodes: {n_nodes}, edges: {n_edges}",
        transform=ax.transAxes,
        ha="center",
        va="bottom",
        fontsize=8,
        zorder=8,
        clip_on=False,
        bbox=dict(boxstyle="round,pad=0.18", fc="white", ec="0.45", alpha=0.95),
    )
    return nodes


def phi_values(field: Floor_field, selector: PathSelector) -> list[float]:
    return [float(field.valores[y, x]) for x, y in selector.grafo.nodes]


def main() -> None:
    apply_style()
    class_field, class_selector = build_field(classroom_scenario)
    air_field, air_selector = build_field(aircraft_scenario)

    class_goal, class_paths, class_costs = agent_routes(
        class_field, class_selector, CLASSROOM_START
    )
    air_start, search = choose_aircraft_start(air_field, air_selector)
    air_goal, air_paths, air_costs = agent_routes(air_field, air_selector, air_start)

    values = phi_values(class_field, class_selector) + phi_values(air_field, air_selector)
    norm = Normalize(vmin=min(values), vmax=max(values))

    # Classroom is 12 x 10; aircraft is 9 x 30. Equal aspect and equal panel
    # height require width_ratios = (12/10) : (9/30) = 4 : 1.
    fig = plt.figure(figsize=(11.4, 7.7))
    grid = fig.add_gridspec(
        1,
        2,
        width_ratios=(4.0, 1.0),
        wspace=0.32,
        left=0.055,
        right=0.90,
        bottom=0.14,
        top=0.90,
    )
    ax_a = fig.add_subplot(grid[0, 0])
    ax_b = fig.add_subplot(grid[0, 1])

    mappable = draw_panel(
        ax_a,
        class_field,
        class_selector,
        CLASSROOM_START,
        class_paths,
        norm,
        "(a)",
        node_size=16,
        star_size=150,
        agent_size=78,
        route_scale=1.0,
    )
    draw_panel(
        ax_b,
        air_field,
        air_selector,
        air_start,
        air_paths,
        norm,
        "(b)",
        node_size=7,
        star_size=48,
        agent_size=28,
        route_scale=0.72,
    )

    fig.canvas.draw()
    box = ax_b.get_position()
    cax = fig.add_axes([box.x1 + 0.018, box.y0, 0.016, box.y1 - box.y0])
    colorbar = fig.colorbar(mappable, cax=cax)
    colorbar.set_label(r"Distance to nearest door, $\phi$")

    handles = [
        Line2D([0], [0], color="black", lw=2.4, label="Route 1"),
        Line2D(
            [0],
            [0],
            color=ROUTE_BLUE,
            lw=1.7,
            ls=(0, (4, 1.6)),
            label="Routes 2–3",
        ),
        Line2D(
            [0],
            [0],
            color=ROUTE_ORANGE,
            lw=1.8,
            ls=(0, (1, 1.1)),
            label="Routes 4–5",
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
        Patch(facecolor=SEAT_FACE, edgecolor=SEAT_EDGE, label="Seat/desk"),
    ]
    fig.legend(
        handles=handles,
        loc="lower center",
        ncol=6,
        frameon=False,
        bbox_to_anchor=(0.46, 0.012),
        columnspacing=1.1,
        handletextpad=0.45,
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stem = OUT_DIR / "model_overview_v2"
    fig.savefig(stem.with_suffix(".pdf"), format="pdf", bbox_inches="tight", pad_inches=0.05)
    fig.savefig(stem.with_suffix(".png"), format="png", dpi=200, bbox_inches="tight", pad_inches=0.05)
    plt.close(fig)

    def report(name: str, start, paths, costs) -> None:
        print(f"{name} agent {start}")
        for index, (path, cost) in enumerate(zip(paths, costs), start=1):
            print(f"  route {index}: cost {cost:.2f} door {tuple(path[-1])}")
        print(f"  n_routes {len(paths)}")

    report("classroom", CLASSROOM_START, class_paths, class_costs)
    print("classroom nearest door", class_goal)
    report("aircraft", air_start, air_paths, air_costs)
    print("aircraft nearest door", air_goal)
    print("aircraft search", search)
    print("wrote", stem.with_suffix(".pdf"))
    print("wrote", stem.with_suffix(".png"))


if __name__ == "__main__":
    main()
