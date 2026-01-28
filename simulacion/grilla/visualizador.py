"""
Sistema completo de visualización compatible con múltiples formatos PKL.
USO BÁSICO:
python visualizador.py historia.pkl
python visualizador.py historia.pkl interactivo
python visualizador.py historia.pkl completo
"""

import pickle
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.patches import Rectangle, Circle, Patch
from matplotlib.lines import Line2D
from matplotlib.widgets import Button, Slider
from pathlib import Path
from typing import Dict, List, Tuple, Any
from dataclasses import dataclass
import warnings
warnings.filterwarnings('ignore')

@dataclass
class EstadoAgente:
    """Estado de un agente en un momento dado"""
    id: int
    x: int
    y: int
    tipo: str
    activo: bool
    conflictos_totales: int = 0
    conflictos_perdidos: int = 0
    ansiedad: float = 0  # Changed to float for consistency
    current_path: List[Tuple[int, int]] = None  # Ruta planificada A*
    all_calculated_paths: List[List[Tuple[int, int]]] = None  # Todas las rutas calculadas (hasta 5)
    unlocked_paths_count: int = 1  # Número de rutas desbloqueadas (1, 3, o 5)
    current_path_index: int = 0  # Posición actual en la ruta
    steps_without_moving: int = 0  # Pasos consecutivos sin moverse


def _get_stats_field(stats, new_name: str, old_name: str, default=0):
    """
    Helper function to get statistics field with backward compatibility.
    
    Args:
        stats: EstadisticasPaso object
        new_name: New field name (e.g., 'rapidos_activos')
        old_name: Old field name (e.g., 'vivos_activos')
        default: Default value if neither exists
    
    Returns:
        Field value
    """
    return getattr(stats, new_name, getattr(stats, old_name, default))


@dataclass  
class EstadisticasPaso:
    """Estadísticas de un paso de simulación"""
    paso: int
    rapidos_activos: int
    lentos_activos: int
    rapidos_evacuados: int
    lentos_evacuados: int
    conflictos_en_paso: int
    agentes_en_conflicto: int


class VisualizadorSimulacion:
    """
    Visualizador universal para simulaciones de evacuación.
    Formatos soportados:
    - AgentExtendido: Agent.history (lista de listas + dict config)
    - SimulationLogger: dict con 'configuracion', 'historial_agentes', etc.
    """

    COLORES = {
        'rapido': '#00FF00',        # Verde brillante
        'lento': '#FF0000',  # Rojo
        'obstaculo': '#000000',   # Negro
        'puerta': '#FFD700',      # Dorado
        'vacio': '#FFFFFF',       # Blanco
        'floor_field': '#E0E0E0', # Gris claro
        'agent_0': '#FF6B6B',
        'agent_1': '#4ECDC4',
        'agent_2': '#45B7D1',
        'agent_3': '#FFA07A',
        'agent_4': '#98D8C8'
    }
    
    def __init__(self, archivo_pkl: str):
        """
        Inicializa cargando datos desde PKL.
        archivo_pkl : str
            Ruta al archivo .pkl con datos de simulación
        """
        self.archivo_pkl = archivo_pkl
        self.datos = None
        self.configuracion = None
        self.historial_agentes = None
        self.historial_estadisticas = None
        self.formato = None
        self._cargar_datos()
    
    def _cargar_datos(self):
        """Carga y detecta formato automáticamente"""
        try:
            # Import classes that might be needed for pickle deserialization
            import sys
            import os
            
            # Add parent directories to path
            current_dir = os.path.dirname(os.path.abspath(__file__))
            parent_dir = os.path.dirname(current_dir)
            root_dir = os.path.dirname(parent_dir)
            
            for dir_path in [root_dir, parent_dir, current_dir]:
                if dir_path not in sys.path:
                    sys.path.insert(0, dir_path)
            
            # Import classes that pickle might need (with fallback)
            try:
                from simulacion.grilla.simulacion_logger import EstadoAgente as EstadoAgenteLogger, EstadisticasPaso as EstadisticasPasoLogger
            except ImportError:
                try:
                    from simulacion_logger import EstadoAgente as EstadoAgenteLogger, EstadisticasPaso as EstadisticasPasoLogger
                except ImportError:
                    pass  # Will use local EstadoAgente if needed
            
            # Custom unpickler to handle module path issues
            class CustomUnpickler(pickle.Unpickler):
                def find_class(self, module, name):
                    # Handle simulacion_logger imports
                    if module == 'simulacion_logger':
                        try:
                            from simulacion.grilla.simulacion_logger import EstadoAgente, EstadisticasPaso
                            if name == 'EstadoAgente':
                                return EstadoAgente
                            elif name == 'EstadisticasPaso':
                                return EstadisticasPaso
                        except ImportError:
                            pass
                    # Fallback to default behavior
                    return super().find_class(module, name)
            
            with open(self.archivo_pkl, 'rb') as f:
                try:
                    unpickler = CustomUnpickler(f)
                    datos_raw = unpickler.load()
                except Exception:
                    # Fallback to standard pickle if custom unpickler fails
                    f.seek(0)
                    datos_raw = pickle.load(f)
            
            # Detección de formato
            if isinstance(datos_raw, dict) and 'configuracion' in datos_raw:
                # Formato SimulationLogger
                self.formato = 'simulacion_logger'
                self._cargar_formato_simulacion_logger(datos_raw)
            
            elif isinstance(datos_raw, list):
                # Formato AgentExtendido (Agent.history)
                self.formato = 'agent_extendido'
                self._cargar_formato_agent_extendido(datos_raw)
            
            else:
                raise ValueError("Formato PKL no reconocido")
            
            print(f"Datos cargados exitosamente")
            print(f"Archivo: {self.archivo_pkl}")
            print(f"Formato: {self.formato}")
            print(f"Pasos: {len(self.historial_agentes)}")
            print(f"Agentes: {len(self.historial_agentes[0])}")
            
            # Mostrar información de evacuados del último paso
            if self.historial_estadisticas:
                stats_final = self.historial_estadisticas[-1]
                # Handle both old and new field names
                rapidos_evac = getattr(stats_final, 'rapidos_evacuados', 
                                      getattr(stats_final, 'vivos_evacuados', 0))
                lentos_evac = getattr(stats_final, 'lentos_evacuados',
                                     getattr(stats_final, 'menos_vivos_evacuados', 0))
                total_evacuados = rapidos_evac + lentos_evac
                print(f"\nEvacuados en último paso:")
                print(f"Rapidos: {rapidos_evac}")
                print(f"Lentos: {lentos_evac}")
                print(f"Total: {total_evacuados}")
        
        except FileNotFoundError:
            raise FileNotFoundError(f"No se encontró: {self.archivo_pkl}")
        except Exception as e:
            raise ValueError(f"Error al cargar: {e}")
    
    def _cargar_formato_simulacion_logger(self, datos: dict):
        """
        Carga formato SimulationLogger (dict complejo).
        Convierte EstadoAgente del logger a formato interno con current_path.
        """
        self.configuracion = datos['configuracion']
        
        # Convertir historial_agentes si es necesario para incluir current_path
        historial_raw = datos['historial_agentes']
        self.historial_agentes = []
        
        for paso_agentes in historial_raw:
            estados_paso = []
            for agent_estado in paso_agentes:
                # Si ya es EstadoAgente, usar directamente
                if isinstance(agent_estado, EstadoAgente):
                    estados_paso.append(agent_estado)
                else:
                    # Convertir desde dataclass o dict con compatibilidad hacia atrás
                    # Helper function para obtener atributos con valores por defecto
                    def get_attr_safe(obj, attr, default):
                        if isinstance(obj, dict):
                            return obj.get(attr, default)
                        return getattr(obj, attr, default)
                    
                    estado = EstadoAgente(
                        id=get_attr_safe(agent_estado, 'id', 0),
                        x=get_attr_safe(agent_estado, 'x', 0),
                        y=get_attr_safe(agent_estado, 'y', 0),
                        tipo=get_attr_safe(agent_estado, 'tipo', 'rapido'),
                        activo=get_attr_safe(agent_estado, 'activo', True),
                        conflictos_totales=get_attr_safe(agent_estado, 'conflictos_totales', 0),
                        conflictos_perdidos=get_attr_safe(agent_estado, 'conflictos_perdidos', 0),
                        ansiedad=get_attr_safe(agent_estado, 'ansiedad', 0),
                        # NEW FIELDS with backward compatibility:
                        current_path=get_attr_safe(agent_estado, 'current_path', None),
                        all_calculated_paths=get_attr_safe(agent_estado, 'all_calculated_paths', None),
                        unlocked_paths_count=get_attr_safe(agent_estado, 'unlocked_paths_count', 1),
                        current_path_index=get_attr_safe(agent_estado, 'current_path_index', 
                                                         get_attr_safe(agent_estado, 'path_index', 0)),  # Support both names
                        steps_without_moving=get_attr_safe(agent_estado, 'steps_without_moving', 0)
                    )
                    estados_paso.append(estado)
            self.historial_agentes.append(estados_paso)
        
        self.historial_estadisticas = datos['historial_estadisticas']
    
    def _cargar_formato_agent_extendido(self, datos: list):
        """
        Convierte formato AgentExtendido a formato interno.
        Formato entrada: [paso0, paso1, ..., pasoN, config_dict]
        """
        # Último elemento = configuración
        config_dict = datos[-1]
        historia_agentes = datos[:-1]
        
        # Extraer configuración
        self.configuracion = {
            'width': config_dict.get('size_x', 10),
            'height': config_dict.get('size_y', 10),
            'obstaculos': config_dict.get('obstacles', []),
            'puertas': config_dict.get('puertas', [])
        }
        
        # Convertir historia paso a paso
        self.historial_agentes = []
        self.historial_estadisticas = []
        
        for paso_idx, paso_agentes in enumerate(historia_agentes):
            # Procesar agentes del paso
            estados_paso = []
            rapidos_activos = 0
            lentos_activos = 0
            rapidos_evacuados = 0
            lentos_evacuados = 0
            
            for agent in paso_agentes:
                # Determinar tipo (con fallback)
                tipo = getattr(agent, 'tipo', 
                              getattr(agent, 'agent_type', 'rapido'))
                
                # Verificar si está activo
                # Usar getattr con default True, pero también verificar explícitamente
                activo = getattr(agent, 'activo', True)
                
                # Debug: verificar si el atributo existe y su valor
                # (comentado para producción, descomentar si hay problemas)
                # if paso_idx == len(historia_agentes) - 1:  # Último paso
                #     print(f"Agente {getattr(agent, 'id', '?')}: activo={activo}, tipo={tipo}, hasattr_activo={hasattr(agent, 'activo')}")
                
                # Contar por categoría
                if tipo == 'rapido':
                    if activo:
                        rapidos_activos += 1
                    else:
                        rapidos_evacuados += 1
                elif tipo == 'lento':
                    if activo:
                        lentos_activos += 1
                    else:
                        lentos_evacuados += 1
                
                # Obtener posiciones con validación
                pos_x = getattr(agent, 'pos_x', None)
                pos_y = getattr(agent, 'pos_y', None)
                
                # Si las posiciones son None, usar valores por defecto (0,0) pero marcar como no activo
                if pos_x is None or pos_y is None:
                    pos_x = pos_x if pos_x is not None else 0
                    pos_y = pos_y if pos_y is not None else 0
                    # Si no tiene posición, probablemente no debería estar activo
                    if pos_x == 0 and pos_y == 0 and not hasattr(agent, 'pos_x'):
                        activo = False
                
                # Obtener ruta planificada si existe
                current_path = getattr(agent, 'current_path', None)
                # Si no existe current_path, intentar con ruta_planificada (compatibilidad)
                if current_path is None:
                    current_path = getattr(agent, 'ruta_planificada', None)
                
                # Obtener todas las rutas calculadas y número de rutas desbloqueadas
                all_calculated_paths = getattr(agent, 'all_calculated_paths', None)
                unlocked_paths_count = getattr(agent, 'unlocked_paths_count', 1)
                
                # Si all_calculated_paths es None pero hay alternative_paths, usar esos
                if all_calculated_paths is None:
                    alternative_paths = getattr(agent, 'alternative_paths', None)
                    if alternative_paths:
                        all_calculated_paths = alternative_paths
                
                # Obtener índice de ruta actual y pasos sin moverse
                current_path_index = getattr(agent, 'current_path_index', 
                                            getattr(agent, 'path_index', 0))
                steps_without_moving = getattr(agent, 'steps_without_moving', 0)
                
                # Crear estado con todos los campos nuevos
                estado = EstadoAgente(
                    id=getattr(agent, 'id', len(estados_paso)),
                    x=pos_x,
                    y=pos_y,
                    tipo=tipo,
                    activo=activo,
                    conflictos_totales=getattr(agent, 'conflictos_totales', 0),
                    conflictos_perdidos=getattr(agent, 'conflictos_perdidos', 0),
                    ansiedad=getattr(agent, 'ansiedad', 0),
                    current_path=current_path,
                    all_calculated_paths=all_calculated_paths,
                    unlocked_paths_count=unlocked_paths_count if unlocked_paths_count >= 1 else 1,
                    current_path_index=current_path_index,
                    steps_without_moving=steps_without_moving
                )
                estados_paso.append(estado)
            
            self.historial_agentes.append(estados_paso)
            
            # Crear estadísticas del paso
            stats = EstadisticasPaso(
                paso=paso_idx,
                rapidos_activos=rapidos_activos,
                lentos_activos=lentos_activos,
                rapidos_evacuados=rapidos_evacuados,
                lentos_evacuados=lentos_evacuados,
                conflictos_en_paso=0,
                agentes_en_conflicto=0
            )
            self.historial_estadisticas.append(stats)
    
    def crear_animacion_interactiva(self, show_paths: bool = False):
        """
        Crea animación interactiva con controles.
        
        Parámetros:
        show_paths : bool
            Si True, muestra las rutas planificadas A* de los agentes
        """
        fig = plt.figure(figsize=(16, 12))
        title = 'Simulación de Evacuación - Visualizador Interactivo'
        if show_paths:
            title += ' (Rutas A* visibles)'
        fig.suptitle(title, fontsize=16, weight='bold')
        # Layout con gridspec
        gs = fig.add_gridspec(20, 20, hspace=0.3, wspace=0.3)
        # Áreas principales
        ax_main = fig.add_subplot(gs[0:15, 0:14])   # Animación
        ax_info = fig.add_subplot(gs[0:15, 14:20])  # Panel info
        # Controles (fila inferior)
        ax_play = fig.add_subplot(gs[16, 1:3])
        ax_prev = fig.add_subplot(gs[16, 4:6])
        ax_next = fig.add_subplot(gs[16, 7:9])
        ax_reset = fig.add_subplot(gs[16, 10:12])
        ax_slider_paso = fig.add_subplot(gs[17, 1:13])
        ax_slider_vel = fig.add_subplot(gs[18, 1:13])
        # Estado de animación
        state = {
            'current_frame': 0,
            'playing': False,
            'interval': 500  # milisegundos
        }
        
        # Datos de configuración
        width = self.configuracion['width']
        height = self.configuracion['height']
        puertas = self.configuracion['puertas']
        obstaculos = self.configuracion['obstaculos']
        max_frames = len(self.historial_agentes) - 1
        
        # Crear botones
        btn_play = Button(ax_play, '▶ Play', color='lightgreen')
        btn_prev = Button(ax_prev, '⏮ Ant', color='lightblue')
        btn_next = Button(ax_next, 'Sig ⏭', color='lightblue')
        btn_reset = Button(ax_reset, '⏹ Reset', color='salmon')
        
        # Crear sliders
        slider_paso = Slider(
            ax_slider_paso, 'Paso', 0, max_frames,
            valinit=0, valstep=1, color='steelblue'
        )
        
        slider_vel = Slider(
            ax_slider_vel, 'Velocidad (ms)', 100, 2000,
            valinit=500, valstep=50, color='orange'
        )
        
        def actualizar_frame(frame_num):
            """Renderiza un frame específico"""
            ax_main.clear()
            ax_info.clear()
            
            # Configurar área principal
            ax_main.set_xlim(-0.5, width - 0.5)
            ax_main.set_ylim(-0.5, height - 0.5)
            ax_main.set_aspect('equal')
            ax_main.invert_yaxis()
            
            # Dibujar grilla
            for i in range(width + 1):
                ax_main.axvline(i - 0.5, color='lightgray', linewidth=0.5)
            for j in range(height + 1):
                ax_main.axhline(j - 0.5, color='lightgray', linewidth=0.5)
            
            # Dibujar obstáculos
            for x, y in obstaculos:
                rect = Rectangle(
                    (x-0.5, y-0.5), 1, 1,
                    facecolor=self.COLORES['obstaculo'],
                    edgecolor='black', linewidth=1
                )
                ax_main.add_patch(rect)
            
            # Dibujar puertas
            for x, y in puertas:
                rect = Rectangle(
                    (x-0.5, y-0.5), 1, 1,
                    facecolor=self.COLORES['puerta'],
                    edgecolor='orange', linewidth=2
                )
                ax_main.add_patch(rect)
            
            # Obtener datos del frame
            # Asegurarse de que el índice esté dentro del rango válido
            if frame_num >= len(self.historial_agentes):
                frame_num = len(self.historial_agentes) - 1
            if frame_num < 0:
                frame_num = 0
                
            estados = self.historial_agentes[frame_num]
            stats = self.historial_estadisticas[frame_num]
            
            # Dibujar rutas si está habilitado
            if show_paths:
                # Use new multi-level path visualization
                for estado in estados:
                    if not estado.activo:
                        continue
                    
                    # Get all calculated paths for this agent
                    all_paths = estado.all_calculated_paths if estado.all_calculated_paths else []
                    unlocked_count = estado.unlocked_paths_count if estado.unlocked_paths_count >= 1 else 1
                    current_path = estado.current_path
                    
                    if not all_paths:
                        # Fallback: if no all_calculated_paths but has current_path, show that
                        if current_path:
                            all_paths = [current_path]
                            unlocked_count = 1
                        else:
                            continue
                    
                    # Draw all unlocked paths
                    for i, path in enumerate(all_paths[:unlocked_count]):
                        if not path or len(path) == 0:
                            continue
                        
                        # Check if this is the current path
                        is_current = (path == current_path) or (current_path and len(path) == len(current_path) and 
                                                               path[0] == current_path[0] and path[-1] == current_path[-1])
                        
                        # Visual properties
                        alpha = 0.7 if is_current else 0.25  # Current path more visible
                        linewidth = 2.5 if is_current else 1.2
                        linestyle = '-' if is_current else '--'
                        
                        # Color based on path index or anxiety
                        if is_current:
                            color = self._get_color_by_anxiety(estado.ansiedad)
                        else:
                            color = self._get_path_color(i, unlocked_count)
                        
                        # Draw path
                        if len(path) > 1:
                            xs, ys = zip(*path)
                            ax_main.plot(xs, ys, color=color, alpha=alpha, linewidth=linewidth,
                                       linestyle=linestyle, zorder=1)
                        else:
                            # Single point path
                            ax_main.plot(path[0][0], path[0][1], 'o', color=color, 
                                       markersize=4, alpha=alpha, zorder=2)
            
            # Dibujar agentes activos
            for estado in estados:
                # Solo dibujar si está activo y tiene posición válida
                if estado.activo and estado.x is not None and estado.y is not None:
                    # Verificar que la posición esté dentro del rango del escenario
                    if 0 <= estado.x < width and 0 <= estado.y < height:
                        # Determinar color según tipo
                        if estado.tipo in self.COLORES:
                            color = self.COLORES[estado.tipo]
                        else:
                            # Para tipos genéricos
                            color = self.COLORES.get(
                                f'agent_{estado.id % 5}',
                                '#888888'
                            )
                        
                        # Círculo del agente
                        circle = Circle(
                            (estado.x, estado.y), 0.35,
                            color=color, alpha=0.8, zorder=10
                        )
                        ax_main.add_patch(circle)
                        
                        # ID del agente
                        ax_main.text(
                            estado.x, estado.y, str(estado.id),
                            ha='center', va='center',
                            fontsize=8, color='white',
                            weight='bold', zorder=11
                        )
            
            # Título con info clave (con compatibilidad hacia atrás)
            rapidos_activos = _get_stats_field(stats, 'rapidos_activos', 'vivos_activos', 0)
            lentos_activos = _get_stats_field(stats, 'lentos_activos', 'menos_vivos_activos', 0)
            rapidos_evacuados = _get_stats_field(stats, 'rapidos_evacuados', 'vivos_evacuados', 0)
            lentos_evacuados = _get_stats_field(stats, 'lentos_evacuados', 'menos_vivos_evacuados', 0)
            total_activos = rapidos_activos + lentos_activos
            total_evacuados = rapidos_evacuados + lentos_evacuados
            
            ax_main.set_title(
                f'Paso: {frame_num}/{max_frames} | '
                f'Activos: {total_activos} | '
                f'Evacuados: {total_evacuados}',
                fontsize=13, weight='bold', pad=10
            )
            
            ax_main.set_xlabel('X', fontsize=11)
            ax_main.set_ylabel('Y', fontsize=11)
            
            # ═══ PANEL DE INFORMACIÓN ═══
            ax_info.axis('off')
            
            total_agentes = len(estados)
            porcentaje_evacuado = (total_evacuados / total_agentes * 100) if total_agentes > 0 else 0
            
            info_text = f""" PASO {frame_num:3d}/{max_frames:3d}     
                AGENTES RAPIDOS:
                Activos: {_get_stats_field(stats, 'rapidos_activos', 'vivos_activos', 0)}
                Evacuados: {_get_stats_field(stats, 'rapidos_evacuados', 'vivos_evacuados', 0)}

                AGENTES LENTOS:
                Activos: {_get_stats_field(stats, 'lentos_activos', 'menos_vivos_activos', 0)}
                Evacuados: {_get_stats_field(stats, 'lentos_evacuados', 'menos_vivos_evacuados', 0)}

                CONFLICTOS:
                En este paso: {stats.conflictos_en_paso}
                Agentes involucrados: {stats.agentes_en_conflicto}

                PROGRESO GLOBAL:
                Total agentes: {total_agentes}
                Evacuados: {total_evacuados}
                Porcentaje: {porcentaje_evacuado:.1f}%

                FORMATO: {self.formato:12s} 

                """
            
            ax_info.text(
                0.05, 0.95, info_text,
                transform=ax_info.transAxes,
                fontsize=10, verticalalignment='top',
                family='monospace',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3)
            )
            
            # Leyenda
            from matplotlib.patches import Patch
            leyenda_items = []
            
            # Detectar tipos presentes
            tipos_presentes = set(e.tipo for e in estados)
            
            for tipo in sorted(tipos_presentes):
                if tipo in self.COLORES:
                    leyenda_items.append(
                        Patch(facecolor=self.COLORES[tipo], 
                             label=tipo.replace('_', ' ').capitalize())
                    )
            
            leyenda_items.extend([
                Patch(facecolor=self.COLORES['puerta'], label='Puerta'),
                Patch(facecolor=self.COLORES['obstaculo'], label='Obstáculo')
            ])
            
            ax_main.legend(
                handles=leyenda_items,
                loc='upper right',
                fontsize=9,
                framealpha=0.9
            )
            
            fig.canvas.draw_idle()
        
        
        def on_play(event):
            """Toggle Play/Pause"""
            state['playing'] = not state['playing']
            if state['playing']:
                btn_play.label.set_text('⏸ Pause')
                btn_play.color = 'lightyellow'
            else:
                btn_play.label.set_text('▶ Play')
                btn_play.color = 'lightgreen'
            fig.canvas.draw_idle()
        
        def on_prev(event):
            """Paso anterior"""
            if state['current_frame'] > 0:
                state['current_frame'] -= 1
                slider_paso.set_val(state['current_frame'])
                actualizar_frame(state['current_frame'])
        
        def on_next(event):
            """Paso siguiente"""
            if state['current_frame'] < max_frames:
                state['current_frame'] += 1
                slider_paso.set_val(state['current_frame'])
                actualizar_frame(state['current_frame'])
        
        def on_reset(event):
            """Volver al inicio"""
            state['current_frame'] = 0
            state['playing'] = False
            btn_play.label.set_text('▶ Play')
            btn_play.color = 'lightgreen'
            slider_paso.set_val(0)
            actualizar_frame(0)
        
        def on_slider_paso(val):
            """Cambio en slider de paso"""
            state['current_frame'] = int(val)
            actualizar_frame(state['current_frame'])
        
        def on_slider_vel(val):
            """Cambio en slider de velocidad"""
            state['interval'] = int(val)
        
        # Conectar eventos
        btn_play.on_clicked(on_play)
        btn_prev.on_clicked(on_prev)
        btn_next.on_clicked(on_next)
        btn_reset.on_clicked(on_reset)
        slider_paso.on_changed(on_slider_paso)
        slider_vel.on_changed(on_slider_vel)
        
        
        def animate(frame):
            """Bucle de animación automática"""
            if state['playing']:
                if state['current_frame'] < max_frames:
                    state['current_frame'] += 1
                else:
                    state['current_frame'] = 0
                
                slider_paso.set_val(state['current_frame'])
                actualizar_frame(state['current_frame'])
            
            return []
        
        anim = animation.FuncAnimation(
            fig, animate,
            frames=max_frames + 1,
            interval=500,
            repeat=True,
            blit=False
        )
        
        # Frame inicial
        actualizar_frame(0)
        
        plt.tight_layout()
        plt.show()
        
        return anim
    
    def crear_animacion(self, intervalo: int = 200, guardar_video: bool = False,
                       nombre_video: str = 'simulacion.mp4', show_paths: bool = False):
        """
        Animación simple sin controles.
        
        Parámetros:
        intervalo : int
            Intervalo entre frames en milisegundos
        guardar_video : bool
            Si True, guarda el video en archivo
        nombre_video : str
            Nombre del archivo de video
        show_paths : bool
            Si True, muestra las rutas planificadas A* de los agentes
        """
        fig, ax = plt.subplots(figsize=(12, 10))
        
        width = self.configuracion['width']
        height = self.configuracion['height']
        puertas = self.configuracion['puertas']
        obstaculos = self.configuracion['obstaculos']
        
        def actualizar_frame(paso):
            ax.clear()
            ax.set_xlim(-0.5, width - 0.5)
            ax.set_ylim(-0.5, height - 0.5)
            ax.set_aspect('equal')
            ax.invert_yaxis()
            
            # Grilla
            for i in range(width + 1):
                ax.axvline(i - 0.5, color='lightgray', linewidth=0.5)
            for j in range(height + 1):
                ax.axhline(j - 0.5, color='lightgray', linewidth=0.5)
            
            # Obstáculos
            for x, y in obstaculos:
                rect = Rectangle((x-0.5, y-0.5), 1, 1,
                               facecolor=self.COLORES['obstaculo'],
                               edgecolor='black', linewidth=1)
                ax.add_patch(rect)
            
            # Puertas
            for x, y in puertas:
                rect = Rectangle((x-0.5, y-0.5), 1, 1,
                               facecolor=self.COLORES['puerta'],
                               edgecolor='orange', linewidth=2)
                ax.add_patch(rect)
            
            # Agentes y rutas
            estados = self.historial_agentes[paso]
            stats = self.historial_estadisticas[paso]
            
            # Primero dibujar rutas si está habilitado
            if show_paths:
                for estado in estados:
                    if estado.activo and estado.current_path is not None:
                        path = estado.current_path
                        if len(path) > 1:
                            anxiety = estado.ansiedad
                            color = self._get_color_by_anxiety(anxiety)
                            xs, ys = zip(*path)
                            ax.plot(xs, ys, color=color, alpha=0.4, linewidth=1.5,
                                   linestyle='--', zorder=1)
            
            # Luego dibujar agentes
            for estado in estados:
                # Solo dibujar si está activo y tiene posición válida
                if estado.activo and estado.x is not None and estado.y is not None:
                    # Verificar que la posición esté dentro del rango del escenario
                    if 0 <= estado.x < width and 0 <= estado.y < height:
                        color = self.COLORES.get(estado.tipo, '#888888')
                        
                        circle = Circle((estado.x, estado.y), 0.35,
                                       color=color, alpha=0.8, zorder=10)
                        ax.add_patch(circle)
                        
                        ax.text(estado.x, estado.y, str(estado.id),
                               ha='center', va='center', fontsize=8,
                               color='white', weight='bold', zorder=11)
            
            rapidos_activos = _get_stats_field(stats, 'rapidos_activos', 'vivos_activos', 0)
            lentos_activos = _get_stats_field(stats, 'lentos_activos', 'menos_vivos_activos', 0)
            total_activos = rapidos_activos + lentos_activos
            title = f'Paso: {paso} | Activos: {total_activos}'
            if show_paths:
                title += ' | Rutas A* mostradas'
            ax.set_title(title, fontsize=14, weight='bold')
            
            ax.set_xlabel('X', fontsize=12)
            ax.set_ylabel('Y', fontsize=12)
        
        anim = animation.FuncAnimation(
            fig, actualizar_frame,
            frames=len(self.historial_agentes),
            interval=intervalo,
            repeat=True
        )
        
        if guardar_video:
            print(f"Guardando video: {nombre_video}")
            Writer = animation.writers['ffmpeg']
            writer = Writer(fps=5, metadata=dict(artist='Evacuacion'), bitrate=1800)
            anim.save(nombre_video, writer=writer)
            print(f"Video guardado exitosamente")
        
        plt.tight_layout()
        plt.show()
        
        return anim
    
    def _get_color_by_anxiety(self, anxiety_level: float) -> str:
        """
        Retorna color basado en nivel de ansiedad.
        
        Parámetros:
        anxiety_level : float
            Nivel de ansiedad (0-100)
            
        Returns:
        str : Color en formato matplotlib (nombre o hex)
        """
        if anxiety_level < 30:
            return 'green'  # Baja ansiedad
        elif anxiety_level < 70:
            return 'yellow'  # Ansiedad óptima
        else:
            return 'red'  # Alta ansiedad/pánico
    
    def visualizar_rutas_agentes(self, frame_index: int, output_file: str = None):
        """
        Visualiza las rutas planificadas de los agentes en un frame específico.
        
        Parámetros:
        frame_index : int
            Índice del frame a visualizar
        output_file : str, opcional
            Ruta para guardar la imagen. Si None, muestra la figura.
        """
        if frame_index < 0 or frame_index >= len(self.historial_agentes):
            raise ValueError(f"Frame index {frame_index} fuera de rango [0, {len(self.historial_agentes)-1}]")
        
        frame = self.historial_agentes[frame_index]
        
        fig, ax = plt.subplots(figsize=(14, 12))
        
        width = self.configuracion['width']
        height = self.configuracion['height']
        puertas = self.configuracion['puertas']
        obstaculos = self.configuracion['obstaculos']
        
        # Configurar ejes
        ax.set_xlim(-0.5, width - 0.5)
        ax.set_ylim(-0.5, height - 0.5)
        ax.set_aspect('equal')
        ax.invert_yaxis()
        
        # Dibujar grilla
        for i in range(width + 1):
            ax.axvline(i - 0.5, color='lightgray', linewidth=0.5, alpha=0.3)
        for j in range(height + 1):
            ax.axhline(j - 0.5, color='lightgray', linewidth=0.5, alpha=0.3)
        
        # Floor field background (si está disponible en datos)
        # Intentar obtener floor_field desde configuración o datos
        ff_data = None
        if hasattr(self, 'datos') and self.datos:
            ff_data = self.datos.get('floor_field')
        if ff_data is None and hasattr(self, 'configuracion'):
            ff_data = self.configuracion.get('floor_field')
        
        if ff_data is not None:
            # ff_data debería ser un array numpy 2D
            if isinstance(ff_data, np.ndarray):
                ax.imshow(ff_data, cmap='gray_r', alpha=0.2, 
                         extent=[-0.5, width - 0.5, height - 0.5, -0.5],
                         origin='upper')
        
        # Dibujar obstáculos
        for x, y in obstaculos:
            rect = Rectangle(
                (x-0.5, y-0.5), 1, 1,
                facecolor=self.COLORES['obstaculo'],
                edgecolor='black', linewidth=1
            )
            ax.add_patch(rect)
        
        # Dibujar puertas
        for x, y in puertas:
            rect = Rectangle(
                (x-0.5, y-0.5), 1, 1,
                facecolor=self.COLORES['puerta'],
                edgecolor='orange', linewidth=2
            )
            ax.add_patch(rect)
            ax.text(x, y, 'P', ha='center', va='center', 
                   fontsize=12, weight='bold', color='black')
        
        # Dibujar rutas de cada agente activo
        routes_drawn = 0
        for agent_data in frame:
            if agent_data.activo and agent_data.current_path is not None:
                path = agent_data.current_path
                if len(path) > 0:
                    anxiety = agent_data.ansiedad
                    
                    # Color basado en ansiedad
                    color = self._get_color_by_anxiety(anxiety)
                    
                    # Dibujar ruta
                    if len(path) > 1:
                        xs, ys = zip(*path)
                        ax.plot(xs, ys, color=color, alpha=0.6, linewidth=2,
                               linestyle='--', marker='o', markersize=4,
                               label=f'Agente {agent_data.id}' if routes_drawn < 5 else '')
                    else:
                        # Ruta de un solo punto
                        ax.plot(path[0][0], path[0][1], 'o', color=color, markersize=6)
                    
                    # Marcar posición actual del agente
                    pos = (agent_data.x, agent_data.y)
                    ax.plot(pos[0], pos[1], 'o', color=color, markersize=10,
                           markeredgecolor='black', markeredgewidth=1.5)
                    
                    # Etiqueta del agente
                    ax.text(pos[0], pos[1] + 0.3, str(agent_data.id),
                           ha='center', va='bottom', fontsize=8,
                           weight='bold', color='black',
                           bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.7))
                    
                    routes_drawn += 1
        
        # Título
        stats = self.historial_estadisticas[frame_index]
        total_activos = stats.rapidos_activos + stats.lentos_activos
        ax.set_title(
            f'Rutas Planificadas A* - Paso {frame_index}\n'
            f'Agentes activos: {total_activos} | Rutas mostradas: {routes_drawn}',
            fontsize=14, weight='bold'
        )
        
        ax.set_xlabel('X Coordinate', fontsize=12)
        ax.set_ylabel('Y Coordinate', fontsize=12)
        ax.grid(True, alpha=0.3)
        
        # Leyenda de colores por ansiedad
        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor='green', label='Baja ansiedad (0-30)'),
            Patch(facecolor='yellow', label='Ansiedad óptima (30-70)'),
            Patch(facecolor='red', label='Alta ansiedad (70-100)'),
            Patch(facecolor=self.COLORES['puerta'], label='Puerta'),
            Patch(facecolor=self.COLORES['obstaculo'], label='Obstáculo')
        ]
        ax.legend(handles=legend_elements, loc='upper left', fontsize=9)
        
        plt.tight_layout()
        
        if output_file:
            plt.savefig(output_file, dpi=150, bbox_inches='tight')
            print(f"Visualización guardada en: {output_file}")
            plt.close()
        else:
            plt.show()
    
    def _dibujar_floor_field(self, ax):
        """
        Helper method to draw floor field as background.
        
        Args:
            ax: Matplotlib axis
        """
        width = self.configuracion['width']
        height = self.configuracion['height']
        puertas = self.configuracion['puertas']
        obstaculos = self.configuracion['obstaculos']
        
        # Configurar ejes
        ax.set_xlim(-0.5, width - 0.5)
        ax.set_ylim(-0.5, height - 0.5)
        ax.set_aspect('equal')
        ax.invert_yaxis()
        
        # Dibujar grilla
        for i in range(width + 1):
            ax.axvline(i - 0.5, color='lightgray', linewidth=0.5, alpha=0.3)
        for j in range(height + 1):
            ax.axhline(j - 0.5, color='lightgray', linewidth=0.5, alpha=0.3)
        
        # Dibujar obstáculos
        for x, y in obstaculos:
            rect = Rectangle(
                (x-0.5, y-0.5), 1, 1,
                facecolor=self.COLORES['obstaculo'],
                edgecolor='black', linewidth=1
            )
            ax.add_patch(rect)
        
        # Dibujar puertas
        for x, y in puertas:
            rect = Rectangle(
                (x-0.5, y-0.5), 1, 1,
                facecolor=self.COLORES['puerta'],
                edgecolor='orange', linewidth=2
            )
            ax.add_patch(rect)
            ax.text(x, y, 'P', ha='center', va='center', 
                   fontsize=12, weight='bold', color='black')
    
    def _get_path_color(self, path_index: int, total_unlocked: int) -> str:
        """
        Get color for path based on its index.
        
        Args:
            path_index: Index of the path (0 = optimal, 1-4 = alternatives)
            total_unlocked: Total number of unlocked paths
        
        Returns:
            Color string for matplotlib
        """
        colors = {
            0: 'green',    # Optimal path
            1: 'yellow',   # Alternative 1
            2: 'orange',   # Alternative 2
            3: 'red',      # Alternative 3
            4: 'purple'    # Alternative 4
        }
        return colors.get(path_index, 'gray')
    
    def _get_agent_color(self, estado: EstadoAgente) -> str:
        """
        Get agent color based on type.
        
        Args:
            estado: EstadoAgente instance
        
        Returns:
            Color string for matplotlib
        """
        return 'lightgreen' if estado.tipo == 'rapido' else 'lightcoral'
    
    def _add_paths_legend(self, ax):
        """
        Add legend explaining path visualization.
        
        Args:
            ax: Matplotlib axis
        """
        legend_elements = [
            Line2D([0], [0], color='green', lw=3, label='Optimal Path (Current)', alpha=0.9),
            Line2D([0], [0], color='yellow', lw=1.5, linestyle='--', label='Alternative Path', alpha=0.3),
            Line2D([0], [0], marker='o', color='w', markerfacecolor='lightgreen', 
                  markersize=10, label='Fast Agent', markeredgecolor='black'),
            Line2D([0], [0], marker='o', color='w', markerfacecolor='lightcoral', 
                  markersize=10, label='Slow Agent', markeredgecolor='black'),
            Patch(facecolor=self.COLORES['puerta'], label='Door'),
            Patch(facecolor=self.COLORES['obstaculo'], label='Obstacle')
        ]
        ax.legend(handles=legend_elements, loc='upper right', fontsize=9)
    
    def visualizar_rutas_multinivel(self, paso_idx: int, ax=None, show_legend=True):
        """
        Visualize all unlocked paths for each agent at a given step.
        
        Shows progressive path unlocking system:
        - Current path (thick, solid line, color based on anxiety)
        - Alternative unlocked paths (thin, dashed lines, colors by index)
        - Agent position with unlocked paths count (e.g., "3P" = 3 paths unlocked)
        
        The visualization demonstrates how agents unlock more paths (1→3→5) as they
        get stuck, providing visual feedback on the progressive unlocking mechanism.
        
        Path colors:
        - Green: Optimal path (index 0)
        - Yellow: Alternative 1 (index 1)
        - Orange: Alternative 2 (index 2)
        - Red: Alternative 3 (index 3)
        - Purple: Alternative 4 (index 4)
        
        Args:
            paso_idx: Step index to visualize
            ax: Matplotlib axis (creates new if None)
            show_legend: Whether to show legend explaining colors and styles
        
        Returns:
            Matplotlib axis
        
        Example:
            >>> viz = VisualizadorSimulacion('datos/simulacion.pkl')
            >>> viz.visualizar_rutas_multinivel(paso_idx=10)
        """
        if paso_idx < 0 or paso_idx >= len(self.historial_agentes):
            raise ValueError(f"Step index {paso_idx} fuera de rango [0, {len(self.historial_agentes)-1}]")
        
        if ax is None:
            fig, ax = plt.subplots(figsize=(14, 12))
        
        # Draw floor field as background
        self._dibujar_floor_field(ax)
        
        # Get agent states at this step
        estados = self.historial_agentes[paso_idx]
        
        for estado in estados:
            if not estado.activo:
                continue
            
            agent_id = estado.id
            
            # Get all calculated paths for this agent
            all_paths = estado.all_calculated_paths if estado.all_calculated_paths else []
            unlocked_count = estado.unlocked_paths_count if estado.unlocked_paths_count >= 1 else 1
            current_path = estado.current_path
            
            if not all_paths:
                # Fallback: if no all_calculated_paths but has current_path, show that
                if current_path:
                    all_paths = [current_path]
                    unlocked_count = 1
                else:
                    continue
            
            # Draw all unlocked paths with different transparency
            for i, path in enumerate(all_paths[:unlocked_count]):
                if not path or len(path) == 0:
                    continue
                
                # Check if this is the current path
                is_current = (path == current_path) or (current_path and len(path) == len(current_path) and 
                                                       path[0] == current_path[0] and path[-1] == current_path[-1])
                
                # Visual properties
                alpha = 0.9 if is_current else 0.3  # Current path more visible
                linewidth = 3 if is_current else 1.5
                linestyle = '-' if is_current else '--'
                
                # Color based on path index
                color = self._get_path_color(i, unlocked_count)
                
                # Draw path
                if len(path) > 1:
                    xs, ys = zip(*path)
                    ax.plot(xs, ys, color=color, alpha=alpha, 
                           linewidth=linewidth, linestyle=linestyle,
                           marker='o', markersize=2, zorder=2 if is_current else 1)
                else:
                    # Single point path
                    ax.plot(path[0][0], path[0][1], 'o', color=color, 
                           markersize=6, alpha=alpha, zorder=3)
            
            # Draw agent current position
            agent_color = self._get_agent_color(estado)
            ax.plot(estado.x, estado.y, 'o', color=agent_color,
                   markersize=10, markeredgecolor='black', markeredgewidth=1.5, zorder=10)
            
            # Add label showing unlocked paths count
            ax.text(estado.x + 0.3, estado.y + 0.3, 
                   f"A{agent_id}\n{unlocked_count}P",
                   fontsize=8, bbox=dict(boxstyle='round', facecolor='white', alpha=0.7),
                   zorder=11)
        
        # Title
        stats = self.historial_estadisticas[paso_idx]
        total_activos = stats.rapidos_activos + stats.lentos_activos
        ax.set_title(
            f'Progressive Path Unlocking - Paso {paso_idx}\n'
            f'Agentes activos: {total_activos}',
            fontsize=14, weight='bold'
        )
        
        ax.set_xlabel('X Coordinate', fontsize=12)
        ax.set_ylabel('Y Coordinate', fontsize=12)
        ax.grid(True, alpha=0.3)
        
        if show_legend:
            self._add_paths_legend(ax)
        
        return ax
    
    def grafico_evacuacion_temporal(self, guardar: bool = False,
                                   nombre_archivo: str = 'evacuacion_temporal.png'):
        """
        Genera gráfico de evolución temporal de evacuación.
        
        Muestra:
        - Agentes activos vs evacuados por tipo
        - Progreso de evacuación (%)
        """
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))
        pasos = [s.paso for s in self.historial_estadisticas]
        
        # Gráfico 1: Activos vs evacuados
        rapidos_activos = [s.rapidos_activos for s in self.historial_estadisticas]
        lentos_activos = [s.lentos_activos for s in self.historial_estadisticas]
        rapidos_evacuados = [s.rapidos_evacuados for s in self.historial_estadisticas]
        lentos_evacuados = [s.lentos_evacuados for s in self.historial_estadisticas]
        
        ax1.plot(pasos, rapidos_activos, 'g-', linewidth=2, label='Rapidos activos', marker='o')
        ax1.plot(pasos, lentos_activos, 'r-', linewidth=2, label='Lentos activos', marker='s')
        ax1.plot(pasos, rapidos_evacuados, 'g--', linewidth=2, label='Rapidos evacuados', alpha=0.7)
        ax1.plot(pasos, lentos_evacuados, 'r--', linewidth=2, label='Lentos evacuados', alpha=0.7)
        
        ax1.set_xlabel('Paso de tiempo', fontsize=12, weight='bold')
        ax1.set_ylabel('Número de agentes', fontsize=12, weight='bold')
        ax1.set_title('Evolución Temporal de la Evacuación', fontsize=14, weight='bold')
        ax1.legend(loc='best', fontsize=10)
        ax1.grid(True, alpha=0.3)
        
        # Gráfico 2: Progreso
        total_inicial = rapidos_activos[0] + lentos_activos[0]
        if total_inicial > 0:
            evacuados_totales = [v + m for v, m in zip(rapidos_evacuados, lentos_evacuados)]
            porcentaje = [(e / total_inicial) * 100 for e in evacuados_totales]
            
            ax2.plot(pasos, porcentaje, 'b-', linewidth=3, marker='o')
            ax2.fill_between(pasos, 0, porcentaje, alpha=0.3)
            ax2.set_xlabel('Paso de tiempo', fontsize=12, weight='bold')
            ax2.set_ylabel('Porcentaje evacuado (%)', fontsize=12, weight='bold')
            ax2.set_title('Progreso de Evacuación', fontsize=14, weight='bold')
            ax2.grid(True, alpha=0.3)
            ax2.set_ylim(0, 105)
        
        plt.tight_layout()
        
        if guardar:
            plt.savefig(nombre_archivo, dpi=300, bbox_inches='tight')
            print(f"Gráfico guardado: {nombre_archivo}")
        
        plt.show()
    
    def grafico_conflictos(self, guardar: bool = False, nombre_archivo: str = 'analisis_conflictos.png'):
        """
        Genera análisis de conflictos durante evacuación.
        
        Muestra:
        - Evolución temporal de conflictos
        - Distribución de conflictos por tipo de agente
        """
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
        
        pasos = [s.paso for s in self.historial_estadisticas]
        conflictos = [s.conflictos_en_paso for s in self.historial_estadisticas]
        agentes_conflicto = [s.agentes_en_conflicto for s in self.historial_estadisticas]
        
        # Gráfico 1: Evolución
        ax1.bar(pasos, conflictos, color='orange', alpha=0.7, label='Conflictos')
        ax1.plot(pasos, agentes_conflicto, 'r-', linewidth=2, marker='o', label='Agentes en conflicto')
        ax1.set_xlabel('Paso de tiempo', fontsize=12, weight='bold')
        ax1.set_ylabel('Cantidad', fontsize=12, weight='bold')
        ax1.set_title('Evolución de Conflictos', fontsize=14, weight='bold')
        ax1.legend(loc='best', fontsize=10)
        ax1.grid(True, alpha=0.3, axis='y')
        
        # Gráfico 2: Distribución por tipo
        estados_finales = self.historial_agentes[-1]
        conflictos_rapidos = [e.conflictos_totales for e in estados_finales if e.tipo == 'rapido']
        conflictos_lentos = [e.conflictos_totales for e in estados_finales if e.tipo == 'lento']
        
        if conflictos_rapidos or conflictos_lentos:
            data = [conflictos_rapidos, conflictos_lentos]
            labels = ['Rapidos', 'Lentos']
            colors = ['green', 'red']
            
            bp = ax2.boxplot(data, labels=labels, patch_artist=True, showmeans=True, meanline=True)
            
            for patch, color in zip(bp['boxes'], colors):
                patch.set_facecolor(color)
                patch.set_alpha(0.6)
            
            ax2.set_ylabel('Conflictos totales por agente', fontsize=12, weight='bold')
            ax2.set_title('Distribución de Conflictos por Tipo', fontsize=14, weight='bold')
            ax2.grid(True, alpha=0.3, axis='y')
        
        plt.tight_layout()
        
        if guardar:
            plt.savefig(nombre_archivo, dpi=300, bbox_inches='tight')
            print(f"Gráfico guardado: {nombre_archivo}")
        
        plt.show()
    
    def mostrar_resumen(self):
        """resumen estadístico completo"""
        stats_finales = self.historial_estadisticas[-1]
        total_pasos = len(self.historial_agentes)
        total_conflictos = sum(s.conflictos_en_paso for s in self.historial_estadisticas)
        
        estados_finales = self.historial_agentes[-1]
        rapidos = [e for e in estados_finales if e.tipo == 'rapido']
        lentos = [e for e in estados_finales if e.tipo == 'lento']
        print(f"\n ARCHIVO:")
        print(f"Ruta: {self.archivo_pkl}")
        print(f"Formato: {self.formato}")
        
        print(f"\nESTADÍSTICAS GENERALES:")
        print(f"Pasos totales: {total_pasos}")
        print(f"Conflictos totales: {total_conflictos}")
        if total_pasos > 0:
            print(f"Conflictos promedio/paso: {total_conflictos/total_pasos:.2f}")
        
        if rapidos:
            print(f"\nAGENTES RAPIDOS:")
            print(f"Total: {len(rapidos)}")
            print(f"Evacuados: {stats_finales.rapidos_evacuados}")
            print(f"Conflictos promedio: {np.mean([e.conflictos_totales for e in rapidos]):.2f}")
            print(f"Conflictos perdidos promedio: {np.mean([e.conflictos_perdidos for e in rapidos]):.2f}")
        
        if lentos:
            print(f"\nAGENTES LENTOS:")
            print(f"Total: {len(lentos)}")
            print(f"Evacuados: {stats_finales.lentos_evacuados}")
            print(f"Conflictos promedio: {np.mean([e.conflictos_totales for e in lentos]):.2f}")
            print(f"Conflictos perdidos promedio: {np.mean([e.conflictos_perdidos for e in lentos]):.2f}")
        
    
    def generar_reporte_completo(self, directorio_salida: str = 'reportes'):
        Path(directorio_salida).mkdir(parents=True, exist_ok=True)
        print(f"\n Generando reporte completo en: {directorio_salida}/")
        # Video
        self.crear_animacion(
            guardar_video=True,
            nombre_video=f'{directorio_salida}/simulacion.mp4'
        )
        
        # Gráficos
        self.grafico_evacuacion_temporal(
            guardar=True,
            nombre_archivo=f'{directorio_salida}/evacuacion_temporal.png'
        )
        
        self.grafico_conflictos(
            guardar=True,
            nombre_archivo=f'{directorio_salida}/analisis_conflictos.png'
        )
        
        print(f"\nReporte completo generado exitosamente")
        print(f"Archivos en: {directorio_salida}/")

def visualizar_simulacion(archivo_pkl: str, modo: str = 'interactivo'):
    """
    Función rápida para visualizar simulación.
    Ejemplo:
    visualizar_simulacion('historia.pkl')
    visualizar_simulacion('historia.pkl', modo='completo')
    """
    viz = VisualizadorSimulacion(archivo_pkl)
    viz.mostrar_resumen()
    if modo == 'interactivo':
        viz.crear_animacion_interactiva()
    elif modo == 'animacion':
        viz.crear_animacion()
    elif modo == 'graficos':
        viz.grafico_evacuacion_temporal()
        viz.grafico_conflictos()
    elif modo == 'completo':
        viz.crear_animacion_interactiva()
        viz.grafico_evacuacion_temporal()
        viz.grafico_conflictos()
    else:
        print(f"Modo '{modo}' no reconocido")
        print("Modos válidos: interactivo, animacion, graficos, completo")


if __name__ == '__main__':
    import sys
    print("VISUALIZADOR INTEGRADO DE SIMULACIONES")
    if len(sys.argv) > 1:
        archivo = sys.argv[1]
        modo = sys.argv[2] if len(sys.argv) > 2 else 'interactivo'
        try:
            visualizar_simulacion(archivo, modo)
        except Exception as e:
            print(f"\n Error: {e}\n")
    else:
        print("USO:")
        print("  python visualizador.py <archivo.pkl> [modo]")
        print("\nMODOS DISPONIBLES:")
        print("  interactivo  - Animación con controles Play/Pause (default)")
        print("  animacion    - Animación simple sin controles")
        print("  graficos     - Solo gráficos estadísticos")
        print("  completo     - Todo (interactivo + gráficos)")
        print("\nEJEMPLOS:")
        print("  python visualizador.py historia.pkl")
        print("  python visualizador.py historia.pkl interactivo")
        print("  python visualizador.py historia_basico.pkl completo")
        print("\nFORMATOS SOPORTADOS:")
        print("AgentExtendido (Agent.history)")
        print("SimulationLogger (dict complejo)")