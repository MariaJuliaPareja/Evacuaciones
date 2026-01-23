"""
Este módulo se encarga de registrar todos los datos de la simulación 
en cada paso de tiempo para posterior análisis y visualización.
Funcionalidades:
- Registra posición, tipo y estado de cada agente
- Guarda estadísticas de conflictos
- Exporta datos en formato PKL 
"""

import pickle
import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Tuple
from pathlib import Path

@dataclass
class EstadoAgente:
    """
    Representa el estado de un agente en un instante de tiempo.
    Atributos:
    id : int
        Identificador único del agente
    x, y : int
        Posición en la grilla
    activo : bool
        Si el agente está activo o ya evacuó
    tipo : str
        'vivo' o 'menos_vivo'
    conflictos_totales : int
        Total de conflictos acumulados
    conflictos_perdidos : int
        Conflictos perdidos acumulados
    ansiedad : int
        Nivel de ansiedad del agente
    """
    id: int
    x: int
    y: int
    activo: bool
    tipo: str
    conflictos_totales: int
    conflictos_perdidos: int
    ansiedad: int

@dataclass
class EstadisticasPaso:
    """
    Estadísticas agregadas de un paso de tiempo.
    Atributos:
    paso : int
        Número del paso de tiempo
    vivos_activos : int
        Cantidad de agentes 'vivos' que aún no evacuaron
    menos_vivos_activos : int
        Cantidad de agentes 'menos_vivos' que aún no evacuaron
    vivos_evacuados : int
        Cantidad acumulada de agentes 'vivos' evacuados
    menos_vivos_evacuados : int
        Cantidad acumulada de agentes 'menos_vivos' evacuados
    conflictos_en_paso : int
        Conflictos ocurridos en este paso
    agentes_en_conflicto : int
        Agentes involucrados en conflictos en este paso
    """
    paso: int
    vivos_activos: int
    menos_vivos_activos: int
    vivos_evacuados: int
    menos_vivos_evacuados: int
    conflictos_en_paso: int
    agentes_en_conflicto: int

class SimulacionLogger:
    """
    Esta clase mantiene el historial completo de la simulación y permite
    exportarlo para análisis posterior con el visualizador.
    """
    
    def __init__(self, width: int, height: int, puertas: List[Tuple[int, int]],
                 obstaculos: List[Tuple[int, int]]):
        """
        Inicializa el logger con la configuración del escenario.      
        Parámetros:
        width : int
            Ancho de la grilla
        height : int
            Alto de la grilla
        puertas : list
            Lista de tuplas (x, y) con las posiciones de las puertas
        obstaculos : list
            Lista de tuplas (x, y) con las posiciones de los obstáculos
        """
        # Configuración del escenario
        self.width = width
        self.height = height
        self.puertas = puertas
        self.obstaculos = obstaculos
        
        # Historial de la simulación
        self.historial_agentes: List[List[EstadoAgente]] = []  # Lista de listas: [paso][agentes]
        self.historial_estadisticas: List[EstadisticasPaso] = []
        
        # Contadores para evacuados
        self.vivos_evacuados_total = 0
        self.menos_vivos_evacuados_total = 0
    
    def registrar_paso(self, agentes: list, paso: int, stats_movimiento: dict):
        """
        Registra el estado completo de un paso de tiempo.
        Este método debe llamarse después de cada iteración de mover_agentes().   
        Parámetros:
        agentes : list
            Lista de todos los agentes en la simulación
        paso : int
            Número del paso de tiempo actual
        stats_movimiento : dict
            Estadísticas retornadas por mover_agentes()
        """
        # Registrar estado de cada agente
        estados_actuales = []
        vivos_activos = 0
        menos_vivos_activos = 0
        
        for idx, agente in enumerate(agentes):
            # Crear estado del agente
            estado = EstadoAgente(
                id=idx,
                x=agente.x,
                y=agente.y,
                activo=agente.activo,
                tipo=agente.tipo,
                conflictos_totales=agente.conflictos_totales,
                conflictos_perdidos=agente.conflictos_perdidos,
                ansiedad=agente.ansiedad
            )
            estados_actuales.append(estado)
            
            # Contar agentes activos por tipo
            if agente.activo:
                if agente.tipo == 'vivo':
                    vivos_activos += 1
                else:
                    menos_vivos_activos += 1
        
        self.historial_agentes.append(estados_actuales)
        
        # Calcular evacuados en este paso
        # (comparando con el paso anterior si existe)
        if len(self.historial_agentes) > 1:
            for idx, agente in enumerate(agentes):
                estado_anterior = self.historial_agentes[-2][idx]
                if estado_anterior.activo and not agente.activo:
                    # Este agente evacuó en este paso
                    if agente.tipo == 'vivo':
                        self.vivos_evacuados_total += 1
                    else:
                        self.menos_vivos_evacuados_total += 1
        
        # Crear estadísticas del paso
        estadisticas = EstadisticasPaso(
            paso=paso,
            vivos_activos=vivos_activos,
            menos_vivos_activos=menos_vivos_activos,
            vivos_evacuados=self.vivos_evacuados_total,
            menos_vivos_evacuados=self.menos_vivos_evacuados_total,
            conflictos_en_paso=stats_movimiento.get('conflictos_totales', 0),
            agentes_en_conflicto=stats_movimiento.get('agentes_en_conflicto', 0)
        )
        self.historial_estadisticas.append(estadisticas)
    
    def log_path_selector_stats(self, path_selector):
        """
        Registra estadísticas del PathSelector en el paso actual.
        
        Parámetros:
        path_selector : PathSelector
            Instancia del PathSelector con estadísticas a registrar
        """
        if path_selector is None:
            return
        
        stats = path_selector.get_statistics()
        
        # Crear diccionario de estadísticas de PathSelector
        path_selector_stats = {
            'total_a_star_calls': stats.get('total_a_star_calls', 0),
            'cache_hits': stats.get('cache_hits', 0),
            'cache_hit_rate': stats.get('cache_hit_rate', 0.0),
            'avg_nodes_explored': stats.get('avg_nodes_explored', 0.0),
            'max_nodes_explored': stats.get('max_nodes_explored', 0),
            'total_paths_calculated': stats.get('total_paths_calculated', 0),
            'recalculations_by_anxiety': stats.get('recalculations_by_anxiety', {'low': 0, 'medium': 0, 'high': 0})
        }
        
        # Inicializar lista si no existe
        if not hasattr(self, 'path_selector_stats'):
            self.path_selector_stats = []
        
        # Asegurar que la lista tenga el mismo tamaño que historial_estadisticas
        # Si no hay pasos registrados aún, crear un paso inicial
        target_size = len(self.historial_estadisticas) if self.historial_estadisticas else 1
        while len(self.path_selector_stats) < target_size:
            self.path_selector_stats.append({})
        
        # Actualizar el último paso (o el único si no hay pasos registrados)
        if self.path_selector_stats:
            self.path_selector_stats[-1] = path_selector_stats
        else:
            self.path_selector_stats.append(path_selector_stats)
    
    def guardar_pkl(self, nombre_archivo: str):
        """
        Guarda todos los datos de la simulación en un archivo PKL.
        El archivo contiene un diccionario con:
        - 'configuracion': datos del escenario
        - 'historial_agentes': estados de agentes en cada paso
        - 'historial_estadisticas': estadísticas de cada paso
        """
        datos = {
            'configuracion': {
                'width': self.width,
                'height': self.height,
                'puertas': self.puertas,
                'obstaculos': self.obstaculos
            },
            'historial_agentes': self.historial_agentes,
            'historial_estadisticas': self.historial_estadisticas
        }
        
        # Agregar estadísticas de PathSelector si están disponibles
        if hasattr(self, 'path_selector_stats') and self.path_selector_stats:
            datos['path_selector_stats'] = self.path_selector_stats
        
        # Crear directorio si no existe
        path = Path(nombre_archivo)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(nombre_archivo, 'wb') as f:
            pickle.dump(datos, f)
        
        print(f"Datos guardados en: {nombre_archivo}")
        print(f"- Total de pasos: {len(self.historial_agentes)}")
        print(f"- Agentes vivos evacuados: {self.vivos_evacuados_total}")
        print(f"- Agentes menos_vivos evacuados: {self.menos_vivos_evacuados_total}")
    
    def obtener_resumen(self) -> dict:
        """
        Retorna un resumen de la simulación.

        """
        if not self.historial_estadisticas:
            return {}
        
        ultima_stats = self.historial_estadisticas[-1]
        total_conflictos = sum(s.conflictos_en_paso for s in self.historial_estadisticas)
        
        return {
            'pasos_totales': len(self.historial_agentes),
            'vivos_evacuados': self.vivos_evacuados_total,
            'menos_vivos_evacuados': self.menos_vivos_evacuados_total,
            'conflictos_totales': total_conflictos,
            'tiempo_promedio_evacuacion': len(self.historial_agentes)
        }





