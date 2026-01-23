
from typing import Self, Optional, Tuple, Dict
import random
import numpy as np
import copy

class AgentExtendido:
    """
    Agent con características avanzadas.
        - instances: lista de clase con todos los agentes
        - history: lista de snapshots
        - stores(): guarda estado actual
        - floor_field: navegación inteligente
        - tipo: 'vivo'/'menos_vivo' (priorización)
        - conflictos: tracking de colisiones
        - proponer_movimiento(): movimiento automático inteligente
    """
    
    # Atributos de clase (igual que tu Agent)
    instances: list[Self] = []
    history: list[list[Self]] = []
    
    def __init__(self, 
                 type: str = "defaults",
                 agent_type: str = "vivo",  # 'vivo' o 'menos_vivo'
                 floor_field = None,
                 path_selector = None,
                 x: Optional[int] = None,
                 y: Optional[int] = None):
        """
        Inicializa agente extendido.
        Parámetros:
        type : str
            Tipo de agente
        agent_type : str
            'vivo' o 'menos_vivo' - para priorización en conflictos
        floor_field : Floor_field, opcional
            Campo de piso para navegación inteligente
        path_selector : PathSelector, opcional
            Selector de rutas para navegación inteligente con A*
        x, y : int, opcional
            Posición inicial del agente
        """

        self.id: int = len(AgentExtendido.instances)
        self.agent_type: str = type
        self.pos_x: int | None = x
        self.pos_y: int | None = y
        self.if_change: bool = False
        self.tipo: str = agent_type  # 'vivo' o 'menos_vivo'
        self.activo: bool = True  # False cuando evacua
        self.floor_field = floor_field  # Para navegación inteligente
        self.conflictos_totales: int = 0
        self.conflictos_perdidos: int = 0
        self.ansiedad: int = 0   # Nivel de ansiedad (0-100)
        
        # PathSelector integration
        self.path_selector = path_selector
        self.usa_enrutamiento_inteligente = (path_selector is not None)
        
        # Nuevos atributos para PathSelector
        self.current_path: Optional[list] = None  # Ruta actual que está siguiendo
        self.path_index: int = 0  # Índice actual en la ruta
        self.steps_without_moving: int = 0  # Pasos sin moverse
        self.alternative_paths: list = []  # Las 3 rutas alternativas calculadas
        
        # Mantener compatibilidad con código existente
        self.ruta_planificada = None  # Alias para current_path (compatibilidad)
        self.pasos_desde_recalculo = 0  # Alias para steps_without_moving (compatibilidad)
        
        AgentExtendido.instances.append(self)
    
    
    @classmethod
    def stores(cls) -> None:
        """Guarda snapshot del estado actual"""
        # Hacer copia profunda de los agentes para preservar su estado
        snapshot = [copy.deepcopy(agent) for agent in cls.instances]
        cls.history.append(snapshot)
    
    def proponer_movimiento(self, goal: Optional[Tuple[int, int]] = None,
                           agent_positions: Optional[Dict[Tuple[int, int], int]] = None) -> Tuple[int, int]:
        """
        Propone movimiento del agente.
        
        Si usa PathSelector, utiliza elegir_ruta para seleccionar/calcular ruta.
        Si no, usa comportamiento greedy con floor_field.
        
        Parámetros:
        goal : Tuple[int, int], opcional
            Posición objetivo (puerta). Si None y hay path_selector, se calcula automáticamente.
        agent_positions : Dict[Tuple[int, int], int], opcional
            Diccionario con ocupación de celdas {(x,y): num_agents}.
            Si None, se calcula automáticamente desde AgentExtendido.instances.
        
        Returns:
        Tuple[int, int] : Posición propuesta
        """
        if not self.activo or self.pos_x is None or self.pos_y is None:
            return (self.pos_x, self.pos_y)
        
        if self.usa_enrutamiento_inteligente:
            return self._movimiento_con_path_selector(goal, agent_positions)
        return self._movimiento_greedy_floor_field()
    
    def _movimiento_greedy_floor_field(self) -> Tuple[int, int]: #PARA LA GRILLA
        """
        Comportamiento ORIGINAL: seguir floor field de manera greedy.
        Propone el mejor movimiento según floor_field.
        
        Si NO tiene floor_field, retorna posición actual.
        Si tiene floor_field, elige la celda vecina con menor valor.
        
        Retorna:(x, y) : Tupla con la posición propuesta
        """
        if self.floor_field is None:
            return (self.pos_x, self.pos_y)
        
        pasos = [
            (0, 1), (1, 0), (0, -1), (-1, 0),
            (1, 1), (1, -1), (-1, 1), (-1, -1)
        ]
        
        mejor_valor = self.floor_field.valores[self.pos_y, self.pos_x]
        mejores = [(self.pos_x, self.pos_y)]
        
        for dx, dy in pasos:
            nx, ny = self.pos_x + dx, self.pos_y + dy
            
            if 0 <= nx < self.floor_field.width and 0 <= ny < self.floor_field.height:
                v = self.floor_field.valores[ny, nx]
                
                if v < mejor_valor:
                    mejor_valor = v
                    mejores = [(nx, ny)]
                elif np.isclose(v, mejor_valor):
                    mejores.append((nx, ny))
        
        return random.choice(mejores)

    def _get_agent_positions(self) -> Dict[Tuple[int, int], int]:
        """
        Obtiene diccionario con ocupación de celdas desde AgentExtendido.instances.
        
        Returns:
        Dict[Tuple[int, int], int] : {(x,y): num_agents}
        """
        agent_positions = {}
        for agent in AgentExtendido.instances:
            if agent.activo and agent.pos_x is not None and agent.pos_y is not None:
                pos = (agent.pos_x, agent.pos_y)
                agent_positions[pos] = agent_positions.get(pos, 0) + 1
        return agent_positions
    
    def elegir_ruta(self, goal: Tuple[int, int], 
                   agent_positions: Optional[Dict[Tuple[int, int], int]] = None):
        """
        Elige o recalcula la ruta del agente basándose en su estado.
        
        Determina si necesita recalcular usando should_recalculate.
        Si necesita recalcular, encuentra 3 rutas alternativas y selecciona una
        basándose en el nivel de ansiedad del agente.
        
        Parámetros:
        goal : Tuple[int, int]
            Posición objetivo (puerta) (x, y)
        agent_positions : Dict[Tuple[int, int], int], opcional
            Diccionario con ocupación de celdas {(x,y): num_agents}.
            Si None, se calcula automáticamente.
        """
        if not self.usa_enrutamiento_inteligente or self.path_selector is None:
            return
        
        # Obtener agent_positions si no se proporcionó
        if agent_positions is None:
            agent_positions = self._get_agent_positions()
        
        pos_actual = (self.pos_x, self.pos_y)
        
        # Determinar si necesita recalcular
        needs_recalc = (
            self.current_path is None or
            len(self.current_path) == 0 or
            self.path_selector.should_recalculate(
                agent_pos=pos_actual,
                current_path=self.current_path,
                path_index=self.path_index,
                agent_positions=agent_positions,
                steps_without_moving=self.steps_without_moving
            )
        )
        
        if needs_recalc:
            # Encontrar 3 rutas alternativas
            self.alternative_paths = self.path_selector.find_k_paths(
                start=pos_actual,
                goal=goal,
                k=3
            )
            
            # Si se encontraron rutas, seleccionar basándose en ansiedad
            if self.alternative_paths and len(self.alternative_paths) > 0:
                # Seleccionar ruta basándose en ansiedad (0-100)
                anxiety_level = float(self.ansiedad)  # Convertir a float si es necesario
                self.current_path = self.path_selector.select_path_by_anxiety(
                    k_paths=self.alternative_paths,
                    anxiety_level=anxiety_level
                )
                
                # Sincronizar con atributos de compatibilidad
                self.ruta_planificada = self.current_path
                
                # Resetear índices y contadores
                self.path_index = 0
                self.steps_without_moving = 0
                self.pasos_desde_recalculo = 0
            else:
                # No se encontraron rutas, limpiar
                self.current_path = None
                self.ruta_planificada = None
    
    def _movimiento_con_path_selector(self, 
                                     goal: Optional[Tuple[int, int]] = None,
                                     agent_positions: Optional[Dict[Tuple[int, int], int]] = None) -> Tuple[int, int]:
        """
        Movimiento inteligente usando PathSelector con A* y selección por ansiedad.
        
        Estrategia:
        1. Llama a elegir_ruta para seleccionar/calcular ruta
        2. Sigue la ruta planificada
        3. Si ruta falla -> fallback a greedy
        
        Parámetros:
        goal : Tuple[int, int], opcional
            Posición objetivo (puerta). Si None, se calcula automáticamente.
        agent_positions : Dict[Tuple[int, int], int], opcional
            Diccionario con ocupación de celdas.
        
        Returns:
        Tuple[int, int] : Posición propuesta
        """
        pos_actual = (self.pos_x, self.pos_y)
        
        # Obtener goal si no se proporcionó
        if goal is None:
            if self.floor_field is not None and hasattr(self.floor_field, 'puertas'):
                puertas = self.floor_field.puertas
                if puertas:
                    goal = self.path_selector.encontrar_mejor_puerta(pos_actual, puertas)
                else:
                    # Sin puertas, usar fallback
                    return self._movimiento_greedy_floor_field()
            else:
                # Sin floor_field, usar fallback
                return self._movimiento_greedy_floor_field()
        
        # Elegir o recalcular ruta
        self.elegir_ruta(goal, agent_positions)
        
        # Seguir la ruta planificada
        if self.current_path and self.path_index < len(self.current_path):
            next_pos = self.current_path[self.path_index]
            
            # Verificar que la siguiente posición es válida
            if next_pos == pos_actual:
                # Ya estamos en la posición objetivo, avanzar índice
                self.path_index += 1
                if self.path_index < len(self.current_path):
                    next_pos = self.current_path[self.path_index]
                else:
                    # Llegamos al final de la ruta
                    return pos_actual
            else:
                # Avanzar índice para la próxima vez
                self.path_index += 1
            
            return next_pos
        
        # Fallback a comportamiento greedy
        return self._movimiento_greedy_floor_field()
    
    def _proponer_movimiento_legacy(self) -> Tuple[int, int]:
        """
        Método legacy para compatibilidad con código existente.
        Usa el comportamiento greedy original.
        
        Returns:
        Tuple[int, int] : Posición propuesta
        """
        return self._movimiento_greedy_floor_field()

    def mover_a(self, nueva_x: int, nueva_y: int):
        """
        Mueve el agente a la nueva posición.
        Parámetros:
        nueva_x, nueva_y : int
            Nueva posición
        """
        if not self.activo:
            return
        
        # Detectar si hubo cambio
        old_pos = (self.pos_x, self.pos_y)
        self.if_change = (nueva_x != self.pos_x or nueva_y != self.pos_y)
        
        # Actualizar posición
        self.pos_x = nueva_x
        self.pos_y = nueva_y
        
        # Actualizar contador de pasos sin moverse
        if self.if_change:
            self.steps_without_moving = 0
            self.pasos_desde_recalculo = 0
        else:
            self.steps_without_moving += 1
            self.pasos_desde_recalculo += 1
        
        # Verificar si llegó a la salida (valor = 0 en floor_field)
        if self.floor_field is not None:
            if self.floor_field.valores[self.pos_y, self.pos_x] == 0:
                self.activo = False
                # Limpiar ruta cuando evacua
                self.current_path = None
                self.ruta_planificada = None
    
    def __repr__(self):
        """Representación para debugging"""
        estado = "activo" if self.activo else "evacuado"
        return f"Agent#{self.id}({self.pos_x},{self.pos_y})[{self.tipo}][{estado}]"

# ========== FUNCIONES DE MOVIMIENTO CON RESOLUCIÓN DE CONFLICTOS ==========

def mover_agentes_con_conflictos(agentes: list[AgentExtendido]) -> dict:
    """
    Mueve todos los agentes resolviendo conflictos con priorización (movimiento
    automático inteligente basado en floor_field).
    
    Reglas:
    1. Cada agente propone su movimiento (según floor_field)
    2. Si varios quieren la misma celda:
       - Prioridad a 'vivos' sobre 'menos_vivos'
       - Si empate de tipo, azar
    3. Los perdedores se quedan quietos
    4. Se registran conflictos
    5. NUNCA dos agentes pueden estar en la misma celda
    
    Parámetros:
    agentes : list[AgentExtendido]
        Lista de agentes a mover
    
    Retorna:
    dict : Estadísticas del paso
        - 'conflictos_totales': número de celdas con conflicto
        - 'agentes_en_conflicto': agentes involucrados
        - 'movimientos': agentes que se movieron
    """
    propuestas = {}
    
    # Paso 1: Cada agente propone su movimiento
    for agente in agentes:
        if agente.activo:
            destino = agente.proponer_movimiento()
            propuestas.setdefault(destino, []).append(agente)
    
    # Paso 2: Resolver conflictos y asegurar que no haya dos agentes en la misma celda
    stats = {
        'conflictos_totales': 0,
        'agentes_en_conflicto': 0,
        'movimientos': 0
    }
    
    # Rastrear qué celdas están ocupadas después de los movimientos
    celdas_ocupadas = {}
    
    # Primero, registrar las posiciones actuales de los agentes activos
    for agente in agentes:
        if agente.activo and agente.pos_x is not None and agente.pos_y is not None:
            pos_actual = (agente.pos_x, agente.pos_y)
            celdas_ocupadas[pos_actual] = agente
    
    # Procesar propuestas en orden de prioridad
    for destino, lista_agentes in propuestas.items():
        # Verificar si el destino ya está ocupado por otro agente que ya se movió
        if destino in celdas_ocupadas:
            # El destino ya está ocupado, todos los que querían ir ahí se quedan quietos
            stats['conflictos_totales'] += 1
            stats['agentes_en_conflicto'] += len(lista_agentes)
            
            for a in lista_agentes:
                a.conflictos_totales += 1
                a.conflictos_perdidos += 1
                a.if_change = False
            continue
        
        if len(lista_agentes) == 1:
            # Sin conflicto entre agentes que quieren esta celda
            agente = lista_agentes[0]
            # Verificar que el agente realmente se puede mover (no está ya en esa posición)
            if agente.pos_x != destino[0] or agente.pos_y != destino[1]:
                agente.mover_a(destino[0], destino[1])
                if agente.if_change:
                    stats['movimientos'] += 1
                    # Marcar la celda como ocupada
                    celdas_ocupadas[destino] = agente
        else:
            # CONFLICTO: varios quieren la misma celda
            stats['conflictos_totales'] += 1
            stats['agentes_en_conflicto'] += len(lista_agentes)
            
            # Registrar conflicto en todos
            for a in lista_agentes:
                a.conflictos_totales += 1
            
            # Priorización: vivos > menos_vivos
            vivos = [a for a in lista_agentes if a.tipo == 'vivo']
            menos_vivos = [a for a in lista_agentes if a.tipo == 'menos_vivo']
            
            if vivos:
                elegido = random.choice(vivos)
            else:
                elegido = random.choice(menos_vivos)
            
            # Mover al ganador solo si realmente se puede mover
            if elegido.pos_x != destino[0] or elegido.pos_y != destino[1]:
                elegido.mover_a(destino[0], destino[1])
                if elegido.if_change:
                    stats['movimientos'] += 1
                    # Marcar la celda como ocupada
                    celdas_ocupadas[destino] = elegido
            
            # Perdedores se quedan quietos
            for otro in lista_agentes:
                if otro != elegido:
                    otro.conflictos_perdidos += 1
                    otro.if_change = False
    
    return stats
