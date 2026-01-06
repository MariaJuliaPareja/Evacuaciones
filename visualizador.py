
"""
Este módulo proporciona herramientas de visualización para analizar
simulaciones de evacuación guardadas en formato PKL.

Funcionalidades:
- Carga datos desde archivos PKL
- Genera animaciones paso a paso
- Muestra gráficos de evolución temporal
- Exporta videos de la simulación
- Visualización modular y escalable

USO:
from visualizador import VisualizadorSimulacion

# Crear visualizador
viz = VisualizadorSimulacion('datos_simulacion.pkl')

# Generar visualizaciones
viz.crear_animacion(guardar_video=True)
viz.grafico_evacuacion_temporal()
viz.grafico_conflictos()
viz.mostrar_resumen()
"""

import pickle
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.patches import Rectangle
from matplotlib.colors import to_rgba
from pathlib import Path
from typing import Dict, List, Tuple
import warnings
warnings.filterwarnings('ignore')

class VisualizadorSimulacion:
    """
    Clase principal para visualizar simulaciones de evacuación.
    
    Esta clase lee datos de archivos PKL y genera diversas visualizaciones
    para analizar el comportamiento de los agentes durante la evacuación.
    """
    
    # Configuración de colores (puede modificarse para personalización)
    COLORES = {
        'vivo': '#00FF00',        # Verde brillante para agentes vivos
        'menos_vivo': '#FF0000',  # Rojo para agentes menos vivos
        'obstaculo': '#000000',   # Negro para obstáculos
        'puerta': '#FFD700',      # Dorado para puertas
        'vacio': '#FFFFFF',       # Blanco para celdas vacías
        'floor_field': '#E0E0E0'  # Gris claro para visualizar floor field
    }
    
    def __init__(self, archivo_pkl: str):
        """
        Inicializa el visualizador cargando datos desde un archivo PKL.
        
        Parámetros:
        -----------
        archivo_pkl : str
            Ruta al archivo PKL con los datos de la simulación
        """
        self.archivo_pkl = archivo_pkl
        self.datos = None
        self.configuracion = None
        self.historial_agentes = None
        self.historial_estadisticas = None
        
        self._cargar_datos()
    
    def _cargar_datos(self):
        """
        Carga los datos desde el archivo PKL.
        
        Verifica que el archivo exista y contenga la estructura esperada.
        """
        try:
            with open(self.archivo_pkl, 'rb') as f:
                self.datos = pickle.load(f)
            
            self.configuracion = self.datos['configuracion']
            self.historial_agentes = self.datos['historial_agentes']
            self.historial_estadisticas = self.datos['historial_estadisticas']
            
            print(f"Datos cargados exitosamente desde: {self.archivo_pkl}")
            print(f"  - Pasos de simulación: {len(self.historial_agentes)}")
            print(f"  - Número de agentes: {len(self.historial_agentes[0])}")
        
        except FileNotFoundError:
            raise FileNotFoundError(f"No se encontró el archivo: {self.archivo_pkl}")
        except KeyError as e:
            raise ValueError(f"El archivo PKL no tiene el formato esperado. Falta: {e}")
    
    def crear_animacion(self, intervalo: int = 200, guardar_video: bool = False,
                       nombre_video: str = 'simulacion.mp4'):
        """
        Crea una animación paso a paso de la simulación.
        
        Genera una visualización animada mostrando el movimiento de los agentes
        con colores diferenciados para 'vivos' (verde) y 'menos_vivos' (rojo).
        
        Parámetros:
        intervalo : int, optional (default=200)
            Tiempo en milisegundos entre frames
        guardar_video : bool, optional (default=False)
            Si True, guarda la animación como video MP4
        nombre_video : str, optional (default='simulacion.mp4')
            Nombre del archivo de video (si guardar_video=True)
        """
        fig, ax = plt.subplots(figsize=(12, 10))
        
        width = self.configuracion['width']
        height = self.configuracion['height']
        puertas = self.configuracion['puertas']
        obstaculos = self.configuracion['obstaculos']
        
        def actualizar_frame(paso):
            """Función auxiliar para actualizar cada frame de la animación"""
            ax.clear()
            ax.set_xlim(-0.5, width - 0.5)
            ax.set_ylim(-0.5, height - 0.5)
            ax.set_aspect('equal')
            ax.invert_yaxis()  # Para que (0,0) esté arriba a la izquierda
            
            # Dibujar grilla
            for i in range(width + 1):
                ax.axvline(i - 0.5, color='lightgray', linewidth=0.5)
            for j in range(height + 1):
                ax.axhline(j - 0.5, color='lightgray', linewidth=0.5)
            
            # Dibujar obstáculos
            for x, y in obstaculos:
                rect = Rectangle((x-0.5, y-0.5), 1, 1,
                               facecolor=self.COLORES['obstaculo'],
                               edgecolor='black', linewidth=1)
                ax.add_patch(rect)
            
            # Dibujar puertas
            for x, y in puertas:
                rect = Rectangle((x-0.5, y-0.5), 1, 1,
                               facecolor=self.COLORES['puerta'],
                               edgecolor='orange', linewidth=2)
                ax.add_patch(rect)
            
            # Dibujar agentes activos
            estados = self.historial_agentes[paso]
            stats = self.historial_estadisticas[paso]
            
            for estado in estados:
                if estado.activo:
                    # Color según tipo de agente
                    color = self.COLORES[estado.tipo]
                    
                    # Dibujar círculo para el agente
                    circle = plt.Circle((estado.x, estado.y), 0.35,
                                       color=color, alpha=0.8, zorder=10)
                    ax.add_patch(circle)
                    
                    # Mostrar ID del agente
                    ax.text(estado.x, estado.y, str(estado.id),
                           ha='center', va='center', fontsize=8,
                           color='white', weight='bold', zorder=11)
            
            # Título con información del paso
            ax.set_title(
                f'Paso: {paso} | '
                f'Vivos activos: {stats.vivos_activos} | '
                f'Menos vivos activos: {stats.menos_vivos_activos} | '
                f'Conflictos: {stats.conflictos_en_paso}',
                fontsize=14, weight='bold'
            )
            
            # Etiquetas de ejes
            ax.set_xlabel('X', fontsize=12)
            ax.set_ylabel('Y', fontsize=12)
            
            # Leyenda
            from matplotlib.patches import Patch
            leyenda = [
                Patch(facecolor=self.COLORES['vivo'], label='Vivo'),
                Patch(facecolor=self.COLORES['menos_vivo'], label='Menos vivo'),
                Patch(facecolor=self.COLORES['puerta'], label='Puerta'),
                Patch(facecolor=self.COLORES['obstaculo'], label='Obstáculo')
            ]
            ax.legend(handles=leyenda, loc='upper right', fontsize=10)
        
        # Crear animación
        anim = animation.FuncAnimation(
            fig, actualizar_frame,
            frames=len(self.historial_agentes),
            interval=intervalo,
            repeat=True
        )
        
        # Guardar video si se solicita
        if guardar_video:
            print(f"Guardando video en: {nombre_video}")
            Writer = animation.writers['ffmpeg']
            writer = Writer(fps=5, metadata=dict(artist='SimulacionEvacuacion'), bitrate=1800)
            anim.save(nombre_video, writer=writer)
            print(f"✓ Video guardado exitosamente")
        
        plt.tight_layout()
        plt.show()
        
        return anim
    
    def grafico_evacuacion_temporal(self, guardar: bool = False,
                                   nombre_archivo: str = 'evacuacion_temporal.png'):
        """
        Genera gráfico de evolución temporal de evacuación.
        
        Muestra líneas separadas para agentes 'vivos' y 'menos_vivos',
        comparando cuántos están activos vs evacuados en cada paso.
        
        Parámetros:
        guardar : bool, optional (default=False)
            Si True, guarda el gráfico como imagen
        nombre_archivo : str, optional (default='evacuacion_temporal.png')
            Nombre del archivo de imagen (si guardar=True)
        """
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))
        pasos = [s.paso for s in self.historial_estadisticas]
        
        # Gráfico 1: Agentes activos vs evacuados
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
        
        # Gráfico 2: Tasa de evacuación acumulada
        total_inicial = vivos_activos[0] + menos_vivos_activos[0]
        evacuados_totales = [v + m for v, m in zip(vivos_evacuados, menos_vivos_evacuados)]
        porcentaje_evacuado = [(e / total_inicial) * 100 for e in evacuados_totales]
        
        ax2.plot(pasos, porcentaje_evacuado, 'b-', linewidth=3, marker='o')
        ax2.fill_between(pasos, 0, porcentaje_evacuado, alpha=0.3)
        ax2.set_xlabel('Paso de tiempo', fontsize=12, weight='bold')
        ax2.set_ylabel('Porcentaje evacuado (%)', fontsize=12, weight='bold')
        ax2.set_title('Progreso de Evacuación', fontsize=14, weight='bold')
        ax2.grid(True, alpha=0.3)
        ax2.set_ylim(0, 105)
        
        plt.tight_layout()
        
        if guardar:
            plt.savefig(nombre_archivo, dpi=300, bbox_inches='tight')
            print(f"Gráfico guardado en: {nombre_archivo}")
        
        plt.show()
    
    def grafico_conflictos(self, guardar: bool = False,
                          nombre_archivo: str = 'analisis_conflictos.png'):
        """
        Genera análisis de conflictos durante la evacuación.
        
        Muestra evolución de conflictos en el tiempo y estadísticas
        de conflictos por tipo de agente.
        
        Parámetros:
        guardar : bool, optional (default=False)
            Si True, guarda el gráfico como imagen
        nombre_archivo : str, optional (default='analisis_conflictos.png')
            Nombre del archivo de imagen (si guardar=True)
        """
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
        
        pasos = [s.paso for s in self.historial_estadisticas]
        conflictos = [s.conflictos_en_paso for s in self.historial_estadisticas]
        agentes_en_conflicto = [s.agentes_en_conflicto for s in self.historial_estadisticas]
        
        # Gráfico 1: Evolución de conflictos
        ax1.bar(pasos, conflictos, color='orange', alpha=0.7, label='Conflictos')
        ax1.plot(pasos, agentes_en_conflicto, 'r-', linewidth=2, marker='o',
                label='Agentes en conflicto')
        ax1.set_xlabel('Paso de tiempo', fontsize=12, weight='bold')
        ax1.set_ylabel('Cantidad', fontsize=12, weight='bold')
        ax1.set_title('Evolución de Conflictos', fontsize=14, weight='bold')
        ax1.legend(loc='best', fontsize=10)
        ax1.grid(True, alpha=0.3, axis='y')
        
        # Gráfico 2: Estadísticas finales de conflictos por agente
        estados_finales = self.historial_agentes[-1]
        conflictos_vivos = [e.conflictos_totales for e in estados_finales if e.tipo == 'vivo']
        conflictos_menos_vivos = [e.conflictos_totales for e in estados_finales if e.tipo == 'menos_vivo']
        
        data_boxplot = [conflictos_vivos, conflictos_menos_vivos]
        labels_boxplot = ['Vivos', 'Menos vivos']
        colors = ['green', 'red']
        
        bp = ax2.boxplot(data_boxplot, labels=labels_boxplot, patch_artist=True,
                        showmeans=True, meanline=True)
        
        for patch, color in zip(bp['boxes'], colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.6)
        
        ax2.set_ylabel('Conflictos totales por agente', fontsize=12, weight='bold')
        ax2.set_title('Distribución de Conflictos por Tipo', fontsize=14, weight='bold')
        ax2.grid(True, alpha=0.3, axis='y')
        
        plt.tight_layout()
        
        if guardar:
            plt.savefig(nombre_archivo, dpi=300, bbox_inches='tight')
            print(f"✓ Gráfico guardado en: {nombre_archivo}")
        
        plt.show()
    
    def mostrar_resumen(self):
        """
        Imprime un resumen estadístico completo de la simulación.
        
        Incluye métricas clave como tiempo de evacuación, conflictos,
        y comparación entre tipos de agentes.
        """
        stats_finales = self.historial_estadisticas[-1]
        total_pasos = len(self.historial_agentes)
        total_conflictos = sum(s.conflictos_en_paso for s in self.historial_estadisticas)
        
        # Análisis de conflictos por agente
        estados_finales = self.historial_agentes[-1]
        vivos = [e for e in estados_finales if e.tipo == 'vivo']
        menos_vivos = [e for e in estados_finales if e.tipo == 'menos_vivo']
        
        print("\n" + "="*60)
        print("RESUMEN DE LA SIMULACIÓN")
        print("="*60)
        
        print(f"\nESTADÍSTICAS GENERALES:")
        print(f"  • Pasos totales de evacuación: {total_pasos}")
        print(f"  • Conflictos totales: {total_conflictos}")
        print(f"  • Conflictos promedio por paso: {total_conflictos/total_pasos:.2f}")
        
        print(f"\nAGENTES VIVOS:")
        print(f"  • Total: {len(vivos)}")
        print(f"  • Evacuados: {stats_finales.vivos_evacuados}")
        if vivos:
            print(f"  • Conflictos promedio: {np.mean([e.conflictos_totales for e in vivos]):.2f}")
            print(f"  • Conflictos perdidos promedio: {np.mean([e.conflictos_perdidos for e in vivos]):.2f}")
        
        print(f"\nAGENTES MENOS VIVOS:")
        print(f"  • Total: {len(menos_vivos)}")
        print(f"  • Evacuados: {stats_finales.menos_vivos_evacuados}")
        if menos_vivos:
            print(f"  • Conflictos promedio: {np.mean([e.conflictos_totales for e in menos_vivos]):.2f}")
            print(f"  • Conflictos perdidos promedio: {np.mean([e.conflictos_perdidos for e in menos_vivos]):.2f}")
        
        print("\n" + "="*60 + "\n")
    
    def generar_reporte_completo(self, directorio_salida: str = 'reportes'):
        """
        Genera un reporte completo con todas las visualizaciones.
        
        Crea un directorio con:
        - Video de la simulación
        - Gráficos de evacuación temporal
        - Gráficos de conflictos
        - Archivo de texto con resumen estadístico
        
        Parámetros:
        directorio_salida : str, optional (default='reportes')
            Directorio donde guardar todos los archivos del reporte
        """
        Path(directorio_salida).mkdir(parents=True, exist_ok=True)
        
        print(f"\n Generando reporte completo en: {directorio_salida}/")
        
        # Generar todas las visualizaciones
        self.crear_animacion(guardar_video=True,
                           nombre_video=f'{directorio_salida}/simulacion.mp4')
        self.grafico_evacuacion_temporal(guardar=True,
                                        nombre_archivo=f'{directorio_salida}/evacuacion_temporal.png')
        self.grafico_conflictos(guardar=True,
                               nombre_archivo=f'{directorio_salida}/analisis_conflictos.png')
        
        print(f"\n Reporte completo generado exitosamente!")


# Función de conveniencia para uso rápido
def visualizar_simulacion(archivo_pkl: str, modo: str = 'completo'):
    """
    Función de conveniencia para visualizar rápidamente una simulación.
    
    Parámetros:
    archivo_pkl : str
        Ruta al archivo PKL con los datos
    modo : str, optional (default='completo')
        - 'animacion': Solo muestra la animación
        - 'graficos': Solo muestra los gráficos
        - 'completo': Muestra todo (default)
    """
    viz = VisualizadorSimulacion(archivo_pkl)
    
    viz.mostrar_resumen()
    
    if modo in ['animacion', 'completo']:
        viz.crear_animacion()
    
    if modo in ['graficos', 'completo']:
        viz.grafico_evacuacion_temporal()
        viz.grafico_conflictos()


if __name__ == '__main__':
    # Ejemplo de uso
    import sys
    
    if len(sys.argv) > 1:
        archivo = sys.argv[1]
        visualizar_simulacion(archivo)
    else:
        print("\nUso: python visualizador.py <archivo.pkl>")
        print("\nEjemplo:")
        print("  python visualizador.py datos_simulacion.pkl")