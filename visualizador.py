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
from matplotlib.patches import Rectangle, Circle
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
    ansiedad: int = 0


@dataclass  
class EstadisticasPaso:
    """Estadísticas de un paso de simulación"""
    paso: int
    vivos_activos: int
    menos_vivos_activos: int
    vivos_evacuados: int
    menos_vivos_evacuados: int
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
        'vivo': '#00FF00',        # Verde brillante
        'menos_vivo': '#FF0000',  # Rojo
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
            with open(self.archivo_pkl, 'rb') as f:
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
        
        except FileNotFoundError:
            raise FileNotFoundError(f"No se encontró: {self.archivo_pkl}")
        except Exception as e:
            raise ValueError(f"Error al cargar: {e}")
    
    def _cargar_formato_simulacion_logger(self, datos: dict):
        """Carga formato SimulationLogger (dict complejo)"""
        self.configuracion = datos['configuracion']
        self.historial_agentes = datos['historial_agentes']
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
            vivos_activos = 0
            menos_vivos_activos = 0
            vivos_evacuados = 0
            menos_vivos_evacuados = 0
            
            for agent in paso_agentes:
                # Determinar tipo (con fallback)
                tipo = getattr(agent, 'tipo', 
                              getattr(agent, 'agent_type', 'vivo'))
                
                # Verificar si está activo
                activo = getattr(agent, 'activo', True)
                
                # Contar por categoría
                if tipo == 'vivo':
                    if activo:
                        vivos_activos += 1
                    else:
                        vivos_evacuados += 1
                elif tipo == 'menos_vivo':
                    if activo:
                        menos_vivos_activos += 1
                    else:
                        menos_vivos_evacuados += 1
                
                # Crear estado
                estado = EstadoAgente(
                    id=agent.id,
                    x=agent.pos_x,
                    y=agent.pos_y,
                    tipo=tipo,
                    activo=activo,
                    conflictos_totales=getattr(agent, 'conflictos_totales', 0),
                    conflictos_perdidos=getattr(agent, 'conflictos_perdidos', 0),
                    ansiedad=getattr(agent, 'ansiedad', 0)
                )
                estados_paso.append(estado)
            
            self.historial_agentes.append(estados_paso)
            
            # Crear estadísticas del paso
            stats = EstadisticasPaso(
                paso=paso_idx,
                vivos_activos=vivos_activos,
                menos_vivos_activos=menos_vivos_activos,
                vivos_evacuados=vivos_evacuados,
                menos_vivos_evacuados=menos_vivos_evacuados,
                conflictos_en_paso=0,
                agentes_en_conflicto=0
            )
            self.historial_estadisticas.append(stats)
    
    def crear_animacion_interactiva(self):
        fig = plt.figure(figsize=(16, 12))
        fig.suptitle('Simulación de Evacuación - Visualizador Interactivo', fontsize=16, weight='bold')
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
            estados = self.historial_agentes[frame_num]
            stats = self.historial_estadisticas[frame_num]
            
            # Dibujar agentes activos
            for estado in estados:
                if estado.activo:
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
            
            # Título con info clave
            total_activos = stats.vivos_activos + stats.menos_vivos_activos
            total_evacuados = stats.vivos_evacuados + stats.menos_vivos_evacuados
            
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
            
            info_text = f"""
╔══════════════════════════╗
║   PASO {frame_num:3d}/{max_frames:3d}          ║
╚══════════════════════════╝

AGENTES VIVOS:
  ▶ Activos: {stats.vivos_activos}
  ▶ Evacuados: {stats.vivos_evacuados}

AGENTES MENOS VIVOS:
  ▶ Activos: {stats.menos_vivos_activos}
  ▶ Evacuados: {stats.menos_vivos_evacuados}

CONFLICTOS:
  ▶ En este paso: {stats.conflictos_en_paso}
  ▶ Agentes involucrados: {stats.agentes_en_conflicto}

PROGRESO GLOBAL:
  ▶ Total agentes: {total_agentes}
  ▶ Evacuados: {total_evacuados}
  ▶ Porcentaje: {porcentaje_evacuado:.1f}%

╔══════════════════════════╗
║   FORMATO: {self.formato:12s} ║
╚══════════════════════════╝
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
            interval=lambda: state['interval'],
            repeat=True,
            blit=False
        )
        
        # Frame inicial
        actualizar_frame(0)
        
        plt.tight_layout()
        plt.show()
        
        return anim
    
    def crear_animacion(self, intervalo: int = 200, guardar_video: bool = False,
                       nombre_video: str = 'simulacion.mp4'):
        """
        Animación simple sin controles 
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
            
            # Agentes
            estados = self.historial_agentes[paso]
            stats = self.historial_estadisticas[paso]
            
            for estado in estados:
                if estado.activo:
                    color = self.COLORES.get(estado.tipo, '#888888')
                    
                    circle = Circle((estado.x, estado.y), 0.35,
                                   color=color, alpha=0.8, zorder=10)
                    ax.add_patch(circle)
                    
                    ax.text(estado.x, estado.y, str(estado.id),
                           ha='center', va='center', fontsize=8,
                           color='white', weight='bold', zorder=11)
            
            total_activos = stats.vivos_activos + stats.menos_vivos_activos
            ax.set_title(
                f'Paso: {paso} | Activos: {total_activos}',
                fontsize=14, weight='bold'
            )
            
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
        vivos_activos = [s.vivos_activos for s in self.historial_estadisticas]
        menos_vivos_activos = [s.menos_vivos_activos for s in self.historial_estadisticas]
        vivos_evacuados = [s.vivos_evacuados for s in self.historial_estadisticas]
        menos_vivos_evacuados = [s.menos_vivos_evacuados for s in self.historial_estadisticas]
        
        ax1.plot(pasos, vivos_activos, 'g-', linewidth=2, label='Vivos activos', marker='o')
        ax1.plot(pasos, menos_vivos_activos, 'r-', linewidth=2, label='Menos vivos activos', marker='s')
        ax1.plot(pasos, vivos_evacuados, 'g--', linewidth=2, label='Vivos evacuados', alpha=0.7)
        ax1.plot(pasos, menos_vivos_evacuados, 'r--', linewidth=2, label='Menos vivos evacuados', alpha=0.7)
        
        ax1.set_xlabel('Paso de tiempo', fontsize=12, weight='bold')
        ax1.set_ylabel('Número de agentes', fontsize=12, weight='bold')
        ax1.set_title('Evolución Temporal de la Evacuación', fontsize=14, weight='bold')
        ax1.legend(loc='best', fontsize=10)
        ax1.grid(True, alpha=0.3)
        
        # Gráfico 2: Progreso
        total_inicial = vivos_activos[0] + menos_vivos_activos[0]
        if total_inicial > 0:
            evacuados_totales = [v + m for v, m in zip(vivos_evacuados, menos_vivos_evacuados)]
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
        conflictos_vivos = [e.conflictos_totales for e in estados_finales if e.tipo == 'vivo']
        conflictos_menos_vivos = [e.conflictos_totales for e in estados_finales if e.tipo == 'menos_vivo']
        
        if conflictos_vivos or conflictos_menos_vivos:
            data = [conflictos_vivos, conflictos_menos_vivos]
            labels = ['Vivos', 'Menos vivos']
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
        vivos = [e for e in estados_finales if e.tipo == 'vivo']
        menos_vivos = [e for e in estados_finales if e.tipo == 'menos_vivo']
        print(f"\n ARCHIVO:")
        print(f"Ruta: {self.archivo_pkl}")
        print(f"Formato: {self.formato}")
        
        print(f"\nESTADÍSTICAS GENERALES:")
        print(f"Pasos totales: {total_pasos}")
        print(f"Conflictos totales: {total_conflictos}")
        if total_pasos > 0:
            print(f"Conflictos promedio/paso: {total_conflictos/total_pasos:.2f}")
        
        if vivos:
            print(f"\nAGENTES VIVOS:")
            print(f"Total: {len(vivos)}")
            print(f"Evacuados: {stats_finales.vivos_evacuados}")
            print(f"Conflictos promedio: {np.mean([e.conflictos_totales for e in vivos]):.2f}")
            print(f"Conflictos perdidos promedio: {np.mean([e.conflictos_perdidos for e in vivos]):.2f}")
        
        if menos_vivos:
            print(f"\nAGENTES MENOS VIVOS:")
            print(f"Total: {len(menos_vivos)}")
            print(f"Evacuados: {stats_finales.menos_vivos_evacuados}")
            print(f"Conflictos promedio: {np.mean([e.conflictos_totales for e in menos_vivos]):.2f}")
            print(f"Conflictos perdidos promedio: {np.mean([e.conflictos_perdidos for e in menos_vivos]):.2f}")
        
    
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