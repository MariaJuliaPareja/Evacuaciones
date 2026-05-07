"""
Visualizador interactivo de rutas con animación.
Muestra el proceso de cálculo y recálculo de rutas paso a paso.
"""

import sys
import os
import pickle
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, root_dir)

import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.widgets import Button, Slider
from matplotlib.patches import Rectangle, Circle
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
        
        # Crear agentes en posiciones válidas con caminos hacia las puertas
        self.agentes = []
        
        # Obtener todas las posiciones válidas (no obstáculos, no puertas)
        posiciones_disponibles = [(x, y) for x in range(esc.width) 
                                 for y in range(esc.height)
                                 if (x, y) not in esc.obstaculos 
                                 and (x, y) not in esc.puertas]
        
        # Filtrar posiciones que tengan un camino válido hacia alguna puerta
        # Usar floor_field para verificar que la posición tenga un valor válido (< 500)
        posiciones_validas = []
        for x, y in posiciones_disponibles:
            if self.ff.valores[y, x] < 500:  # Valor válido en floor_field
                # Verificar que tenga al menos un vecino válido (no esté completamente aislado)
                vecinos_validos = 0
                for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
                    nx, ny = x + dx, y + dy
                    if (0 <= nx < esc.width and 0 <= ny < esc.height and
                        (nx, ny) not in esc.obstaculos and
                        self.ff.valores[ny, nx] < 500):
                        vecinos_validos += 1
                
                if vecinos_validos > 0:  # Al menos un vecino válido
                    posiciones_validas.append((x, y))
        
        # Si no hay suficientes posiciones válidas, usar las disponibles
        if len(posiciones_validas) < num_agentes:
            posiciones_validas = posiciones_disponibles[:num_agentes]
        
        # Preferir posiciones lejos de las puertas para que tengan que moverse
        # Ordenar por distancia al floor_field (valores más altos = más lejos)
        posiciones_validas.sort(key=lambda pos: self.ff.valores[pos[1], pos[0]], reverse=True)
        
        # Seleccionar posiciones iniciales
        posiciones_iniciales = posiciones_validas[:min(num_agentes, len(posiciones_validas))]
        
        # Si aún no hay suficientes, completar con posiciones aleatorias válidas
        if len(posiciones_iniciales) < num_agentes:
            restantes = [p for p in posiciones_disponibles if p not in posiciones_iniciales]
            posiciones_iniciales.extend(random.sample(restantes, 
                                                    min(num_agentes - len(posiciones_iniciales), 
                                                        len(restantes))))
        
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
        
        # Estadísticas de desbloqueo y ansiedad
        self.stats_unlock_3 = 0  # Veces que se desbloquean 3 rutas
        self.stats_unlock_5 = 0  # Veces que se desbloquean 5 rutas
        self.stats_ansiedad_historial = []  # Historial de ansiedad por paso
        
        # Estado para controles mejorados
        self.current_step = 0
        self.is_playing = False
        self.animation_speed = 500  # ms per frame
        self.fig = None
        self.ax = None
        self.btn_play = None
        self.speed_slider = None
        self.step_slider = None
        self.info_text = None
        self.animation_timer = None
        
        # Ejecutar simulación solo si no se va a reemplazar después
        # (algunos casos especiales reemplazan _simular antes de llamarlo)
        if not hasattr(self, '_simular_replaced'):
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
                
                # Establecer paso de simulación actual para cooldown de recalculación
                agente._current_simulation_step = paso
                
                # Guardar estado del agente
                agente_estado = {
                    'id': agente.id,
                    'x': agente.pos_x,
                    'y': agente.pos_y,
                    'tipo': agente.tipo,
                    'ansiedad': agente.ansiedad,
                    'current_path': None,
                    'path_index': 0,
                    'recalculado': getattr(agente, 'recalculated_this_step', False),
                    'activo': agente.activo,
                    'all_calculated_paths': getattr(agente, 'all_calculated_paths', None),
                    'unlocked_paths_count': getattr(agente, 'unlocked_paths_count', 1),
                    'trajectory_history': getattr(agente, 'trajectory_history', [])
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
                    # Obtener steps_without_moving ANTES de recalcular
                    # Esto es importante porque necesitamos saber cuánto tiempo estuvo atascado
                    current_steps_stuck = getattr(agente, 'steps_without_moving', 0)
                    
                    # Calculate how many paths should be unlocked based on stagnation
                    unlocked_count = self.ps.calculate_unlocked_paths(
                        steps_without_moving=current_steps_stuck,
                        calmness_threshold=getattr(agente, 'calmness_threshold', 3)
                    )
                    
                    # Find all paths up to 5 (progressive unlocking)
                    try:
                        all_paths = self.ps.find_progressive_paths(
                        start=(agente.pos_x, agente.pos_y),
                        goal=goal,
                            num_paths=5  # Always calculate 5, but only use unlocked ones
                        )
                    except ValueError:
                        # Fallback to find_k_paths if progressive paths fails
                        all_paths = self.ps.find_k_paths(
                            start=(agente.pos_x, agente.pos_y),
                            goal=goal,
                            k=min(5, unlocked_count)
                    )
                    
                    # Verificar que se encontraron rutas
                    if all_paths and len(all_paths) > 0:
                        # Seleccionar ruta según ansiedad de las rutas desbloqueadas
                        selected_path = self.ps.select_path_by_anxiety(
                            k_paths=all_paths,
                            anxiety_level=agente.ansiedad,
                            num_available_paths=unlocked_count
                        )
                    else:
                        # No se encontraron rutas, usar movimiento greedy
                        selected_path = None
                    
                    if selected_path is not None:
                        agente.current_path = selected_path
                        agente.path_index = 0
                        # NO resetear steps_without_moving aquí - se reseteará solo si se mueve exitosamente
                        
                        # Guardar todas las rutas calculadas y número desbloqueado
                        agente.all_calculated_paths = all_paths
                        agente.unlocked_paths_count = unlocked_count
                        agente_estado['all_calculated_paths'] = all_paths
                        agente_estado['unlocked_paths_count'] = unlocked_count
                        
                        # Registrar estadísticas de desbloqueo
                        if unlocked_count == 3:
                            self.stats_unlock_3 += 1
                        elif unlocked_count == 5:
                            self.stats_unlock_5 += 1
                        
                        # Registrar recalculación
                        if ruta_anterior is not None:
                            estado_paso['rutas_recalculadas'].append({
                                'agente_id': agente.id,
                                'ruta_anterior': ruta_anterior,
                                'ruta_nueva': selected_path,
                                'ansiedad': agente.ansiedad,
                                'unlocked_count': unlocked_count
                            })
                        else:
                            estado_paso['rutas_calculadas'].append({
                                'agente_id': agente.id,
                                'ruta': selected_path,
                                'ansiedad': agente.ansiedad,
                                'unlocked_count': unlocked_count
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
                
                # Guardar ruta actual y rutas múltiples
                agente_estado['current_path'] = agente.current_path
                agente_estado['path_index'] = agente.path_index
                agente_estado['all_calculated_paths'] = getattr(agente, 'all_calculated_paths', None)
                # unlocked_paths_count se actualizará después del movimiento basado en steps_without_moving actual
                
                # Mover agente siguiendo la ruta
                if agente.current_path and agente.path_index < len(agente.current_path):
                    next_pos = agente.current_path[agente.path_index]
                    # Verificar si puede moverse (evitar conflictos)
                    if agent_positions.get(next_pos, 0) < 2:
                        # Usar mover_a() del agente para actualizar correctamente steps_without_moving y ansiedad
                        old_pos = (agente.pos_x, agente.pos_y)
                        agente.mover_a(next_pos[0], next_pos[1])
                        # Incrementar path_index después de moverse exitosamente para seguir la ruta
                        if agente.if_change:  # Solo si realmente se movió
                            agente.path_index += 1
                    else:
                        agente.steps_without_moving = getattr(agente, 'steps_without_moving', 0) + 1
                        # Aumentar ansiedad al estar atascado
                        agente.ansiedad = min(100, agente.ansiedad + random.randint(1, 5))
                else:
                    agente.steps_without_moving = getattr(agente, 'steps_without_moving', 0) + 1
                    # Aumentar ansiedad al estar atascado
                    agente.ansiedad = min(100, agente.ansiedad + random.randint(1, 5))
                
                # Actualizar ansiedad y steps_without_moving en estado
                agente_estado['ansiedad'] = agente.ansiedad
                agente_estado['steps_without_moving'] = getattr(agente, 'steps_without_moving', 0)
                
                # SIEMPRE recalcular unlocked_paths_count basado en steps_without_moving actual
                # Esto asegura que el estado refleje correctamente cuántas rutas están desbloqueadas
                current_stuck = agente_estado['steps_without_moving']
                unlocked_count_actual = self.ps.calculate_unlocked_paths(
                    steps_without_moving=current_stuck,
                    calmness_threshold=getattr(agente, 'calmness_threshold', 3)
                )
                agente_estado['unlocked_paths_count'] = unlocked_count_actual
                # Actualizar también en el agente para mantener consistencia
                agente.unlocked_paths_count = unlocked_count_actual
                # Si hay rutas calculadas pero no están en el estado, agregarlas
                if not agente_estado.get('all_calculated_paths') and getattr(agente, 'all_calculated_paths', None):
                    agente_estado['all_calculated_paths'] = agente.all_calculated_paths
                
                # Verificar si llegó a la puerta
                if goal and agente.pos_x == goal[0] and agente.pos_y == goal[1]:
                    agente.activo = False
                
                agente_estado['activo'] = agente.activo
                estado_paso['agentes'].append(agente_estado)
            
            # Registrar ansiedad promedio del paso
            ansiedades_paso = [ag['ansiedad'] for ag in estado_paso['agentes'] if ag.get('activo', True)]
            ansiedad_promedio = np.mean(ansiedades_paso) if ansiedades_paso else 0
            self.stats_ansiedad_historial.append(ansiedad_promedio)
            
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
        """
        Create interactive visualization with enhanced controls.
        """
        fig, ax = plt.subplots(figsize=(16, 12))
        plt.subplots_adjust(bottom=0.25)
        
        self.current_step = 0
        self.is_playing = False
        self.animation_speed = 500  # ms per frame
        self.fig = fig
        self.ax = ax
        
        # Initial plot
        self._update_plot(self.current_step, ax)
        
        # CONTROL PANEL
        # Previous button
        ax_prev = plt.axes([0.1, 0.05, 0.1, 0.04])
        btn_prev = Button(ax_prev, '< Previous')
        btn_prev.on_clicked(lambda event: self._step_backward())
        
        # Play/Pause button
        ax_play = plt.axes([0.25, 0.05, 0.1, 0.04])
        self.btn_play = Button(ax_play, 'Play')
        self.btn_play.on_clicked(lambda event: self._toggle_play())
        
        # Next button
        ax_next = plt.axes([0.4, 0.05, 0.1, 0.04])
        btn_next = Button(ax_next, 'Next >')
        btn_next.on_clicked(lambda event: self._step_forward())
        
        # Speed slider
        ax_speed = plt.axes([0.55, 0.05, 0.3, 0.03])
        self.speed_slider = Slider(ax_speed, 'Speed', 100, 2000, 
                                   valinit=self.animation_speed, valstep=100)
        self.speed_slider.on_changed(lambda val: setattr(self, 'animation_speed', val))
        
        # Step slider
        ax_slider = plt.axes([0.1, 0.12, 0.75, 0.03])
        self.step_slider = Slider(ax_slider, 'Step', 0, len(self.historial)-1,
                        valinit=0, valstep=1)
        self.step_slider.on_changed(self._on_slider_change)
        
        # Info text
        ax_info = plt.axes([0.1, 0.18, 0.75, 0.03])
        ax_info.axis('off')
        self.info_text = ax_info.text(0.5, 0.5, '', transform=ax_info.transAxes,
                                     ha='center', va='center', fontsize=10,
                                     bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
        
        # Keyboard shortcuts
        def on_key(event):
            """Handle keyboard shortcuts."""
            if event.key == 'left':
                self._step_backward()
            elif event.key == 'right':
                self._step_forward()
            elif event.key == ' ':
                self._toggle_play()
        
        fig.canvas.mpl_connect('key_press_event', on_key)
        
        plt.show()
    
    def _step_forward(self):
        """Move to next step."""
        if self.current_step < len(self.historial) - 1:
            self.current_step += 1
            self._update_plot(self.current_step, self.ax)
            if self.step_slider:
                self.step_slider.set_val(self.current_step)
    
    def _step_backward(self):
        """Move to previous step."""
        if self.current_step > 0:
            self.current_step -= 1
            self._update_plot(self.current_step, self.ax)
            if self.step_slider:
                self.step_slider.set_val(self.current_step)
    
    def _step_forward_with_stats(self):
        """Move to next step with statistics."""
        if self.current_step < len(self.historial) - 1:
            self.current_step += 1
            if hasattr(self, 'ax_stats1') and hasattr(self, 'ax_stats2'):
                self._update_plot_with_stats(self.current_step, self.ax, self.ax_stats1, self.ax_stats2)
            else:
                self._update_plot(self.current_step, self.ax)
            if self.step_slider:
                self.step_slider.set_val(self.current_step)
    
    def _step_backward_with_stats(self):
        """Move to previous step with statistics."""
        if self.current_step > 0:
            self.current_step -= 1
            if hasattr(self, 'ax_stats1') and hasattr(self, 'ax_stats2'):
                self._update_plot_with_stats(self.current_step, self.ax, self.ax_stats1, self.ax_stats2)
            else:
                self._update_plot(self.current_step, self.ax)
            if self.step_slider:
                self.step_slider.set_val(self.current_step)
    
    def _on_slider_change_with_stats(self, val):
        """Handle slider change with statistics."""
        step = int(val)
        if step != self.current_step:
            self.current_step = step
            if hasattr(self, 'ax_stats1') and hasattr(self, 'ax_stats2'):
                self._update_plot_with_stats(step, self.ax, self.ax_stats1, self.ax_stats2)
            else:
                self._update_plot(step, self.ax)
    
    def _toggle_play(self):
        """Toggle play/pause animation."""
        self.is_playing = not self.is_playing
        if self.btn_play:
            self.btn_play.label.set_text('Pause' if self.is_playing else 'Play')
        
        if self.is_playing:
            self._play_animation()
        else:
            # Stop animation timer if exists
            if self.animation_timer:
                self.animation_timer.stop()
                self.animation_timer = None
    
    def _play_animation(self):
        """Auto-play through steps."""
        if not self.is_playing or self.current_step >= len(self.historial) - 1:
            self.is_playing = False
            if self.btn_play:
                self.btn_play.label.set_text('Play')
                return
            
        self._step_forward()
        if self.fig:
            self.fig.canvas.draw_idle()
            self.fig.canvas.flush_events()
        
        # Schedule next frame using timer
        if self.fig and self.is_playing:
            # Stop previous timer if exists
            if self.animation_timer:
                self.animation_timer.stop()
            
            self.animation_timer = self.fig.canvas.new_timer(interval=int(self.animation_speed))
            self.animation_timer.add_callback(self._play_animation)
            self.animation_timer.single_shot = True
            self.animation_timer.start()
    
    def _on_slider_change(self, val):
        """Handle slider change."""
        step = int(val)
        if step != self.current_step:
            self.current_step = step
            self._update_plot(step, self.ax)
    
    def _update_plot(self, step: int, ax):
        """
        Update plot for given step.
        Enhanced to show multi-level path visualization.
        """
        ax.clear()
        
        if step < 0 or step >= len(self.historial):
            return
        
        estado = self.historial[step]
        
        # Configurar ejes
        ax.set_xlim(-0.5, esc.width - 0.5)
        ax.set_ylim(-0.5, esc.height - 0.5)
        ax.set_aspect('equal')
        ax.invert_yaxis()
        
        # Dibujar grilla
        for i in range(esc.width + 1):
            ax.axvline(i - 0.5, color='lightgray', linewidth=0.3, alpha=0.5)
        for j in range(esc.height + 1):
            ax.axhline(j - 0.5, color='lightgray', linewidth=0.3, alpha=0.5)
        
        # Floor field de fondo
        valores_plot = self.ff.valores.copy()
        valores_plot[valores_plot >= 500] = np.nan
        ax.imshow(valores_plot, cmap='gray_r', origin='lower', 
                  alpha=0.2, extent=[-0.5, esc.width-0.5, esc.height-0.5, -0.5])
        
        # Dibujar obstáculos
        for x, y in esc.obstaculos:
            rect = Rectangle((x-0.5, y-0.5), 1, 1, 
                            facecolor='black', alpha=0.7)
            ax.add_patch(rect)
        
        # Dibujar puertas
        for x, y in esc.puertas:
            rect = Rectangle((x-0.5, y-0.5), 1, 1, 
                            facecolor='green', alpha=0.8, edgecolor='orange', linewidth=2)
            ax.add_patch(rect)
            ax.text(x, y, 'P', ha='center', va='center', 
                           fontsize=12, weight='bold', color='white')
            
        # Dibujar rutas calculadas en este paso (nuevas rutas)
        for ruta_info in estado['rutas_calculadas']:
            ruta = ruta_info['ruta']
            anxiety = ruta_info['ansiedad']
            color = self._get_color_by_anxiety(anxiety)
            
            if len(ruta) > 1:
                xs, ys = zip(*ruta)
                ax.plot(xs, ys, color=color, linewidth=2, 
                       linestyle='--', alpha=0.6, zorder=1)
        
        # Dibujar rutas recalculadas (más destacadas)
        for ruta_info in estado['rutas_recalculadas']:
            ruta_nueva = ruta_info['ruta_nueva']
            anxiety = ruta_info['ansiedad']
            color = self._get_color_by_anxiety(anxiety)
            
            if len(ruta_nueva) > 1:
                xs, ys = zip(*ruta_nueva)
                ax.plot(xs, ys, color=color, linewidth=3, 
                       linestyle='-', alpha=0.8, zorder=2)
            
        # Dibujar agentes con todas sus rutas desbloqueadas
        for agente_estado in estado['agentes']:
            if not agente_estado.get('activo', True):
                continue
            
            x, y = agente_estado['x'], agente_estado['y']
            anxiety = agente_estado['ansiedad']
            current_path = agente_estado.get('current_path')
            path_index = agente_estado.get('path_index', 0)
            
            # Get all calculated paths and unlocked count
            all_paths = agente_estado.get('all_calculated_paths', [])
            unlocked_count = agente_estado.get('unlocked_paths_count', 1)
            
            # If no all_calculated_paths but has current_path, use that
            if not all_paths and current_path:
                all_paths = [current_path]
                unlocked_count = 1
            
            pos_actual = (x, y)
            
            # ========================================
            # PASO 1: RUTAS ALTERNATIVAS (líneas punteadas)
            # Solo mostrar las rutas desbloqueadas que NO son la actual
            # ========================================
            if all_paths and unlocked_count > 1:
                # Identificar cuál es la ruta actual
                current_path_index = -1
                if current_path:
                    for idx, path in enumerate(all_paths):
                        if path == current_path or (len(path) == len(current_path) and 
                                                    path[0] == current_path[0] and 
                                                    path[-1] == current_path[-1]):
                            current_path_index = idx
                            break
                
                # Dibujar rutas alternativas (saltando la actual)
                for i in range(min(len(all_paths), unlocked_count)):
                    if i == current_path_index:
                        continue  # Saltar la ruta actual
                    
                    alt_path = all_paths[i]
                    if not alt_path or len(alt_path) == 0:
                        continue
                    
                    # Encontrar el punto más cercano a la posición actual
                    min_dist = float('inf')
                    start_idx = 0
                    
                    for idx, (px, py) in enumerate(alt_path):
                        dist = abs(px - x) + abs(py - y)
                        if dist < min_dist:
                            min_dist = dist
                            start_idx = idx
                    
                    # Dibujar solo desde ese punto hacia adelante
                    if start_idx < len(alt_path):
                        segmento_futuro = alt_path[start_idx:]
                        
                        if len(segmento_futuro) > 0:
                            xs = [px for px, py in segmento_futuro]
                            ys = [py for px, py in segmento_futuro]
                            
                            # Color basado en índice
                            colors = ['green', 'yellow', 'orange', 'red', 'purple']
                            color = colors[i % len(colors)]
                            
                            ax.plot(xs, ys, linestyle='--', linewidth=1.5, 
                                   alpha=0.5, color=color, zorder=2,
                                   marker='o', markersize=2)
            
            # ========================================
            # PASO 2: RUTA ACTUAL (línea sólida)
            # Dibujar solo desde path_index hacia adelante
            # ========================================
            if current_path and len(current_path) > 0 and path_index < len(current_path):
                # Segmento restante de la ruta
                remaining_path = current_path[path_index:]
                
                if len(remaining_path) > 0:
                    # Agregar la posición actual como primer punto
                    # para conectar visualmente al agente con la ruta
                    segmento_completo = [pos_actual] + remaining_path
                    
                    xs = [px for px, py in segmento_completo]
                    ys = [py for px, py in segmento_completo]
                    
                    # Color según nivel de ansiedad
                    color_ruta = self._get_color_by_anxiety(anxiety)
                    
                    ax.plot(xs, ys, linestyle='-', linewidth=3, 
                           color=color_ruta, alpha=0.8, zorder=3,
                           marker='o', markersize=2)
            
            # Draw agent current position
            agent_color = 'lightgreen' if agente_estado['tipo'] == 'rapido' else 'lightcoral'
            circle = Circle((x, y), 0.3, color=agent_color, alpha=0.8, zorder=10)
            ax.add_patch(circle)
            
            # Etiqueta del agente con número de rutas desbloqueadas
            ax.text(x, y, str(agente_estado['id']), 
                   ha='center', va='center', fontsize=8,
                   color='white', weight='bold', zorder=11)
            
            # Label showing unlocked paths count
            ax.text(x + 0.3, y + 0.3, 
                   f"{unlocked_count}P",
                   fontsize=7, bbox=dict(boxstyle='round', facecolor='white', alpha=0.7),
                   zorder=12)
            
            # Indicador de recalculación (estrella roja)
            if agente_estado.get('recalculado', False):
                ax.plot(x, y + 0.5, '*', color='red', markersize=15,
                       markeredgecolor='darkred', markeredgewidth=1.5, zorder=13)
            
            # (OPCIONAL) Dibujar trayectoria real recorrida (línea azul tenue)
            if hasattr(agente_estado, 'trajectory_history') and agente_estado.get('trajectory_history'):
                traj = agente_estado['trajectory_history']
                if len(traj) > 1:
                    xs_traj = [px for px, py in traj]
                    ys_traj = [py for px, py in traj]
                    ax.plot(xs_traj, ys_traj, 'b-', linewidth=1, alpha=0.2, zorder=1)
        
        # Título con información
        total_activos = sum(1 for a in estado['agentes'] if a.get('activo', True))
        total_evacuados = len(estado['agentes']) - total_activos
        
        ax.set_title(
            f'Evacuation Simulation - Step {step}/{len(self.historial)-1} | '
            f'Active: {total_activos} | Evacuated: {total_evacuados}',
            fontsize=13, weight='bold'
        )
        
        ax.set_xlabel('X', fontsize=12)
        ax.set_ylabel('Y', fontsize=12)
        ax.grid(True, alpha=0.3)
        
        # Leyenda mejorada
        from matplotlib.patches import Patch
        from matplotlib.lines import Line2D
        legend_elements = [
            Patch(facecolor='green', label='Low anxiety (0-30)'),
            Patch(facecolor='yellow', label='Optimal anxiety (30-70)'),
            Patch(facecolor='red', label='High anxiety (70-100)'),
            Line2D([0], [0], color='black', linestyle='-', linewidth=3, label='Current path'),
            Line2D([0], [0], color='black', linestyle='--', linewidth=1.5, label='Alternative path', alpha=0.3),
            Line2D([0], [0], marker='o', color='w', markerfacecolor='lightgreen', 
                  markersize=8, label='Fast Agent', markeredgecolor='black'),
            Line2D([0], [0], marker='o', color='w', markerfacecolor='lightcoral', 
                  markersize=8, label='Slow Agent', markeredgecolor='black'),
            Line2D([0], [0], marker='*', color='red', linestyle='None', markersize=10, label='Recalculated')
        ]
        ax.legend(handles=legend_elements, loc='upper left', fontsize=8)
        
        # Update info text
        if self.info_text:
            active_agents = [ag for ag in estado['agentes'] if ag.get('activo', True)]
            avg_anxiety = np.mean([ag['ansiedad'] for ag in active_agents]) if active_agents else 0
            # Calculate average unlocked paths
            unlocked_counts = [ag.get('unlocked_paths_count', 1) for ag in active_agents]
            avg_unlocked = np.mean(unlocked_counts) if unlocked_counts else 1
            
            # Contar desbloqueos en este paso
            unlock_3_este_paso = sum(1 for ag in estado['agentes'] 
                                    if ag.get('unlocked_paths_count', 1) == 3)
            unlock_5_este_paso = sum(1 for ag in estado['agentes'] 
                                    if ag.get('unlocked_paths_count', 1) == 5)
            
            info_str = f"Step: {step}/{len(self.historial)-1} | "
            info_str += f"Active: {total_activos} | "
            info_str += f"Avg Anxiety: {avg_anxiety:.1f} | "
            info_str += f"Unlocked: 3P={unlock_3_este_paso} 5P={unlock_5_este_paso} | "
            info_str += f"Total: 3P={self.stats_unlock_3} 5P={self.stats_unlock_5}"
            self.info_text.set_text(info_str)
        
        if self.fig:
            self.fig.canvas.draw_idle()
    
    def _update_plot_with_stats(self, step: int, ax_main, ax_stats1, ax_stats2):
        """
        Update plot with statistics graphs.
        Shows main simulation and two statistics graphs.
        """
        # Update main plot
        self._update_plot(step, ax_main)
        
        # Update statistics graphs
        ax_stats1.clear()
        ax_stats2.clear()
        
        # Graph 1: Desbloqueos por paso
        steps_range = range(min(step + 1, len(self.historial)))
        unlock_3_por_paso = []
        unlock_5_por_paso = []
        
        for s in steps_range:
            estado = self.historial[s]
            unlock_3 = sum(1 for ag in estado['agentes'] 
                          if ag.get('unlocked_paths_count', 1) == 3)
            unlock_5 = sum(1 for ag in estado['agentes'] 
                          if ag.get('unlocked_paths_count', 1) == 5)
            unlock_3_por_paso.append(unlock_3)
            unlock_5_por_paso.append(unlock_5)
        
        ax_stats1.plot(steps_range, unlock_3_por_paso, 'o-', color='orange', 
                      label='3 Paths Unlocked', linewidth=2, markersize=4)
        ax_stats1.plot(steps_range, unlock_5_por_paso, 's-', color='red', 
                      label='5 Paths Unlocked', linewidth=2, markersize=4)
        ax_stats1.set_xlabel('Step')
        ax_stats1.set_ylabel('Agents Count')
        ax_stats1.set_title('Paths Unlocked per Step')
        ax_stats1.legend()
        ax_stats1.grid(True, alpha=0.3)
        if len(self.historial) > 0:
            ax_stats1.set_xlim(-0.5, len(self.historial) - 0.5)
        
        # Graph 2: Ansiedad promedio
        ansiedad_hist = self.stats_ansiedad_historial[:step+1] if step < len(self.stats_ansiedad_historial) else self.stats_ansiedad_historial
        steps_ansiedad = range(len(ansiedad_hist))
        
        if len(ansiedad_hist) > 0:
            ax_stats2.plot(steps_ansiedad, ansiedad_hist, 'o-', color='purple', 
                          linewidth=2, markersize=4)
            ax_stats2.axhline(y=30, color='green', linestyle='--', alpha=0.5, label='Low threshold')
            ax_stats2.axhline(y=70, color='red', linestyle='--', alpha=0.5, label='High threshold')
        ax_stats2.set_xlabel('Step')
        ax_stats2.set_ylabel('Average Anxiety')
        ax_stats2.set_title('Average Anxiety Over Time')
        ax_stats2.legend()
        ax_stats2.grid(True, alpha=0.3)
        ax_stats2.set_ylim(0, 100)
        
        if self.fig:
            self.fig.canvas.draw_idle()


def crear_caso_desbloqueo_1_ruta():
    """
    Caso 1: Demuestra el uso de UNA sola ruta.
    El agente se mueve libremente sin desbloquear rutas adicionales.
    """
    print("\n" + "="*60)
    print("CASO 1: DESBLOQUEO DE 1 RUTA")
    print("="*60)
    print("Un agente se mueve hacia la salida usando solo 1 ruta.")
    print("- No se atasca lo suficiente para desbloquear 3 o 5 rutas")
    print("="*60 + "\n")
    
    viz = VisualizadorAnimacionRutas(num_agentes=1, max_pasos=30)
    viz.crear_visualizacion_interactiva()
    return viz


def crear_caso_desbloqueo_3_rutas():
    """
    Caso 2: Demuestra el desbloqueo de 3 rutas.
    El agente se atasca moderadamente (3-4 pasos) y desbloquea 3 rutas alternativas.
    """
    print("\n" + "="*60)
    print("CASO 2: DESBLOQUEO DE 3 RUTAS Y SELECCIÓN")
    print("="*60)
    print("Un agente se atasca moderadamente y desbloquea 3 rutas.")
    print("- Se fuerza un atasco de 3-4 pasos sin movimiento")
    print("- El agente selecciona una de las 3 rutas según su ansiedad")
    print("="*60 + "\n")
    
    # Crear visualizador SIN ejecutar simulación inicial
    viz = VisualizadorAnimacionRutas.__new__(VisualizadorAnimacionRutas)
    viz.num_agentes = 2
    viz.max_pasos = 40
    
    # Setup del escenario
    viz.ff = Floor_field(esc.width, esc.height, esc.puertas, esc.obstaculos)
    viz.ps = PathSelector(viz.ff)
    
    # Crear agentes
    viz.agentes = []
    posiciones_disponibles = [(x, y) for x in range(esc.width) 
                             for y in range(esc.height)
                             if (x, y) not in esc.obstaculos 
                             and (x, y) not in esc.puertas]
    
    posiciones_validas = []
    for x, y in posiciones_disponibles:
        if viz.ff.valores[y, x] < 500:
            vecinos_validos = 0
            for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
                nx, ny = x + dx, y + dy
                if (0 <= nx < esc.width and 0 <= ny < esc.height and
                    (nx, ny) not in esc.obstaculos and
                    viz.ff.valores[ny, nx] < 500):
                    vecinos_validos += 1
            if vecinos_validos > 0:
                posiciones_validas.append((x, y))
    
    if len(posiciones_validas) < viz.num_agentes:
        posiciones_validas = posiciones_disponibles[:viz.num_agentes]
    
    posiciones_validas.sort(key=lambda pos: viz.ff.valores[pos[1], pos[0]], reverse=True)
    posiciones_iniciales = posiciones_validas[:min(viz.num_agentes, len(posiciones_validas))]
    
    if len(posiciones_iniciales) < viz.num_agentes:
        restantes = [p for p in posiciones_disponibles if p not in posiciones_iniciales]
        posiciones_iniciales.extend(random.sample(restantes, 
                                                min(viz.num_agentes - len(posiciones_iniciales), 
                                                    len(restantes))))
    
    for i, (x, y) in enumerate(posiciones_iniciales):
        agente = AgentExtendido(
            agent_type='rapido' if i % 2 == 0 else 'lento',
            floor_field=viz.ff,
            path_selector=viz.ps,
            x=x,
            y=y
        )
        agente.ansiedad = random.uniform(40, 60)
        agente.steps_without_moving = 0
        viz.agentes.append(agente)
    
    # Historial y estadísticas
    viz.historial = []
    viz.paso_actual = 0
    viz.playing = False
    viz.stats_unlock_3 = 0
    viz.stats_unlock_5 = 0
    viz.stats_ansiedad_historial = []
    viz.current_step = 0
    viz.is_playing = False
    viz.animation_speed = 500
    viz.fig = None
    viz.ax = None
    viz.btn_play = None
    viz.speed_slider = None
    viz.step_slider = None
    viz.info_text = None
    viz.animation_timer = None
    
    # Simulación modificada que fuerza atasco de 3-4 pasos
    def _simular_caso_3_rutas():
        """Simulación que fuerza atasco para desbloquear 3 rutas."""
        print(f"Simulando {viz.max_pasos} pasos con {viz.num_agentes} agentes (desbloqueo de 3 rutas)...")
        
        for paso in range(viz.max_pasos):
            estado_paso = {
                'paso': paso,
                'agentes': [],
                'rutas_calculadas': [],
                'rutas_recalculadas': []
            }
            
            # Calcular posiciones actuales de agentes
            agent_positions = {}
            for agente in viz.agentes:
                if agente.activo and agente.pos_x is not None and agente.pos_y is not None:
                    pos = (agente.pos_x, agente.pos_y)
                    agent_positions[pos] = agent_positions.get(pos, 0) + 1
            
            # Procesar cada agente
            for agente in viz.agentes:
                if not agente.activo:
                    continue
                
                # Establecer paso de simulación actual para cooldown de recalculación
                agente._current_simulation_step = paso
                
                agente_estado = {
                    'id': agente.id,
                    'x': agente.pos_x,
                    'y': agente.pos_y,
                    'tipo': agente.tipo,
                    'ansiedad': agente.ansiedad,
                    'current_path': None,
                    'path_index': 0,
                    'recalculado': getattr(agente, 'recalculated_this_step', False),
                    'activo': agente.activo,
                    'all_calculated_paths': getattr(agente, 'all_calculated_paths', None),
                    'unlocked_paths_count': getattr(agente, 'unlocked_paths_count', 1),
                    'trajectory_history': getattr(agente, 'trajectory_history', [])
                }
                
                goal = viz._encontrar_puerta_mas_cercana(agente)
                ruta_anterior = getattr(agente, 'current_path', None)
                path_index_anterior = getattr(agente, 'path_index', 0)
                
                should_recalc = (
                    ruta_anterior is None or
                    viz.ps.should_recalculate(
                        agent_pos=(agente.pos_x, agente.pos_y),
                        current_path=ruta_anterior,
                        path_index=path_index_anterior,
                        agent_positions=agent_positions,
                        steps_without_moving=getattr(agente, 'steps_without_moving', 0),
                        anxiety_level=agente.ansiedad
                    )
                )
                
                if should_recalc:
                    current_steps_stuck = getattr(agente, 'steps_without_moving', 0)
                    unlocked_count = viz.ps.calculate_unlocked_paths(
                        steps_without_moving=current_steps_stuck,
                        calmness_threshold=getattr(agente, 'calmness_threshold', 3)
                    )
                    
                    try:
                        all_paths = viz.ps.find_progressive_paths(
                            start=(agente.pos_x, agente.pos_y),
                            goal=goal,
                            num_paths=5
                        )
                    except ValueError:
                        all_paths = viz.ps.find_k_paths(
                            start=(agente.pos_x, agente.pos_y),
                            goal=goal,
                            k=min(5, unlocked_count)
                        )
                    
                    if all_paths and len(all_paths) > 0:
                        selected_path = viz.ps.select_path_by_anxiety(
                            k_paths=all_paths,
                            anxiety_level=agente.ansiedad,
                            num_available_paths=unlocked_count
                        )
                    else:
                        selected_path = None
                    
                    if selected_path is not None:
                        agente.current_path = selected_path
                        agente.path_index = 0
                        agente.all_calculated_paths = all_paths
                        agente.unlocked_paths_count = unlocked_count
                        agente_estado['all_calculated_paths'] = all_paths
                        agente_estado['unlocked_paths_count'] = unlocked_count
                        
                        if unlocked_count == 3:
                            viz.stats_unlock_3 += 1
                        elif unlocked_count == 5:
                            viz.stats_unlock_5 += 1
                        
                        if ruta_anterior is not None:
                            estado_paso['rutas_recalculadas'].append({
                                'agente_id': agente.id,
                                'ruta_anterior': ruta_anterior,
                                'ruta_nueva': selected_path,
                                'ansiedad': agente.ansiedad,
                                'unlocked_count': unlocked_count
                            })
                        else:
                            estado_paso['rutas_calculadas'].append({
                                'agente_id': agente.id,
                                'ruta': selected_path,
                                'ansiedad': agente.ansiedad,
                                'unlocked_count': unlocked_count
                            })
                        
                        agente_estado['recalculado'] = True
                    else:
                        if ruta_anterior is None:
                            agente.current_path = None
                            agente.path_index = 0
                else:
                    agente.path_index += 1
                
                agente_estado['current_path'] = agente.current_path
                agente_estado['path_index'] = agente.path_index
                agente_estado['all_calculated_paths'] = getattr(agente, 'all_calculated_paths', None)
                
                # Forzar bloqueo para llegar a 3-4 pasos atascado
                current_stuck = getattr(agente, 'steps_without_moving', 0)
                
                # Bloquear si aún no llegó a 3 pasos atascado
                if current_stuck < 3 and paso < 10:
                    # Forzar bloqueo aumentando steps_without_moving
                    agente.steps_without_moving = current_stuck + 1
                    agente.ansiedad = min(100, agente.ansiedad + random.randint(2, 5))
                elif agente.current_path and agente.path_index < len(agente.current_path):
                    # Permitir movimiento normal
                    next_pos = agente.current_path[agente.path_index]
                    if agent_positions.get(next_pos, 0) < 2:
                        old_pos = (agente.pos_x, agente.pos_y)
                        agente.mover_a(next_pos[0], next_pos[1])
                        if agente.if_change:
                            agente.path_index += 1
                    else:
                        agente.steps_without_moving = getattr(agente, 'steps_without_moving', 0) + 1
                        agente.ansiedad = min(100, agente.ansiedad + random.randint(1, 5))
                else:
                    agente.steps_without_moving = getattr(agente, 'steps_without_moving', 0) + 1
                    agente.ansiedad = min(100, agente.ansiedad + random.randint(1, 5))
                
                agente_estado['ansiedad'] = agente.ansiedad
                agente_estado['steps_without_moving'] = getattr(agente, 'steps_without_moving', 0)
                
                current_stuck = agente_estado['steps_without_moving']
                unlocked_count_actual = viz.ps.calculate_unlocked_paths(
                    steps_without_moving=current_stuck,
                    calmness_threshold=getattr(agente, 'calmness_threshold', 3)
                )
                agente_estado['unlocked_paths_count'] = unlocked_count_actual
                agente.unlocked_paths_count = unlocked_count_actual
                
                if not agente_estado.get('all_calculated_paths') and getattr(agente, 'all_calculated_paths', None):
                    agente_estado['all_calculated_paths'] = agente.all_calculated_paths
                
                if goal and agente.pos_x == goal[0] and agente.pos_y == goal[1]:
                    agente.activo = False
                
                agente_estado['activo'] = agente.activo
                estado_paso['agentes'].append(agente_estado)
            
            ansiedades_paso = [ag['ansiedad'] for ag in estado_paso['agentes'] if ag.get('activo', True)]
            ansiedad_promedio = np.mean(ansiedades_paso) if ansiedades_paso else 0
            viz.stats_ansiedad_historial.append(ansiedad_promedio)
            
            viz.historial.append(estado_paso)
            
            if all(not agente.activo for agente in viz.agentes):
                print(f"Todos los agentes evacuaron en paso {paso}")
                break
        
        print(f"Simulación completada: {len(viz.historial)} pasos")
        print(f"Desbloqueos de 3 rutas: {viz.stats_unlock_3}")
        print(f"Desbloqueos de 5 rutas: {viz.stats_unlock_5}")
    
    viz._simular_replaced = True
    viz._simular = _simular_caso_3_rutas
    viz._simular()
    
    viz.crear_visualizacion_interactiva()
    return viz


def crear_caso_desbloqueo_5_rutas_colisiones():
    """
    Caso 3: Demuestra el desbloqueo de 5 rutas con colisiones.
    Múltiples agentes compiten por espacio, generando atascos de 5+ pasos.
    """
    print("\n" + "="*60)
    print("CASO 3: DESBLOQUEO DE 5 RUTAS CON COLISIONES")
    print("="*60)
    print("Varios agentes compiten por espacio y se atascan fuertemente.")
    print("- Se fuerza un atasco de 5+ pasos sin movimiento")
    print("- Los agentes desbloquean 5 rutas alternativas")
    print("- Seleccionan rutas según ansiedad lidiando con colisiones")
    print("="*60 + "\n")
    
    # Crear visualizador SIN ejecutar simulación inicial
    viz = VisualizadorAnimacionRutas.__new__(VisualizadorAnimacionRutas)
    viz.num_agentes = 4
    viz.max_pasos = 50
    
    # Setup del escenario
    viz.ff = Floor_field(esc.width, esc.height, esc.puertas, esc.obstaculos)
    viz.ps = PathSelector(viz.ff)
    
    # Crear agentes
    viz.agentes = []
    posiciones_disponibles = [(x, y) for x in range(esc.width) 
                             for y in range(esc.height)
                             if (x, y) not in esc.obstaculos 
                             and (x, y) not in esc.puertas]
    
    posiciones_validas = []
    for x, y in posiciones_disponibles:
        if viz.ff.valores[y, x] < 500:
            vecinos_validos = 0
            for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
                nx, ny = x + dx, y + dy
                if (0 <= nx < esc.width and 0 <= ny < esc.height and
                    (nx, ny) not in esc.obstaculos and
                    viz.ff.valores[ny, nx] < 500):
                    vecinos_validos += 1
            if vecinos_validos > 0:
                posiciones_validas.append((x, y))
    
    if len(posiciones_validas) < viz.num_agentes:
        posiciones_validas = posiciones_disponibles[:viz.num_agentes]
    
    posiciones_validas.sort(key=lambda pos: viz.ff.valores[pos[1], pos[0]], reverse=True)
    posiciones_iniciales = posiciones_validas[:min(viz.num_agentes, len(posiciones_validas))]
    
    if len(posiciones_iniciales) < viz.num_agentes:
        restantes = [p for p in posiciones_disponibles if p not in posiciones_iniciales]
        posiciones_iniciales.extend(random.sample(restantes, 
                                                min(viz.num_agentes - len(posiciones_iniciales), 
                                                    len(restantes))))
    
    for i, (x, y) in enumerate(posiciones_iniciales):
        agente = AgentExtendido(
            agent_type='rapido' if i % 2 == 0 else 'lento',
            floor_field=viz.ff,
            path_selector=viz.ps,
            x=x,
            y=y
        )
        agente.ansiedad = random.uniform(50, 80)
        agente.steps_without_moving = 0
        viz.agentes.append(agente)
    
    # Historial y estadísticas
    viz.historial = []
    viz.paso_actual = 0
    viz.playing = False
    viz.stats_unlock_3 = 0
    viz.stats_unlock_5 = 0
    viz.stats_ansiedad_historial = []
    viz.current_step = 0
    viz.is_playing = False
    viz.animation_speed = 500
    viz.fig = None
    viz.ax = None
    viz.btn_play = None
    viz.speed_slider = None
    viz.step_slider = None
    viz.info_text = None
    viz.animation_timer = None
    
    # Simulación modificada que fuerza atasco de 5+ pasos
    def _simular_caso_5_rutas():
        """Simulación que fuerza atasco para desbloquear 5 rutas."""
        print(f"Simulando {viz.max_pasos} pasos con {viz.num_agentes} agentes (desbloqueo de 5 rutas)...")
        
        for paso in range(viz.max_pasos):
            estado_paso = {
                'paso': paso,
                'agentes': [],
                'rutas_calculadas': [],
                'rutas_recalculadas': []
            }
            
            # Calcular posiciones actuales de agentes
            agent_positions = {}
            for agente in viz.agentes:
                if agente.activo and agente.pos_x is not None and agente.pos_y is not None:
                    pos = (agente.pos_x, agente.pos_y)
                    agent_positions[pos] = agent_positions.get(pos, 0) + 1
            
            # Procesar cada agente
            for agente in viz.agentes:
                if not agente.activo:
                    continue
                
                # Establecer paso de simulación actual para cooldown de recalculación
                agente._current_simulation_step = paso
                
                agente_estado = {
                    'id': agente.id,
                    'x': agente.pos_x,
                    'y': agente.pos_y,
                    'tipo': agente.tipo,
                    'ansiedad': agente.ansiedad,
                    'current_path': None,
                    'path_index': 0,
                    'recalculado': getattr(agente, 'recalculated_this_step', False),
                    'activo': agente.activo,
                    'all_calculated_paths': getattr(agente, 'all_calculated_paths', None),
                    'unlocked_paths_count': getattr(agente, 'unlocked_paths_count', 1),
                    'trajectory_history': getattr(agente, 'trajectory_history', [])
                }
                
                goal = viz._encontrar_puerta_mas_cercana(agente)
                ruta_anterior = getattr(agente, 'current_path', None)
                path_index_anterior = getattr(agente, 'path_index', 0)
                
                should_recalc = (
                    ruta_anterior is None or
                    viz.ps.should_recalculate(
                        agent_pos=(agente.pos_x, agente.pos_y),
                        current_path=ruta_anterior,
                        path_index=path_index_anterior,
                        agent_positions=agent_positions,
                        steps_without_moving=getattr(agente, 'steps_without_moving', 0),
                        anxiety_level=agente.ansiedad
                    )
                )
                
                if should_recalc:
                    current_steps_stuck = getattr(agente, 'steps_without_moving', 0)
                    unlocked_count = viz.ps.calculate_unlocked_paths(
                        steps_without_moving=current_steps_stuck,
                        calmness_threshold=getattr(agente, 'calmness_threshold', 3)
                    )
                    
                    try:
                        all_paths = viz.ps.find_progressive_paths(
                            start=(agente.pos_x, agente.pos_y),
                            goal=goal,
                            num_paths=5
                        )
                    except ValueError:
                        all_paths = viz.ps.find_k_paths(
                            start=(agente.pos_x, agente.pos_y),
                            goal=goal,
                            k=min(5, unlocked_count)
                        )
                    
                    if all_paths and len(all_paths) > 0:
                        selected_path = viz.ps.select_path_by_anxiety(
                            k_paths=all_paths,
                            anxiety_level=agente.ansiedad,
                            num_available_paths=unlocked_count
                        )
                    else:
                        selected_path = None
                    
                    if selected_path is not None:
                        agente.current_path = selected_path
                        agente.path_index = 0
                        agente.all_calculated_paths = all_paths
                        agente.unlocked_paths_count = unlocked_count
                        agente_estado['all_calculated_paths'] = all_paths
                        agente_estado['unlocked_paths_count'] = unlocked_count
                        
                        if unlocked_count == 3:
                            viz.stats_unlock_3 += 1
                        elif unlocked_count == 5:
                            viz.stats_unlock_5 += 1
                        
                        if ruta_anterior is not None:
                            estado_paso['rutas_recalculadas'].append({
                                'agente_id': agente.id,
                                'ruta_anterior': ruta_anterior,
                                'ruta_nueva': selected_path,
                                'ansiedad': agente.ansiedad,
                                'unlocked_count': unlocked_count
                            })
                        else:
                            estado_paso['rutas_calculadas'].append({
                                'agente_id': agente.id,
                                'ruta': selected_path,
                                'ansiedad': agente.ansiedad,
                                'unlocked_count': unlocked_count
                            })
                        
                        agente_estado['recalculado'] = True
                    else:
                        if ruta_anterior is None:
                            agente.current_path = None
                            agente.path_index = 0
                else:
                    agente.path_index += 1
                
                agente_estado['current_path'] = agente.current_path
                agente_estado['path_index'] = agente.path_index
                agente_estado['all_calculated_paths'] = getattr(agente, 'all_calculated_paths', None)
                
                # Forzar bloqueo para llegar a 5+ pasos atascado
                current_stuck = getattr(agente, 'steps_without_moving', 0)
                
                # Bloquear si aún no llegó a 5 pasos atascado
                if current_stuck < 5 and paso < 15:
                    # Forzar bloqueo aumentando steps_without_moving
                    agente.steps_without_moving = current_stuck + 1
                    agente.ansiedad = min(100, agente.ansiedad + random.randint(3, 7))
                elif agente.current_path and agente.path_index < len(agente.current_path):
                    # Permitir movimiento normal con colisiones ocasionales
                    next_pos = agente.current_path[agente.path_index]
                    # Aumentar restricción de posición para simular colisiones
                    if agent_positions.get(next_pos, 0) < 1:
                        old_pos = (agente.pos_x, agente.pos_y)
                        agente.mover_a(next_pos[0], next_pos[1])
                        if agente.if_change:
                            agente.path_index += 1
                    else:
                        agente.steps_without_moving = getattr(agente, 'steps_without_moving', 0) + 1
                        agente.ansiedad = min(100, agente.ansiedad + random.randint(2, 6))
                else:
                    agente.steps_without_moving = getattr(agente, 'steps_without_moving', 0) + 1
                    agente.ansiedad = min(100, agente.ansiedad + random.randint(2, 6))
                
                agente_estado['ansiedad'] = agente.ansiedad
                agente_estado['steps_without_moving'] = getattr(agente, 'steps_without_moving', 0)
                
                current_stuck = agente_estado['steps_without_moving']
                unlocked_count_actual = viz.ps.calculate_unlocked_paths(
                    steps_without_moving=current_stuck,
                    calmness_threshold=getattr(agente, 'calmness_threshold', 3)
                )
                agente_estado['unlocked_paths_count'] = unlocked_count_actual
                agente.unlocked_paths_count = unlocked_count_actual
                
                if not agente_estado.get('all_calculated_paths') and getattr(agente, 'all_calculated_paths', None):
                    agente_estado['all_calculated_paths'] = agente.all_calculated_paths
                
                if goal and agente.pos_x == goal[0] and agente.pos_y == goal[1]:
                    agente.activo = False
                
                agente_estado['activo'] = agente.activo
                estado_paso['agentes'].append(agente_estado)
            
            ansiedades_paso = [ag['ansiedad'] for ag in estado_paso['agentes'] if ag.get('activo', True)]
            ansiedad_promedio = np.mean(ansiedades_paso) if ansiedades_paso else 0
            viz.stats_ansiedad_historial.append(ansiedad_promedio)
            
            viz.historial.append(estado_paso)
            
            if all(not agente.activo for agente in viz.agentes):
                print(f"Todos los agentes evacuaron en paso {paso}")
                break
        
        print(f"Simulación completada: {len(viz.historial)} pasos")
        print(f"Desbloqueos de 3 rutas: {viz.stats_unlock_3}")
        print(f"Desbloqueos de 5 rutas: {viz.stats_unlock_5}")
    
    viz._simular_replaced = True
    viz._simular = _simular_caso_5_rutas
    viz._simular()
    
    viz.crear_visualizacion_interactiva()
    return viz


def _construir_visualizador_desde_pkl(ruta_pkl: str):
    """
    Crea un VisualizadorAnimacionRutas desde un historial PKL (dynamics.py).
    """
    with open(ruta_pkl, "rb") as f:
        historia_raw = pickle.load(f)

    if not isinstance(historia_raw, list) or not historia_raw:
        raise ValueError(f"Formato de historial inválido: {ruta_pkl}")

    config = historia_raw[-1] if isinstance(historia_raw[-1], dict) else {}
    frames_raw = [frame for frame in historia_raw if isinstance(frame, list)]
    if not frames_raw:
        raise ValueError(f"No se encontraron frames en: {ruta_pkl}")

    # Ajustar escenario global con metadatos del PKL cuando estén disponibles.
    if config:
        if "size_x" in config:
            esc.width = int(config["size_x"])
        if "size_y" in config:
            esc.height = int(config["size_y"])
        if "puertas" in config:
            esc.puertas = list(config["puertas"])
        if "obstacles" in config:
            esc.obstaculos = list(config["obstacles"])

    class _VisualizadorDesdePKL(VisualizadorAnimacionRutas):
        def __init__(self):
            self._simular_replaced = True
            super().__init__(num_agentes=1, max_pasos=1)

    viz = _VisualizadorDesdePKL()
    viz.ff = Floor_field(esc.width, esc.height, esc.puertas, esc.obstaculos)
    viz.ps = PathSelector(viz.ff)
    viz.agentes = []
    viz.historial = []
    viz.max_pasos = len(frames_raw)
    viz.current_step = 0
    viz.stats_unlock_3 = 0
    viz.stats_unlock_5 = 0
    viz.stats_ansiedad_historial = []

    for paso, frame in enumerate(frames_raw):
        estado_paso = {
            "paso": paso,
            "agentes": [],
            "rutas_calculadas": [],
            "rutas_recalculadas": [],
        }

        ansiedades_activas = []
        for a in frame:
            ansiedad = float(getattr(a, "ansiedad", 0.0) or 0.0)
            activo = bool(getattr(a, "activo", True))
            unlocked = int(getattr(a, "unlocked_paths_count", 1) or 1)
            estado_agente = {
                "id": int(getattr(a, "id", -1)),
                "x": getattr(a, "pos_x", None),
                "y": getattr(a, "pos_y", None),
                "tipo": getattr(a, "tipo", "lento"),
                "ansiedad": ansiedad,
                "current_path": getattr(a, "current_path", None),
                "path_index": int(getattr(a, "path_index", 0) or 0),
                "recalculado": False,
                "activo": activo,
                "all_calculated_paths": getattr(a, "all_calculated_paths", None),
                "unlocked_paths_count": unlocked,
                "trajectory_history": [],
            }
            estado_paso["agentes"].append(estado_agente)

            if unlocked == 3:
                viz.stats_unlock_3 += 1
            elif unlocked == 5:
                viz.stats_unlock_5 += 1

            if activo:
                ansiedades_activas.append(ansiedad)

        viz.stats_ansiedad_historial.append(float(np.mean(ansiedades_activas)) if ansiedades_activas else 0.0)
        viz.historial.append(estado_paso)

    return viz


def main():
    """Función principal con menú de casos de prueba."""
    import sys
    
    print("="*60)
    print("VISUALIZADOR INTERACTIVO DE RUTAS - CASOS DE PRUEBA")
    print("="*60)
    print("\nEste visualizador demuestra la logica de agent_extendido.py:")
    print("- Sistema de desbloqueo progresivo (1->3->5 rutas)")
    print("- Seleccion de rutas basada en ansiedad")
    print("- Recalculacion automatica cuando hay bloqueos")
    print("- Diferencia entre agentes rapidos y lentos")
    print("\nControles:")
    print("- Previous / Left Arrow: Retroceder un paso")
    print("- Play / Pause / Space: Reproducir/pausar animacion")
    print("- Next / Right Arrow: Avanzar un paso")
    print("- Step Slider: Saltar a cualquier paso")
    print("- Speed Slider: Ajustar velocidad de animacion (100-2000 ms)")
    print("\n" + "="*60)
    print("\nCASOS DE PRUEBA DISPONIBLES:")
    print("  1. Desbloqueo de 1 ruta")
    print("  2. Desbloqueo de 3 rutas y selección de otra ruta")
    print("  3. Desbloqueo de 5 rutas con colisiones")
    print("\n" + "="*60)
    
    # Si se pasa argumento, puede ser un caso (1-3) o un .pkl.
    if len(sys.argv) > 1:
        arg1 = sys.argv[1]
        if arg1.lower().endswith(".pkl") and os.path.exists(arg1):
            print(f"\nCargando historial desde PKL: {arg1}")
            viz = _construir_visualizador_desde_pkl(arg1)
            print(f"Frames cargados: {len(viz.historial)}")
            viz.crear_visualizacion_interactiva()
            return
        caso = arg1
    else:
        try:
            caso = input("\nSelecciona caso (1-3) o Enter para caso 1: ").strip()
        except (EOFError, KeyboardInterrupt):
            caso = "1"
        if not caso:
            caso = "1"
    
    casos = {
        "1": crear_caso_desbloqueo_1_ruta,
        "2": crear_caso_desbloqueo_3_rutas,
        "3": crear_caso_desbloqueo_5_rutas_colisiones
    }
    
    if caso in casos and casos[caso]:
        casos[caso]()
    else:
        print(f"\nCaso '{caso}' no valido. Usando caso 1 por defecto.")
        crear_caso_desbloqueo_1_ruta()


if __name__ == "__main__":
    main()
