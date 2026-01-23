#  Sistema de enrutamiento inteligente con A*
import numpy as np
import networkx as nx
from typing import List, Tuple, Optional, Dict
import heapq
import math
from functools import lru_cache
import random
import logging

class PathSelector:
    """
    Sistema de enrutamiento dinámico que:
    1. Convierte floor_field en grafo de nodos
    2. Usa A* con métricas dinámicas (congestión, velocidad, ansiedad)
    3. Recalcula rutas cuando detecta congestión adelante
    
    Preparado para evolucionar a D* Lite y Social Force Model en futuro.
    """
    
    def __init__(self, floor_field, umbral_recalculo=0.6, anxiety_thresholds: Tuple[int, int] = (30, 70)):
        """
        Parámetros:
        floor_field : Floor_field
            Campo de piso ya calculado
        umbral_recalculo : float
            Umbral de congestión para forzar recálculo (0-1)
        anxiety_thresholds : Tuple[int, int]
            Umbrales de ansiedad (mild_max, optimal_max) por defecto (30, 70)
            Define los rangos: 0-mild_max (baja), mild_max-optimal_max (óptima), optimal_max-100 (alta)
        """
        self.floor_field = floor_field
        self.umbral_recalculo = umbral_recalculo
        self.anxiety_thresholds = anxiety_thresholds
        
        # Crear grafo de nodos (cada celda válida = nodo)
        self.grafo = self._build_graph_from_floor_field()
        
        # Caché de rutas: {(start, goal): path}
        self.path_cache = {}
        
        # Estadísticas mejoradas
        self.stats = {
            'calls': 0,           # Total de llamadas a encontrar_ruta_a_star
            'cache_hits': 0,      # Rutas encontradas en caché
            'nodes_explored': [],  # Lista de nodos explorados por búsqueda
            'recalculations_by_anxiety': {'low': 0, 'medium': 0, 'high': 0}  # Recalculaciones por ansiedad
        }
        
        # Log de decisiones de selección por ansiedad
        self.anxiety_decisions = []  # Lista de decisiones para análisis posterior
        
        # Configurar logging
        self.logger = logging.getLogger(f'PathSelector_{id(self)}')
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
        
        # Métricas dinámicas
        self.densidad_local = {}  # (x,y) -> densidad [0-1]
        self.velocidad_promedio = {}  # (x,y) -> velocidad promedio
        self.ansiedad_promedio = {}  # (x,y) -> ansiedad promedio
        
        # Pesos actuales de aristas
        self.pesos_actuales = {}  # (nodo1, nodo2) -> peso
        
        # Estadísticas para análisis (mantener compatibilidad)
        self.num_recalculos = 0
        self.rutas_calculadas = 0
        
    def _build_graph_from_floor_field(self) -> nx.DiGraph:
        """
        Convierte floor_field en grafo dirigido de nodos.
        Cada celda válida (no pared/obstáculo) se convierte en nodo.
        Aristas conectan vecinos en 8 direcciones con pesos:
        - 1.0 para movimientos ortogonales (N, S, E, O)
        - 1.5 para movimientos diagonales (NE, SE, NO, SO)
        
        Returns:
        G : nx.DiGraph
            Grafo con nodos=(x,y) y aristas con peso='weight'
        """
        return self._construir_grafo_nodos_impl()
    
    def _construir_grafo_nodos_impl(self) -> nx.DiGraph:
        """
        Implementación interna de construcción de grafo.
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
    
    def _construir_grafo_nodos(self) -> nx.DiGraph:
        """
        Alias para compatibilidad con código existente.
        Llama a _build_graph_from_floor_field.
        """
        return self._build_graph_from_floor_field()
    
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
    
    def calculate_heuristic(self, pos1: Tuple[int, int], pos2: Tuple[int, int]) -> float:
        """
        Función heurística consistente para A* (distancia euclidiana).
        Respeta los pesos del grafo: ortogonales (1.0) y diagonales (1.5).
        
        Parámetros:
        pos1 : (x, y)
            Posición inicial
        pos2 : (x, y)
            Posición objetivo
        Returns:
        h : float
            Estimación de costo restante (admisible)
        """
        dx = abs(pos1[0] - pos2[0])
        dy = abs(pos1[1] - pos2[1])
        # Distancia euclidiana que respeta pesos del grafo
        return math.sqrt(dx**2 + dy**2)
    
    def heuristica_a_star(self, nodo: Tuple[int, int], meta: Tuple[int, int]) -> float:
        """
        Función heurística para A* (distancia euclidiana + estimación congestión).
        Mantiene compatibilidad con código existente.
        Internamente usa calculate_heuristic.
        
        Parámetros:
        nodo : (x, y)
            Nodo actual
        meta : (x, y)
            Nodo objetivo
        Returns:
        h : float
            Estimación de costo restante (admisible)
        """
        return self.calculate_heuristic(nodo, meta)
    def encontrar_ruta_a_star(self, origen: Tuple[int, int], meta: Tuple[int, int], 
                              usar_cache: bool = True) -> Optional[List[Tuple[int, int]]]:
        """
        Encuentra ruta óptima de origen a meta usando A*.
        Implementación manual de A* con heap para eficiencia.
        Incluye caché de rutas para optimización.
        
        Parámetros:
        origen : (x, y)
            Posición inicial
        meta : (x, y)
            Posición objetivo (puerta)
        usar_cache : bool
            Si True, usa caché de rutas (por defecto True)
        Returns:
        ruta : List[(x,y)] o None
            Lista de nodos desde origen hasta meta, o None si no hay camino
        """
        # Actualizar estadísticas
        self.stats['calls'] += 1
        
        # Logging automático
        self.logger.debug(f"A* call: {origen} -> {meta}")
        
        # Verificar caché
        cache_key = (origen, meta)
        if usar_cache and cache_key in self.path_cache:
            self.stats['cache_hits'] += 1
            self.logger.debug(f"Cache hit for {cache_key}")
            return self.path_cache[cache_key].copy()  # Retornar copia para evitar mutaciones
        
        # Validar nodos
        if origen not in self.grafo or meta not in self.grafo:
            return None
        
        # Estructuras A*
        open_set = []  # heap: (f_score, contador, nodo)
        heapq.heappush(open_set, (0, 0, origen))
        
        came_from = {}  # Para reconstruir camino
        g_score = {origen: 0}  # Costo acumulado
        f_score = {origen: self.calculate_heuristic(origen, meta)}
        
        contador = 1  # Para desempatar en heap
        nodes_explored_this_search = 0
        
        while open_set:
            _, _, current = heapq.heappop(open_set)
            nodes_explored_this_search += 1
            
            # ¿Llegamos a la meta?
            if current == meta:
                # Reconstruir camino
                ruta = [current]
                while current in came_from:
                    current = came_from[current]
                    ruta.append(current)
                ruta.reverse()
                
                # Guardar en caché
                if usar_cache:
                    self.path_cache[cache_key] = ruta.copy()
                
                # Actualizar estadísticas
                self.rutas_calculadas += 1
                self.stats['nodes_explored'].append(nodes_explored_this_search)
                
                # Logging automático
                self.logger.info(f"Path found: {origen} -> {meta}, length={len(ruta)}, nodes_explored={nodes_explored_this_search}")
                
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
                    f_score[vecino] = tentative_g + self.calculate_heuristic(vecino, meta)
                    
                    # Agregar a open_set si no está
                    if vecino not in [item[2] for item in open_set]:
                        heapq.heappush(open_set, (f_score[vecino], contador, vecino))
                        contador += 1
        
        # No se encontró camino
        self.stats['nodes_explored'].append(nodes_explored_this_search)
        self.logger.warning(f"No path found: {origen} -> {meta}, nodes_explored={nodes_explored_this_search}")
        return None
    
    def _calculate_path_difference(self, path1: List[Tuple[int, int]], 
                                   path2: List[Tuple[int, int]]) -> float:
        """
        Calcula el porcentaje de celdas distintas entre dos rutas.
        
        Parámetros:
        path1 : List[(x,y)]
            Primera ruta
        path2 : List[(x,y)]
            Segunda ruta
            
        Returns:
        diferencia : float
            Porcentaje de celdas distintas (0.0 a 1.0)
        """
        set1 = set(path1)
        set2 = set(path2)
        
        # Celdas únicas en cada ruta
        solo_path1 = set1 - set2
        solo_path2 = set2 - set1
        
        # Total de celdas únicas
        total_unicas = len(solo_path1) + len(solo_path2)
        total_celdas = max(len(set1), len(set2))
        
        if total_celdas == 0:
            return 0.0
        
        return total_unicas / total_celdas
    
    def find_k_paths(self, start: Tuple[int, int], goal: Tuple[int, int], 
                    k: int = 3, penalty_factor: float = 0.5) -> List[List[Tuple[int, int]]]:
        """
        Encuentra k rutas alternativas desde start hasta goal.
        
        Algoritmo:
        1. Path 1: A* normal (ruta óptima)
        2. Paths 2-k: A* con penalizaciones para celdas ya usadas
        
        Valida que las rutas sean distintas (>30% celdas diferentes).
        
        Parámetros:
        start : (x, y)
            Posición inicial
        goal : (x, y)
            Posición objetivo
        k : int
            Número de rutas a encontrar (por defecto 3)
        penalty_factor : float
            Penalización por celda ya usada (por defecto 0.5)
            
        Returns:
        paths : List[List[(x,y)]]
            Lista de rutas encontradas (puede ser menor que k si no se encuentran suficientes)
        """
        # Actualizar estadísticas
        self.stats['calls'] += 1
        
        paths_found = []
        penalty_costs = {}  # {(x,y): veces_usada}
        
        # Path 1: Ruta óptima usando A* normal (sin caché para evitar conflictos)
        path1 = self.encontrar_ruta_a_star(start, goal, usar_cache=False)
        
        if path1 is None:
            return []  # No hay camino posible
        
        paths_found.append(path1)
        
        # Actualizar penalizaciones con la primera ruta
        for cell in path1:
            penalty_costs[cell] = penalty_costs.get(cell, 0) + 1
        
        # Paths 2 a k: Rutas alternativas con penalizaciones
        for path_num in range(2, k + 1):
            # Buscar ruta con penalizaciones
            
            # Validar nodos
            if start not in self.grafo or goal not in self.grafo:
                break
            
            # Estructuras A* con penalizaciones
            open_set = []
            heapq.heappush(open_set, (0, 0, start))
            
            came_from = {}
            g_score = {start: 0}
            f_score = {start: self.calculate_heuristic(start, goal)}
            
            contador = 1
            found_path = False
            
            while open_set:
                _, _, current = heapq.heappop(open_set)
                
                # ¿Llegamos a la meta?
                if current == goal:
                    # Reconstruir camino
                    ruta = [current]
                    while current in came_from:
                        current = came_from[current]
                        ruta.append(current)
                    ruta.reverse()
                    
                    # Validar que la ruta es suficientemente diferente
                    is_different = True
                    for existing_path in paths_found:
                        diferencia = self._calculate_path_difference(ruta, existing_path)
                        if diferencia < 0.3:  # Menos del 30% diferente
                            is_different = False
                            break
                    
                    if is_different:
                        paths_found.append(ruta)
                        # Actualizar penalizaciones
                        for cell in ruta:
                            penalty_costs[cell] = penalty_costs.get(cell, 0) + 1
                        found_path = True
                    break
                
                # Explorar vecinos
                for vecino in self.grafo.neighbors(current):
                    # Costo base del grafo
                    peso_base = self.grafo[current][vecino]['weight']
                    
                    # Aplicar penalización si la celda ha sido usada
                    veces_usada = penalty_costs.get(vecino, 0)
                    peso_penalizado = peso_base + (penalty_factor * veces_usada)
                    
                    tentative_g = g_score[current] + peso_penalizado
                    
                    # ¿Es mejor camino?
                    if vecino not in g_score or tentative_g < g_score[vecino]:
                        came_from[vecino] = current
                        g_score[vecino] = tentative_g
                        f_score[vecino] = tentative_g + self.calculate_heuristic(vecino, goal)
                        
                        # Agregar a open_set si no está
                        if vecino not in [item[2] for item in open_set]:
                            heapq.heappush(open_set, (f_score[vecino], contador, vecino))
                            contador += 1
            
            # Si no se encontró una ruta diferente, intentar con más penalización
            if not found_path:
                # Incrementar penalización y reintentar una vez más
                penalty_factor_temp = penalty_factor * 2
                
                open_set = []
                heapq.heappush(open_set, (0, 0, start))
                came_from = {}
                g_score = {start: 0}
                f_score = {start: self.calculate_heuristic(start, goal)}
                contador = 1
                
                while open_set:
                    _, _, current = heapq.heappop(open_set)
                    
                    if current == goal:
                        ruta = [current]
                        while current in came_from:
                            current = came_from[current]
                            ruta.append(current)
                        ruta.reverse()
                        
                        # Validar diferencia
                        is_different = True
                        for existing_path in paths_found:
                            diferencia = self._calculate_path_difference(ruta, existing_path)
                            if diferencia < 0.3:
                                is_different = False
                                break
                        
                        if is_different:
                            paths_found.append(ruta)
                            for cell in ruta:
                                penalty_costs[cell] = penalty_costs.get(cell, 0) + 1
                            found_path = True
                        break
                    
                    for vecino in self.grafo.neighbors(current):
                        peso_base = self.grafo[current][vecino]['weight']
                        veces_usada = penalty_costs.get(vecino, 0)
                        peso_penalizado = peso_base + (penalty_factor_temp * veces_usada)
                        
                        tentative_g = g_score[current] + peso_penalizado
                        
                        if vecino not in g_score or tentative_g < g_score[vecino]:
                            came_from[vecino] = current
                            g_score[vecino] = tentative_g
                            f_score[vecino] = tentative_g + self.calculate_heuristic(vecino, goal)
                            
                            if vecino not in [item[2] for item in open_set]:
                                heapq.heappush(open_set, (f_score[vecino], contador, vecino))
                                contador += 1
                
                # Si aún no encontramos una ruta diferente después de ambos intentos, salir
                if not found_path:
                    break
        
        # Log del número de rutas encontradas
        print(f"find_k_paths: Encontradas {len(paths_found)}/{k} rutas desde {start} hasta {goal}")
        
        return paths_found
    
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
        """
        Retorna estadísticas del selector de rutas.
        Incluye métricas de caché y nodos explorados.
        Alias de get_statistics() para compatibilidad.
        """
        return self.get_statistics()
    
    def get_statistics(self) -> Dict:
        """
        Returns usage statistics of PathSelector.
        
        Returns:
            Dict with performance metrics
        """
        total_calls = self.stats['calls']
        cache_hits = self.stats['cache_hits']
        nodes_explored = self.stats['nodes_explored']
        
        cache_hit_rate = (cache_hits / total_calls if total_calls > 0 else 0.0)
        avg_nodes_explored = np.mean(nodes_explored) if nodes_explored else 0.0
        max_nodes_explored = max(nodes_explored) if nodes_explored else 0
        
        return {
            'total_a_star_calls': total_calls,
            'cache_hits': cache_hits,
            'cache_hit_rate': cache_hit_rate,
            'avg_nodes_explored': avg_nodes_explored,
            'max_nodes_explored': max_nodes_explored,
            'total_paths_calculated': len(self.path_cache),
            # Estadísticas adicionales (compatibilidad)
            'rutas_calculadas': self.rutas_calculadas,
            'num_recalculos': self.num_recalculos,
            'nodos_grafo': self.grafo.number_of_nodes(),
            'aristas_grafo': self.grafo.number_of_edges(),
            'densidad_promedio': np.mean(list(self.densidad_local.values())) if self.densidad_local else 0.0,
            'cache_size': len(self.path_cache),
            'nodes_explored_total': sum(nodes_explored),
            'recalculations_by_anxiety': self.stats['recalculations_by_anxiety'].copy()
        }
    
    def reset_statistics(self):
        """
        Resets counters for new simulation.
        Limpia todas las estadísticas pero mantiene el grafo y caché.
        """
        self.stats = {
            'calls': 0,
            'cache_hits': 0,
            'nodes_explored': [],
            'recalculations_by_anxiety': {'low': 0, 'medium': 0, 'high': 0}
        }
        self.anxiety_decisions = []
        self.rutas_calculadas = 0
        self.num_recalculos = 0
        
        self.logger.info("Statistics reset")
    
    def print_report(self):
        """
        Imprime un reporte completo de estadísticas del PathSelector.
        """
        stats = self.get_statistics()
        
        print("\n" + "="*50)
        print("PathSelector REPORT")
        print("="*50)
        print(f"A* calls: {stats['total_a_star_calls']}")
        print(f"Cache hits: {stats['cache_hits']}")
        print(f"Cache hit rate: {stats['cache_hit_rate']:.1%}")
        print(f"Nodes explored (average): {stats['avg_nodes_explored']:.1f}")
        print(f"Nodes explored (max): {stats['max_nodes_explored']}")
        print(f"Unique paths calculated: {stats['total_paths_calculated']}")
        print(f"Total paths calculated: {stats['rutas_calculadas']}")
        print(f"Recalculations: {stats['num_recalculos']}")
        
        # Recalculaciones por ansiedad
        recalc_by_anxiety = stats['recalculations_by_anxiety']
        if any(recalc_by_anxiety.values()):
            print(f"\nRecalculations by anxiety level:")
            print(f"  Low (0-30): {recalc_by_anxiety['low']}")
            print(f"  Medium (30-70): {recalc_by_anxiety['medium']}")
            print(f"  High (70-100): {recalc_by_anxiety['high']}")
        
        # Estadísticas de ansiedad si hay decisiones
        anxiety_stats = self.get_anxiety_statistics()
        if anxiety_stats['total_decisions'] > 0:
            print(f"\nAnxiety-based selections: {anxiety_stats['total_decisions']}")
            print(f"  Distribution: {anxiety_stats['by_category']}")
            print(f"  Noise added rate: {anxiety_stats['noise_rate']:.2%}")
            print(f"  Average anxiety: {anxiety_stats['average_anxiety']:.1f}")
        
        print("="*50)
    
    def limpiar_cache(self):
        """Limpia el caché de rutas. Útil cuando el grafo cambia dinámicamente."""
        self.path_cache.clear()
        self.stats['cache_hits'] = 0  # Reset cache hits pero mantener calls
    
    def _calculate_base_path_cost(self, path: List[Tuple[int, int]]) -> float:
        """
        Calcula el costo base de una ruta sumando los pesos de las aristas del grafo.
        
        Parámetros:
        path : List[(x,y)]
            Ruta a evaluar
            
        Returns:
        costo_base : float
            Costo total de la ruta sin considerar congestión
        """
        if len(path) < 2:
            return 0.0
        
        costo_total = 0.0
        for i in range(len(path) - 1):
            current = path[i]
            next_cell = path[i + 1]
            
            # Si hay arista en el grafo, usar su peso
            if self.grafo.has_edge(current, next_cell):
                peso = self.grafo[current][next_cell]['weight']
                costo_total += peso
            else:
                # Si no hay arista directa, calcular distancia euclidiana como fallback
                dx = abs(current[0] - next_cell[0])
                dy = abs(current[1] - next_cell[1])
                # Aproximación: ortogonal=1.0, diagonal=1.5
                if dx == 0 or dy == 0:
                    costo_total += 1.0
                else:
                    costo_total += 1.5
        
        return costo_total
    
    def get_path_cost(self, path: List[Tuple[int, int]], 
                     agent_positions: Dict[Tuple[int, int], int]) -> float:
        """
        Calcula el costo de una ruta considerando la congestión actual.
        
        Fórmula: costo_base + (congestión × factor_penalización)
        
        Parámetros:
        path : List[(x,y)]
            Ruta a evaluar
        agent_positions : Dict[(x,y), int]
            Diccionario con número de agentes en cada posición {(x,y): num_agents}
            
        Returns:
        costo_total : float
            Costo total de la ruta considerando congestión
        """
        # Costo base de la ruta (suma de pesos de aristas)
        base_cost = self._calculate_base_path_cost(path)
        
        # Costo de congestión: penalización por cada agente en las celdas de la ruta
        congestion_cost = sum(agent_positions.get(pos, 0) * 0.5 for pos in path)
        
        return base_cost + congestion_cost
    
    def _hash_agents_on_path(self, path: List[Tuple[int, int]], 
                             agent_positions: Dict[Tuple[int, int], int]) -> int:
        """
        Genera un hash de las posiciones de agentes en la ruta.
        Usado como parte de la clave del caché LRU.
        
        Parámetros:
        path : List[(x,y)]
            Ruta a evaluar
        agent_positions : Dict[(x,y), int]
            Posiciones de agentes
            
        Returns:
        hash_value : int
            Hash de las posiciones de agentes en la ruta
        """
        # Crear tupla de (celda, num_agents) para celdas en la ruta
        agents_on_path = tuple((pos, agent_positions.get(pos, 0)) for pos in path)
        return hash(agents_on_path)
    
    @lru_cache(maxsize=100)
    def _cached_path_calculation(self, start: Tuple[int, int], goal: Tuple[int, int], 
                                agents_hash: int) -> Optional[Tuple[Tuple[int, int], ...]]:
        """
        Método auxiliar con caché LRU para cálculos de rutas.
        Retorna tupla (hashable) en lugar de lista para compatibilidad con lru_cache.
        
        Parámetros:
        start : (x, y)
            Posición inicial
        goal : (x, y)
            Posición objetivo
        agents_hash : int
            Hash de las posiciones de agentes en la ruta
            
        Returns:
        ruta : Tuple[(x,y), ...] o None
            Ruta calculada como tupla (hashable) o None si no hay camino
        """
        # Llamar al método A* sin caché para evitar doble caché
        path = self.encontrar_ruta_a_star(start, goal, usar_cache=False)
        if path is None:
            return None
        # Convertir a tupla para que sea hashable (requerido por lru_cache)
        return tuple(path)
    
    def should_recalculate(self, agent_pos: Tuple[int, int], 
                          current_path: List[Tuple[int, int]],
                          path_index: int,
                          agent_positions: Dict[Tuple[int, int], int],
                          steps_without_moving: int,
                          anxiety_level: Optional[float] = None) -> bool:
        """
        Determina si el agente debe recalcular su ruta.
        
        Condiciones de recálculo:
        1. Bloqueo inmediato: siguiente celda tiene >= 2 agentes
        2. Estancamiento: steps_without_moving >= 3
        3. Cerca del objetivo pero bloqueado: distancia < 3 y no puede avanzar
        4. Ruta inválida: path_index >= len(current_path)
        
        Parámetros:
        agent_pos : (x, y)
            Posición actual del agente
        current_path : List[(x,y)]
            Ruta que está siguiendo
        path_index : int
            Índice actual en la ruta
        agent_positions : Dict[(x,y), int]
            Diccionario con número de agentes en cada posición {(x,y): num_agents}
        steps_without_moving : int
            Número de timesteps sin moverse
            
        Returns:
        should_recalc : bool
            True si debe recalcular, False si continúa
        """
        # Condición 1: Ruta inválida o vacía
        if not current_path or path_index >= len(current_path):
            if anxiety_level is not None:
                self._log_recalculation_by_anxiety(anxiety_level, 'invalid_path')
            return True
        
        # Condición 2: Estancamiento (no se ha movido en varios pasos)
        if steps_without_moving >= 3:
            if anxiety_level is not None:
                self._log_recalculation_by_anxiety(anxiety_level, 'stagnation')
            self.logger.debug(f"Recalculation triggered: stagnation (steps={steps_without_moving})")
            return True
        
        # Condición 3: Bloqueo inmediato en la siguiente celda
        if path_index + 1 < len(current_path):
            next_cell = current_path[path_index + 1]
            agents_in_next = agent_positions.get(next_cell, 0)
            if agents_in_next >= 2:
                if anxiety_level is not None:
                    self._log_recalculation_by_anxiety(anxiety_level, 'immediate_blockage')
                self.logger.debug(f"Recalculation triggered: immediate blockage at {next_cell}")
                return True
        
        # Condición 4: Cerca del objetivo pero bloqueado
        if len(current_path) > 0:
            goal = current_path[-1]
            distance_to_goal = len(current_path) - path_index - 1
            
            if distance_to_goal < 3:
                # Verificar si puede avanzar hacia el objetivo
                if path_index + 1 < len(current_path):
                    next_cell = current_path[path_index + 1]
                    agents_in_next = agent_positions.get(next_cell, 0)
                    if agents_in_next >= 1:  # Bloqueado por al menos 1 agente
                        if anxiety_level is not None:
                            self._log_recalculation_by_anxiety(anxiety_level, 'near_goal_blocked')
                        self.logger.debug(f"Recalculation triggered: near goal but blocked (distance={distance_to_goal})")
                        return True
                else:
                    # Ya está en el objetivo o la ruta es inválida
                    return False
        
        # Si ninguna condición se cumple, no recalcular
        return False
    
    def _log_recalculation_by_anxiety(self, anxiety_level: float, reason: str):
        """
        Registra una recalculación categorizada por nivel de ansiedad.
        
        Parámetros:
        anxiety_level : float
            Nivel de ansiedad del agente (0-100)
        reason : str
            Razón de la recalculación
        """
        if anxiety_level <= 30:
            category = 'low'
        elif anxiety_level <= 70:
            category = 'medium'
        else:
            category = 'high'
        
        self.stats['recalculations_by_anxiety'][category] += 1
        self.logger.debug(f"Recalculation logged: anxiety={anxiety_level:.1f} ({category}), reason={reason}")
    
    def _hash_agents_near_positions(self, start: Tuple[int, int], goal: Tuple[int, int],
                                    agent_positions: Dict[Tuple[int, int], int],
                                    radius: int = 3) -> int:
        """
        Genera un hash de las posiciones de agentes cerca de start y goal.
        Alternativa más eficiente que no requiere conocer la ruta completa.
        
        Parámetros:
        start : (x, y)
            Posición inicial
        goal : (x, y)
            Posición objetivo
        agent_positions : Dict[(x,y), int]
            Posiciones de agentes
        radius : int
            Radio de búsqueda alrededor de start/goal (por defecto 3)
            
        Returns:
        hash_value : int
            Hash de las posiciones de agentes cerca de start y goal
        """
        agents_near = {}
        
        # Agentes cerca de start
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                pos = (start[0] + dx, start[1] + dy)
                if pos in agent_positions:
                    agents_near[pos] = agent_positions[pos]
        
        # Agentes cerca de goal
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                pos = (goal[0] + dx, goal[1] + dy)
                if pos in agent_positions:
                    agents_near[pos] = agent_positions[pos]
        
        # Crear tupla ordenada para hash consistente
        agents_tuple = tuple(sorted(agents_near.items()))
        return hash(agents_tuple)
    
    def find_path_with_blockage_detection(self, start: Tuple[int, int], 
                                         goal: Tuple[int, int],
                                         agent_positions: Dict[Tuple[int, int], int],
                                         current_path: Optional[List[Tuple[int, int]]] = None) -> Optional[List[Tuple[int, int]]]:
        """
        Encuentra una ruta usando el sistema de detección de bloqueos con caché LRU.
        
        Este método usa el caché LRU para optimizar recálculos frecuentes.
        Si se proporciona current_path, usa agentes en esa ruta para el hash del caché.
        Si no, usa agentes cerca de start/goal (más eficiente).
        
        Parámetros:
        start : (x, y)
            Posición inicial
        goal : (x, y)
            Posición objetivo
        agent_positions : Dict[(x,y), int]
            Posiciones actuales de agentes
        current_path : List[(x,y)], opcional
            Ruta actual si existe (para optimizar el hash del caché)
            
        Returns:
        ruta : List[(x,y)] o None
            Ruta calculada o None si no hay camino
        """
        # Generar hash de agentes para la clave del caché
        if current_path:
            # Si tenemos ruta actual, usar agentes en esa ruta
            agents_hash = self._hash_agents_on_path(current_path, agent_positions)
        else:
            # Si no, usar agentes cerca de start/goal (más eficiente, no requiere calcular ruta primero)
            agents_hash = self._hash_agents_near_positions(start, goal, agent_positions)
        
        # Intentar obtener del caché LRU
        try:
            cached_path = self._cached_path_calculation(start, goal, agents_hash)
            if cached_path is not None:
                return list(cached_path)  # Convertir de tupla a lista
        except (TypeError, AttributeError):
            # Si hay error, continuar sin caché
            pass
        
        # Si no está en caché o hay error, calcular normalmente
        return self.encontrar_ruta_a_star(start, goal, usar_cache=True)
    
    def _add_path_noise(self, path: List[Tuple[int, int]], noise_probability: float = 0.15) -> List[Tuple[int, int]]:
        """
        Añade pequeñas desviaciones a la ruta simulando comportamiento errático en pánico.
        Mantiene la dirección general pero introduce variaciones aleatorias.
        
        Parámetros:
        path : List[(x,y)]
            Ruta original
        noise_probability : float
            Probabilidad de añadir ruido a cada celda (por defecto 0.15)
            
        Returns:
        noisy_path : List[(x,y)]
            Ruta con ruido añadido
        """
        if len(path) < 2:
            return path
        
        noisy_path = [path[0]]  # Mantener inicio
        
        for i in range(1, len(path) - 1):  # No modificar inicio ni fin
            current = path[i]
            
            # Decidir si añadir ruido a esta celda
            if random.random() < noise_probability:
                # Obtener dirección hacia el siguiente punto
                next_pos = path[i + 1]
                dx = next_pos[0] - current[0]
                dy = next_pos[1] - current[1]
                
                # Normalizar dirección
                if dx != 0:
                    dx = 1 if dx > 0 else -1
                if dy != 0:
                    dy = 1 if dy > 0 else -1
                
                # Generar variación aleatoria (pequeña desviación)
                # Opciones: moverse en dirección perpendicular o ligeramente diferente
                variations = [
                    (dx, dy),  # Dirección original
                    (-dy, dx),  # Perpendicular izquierda
                    (dy, -dx),  # Perpendicular derecha
                    (dx + (-1 if random.random() < 0.5 else 1), dy),  # Variación en X
                    (dx, dy + (-1 if random.random() < 0.5 else 1)),  # Variación en Y
                ]
                
                # Seleccionar variación aleatoria
                variation = random.choice(variations)
                new_pos = (current[0] + variation[0], current[1] + variation[1])
                
                # Verificar que la nueva posición es válida en el grafo
                if new_pos in self.grafo and new_pos != noisy_path[-1]:
                    noisy_path.append(new_pos)
                else:
                    # Si no es válida, mantener posición original
                    noisy_path.append(current)
            else:
                # Sin ruido, mantener posición original
                noisy_path.append(current)
        
        # Mantener fin de ruta
        noisy_path.append(path[-1])
        
        return noisy_path
    
    def select_path_by_anxiety(self, k_paths: List[List[Tuple[int, int]]],
                               anxiety_level: float,
                               anxiety_thresholds: Optional[Tuple[int, int]] = None) -> List[Tuple[int, int]]:
        """
        Selecciona una ruta de k_paths basándose en el nivel de ansiedad del agente.
        
        Lógica de selección:
        - Baja ansiedad (0-30): Siempre ruta óptima
        - Ansiedad óptima (30-70): 70% óptima, 20% media, 10% subóptima
        - Alta ansiedad/Pánico (70-100): 30% óptima, 30% media, 40% subóptima
          + 10% probabilidad de añadir ruido (movimientos erráticos)
        
        Parámetros:
        k_paths : List[List[(x,y)]]
            Lista con rutas alternativas [óptima, media, subóptima]
            Debe tener al menos 1 ruta, preferiblemente 3
        anxiety_level : float
            Nivel de ansiedad del agente (0-100)
        anxiety_thresholds : Tuple[int, int], opcional
            Umbrales de ansiedad (mild_max, optimal_max). Si None, usa self.anxiety_thresholds
            
        Returns:
        selected_path : List[(x,y)]
            Ruta seleccionada según el nivel de ansiedad
        """
        # Validar entrada
        if not k_paths or len(k_paths) == 0:
            raise ValueError("k_paths debe contener al menos una ruta")
        
        # Usar umbrales proporcionados o los del objeto
        mild_threshold, optimal_threshold = anxiety_thresholds if anxiety_thresholds else self.anxiety_thresholds
        
        # Asegurar que tenemos al menos 3 rutas (rellenar con la primera si es necesario)
        while len(k_paths) < 3:
            k_paths.append(k_paths[0])
        
        # Limitar ansiedad al rango válido
        anxiety_level = max(0.0, min(100.0, anxiety_level))
        
        selected_path = None
        selection_reason = ""
        noise_added = False
        
        # Lógica de selección según nivel de ansiedad
        if anxiety_level <= mild_threshold:
            # Baja ansiedad (0-30): Siempre ruta óptima
            selected_path = k_paths[0]
            selection_reason = f"Baja ansiedad ({anxiety_level:.1f}): Ruta óptima"
        
        elif anxiety_level <= optimal_threshold:
            # Ansiedad óptima (30-70): Distribución probabilística
            weights = [0.7, 0.2, 0.1]  # 70% óptima, 20% media, 10% subóptima
            selected_path = random.choices(k_paths[:3], weights=weights)[0]
            path_index = k_paths.index(selected_path)
            path_type = ["óptima", "media", "subóptima"][path_index]
            selection_reason = f"Ansiedad óptima ({anxiety_level:.1f}): Ruta {path_type} (probabilística)"
        
        else:
            # Alta ansiedad/Pánico (70-100): Distribución con preferencia por subóptima
            weights = [0.3, 0.3, 0.4]  # 30% óptima, 30% media, 40% subóptima
            selected_path = random.choices(k_paths[:3], weights=weights)[0]
            path_index = k_paths.index(selected_path)
            path_type = ["óptima", "media", "subóptima"][path_index]
            selection_reason = f"Alta ansiedad/Pánico ({anxiety_level:.1f}): Ruta {path_type} (probabilística)"
            
            # Añadir ruido con 10% de probabilidad (movimientos erráticos)
            if random.random() < 0.1:
                selected_path = self._add_path_noise(selected_path)
                noise_added = True
                selection_reason += " + Ruido añadido (comportamiento errático)"
        
        # Log de la decisión para análisis posterior
        decision_log = {
            'anxiety_level': anxiety_level,
            'anxiety_category': (
                'baja' if anxiety_level <= mild_threshold else
                'óptima' if anxiety_level <= optimal_threshold else
                'alta/pánico'
            ),
            'selected_path_index': k_paths.index(selected_path) if selected_path in k_paths else -1,
            'path_length': len(selected_path),
            'noise_added': noise_added,
            'reason': selection_reason,
            'thresholds': (mild_threshold, optimal_threshold)
        }
        self.anxiety_decisions.append(decision_log)
        
        # Logging automático
        anxiety_category = decision_log['anxiety_category']
        self.logger.info(f"Path selected by anxiety: level={anxiety_level:.1f}, category={anxiety_category}, "
                        f"path_index={decision_log['selected_path_index']}, length={len(selected_path)}, "
                        f"noise={noise_added}")
        
        return selected_path
    
    def get_anxiety_statistics(self) -> Dict:
        """
        Retorna estadísticas sobre las decisiones de selección por ansiedad.
        
        Returns:
        stats : Dict
            Diccionario con estadísticas de decisiones
        """
        if not self.anxiety_decisions:
            return {
                'total_decisions': 0,
                'by_category': {},
                'noise_added_count': 0,
                'noise_rate': 0.0
            }
        
        total = len(self.anxiety_decisions)
        by_category = {}
        noise_count = 0
        
        for decision in self.anxiety_decisions:
            category = decision['anxiety_category']
            by_category[category] = by_category.get(category, 0) + 1
            if decision['noise_added']:
                noise_count += 1
        
        return {
            'total_decisions': total,
            'by_category': by_category,
            'noise_added_count': noise_count,
            'noise_rate': noise_count / total if total > 0 else 0.0,
            'average_anxiety': np.mean([d['anxiety_level'] for d in self.anxiety_decisions]) if self.anxiety_decisions else 0.0
        }