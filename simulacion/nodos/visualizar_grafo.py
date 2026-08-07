# visualizar_grafo.py 
import sys
import os
# Agregar directorio raíz al path para importar módulos
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, root_dir)

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import importlib
from simulacion.grilla.floor_field import Floor_field
from simulacion.nodos.path_selector import PathSelector

def _cargar_escenario(nombre_escenario):
    """
    Carga configuración de escenario desde /escenarios.
    """
    modulo = importlib.import_module(f"escenarios.{nombre_escenario}")
    width = int(getattr(modulo, "width"))
    height = int(getattr(modulo, "height"))
    puertas = list(getattr(modulo, "puertas"))
    obstaculos = list(getattr(modulo, "obstaculos", []))
    return width, height, puertas, obstaculos


def visualizar_grafo_nodos(nombre_escenario, mostrar_pesos=False):
    """
    Visualiza el grafo de nodos construido sobre el floor field.
    """
    width, height, puertas, obstaculos = _cargar_escenario(nombre_escenario)

    # Crear floor field
    ff = Floor_field(width, height, puertas, obstaculos)
    
    # Crear path selector (construye grafo)
    ps = PathSelector(ff)
    
    # Configurar visualización
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7))
    
    # === Subplot 1: Floor Field original ===
    ax1.set_title('Floor Field Original', fontsize=14, fontweight='bold')
    ax1.set_xlabel('X')
    ax1.set_ylabel('Y')
    
    # Mostrar floor field como mapa de calor
    valores_plot = ff.valores.copy()
    valores_plot[valores_plot >= 500] = np.nan  # Paredes = NaN
    
    im = ax1.imshow(valores_plot, cmap='viridis', origin='lower')
    plt.colorbar(im, ax=ax1, label='Distancia a Puerta')
    
    # Ajustar límites para que la grilla y los marcadores coincidan con las celdas reales.
    ax1.set_xlim(-0.5, width - 0.5)
    ax1.set_ylim(-0.5, height - 0.5)
    ax1.set_aspect('equal')
    
    # Marcar puertas en el floor field
    for x, y in puertas:
        ax1.scatter(x, y, marker='*', color='red', edgecolor='black', s=250, zorder=10)
    
    # Marcar obstáculos (bloques negros, no agentes)
    for x, y in obstaculos:
        rect = plt.Rectangle((x - 0.5, y - 0.5), 1, 1, facecolor='black', edgecolor='none', zorder=9)
        ax1.add_patch(rect)
    
    ax1.grid(True, alpha=0.3)
    # No mostrar leyenda en el primer subplot para evitar duplicados y solapamientos.
    
    # Grafo de Nodos
    ax2.set_title('Grafo de Nodos Construido', fontsize=14, fontweight='bold')
    ax2.set_xlabel('X')
    ax2.set_ylabel('Y')
    
    # Ajustar límites para que el grafo respete las coordenadas reales del escenario.
    ax2.set_xlim(-0.5, width - 0.5)
    ax2.set_ylim(-0.5, height - 0.5)
    ax2.set_aspect('equal')
    
    # Posiciones de nodos = coordenadas (x, y)
    pos = {nodo: nodo for nodo in ps.grafo.nodes()}
    
    # Colores de nodos según floor value
    node_colors = []
    for nodo in ps.grafo.nodes():
        floor_val = ps.grafo.nodes[nodo].get('floor_value', 0)
        if floor_val == 0:
            node_colors.append('red')  # Puertas
        elif floor_val < 10:
            node_colors.append('yellow')
        else:
            node_colors.append('lightblue')
    
    # Dibujar grafo
    nx.draw_networkx_edges(ps.grafo, pos, ax=ax2,
                          edge_color='gray', width=0.5, alpha=0.4)
    nx.draw_networkx_nodes(ps.grafo, pos, ax=ax2, 
                          node_color=node_colors, 
                          node_size=30, alpha=0.8)
    
    # Marcar obstáculos explícitamente en el grafo para que se diferencien de los nodos.
    for x, y in obstaculos:
        rect = plt.Rectangle((x - 0.5, y - 0.5), 1, 1, facecolor='black', edgecolor='none', zorder=5)
        ax2.add_patch(rect)
    
    # Marcar puertas al final del proceso para que queden siempre visibles.
    for x, y in puertas:
        ax2.scatter(x, y, marker='*', color='red', edgecolor='black', linewidth=1.0, s=300, zorder=15)
    
    # Ajustar espacio para leyenda e información fuera del área de dibujo.
    fig.subplots_adjust(right=0.78, wspace=0.25)

    # Leyenda fuera del área del grafo y sólo una vez.
    from matplotlib.patches import Patch
    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], marker='*', color='red', markeredgecolor='black', markersize=12,
               linestyle='None', label='Puerta (floor_value=0)'),
        Patch(facecolor='yellow', edgecolor='black', label='Cerca de puertas'),
        Patch(facecolor='lightblue', edgecolor='black', label='Nodo del grafo'),
        Patch(facecolor='black', edgecolor='black', label='Obstáculo (bloque negro, no agente)')
    ]
    fig.legend(handles=legend_elements, loc='upper left', bbox_to_anchor=(0.82, 0.95),
               frameon=True, facecolor='white', framealpha=1.0, edgecolor='black')

    # Información del grafo a la derecha del área de dibujo.
    info_text = f"Nodos: {ps.grafo.number_of_nodes()}\nAristas: {ps.grafo.number_of_edges()}"
    fig.text(0.82, 0.45, info_text,
             verticalalignment='top', bbox=dict(boxstyle='round', facecolor='white', alpha=0.9, edgecolor='black'),
             fontsize=10)

    ax2.grid(True, alpha=0.3)

    fig.tight_layout(rect=[0, 0, 0.78, 1])
    output_dir = os.path.dirname(__file__)
    output_name = f"grafo_{nombre_escenario}.png"
    output_path = os.path.join(output_dir, output_name)
    plt.savefig(output_path, dpi=150, bbox_inches='tight', pad_inches=0.1)
    print(f"Visualización guardada: {output_path}")
    plt.show()

def visualizar_ruta_ejemplo(nombre_escenario):
    """
    Muestra una ruta calculada con A* sobre el grafo.
    """
    width, height, puertas, obstaculos = _cargar_escenario(nombre_escenario)

    # Setup
    ff = Floor_field(width, height, puertas, obstaculos)
    ps = PathSelector(ff)
    
    # Elegir origen y destino
    origen = (8, 8)  # Centro de la sala
    destino = puertas[0]
    
    # Calcular ruta con A*
    ruta = ps.encontrar_ruta_a_star(origen, destino)
    
    if ruta is None:
        print("No se encontró ruta")
        return
    
    # Visualizar
    fig, ax = plt.subplots(figsize=(10, 8))
    ax.set_title(f'Ruta calculada con A*: {origen} → {destino}', 
                fontsize=14, fontweight='bold')
    
    # Floor field de fondo
    valores_plot = ff.valores.copy()
    valores_plot[valores_plot >= 500] = np.nan
    ax.imshow(valores_plot, cmap='gray', origin='lower', alpha=0.3)
    
    # Grafo (solo nodos y aristas relevantes)
    pos = {nodo: nodo for nodo in ps.grafo.nodes()}
    nx.draw_networkx_nodes(ps.grafo, pos, ax=ax, 
                          node_color='lightgray', 
                          node_size=20, alpha=0.5)
    
    # Ruta calculada (RESALTADA)
    ruta_x = [nodo[0] for nodo in ruta]
    ruta_y = [nodo[1] for nodo in ruta]
    ax.plot(ruta_x, ruta_y, 'b-', linewidth=3, alpha=0.7, label='Ruta A*')
    ax.plot(ruta_x, ruta_y, 'bo', markersize=8, alpha=0.7)
    
    # Origen y destino
    ax.plot(origen[0], origen[1], 'go', markersize=15, label='Origen')
    ax.plot(destino[0], destino[1], 'r*', markersize=20, label='Destino (Puerta)')
    
    # Info
    info = f"Longitud ruta: {len(ruta)} nodos\n"
    info += f"Costo total: {len(ruta)-1} movimientos"
    ax.text(0.02, 0.98, info, transform=ax.transAxes,
           verticalalignment='top', bbox=dict(boxstyle='round', 
           facecolor='lightblue', alpha=0.8), fontsize=11)
    
    ax.legend(loc='upper right')
    ax.grid(True, alpha=0.3)
    ax.set_xlabel('X')
    ax.set_ylabel('Y')
    
    plt.tight_layout()
    output_dir = os.path.dirname(__file__)
    output_name = f"ruta_a_star_{nombre_escenario}.png"
    output_path = os.path.join(output_dir, output_name)
    plt.savefig(output_path, dpi=150)
    print(f"Ruta visualizada: {output_path}")
    print(f"Nodos en ruta: {len(ruta)}")
    plt.show()

if __name__ == "__main__":
    print("VISUALIZACIÓN: Sistema de Nodos sobre Grilla")
    print("\nEscenarios disponibles:")
    print("1) Sala de clases")
    print("2) Avión")
    print("3) Escenario base")
    # Flujos opuestos desactivado temporalmente para evitar usar esa lógica.
    # print("4) Flujos opuestos")
    try:
        opcion = input("\nElige un escenario (1-4): ").strip()
    except (EOFError, KeyboardInterrupt):
        opcion = "1"

    mapa = {
        "1": "sala_de_clases",
        "2": "avion",
        "3": "escenario_base",
        # Flujos opuestos desactivado temporalmente.
        # "4": "flujos_opuestos",
    }
    nombre_escenario = mapa.get(opcion or "1", "sala_de_clases")

    visualizar_grafo_nodos(nombre_escenario)
    visualizar_ruta_ejemplo(nombre_escenario)