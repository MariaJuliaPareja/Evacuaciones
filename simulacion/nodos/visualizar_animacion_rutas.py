"""
Visualizador interactivo de rutas con animación.
Muestra el proceso de cálculo y recálculo de rutas paso a paso.
"""

import sys
import os
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, root_dir)

import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.widgets import Button, Slider
import numpy as np
from simulacion.grilla.floor_field import Floor_field
from simulacion.nodos.path_selector import PathSelector
from simulacion.agent_extendido import AgentExtendido
import escenarios.sala_de_clases as esc
import random
from typing import List, Tuple, Dict, Optional

class VisualizadorAnimacionRutas:
    """
    Visualizador interactivo que muestra el cálculo y recálculo de rutas
    con controles para avanzar, retroceder y reproducir.
    """
    
    def __init__(self, num_agentes: int = 5, max_pasos: int = 50):
        """
        Inicializa el visualizador.
        
        Parámetros:
        num_agentes : int
            Número de agentes a simular
        max_pasos : int
            Número máximo de pasos de simulación
        """
        self.num_agentes = num_agentes
        self.max_pasos = max_pasos
        
        # Setup del escenario
        self.ff = Floor_field(esc.width, esc.height, esc.puertas, esc.obstaculos)
        self.ps = PathSelector(self.ff)
        
        # Crear agentes
        self.agentes = []
        posiciones_disponibles = [(x, y) for x in range(esc.width) 
                                 for y in range(esc.height)
                                 if (x, y) not in esc.obstaculos 
                                 and (x, y) not in esc.puertas]
        
        posiciones_iniciales = random.sample(posiciones_disponibles, 
                                           min(num_agentes, len(posiciones_disponibles)))
        
        for i, (x, y) in enumerate(posiciones_iniciales):
            agente = AgentExtendido(
                agent_type='rapido' if i % 2 == 0 else 'lento',
                floor_field=self.ff,
                path_selector=self.ps,
                x=x,
                y=y
            )
            agente.ansiedad = random.uniform(20, 90)  # Ansiedad aleatoria
            self.agentes.append(agente)
        
        # Historial de simulación
        self.historial = []
        self.paso_actual = 0
        self.playing = False
        
        # Ejecutar simulación
        self._simular()
    
    def _simular(self):
        """Ejecuta la simulación y guarda el historial."""
        print(f"Simulando {self.max_pasos} pasos con {self.num_agentes} agentes...")
        
        for paso in range(self.max_pasos):
            estado_paso = {
                'paso': paso,
                'agentes': [],
                'rutas_calculadas': [],
                'rutas_recalculadas': []
            }
            
            # Calcular posiciones actuales de agentes
            agent_positions = {}
            for agente in self.agentes:
                if agente.activo and agente.pos_x is not None and agente.pos_y is not None:
                    pos = (agente.pos_x, agente.pos_y)
                    agent_positions[pos] = agent_positions.get(pos, 0) + 1
            
            # Procesar cada agente
            for agente in self.agentes:
                if not agente.activo:
                    continue
                
                # Guardar estado del agente
                agente_estado = {
                    'id': agente.id,
                    'x': agente.pos_x,
                    'y': agente.pos_y,
                    'tipo': agente.tipo,
                    'ansiedad': agente.ansiedad,
                    'current_path': None,
                    'path_index': 0,
                    'recalculado': False
                }
                
                # Encontrar puerta más cercana
                goal = self._encontrar_puerta_mas_cercana(agente)
                
                # Elegir ruta (puede calcular o recalcular)
                ruta_anterior = getattr(agente, 'current_path', None)
                path_index_anterior = getattr(agente, 'path_index', 0)
                
                # Verificar si debe recalcular
                should_recalc = (
                    ruta_anterior is None or
                    self.ps.should_recalculate(
                        agent_pos=(agente.pos_x, agente.pos_y),
                        current_path=ruta_anterior,
                        path_index=path_index_anterior,
                        agent_positions=agent_positions,
                        steps_without_moving=getattr(agente, 'steps_without_moving', 0),
                        anxiety_level=agente.ansiedad
                    )
                )
                
                if should_recalc:
                    # Calcular nuevas rutas alternativas
                    k_paths = self.ps.find_k_paths(
                        start=(agente.pos_x, agente.pos_y),
                        goal=goal,
                        k=3
                    )
                    
                    # Verificar que se encontraron rutas
                    if k_paths and len(k_paths) > 0:
                        # Seleccionar ruta según ansiedad
                        selected_path = self.ps.select_path_by_anxiety(
                            k_paths, 
                            agente.ansiedad
                        )
                    else:
                        # No se encontraron rutas, usar movimiento greedy
                        selected_path = None
                    
                    if selected_path is not None:
                        agente.current_path = selected_path
                        agente.path_index = 0
                        agente.steps_without_moving = 0
                        
                        # Registrar recalculación
                        if ruta_anterior is not None:
                            estado_paso['rutas_recalculadas'].append({
                                'agente_id': agente.id,
                                'ruta_anterior': ruta_anterior,
                                'ruta_nueva': selected_path,
                                'ansiedad': agente.ansiedad
                            })
                        else:
                            estado_paso['rutas_calculadas'].append({
                                'agente_id': agente.id,
                                'ruta': selected_path,
                                'ansiedad': agente.ansiedad
                            })
                        
                        agente_estado['recalculado'] = True
                    else:
                        # No se pudo calcular ruta, mantener la anterior o limpiar
                        if ruta_anterior is None:
                            agente.current_path = None
                            agente.path_index = 0
                else:
                    # Continuar con ruta existente
                    agente.path_index += 1
                
                # Guardar ruta actual
                agente_estado['current_path'] = agente.current_path
                agente_estado['path_index'] = agente.path_index
                
                # Mover agente siguiendo la ruta
                if agente.current_path and agente.path_index < len(agente.current_path):
                    next_pos = agente.current_path[agente.path_index]
                    # Verificar si puede moverse (evitar conflictos)
                    if agent_positions.get(next_pos, 0) < 2:
                        agente.pos_x, agente.pos_y = next_pos
                        agente.steps_without_moving = 0
                    else:
                        agente.steps_without_moving = getattr(agente, 'steps_without_moving', 0) + 1
                else:
                    agente.steps_without_moving = getattr(agente, 'steps_without_moving', 0) + 1
                
                # Verificar si llegó a la puerta
                if goal and agente.pos_x == goal[0] and agente.pos_y == goal[1]:
                    agente.activo = False
                
                agente_estado['activo'] = agente.activo
                estado_paso['agentes'].append(agente_estado)
            
            self.historial.append(estado_paso)
            
            # Detener si todos evacuaron
            if all(not agente.activo for agente in self.agentes):
                print(f"Todos los agentes evacuaron en paso {paso}")
                break
        
        print(f"Simulación completada: {len(self.historial)} pasos")
    
    def _encontrar_puerta_mas_cercana(self, agente) -> Tuple[int, int]:
        """Encuentra la puerta más cercana al agente."""
        if not esc.puertas:
            return None
        
        min_dist = float('inf')
        puerta_cercana = esc.puertas[0]
        
        for puerta in esc.puertas:
            dist = abs(agente.pos_x - puerta[0]) + abs(agente.pos_y - puerta[1])
            if dist < min_dist:
                min_dist = dist
                puerta_cercana = puerta
        
        return puerta_cercana
    
    def _get_color_by_anxiety(self, anxiety: float) -> str:
        """Retorna color según nivel de ansiedad."""
        if anxiety < 30:
            return 'green'
        elif anxiety < 70:
            return 'yellow'
        else:
            return 'red'
    
    def crear_visualizacion_interactiva(self):
        """Crea la visualización interactiva con controles."""
        fig = plt.figure(figsize=(16, 10))
        gs = fig.add_gridspec(20, 1, hspace=0.3)
        
        # Área principal de visualización
        ax_main = fig.add_subplot(gs[:16, 0])
        
        # Área de controles
        ax_controls = fig.add_subplot(gs[16:, 0])
        ax_controls.axis('off')
        
        # Estado de la animación
        self.state = {
            'current_frame': 0,
            'playing': False,
            'interval': 500
        }
        
        # Crear controles
        ax_prev = plt.axes([0.1, 0.02, 0.08, 0.03])
        ax_play = plt.axes([0.2, 0.02, 0.08, 0.03])
        ax_next = plt.axes([0.3, 0.02, 0.08, 0.03])
        ax_slider = plt.axes([0.45, 0.02, 0.3, 0.03])
        
        btn_prev = Button(ax_prev, '< Anterior')
        btn_play = Button(ax_play, 'Play')
        btn_next = Button(ax_next, 'Siguiente >')
        slider = Slider(ax_slider, 'Paso', 0, len(self.historial) - 1, 
                        valinit=0, valstep=1)
        
        def actualizar_frame(frame_num):
            """Actualiza el frame mostrado."""
            ax_main.clear()
            
            if frame_num >= len(self.historial):
                return
            
            estado = self.historial[frame_num]
            
            # Configurar ejes
            ax_main.set_xlim(-0.5, esc.width - 0.5)
            ax_main.set_ylim(-0.5, esc.height - 0.5)
            ax_main.set_aspect('equal')
            ax_main.invert_yaxis()
            
            # Dibujar grilla
            for i in range(esc.width + 1):
                ax_main.axvline(i - 0.5, color='lightgray', linewidth=0.3, alpha=0.5)
            for j in range(esc.height + 1):
                ax_main.axhline(j - 0.5, color='lightgray', linewidth=0.3, alpha=0.5)
            
            # Floor field de fondo
            valores_plot = self.ff.valores.copy()
            valores_plot[valores_plot >= 500] = np.nan
            ax_main.imshow(valores_plot, cmap='gray_r', origin='lower', 
                          alpha=0.2, extent=[-0.5, esc.width-0.5, esc.height-0.5, -0.5])
            
            # Dibujar obstáculos
            for x, y in esc.obstaculos:
                rect = plt.Rectangle((x-0.5, y-0.5), 1, 1, 
                                    facecolor='black', alpha=0.7)
                ax_main.add_patch(rect)
            
            # Dibujar puertas
            for x, y in esc.puertas:
                rect = plt.Rectangle((x-0.5, y-0.5), 1, 1, 
                                    facecolor='green', alpha=0.8, edgecolor='orange', linewidth=2)
                ax_main.add_patch(rect)
                ax_main.text(x, y, 'P', ha='center', va='center', 
                           fontsize=12, weight='bold', color='white')
            
            # Dibujar rutas calculadas en este paso
            for ruta_info in estado['rutas_calculadas']:
                ruta = ruta_info['ruta']
                anxiety = ruta_info['ansiedad']
                color = self._get_color_by_anxiety(anxiety)
                
                if len(ruta) > 1:
                    xs, ys = zip(*ruta)
                    ax_main.plot(xs, ys, color=color, linewidth=2, 
                               linestyle='--', alpha=0.6, label='Ruta calculada')
            
            # Dibujar rutas recalculadas (más destacadas)
            for ruta_info in estado['rutas_recalculadas']:
                ruta_nueva = ruta_info['ruta_nueva']
                anxiety = ruta_info['ansiedad']
                color = self._get_color_by_anxiety(anxiety)
                
                if len(ruta_nueva) > 1:
                    xs, ys = zip(*ruta_nueva)
                    ax_main.plot(xs, ys, color=color, linewidth=3, 
                               linestyle='-', alpha=0.8, label='Ruta recalculada')
            
            # Dibujar agentes y sus rutas actuales
            for agente_estado in estado['agentes']:
                x, y = agente_estado['x'], agente_estado['y']
                anxiety = agente_estado['ansiedad']
                color = self._get_color_by_anxiety(anxiety)
                current_path = agente_estado['current_path']
                path_index = agente_estado['path_index']
                
                # Dibujar ruta completa si existe
                if current_path:
                    if len(current_path) > 1:
                        xs, ys = zip(*current_path)
                        ax_main.plot(xs, ys, color=color, linewidth=1.5, 
                                   linestyle=':', alpha=0.4)
                        
                        # Marcar posición actual en la ruta
                        if path_index < len(current_path):
                            ax_main.plot(current_path[path_index][0], 
                                       current_path[path_index][1], 
                                       'o', color=color, markersize=8, 
                                       markeredgecolor='black', markeredgewidth=1)
                
                # Dibujar agente
                circle = plt.Circle((x, y), 0.3, color=color, alpha=0.8, zorder=10)
                ax_main.add_patch(circle)
                
                # Etiqueta del agente
                ax_main.text(x, y, str(agente_estado['id']), 
                           ha='center', va='center', fontsize=8,
                           color='white', weight='bold', zorder=11)
                
                # Indicador de recalculación
                if agente_estado['recalculado']:
                    ax_main.plot(x, y + 0.5, 'r*', markersize=10, zorder=12)
            
            # Título con información
            total_activos = sum(1 for a in estado['agentes'] if a.get('activo', True))
            total_evacuados = len(estado['agentes']) - total_activos
            title = f'Paso {estado["paso"]}/{len(self.historial)-1} | Activos: {total_activos} | Evacuados: {total_evacuados}'
            title += f'\nRutas calculadas: {len(estado["rutas_calculadas"])} | Recalculadas: {len(estado["rutas_recalculadas"])}'
            ax_main.set_title(title, fontsize=12, weight='bold')
            
            ax_main.set_xlabel('X', fontsize=12)
            ax_main.set_ylabel('Y', fontsize=12)
            ax_main.grid(True, alpha=0.3)
            
            # Leyenda
            from matplotlib.patches import Patch
            legend_elements = [
                Patch(facecolor='green', label='Baja ansiedad (0-30)'),
                Patch(facecolor='yellow', label='Ansiedad óptima (30-70)'),
                Patch(facecolor='red', label='Alta ansiedad (70-100)'),
                plt.Line2D([0], [0], color='black', linestyle='--', label='Ruta calculada'),
                plt.Line2D([0], [0], color='black', linestyle='-', linewidth=2, label='Ruta recalculada'),
                plt.Line2D([0], [0], marker='*', color='red', linestyle='None', markersize=10, label='Recalculado')
            ]
            ax_main.legend(handles=legend_elements, loc='upper left', fontsize=8)
        
        def on_prev(event):
            """Frame anterior."""
            if self.state['current_frame'] > 0:
                self.state['current_frame'] -= 1
                slider.set_val(self.state['current_frame'])
                actualizar_frame(self.state['current_frame'])
                fig.canvas.draw_idle()
        
        def on_next(event):
            """Frame siguiente."""
            if self.state['current_frame'] < len(self.historial) - 1:
                self.state['current_frame'] += 1
                slider.set_val(self.state['current_frame'])
                actualizar_frame(self.state['current_frame'])
                fig.canvas.draw_idle()
        
        def on_play(event):
            """Toggle play/pause."""
            self.state['playing'] = not self.state['playing']
            if self.state['playing']:
                btn_play.label.set_text('Pause')
            else:
                btn_play.label.set_text('Play')
            fig.canvas.draw_idle()
        
        def on_slider(val):
            """Cambio en slider."""
            self.state['current_frame'] = int(val)
            actualizar_frame(self.state['current_frame'])
            fig.canvas.draw_idle()
        
        # Conectar eventos
        btn_prev.on_clicked(on_prev)
        btn_next.on_clicked(on_next)
        btn_play.on_clicked(on_play)
        slider.on_changed(on_slider)
        
        # Animación automática
        def animate(frame):
            """Bucle de animación."""
            if self.state['playing']:
                if self.state['current_frame'] < len(self.historial) - 1:
                    self.state['current_frame'] += 1
                    slider.set_val(self.state['current_frame'])
                    actualizar_frame(self.state['current_frame'])
                else:
                    self.state['playing'] = False
                    btn_play.label.set_text('Play')
            return []
        
        anim = animation.FuncAnimation(
            fig, animate, frames=len(self.historial),
            interval=self.state['interval'], repeat=True, blit=False
        )
        
        # Frame inicial
        actualizar_frame(0)
        
        plt.tight_layout()
        plt.show()
        
        return anim


def main():
    """Función principal."""
    print("="*60)
    print("VISUALIZADOR INTERACTIVO DE RUTAS")
    print("="*60)
    print("\nEste visualizador muestra:")
    print("- Cálculo de rutas cuando se necesitan")
    print("- Recalculación de rutas cuando hay bloqueos")
    print("- Movimiento de agentes siguiendo las rutas")
    print("- Colores según nivel de ansiedad")
    print("\nControles:")
    print("- < Anterior: Retroceder un paso")
    print("- Play/Pause: Reproducir/pausar animacion")
    print("- Siguiente >: Avanzar un paso")
    print("- Slider: Saltar a cualquier paso")
    print("\n" + "="*60 + "\n")
    
    # Crear visualizador
    viz = VisualizadorAnimacionRutas(num_agentes=5, max_pasos=30)
    
    # Mostrar visualización interactiva
    viz.crear_visualizacion_interactiva()


if __name__ == "__main__":
    main()

