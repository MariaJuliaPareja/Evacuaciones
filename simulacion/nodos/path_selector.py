#  Sistema de enrutamiento inteligente con A*
import numpy as np
import networkx as nx
from typing import List, Tuple, Optional, Dict
import heapq

class PathSelector:
    """
    Sistema de enrutamiento dinámico que:
    1. Convierte floor_field en grafo de nodos
    2. Usa A* con métricas dinámicas (congestión, velocidad, ansiedad)
    3. Recalcula rutas cuando detecta congestión adelante
    
    Preparado para evolucionar a D* Lite y Social Force Model en futuro.
    """
    
    def __init__(self, floor_field, umbral_recalculo=0.6):
        """
        Parámetros:
        floor_field : Floor_field
            Campo de piso ya calculado
        umbral_recalculo : float
            Umbral de congestión para forzar recálculo (0-1)
        """
        self.floor_field = floor_field
        self.umbral_recalculo = umbral_recalculo
        
        # Crear grafo de nodos (cada celda válida = nodo)
        self.grafo = self._construir_grafo_nodos()
        
        # Métricas dinámicas
        self.densidad_local = {}  # (x,y) -> densidad [0-1]
        self.velocidad_promedio = {}  # (x,y) -> velocidad promedio
        self.ansiedad_promedio = {}  # (x,y) -> ansiedad promedio
        
        # Pesos actuales de aristas
        self.pesos_actuales = {}  # (nodo1, nodo2) -> peso
        
        # Estadísticas para análisis
        self.num_recalculos = 0
        self.rutas_calculadas = 0
        
    def _construir_grafo_nodos(self) -> nx.DiGraph:
        """
        Convierte floor_field en grafo dirigido de nodos.
        Cada celda válida (no pared/obstáculo) se convierte en nodo.
        Aristas conectan vecinos en 8 direcciones con pesos iniciales.
        Returns:
        G : nx.DiGraph
            Grafo con nodos=(x,y) y aristas con peso='weight'
        """
        G = nx.DiGraph()
        
        # Direcciones: 4 cardinales + 4 diagonales
        direcciones = [
            (0, 1, 1.0),    # Norte
            (1, 0, 1.0),    # Este
            (0, -1, 1.0),   # Sur
            (-1, 0, 1.0),   # Oeste
            (1, 1, 1.5),    # NE (diagonal)
            (1, -1, 1.5),   # SE
            (-1, 1, 1.5),   # NO
            (-1, -1, 1.5)   # SO
        ]
        
        print(f"Construyendo grafo de nodos para grid {self.floor_field.width}x{self.floor_field.height}...")
        
        nodos_agregados = 0
        aristas_agregadas = 0
        
        # Iterar sobre todas las celdas
        for y in range(self.floor_field.height):
            for x in range(self.floor_field.width):
                valor = self.floor_field.valores[y, x]
                
                # Solo celdas válidas (no paredes ni obstáculos)
                if valor < 500:
                    # Agregar nodo
                    G.add_node((x, y), floor_value=valor)
                    nodos_agregados += 1
                    
                    # Agregar aristas a vecinos válidos
                    for dx, dy, costo_base in direcciones:
                        nx_coord, ny_coord = x + dx, y + dy
                        
                        # Verificar límites
                        if (0 <= nx_coord < self.floor_field.width and 
                            0 <= ny_coord < self.floor_field.height):
                            
                            valor_vecino = self.floor_field.valores[ny_coord, nx_coord]
                            
                            # Solo conectar a celdas válidas
                            if valor_vecino < 500:
                                # Peso inicial = distancia física
                                G.add_edge((x, y), (nx_coord, ny_coord), 
                                          weight=costo_base)
                                aristas_agregadas += 1
        
        print(f"Grafo creado: {nodos_agregados} nodos, {aristas_agregadas} aristas")
        return G
    
    def actualizar_metricas(self, agentes: List):
        """
        Actualiza métricas dinámicas basadas en estado actual de agentes.
        Calcula para cada celda:
        - Densidad local (ocupación)
        - Velocidad promedio de agentes en la celda
        - Nivel de ansiedad promedio
        Parámetros:
        agentes : List[AgentExtendido]
            Lista de todos los agentes en simulación
        """
        # Reset métricas
        self.densidad_local.clear()
        self.velocidad_promedio.clear()
        self.ansiedad_promedio.clear()
        
        # Contador de agentes por celda
        agentes_por_celda = {}
        
        for agente in agentes:
            if not agente.activo or agente.pos_x is None:
                continue
            
            pos = (agente.pos_x, agente.pos_y)
            
            if pos not in agentes_por_celda:
                agentes_por_celda[pos] = {
                    'count': 0,
                    'menos_vivos': 0,
                    'ansiedad_total': 0
                }
            
            agentes_por_celda[pos]['count'] += 1
            
            if agente.tipo == 'menos_vivo':
                agentes_por_celda[pos]['menos_vivos'] += 1
            
            # Asumimos que ansiedad está en el agente
            ansiedad = getattr(agente, 'conflictos_totales', 0)
            agentes_por_celda[pos]['ansiedad_total'] += ansiedad
        
        # Calcular métricas por celda
        for pos, datos in agentes_por_celda.items():
            count = datos['count']
            
            # Densidad: 1 agente por celda = 100%
            self.densidad_local[pos] = min(count, 1.0)
            
            # Velocidad: menos_vivos son más lentos (factor 0.5)
            ratio_lentos = datos['menos_vivos'] / count
            self.velocidad_promedio[pos] = 1.0 - (ratio_lentos * 0.5)
            
            # Ansiedad promedio
            self.ansiedad_promedio[pos] = datos['ansiedad_total'] / count
    
    def actualizar_pesos_grafo(self, alpha=1.5, beta=1.0, gamma=0.5):
        """
        Actualiza pesos de aristas del grafo basado en métricas dinámicas.
        
        Fórmula:
        peso_final = peso_base × (1 + α×densidad + β×factor_velocidad + γ×ansiedad)
        Parámetros:
        alpha : float
            Peso de factor de densidad (por defecto 1.5)
        beta : float
            Peso de factor de velocidad (por defecto 1.0)
        gamma : float
            Peso de factor de ansiedad (por defecto 0.5)
        """
        for (origen, destino, data) in self.grafo.edges(data=True):
            peso_base = data['weight']
            
            # Obtener métricas del nodo destino
            densidad = self.densidad_local.get(destino, 0.0)
            velocidad = self.velocidad_promedio.get(destino, 1.0)
            ansiedad = self.ansiedad_promedio.get(destino, 0.0)
            
            # Normalizar ansiedad (asumiendo max ~20)
            ansiedad_norm = min(ansiedad / 20.0, 1.0)
            
            # Factor de velocidad: a menor velocidad, mayor penalización
            factor_velocidad = 2.0 - velocidad  # si vel=0.5 -> factor=1.5
            
            # Calcular peso final
            penalizacion = (alpha * densidad + beta * (factor_velocidad - 1.0) + gamma * ansiedad_norm)
            peso_final = peso_base * (1.0 + penalizacion)
            
            # Actualizar en grafo
            self.grafo[origen][destino]['weight'] = peso_final
            self.pesos_actuales[(origen, destino)] = peso_final
    
    def heuristica_a_star(self, nodo: Tuple[int, int], meta: Tuple[int, int]) -> float:
        """
        Función heurística para A* (distancia euclidiana + estimación congestión).
        Parámetros:
        nodo : (x, y)
            Nodo actual
        meta : (x, y)
            Nodo objetivo
        Returns:
        h : float
            Estimación de costo restante (admisible)
        """
        # Distancia euclidiana
        dx = nodo[0] - meta[0]
        dy = nodo[1] - meta[1]
        dist_euclidiana = np.sqrt(dx**2 + dy**2)
        # Estimación de congestión en línea recta POR IMPLEMENTAR
        # Por ahora usar solo distancia para garantizar admisibilidad
        return dist_euclidiana
    def encontrar_ruta_a_star(self, origen: Tuple[int, int], meta: Tuple[int, int]) -> Optional[List[Tuple[int, int]]]:
        """
        Encuentra ruta óptima de origen a meta usando A*.
        Implementación manual de A* con heap para eficiencia.
        Parámetros:
        origen : (x, y)
            Posición inicial
        meta : (x, y)
            Posición objetivo (puerta)
        Returns:
        ruta : List[(x,y)] o None
            Lista de nodos desde origen hasta meta, o None si no hay camino
        """
        if origen not in self.grafo or meta not in self.grafo:
            return None
        
        # Estructuras A*
        open_set = []  # heap: (f_score, contador, nodo)
        heapq.heappush(open_set, (0, 0, origen))
        
        came_from = {}  # Para reconstruir camino
        g_score = {origen: 0}  # Costo acumulado
        f_score = {origen: self.heuristica_a_star(origen, meta)}
        
        contador = 1  # Para desempatar en heap
        
        while open_set:
            _, _, current = heapq.heappop(open_set)
            
            # ¿Llegamos a la meta?
            if current == meta:
                # Reconstruir camino
                ruta = [current]
                while current in came_from:
                    current = came_from[current]
                    ruta.append(current)
                ruta.reverse()
                
                self.rutas_calculadas += 1
                return ruta
            
            # Explorar vecinos
            for vecino in self.grafo.neighbors(current):
                # Costo de moverse a vecino
                peso = self.grafo[current][vecino]['weight']
                tentative_g = g_score[current] + peso
                
                # ¿Es mejor camino?
                if vecino not in g_score or tentative_g < g_score[vecino]:
                    came_from[vecino] = current
                    g_score[vecino] = tentative_g
                    f_score[vecino] = tentative_g + self.heuristica_a_star(vecino, meta)
                    
                    # Agregar a open_set si no está
                    if vecino not in [item[2] for item in open_set]:
                        heapq.heappush(open_set, (f_score[vecino], contador, vecino))
                        contador += 1
        
        # No se encontró camino
        return None
    
    def encontrar_mejor_puerta(self, origen: Tuple[int, int], 
                               puertas: List[Tuple[int, int]]) -> Tuple[int, int]:
        """
        Encuentra la puerta más cercana/conveniente desde origen.
        Usa distancia euclidiana + costo estimado de congestión.
        Parámetros:
        origen : (x, y)
            Posición del agente
        puertas : List[(x, y)]
           Lista de coordenadas de puertas      
        Returns:
        mejor_puerta : (x, y)
            Puerta óptima
        """
        mejor_puerta = None
        mejor_costo = float('inf')
        
        for puerta in puertas:
            # Distancia euclidiana
            dx = origen[0] - puerta[0]
            dy = origen[1] - puerta[1]
            dist = np.sqrt(dx**2 + dy**2)
            
            # Penalizar si hay congestión cerca de la puerta
            congestion_puerta = self.densidad_local.get(puerta, 0.0)
            
            # Costo total
            costo = dist * (1.0 + congestion_puerta * 2.0)
            
            if costo < mejor_costo:
                mejor_costo = costo
                mejor_puerta = puerta
        
        return mejor_puerta if mejor_puerta else puertas[0]
    
    def debe_recalcular_ruta(self, agente, ruta_actual: List[Tuple[int, int]], 
                             pasos_adelante: int = 5) -> bool:
        """
        Decide si el agente debe recalcular su ruta.
        Criterios:
        1. Ruta es None o vacía
        2. Congestión alta en próximos pasos
        3. Han pasado muchos pasos desde último cálculo
        Parámetros:
        agente : AgentExtendido
            Agente a evaluar
        ruta_actual : List[(x,y)]
            Ruta planificada actual
        pasos_adelante : int
            Cuántos pasos mirar adelante
        Returns:
        debe_recalcular : bool
        """
        # Caso 1: No hay ruta
        if not ruta_actual or len(ruta_actual) == 0:
            return True
        
        # Caso 2: Muchos pasos desde último cálculo
        if hasattr(agente, 'pasos_desde_recalculo'):
            if agente.pasos_desde_recalculo > 15:
                return True
        
        # Caso 3: Congestión alta adelante
        proximas_celdas = ruta_actual[:min(pasos_adelante, len(ruta_actual))]
        congestion_adelante = 0
        
        for celda in proximas_celdas:
            congestion_adelante += self.densidad_local.get(celda, 0.0)
        
        congestion_promedio = congestion_adelante / len(proximas_celdas)
        
        if congestion_promedio > self.umbral_recalculo:
            self.num_recalculos += 1
            return True
        
        return False
    
    def obtener_estadisticas(self) -> Dict:
        """Retorna estadísticas del selector de rutas"""
        return {
            'rutas_calculadas': self.rutas_calculadas,
            'num_recalculos': self.num_recalculos,
            'nodos_grafo': self.grafo.number_of_nodes(),
            'aristas_grafo': self.grafo.number_of_edges(),
            'densidad_promedio': np.mean(list(self.densidad_local.values())) if self.densidad_local else 0.0
        }