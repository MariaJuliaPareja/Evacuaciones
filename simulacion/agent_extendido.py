"""
Agente extendido con PathSelector, A* y desbloqueo progresivo de rutas.

Este módulo implementa el sistema completo de agentes inteligentes con:
- Desbloqueo progresivo de rutas (1→3→5) basado en estancamiento
- Selección de rutas según ansiedad (Yerkes-Dodson Law)
- Gestión automática de ansiedad y steps_without_moving
- Resolución de conflictos entre agentes

Referencias:
- Ramírez et al. (2019) - Physica A 531: Model with random stalling and anxiety
- Ramírez et al. (2021) - PRE 104: CA model with progressive path unlocking
- Varas et al. (2007) - Physica A 382: Floor field algorithm
"""

import random
from types import SimpleNamespace
from typing import Tuple, Optional, Dict, List


class AgentExtendido:
    """
    Agente con PathSelector, A* y desbloqueo progresivo de rutas.
    
    Sistema de desbloqueo basado en estancamiento:
    - 0-2 pasos estancado: 1 ruta (óptima)
    - 3-5 pasos estancado: 3 rutas alternativas
    - 6+ pasos estancado: 5 rutas (todas las opciones)
    
    Sistema de ansiedad (Yerkes-Dodson Law):
    - Baja ansiedad (0-30): Prefiere ruta óptima
    - Ansiedad óptima (30-70): Balance entre rutas
    - Alta ansiedad (70-100): Prefiere rutas alternativas
    """
    
    # Atributos de clase para tracking global
    instances: List['AgentExtendido'] = []
    history: List[Dict] = []
    
    def __init__(self, agent_type: str, floor_field, path_selector, x: int, y: int):
        """
        Inicializa un agente extendido.
        
        Parámetros:
        agent_type : str
            Tipo de agente ('rapido' o 'lento')
        floor_field : Floor_field
            Campo de piso con valores de distancia
        path_selector : PathSelector o None
            Selector de rutas inteligente. Si es None, usa movimiento greedy
        x, y : int
            Posición inicial del agente
        """
        # ATRIBUTOS BÁSICOS
        self.id = len(AgentExtendido.instances)
        self.tipo = agent_type  # 'rapido' o 'lento'
        self.pos_x = x
        self.pos_y = y
        self.activo = True
        self.if_change = False  # Indica si se movió en el último paso
        
        # INTEGRACIÓN CON PATHFINDER
        self.floor_field = floor_field
        self.path_selector = path_selector
        self.usa_enrutamiento_inteligente = (path_selector is not None)
        
        # SISTEMA DE RUTAS (PathSelector)
        self.current_path = None  # Ruta actual siguiendo
        self.path_index = 0  # Índice en la ruta actual
        self.all_calculated_paths = []  # Hasta 5 rutas calculadas
        self.unlocked_paths_count = 1  # Start con 1 ruta desbloqueada
        
        # SISTEMA DE ANSIEDAD (Yerkes-Dodson Law)
        self.ansiedad = random.uniform(20, 90)  # 0-100
        self.steps_without_moving = 0  # CRÍTICO: controla desbloqueo
        self.calmness_threshold = 3  # Umbral para desbloquear rutas
        
        # TRACKING
        self.conflictos_totales = 0
        self.conflictos_perdidos = 0
        
        # COOLDOWN DE RECALCULACIÓN (inercia cognitiva)
        self.last_recalculation_step = -1  # Paso de la última recalculación
        self.recalculation_cooldown = 4  # Pasos mínimos entre recalculaciones
        
        # FLAG PARA VISUALIZACIÓN
        self.recalculated_this_step = False  # Indica si recalculó en el paso actual
        
        # HISTORIAL DE TRAYECTORIA (opcional, para debugging)
        self.trajectory_history = []  # Lista de (x, y) visitadas
        
        # REGISTRO DE CLASE
        AgentExtendido.instances.append(self)
    
    @classmethod
    def stores(cls) -> None:
        """
        Añade a `history` una instantánea ligera de todos los agentes (serializable a PKL
        y compatible con el visualizador).
        """
        paso = []
        for a in cls.instances:
            cp = getattr(a, 'current_path', None)
            if cp is not None:
                cp = list(cp)
            acp = getattr(a, 'all_calculated_paths', None)
            if acp is not None:
                acp = [list(p) if p is not None else None for p in acp]
            pi = getattr(a, 'path_index', 0)
            paso.append(
                SimpleNamespace(
                    id=a.id,
                    tipo=a.tipo,
                    activo=a.activo,
                    pos_x=a.pos_x,
                    pos_y=a.pos_y,
                    conflictos_totales=a.conflictos_totales,
                    conflictos_perdidos=a.conflictos_perdidos,
                    ansiedad=a.ansiedad,
                    current_path=cp,
                    path_index=pi,
                    current_path_index=pi,
                    all_calculated_paths=acp,
                    unlocked_paths_count=getattr(a, 'unlocked_paths_count', 1),
                    steps_without_moving=getattr(a, 'steps_without_moving', 0),
                )
            )
        cls.history.append(paso)
    
    def elegir_ruta(self, goal: Tuple[int, int], agent_positions: Optional[Dict[Tuple[int, int], int]] = None):
        """
        Elige o recalcula ruta SOLO SI ES NECESARIO.
        NO recalcula si ya tiene una ruta válida.
        
        IMPORTANTE:
        - steps_without_moving se gestiona en mover_a(), NO aquí
        - unlocked_paths_count determina cuántas rutas puede elegir
        - Usar try/except para manejar fallos de pathfinding
        
        Parámetros:
        goal : Tuple[int, int]
            Posición objetivo (puerta)
        agent_positions : Dict[Tuple[int, int], int], opcional
            Diccionario con número de agentes en cada posición
        """
        if not self.usa_enrutamiento_inteligente or self.path_selector is None:
            return
        
        if agent_positions is None:
            agent_positions = {}
        
        # IMPORTANTE: Reset flag al inicio de cada paso
        self.recalculated_this_step = False
        
        pos_actual = (self.pos_x, self.pos_y)
        
        # COOLDOWN: Verificar si pasó suficiente tiempo desde la última recalculación
        # (inercia cognitiva: no cambiar estrategia instantáneamente)
        current_step = getattr(self, '_current_simulation_step', 0)
        steps_since_recalc = current_step - self.last_recalculation_step
        
        if steps_since_recalc < self.recalculation_cooldown and self.current_path is not None:
            # Aún en cooldown, mantener ruta actual
            return
        
        # VERIFICAR SI REALMENTE NECESITA RECALCULAR
        needs_recalc = (
            self.current_path is None or
            len(self.current_path) == 0 or
            self.path_index >= len(self.current_path) or
            self.path_selector.should_recalculate(
                agent_pos=pos_actual,
                current_path=self.current_path,
                path_index=self.path_index,
                agent_positions=agent_positions,
                steps_without_moving=self.steps_without_moving,
                anxiety_level=None  # Ya no usar ansiedad para decidir recálculo
            )
        )
        
        # SI NO NECESITA RECALCULAR, SALIR INMEDIATAMENTE
        if not needs_recalc:
            # Ya tiene una ruta válida, mantenerla
            return
        
        # ========================================
        # SI LLEGA AQUÍ, SÍ VA A RECALCULAR
        # ========================================
        
        # NUEVO: Marcar que recalculó en este paso
        self.recalculated_this_step = True
        
        # IMPORTANTE: Limpiar rutas antiguas antes de recalcular
        self.all_calculated_paths = []
        self.current_path = None
        
        # Si llega aquí, SÍ necesita recalcular
        # Calcular unlocked_paths_count
        current_stuck = self.steps_without_moving
        unlocked_count = self.path_selector.calculate_unlocked_paths(
            steps_without_moving=current_stuck,
            calmness_threshold=self.calmness_threshold
        )
        
        # Encontrar rutas
        try:
            all_paths = self.path_selector.find_progressive_paths(
                start=pos_actual,
                goal=goal,
                num_paths=5
            )
        except (ValueError, Exception) as e:
            # Fallback: intentar con find_k_paths
            try:
                all_paths = self.path_selector.find_k_paths(
                    start=pos_actual,
                    goal=goal,
                    k=min(5, unlocked_count)
                )
            except Exception:
                all_paths = []
        
        # Verificar que encontramos rutas
        if not all_paths or len(all_paths) == 0:
            # No se encontraron rutas, mantener la actual si existe
            return
        
        # Seleccionar ruta según ansiedad
        selected_path = self.path_selector.select_path_by_anxiety(
            k_paths=all_paths,
            anxiety_level=self.ansiedad,
            num_available_paths=unlocked_count
        )
        
        if selected_path is None or len(selected_path) == 0:
            return
        
        # Actualizar ruta
        self.current_path = selected_path
        self.path_index = 0  # Empezar desde el inicio
        self.all_calculated_paths = all_paths
        self.unlocked_paths_count = unlocked_count
        
        # Registrar paso de recalculación para cooldown
        current_step = getattr(self, '_current_simulation_step', 0)
        self.last_recalculation_step = current_step
    
    def proponer_movimiento(self, goal: Optional[Tuple[int, int]] = None, 
                           agent_positions: Optional[Dict[Tuple[int, int], int]] = None) -> Tuple[int, int]:
        """
        Propone siguiente movimiento.
        
        IMPORTANTE:
        - Llama elegir_ruta() que solo recalcula si es necesario
        - Retorna next_pos de la ruta actual
        - NO incrementa path_index (se hace en mover_a)
        
        Parámetros:
        goal : Tuple[int, int], opcional
            Posición objetivo (puerta). Si es None, se calcula automáticamente
        agent_positions : Dict[Tuple[int, int], int], opcional
            Diccionario con número de agentes en cada posición
            
        Returns:
        Tuple[int, int]
            Posición propuesta (x, y)
        """
        if not self.activo or self.pos_x is None or self.pos_y is None:
            return (self.pos_x, self.pos_y)
        
        if self.usa_enrutamiento_inteligente and self.path_selector is not None:
            # Obtener agent_positions si no se proveyó
            if agent_positions is None:
                agent_positions = {}
            
            # Obtener goal si no se proveyó
            if goal is None:
                goal = self._encontrar_puerta_mas_cercana()
            
            if goal is None:
                return self._movimiento_greedy_floor_field()
            
            # Elegir/recalcular ruta (solo si es necesario)
            self.elegir_ruta(goal, agent_positions)
            
            # Verificar que tenemos ruta válida
            if self.current_path is None or len(self.current_path) == 0:
                return self._movimiento_greedy_floor_field()
            
            # Verificar que path_index es válido
            if self.path_index >= len(self.current_path):
                return self._movimiento_greedy_floor_field()
            
            # Si path_index apunta a la posición actual, avanzar al siguiente
            pos_actual = (self.pos_x, self.pos_y)
            if (self.path_index < len(self.current_path) and 
                self.current_path[self.path_index] == pos_actual):
                self.path_index += 1
            
            # Verificar nuevamente después del ajuste
            if self.path_index >= len(self.current_path):
                return self._movimiento_greedy_floor_field()
            
            # Retornar SIGUIENTE posición en la ruta
            next_pos = self.current_path[self.path_index]
            
            # NO incrementar path_index aquí
            # Se incrementa en mover_a() solo si el movimiento fue exitoso
            
            return next_pos
        else:
            # No usa PathSelector, usar greedy tradicional
            return self._movimiento_greedy_floor_field()
    
    def mover_a(self, nueva_x: int, nueva_y: int):
        """
        Ejecuta movimiento y actualiza contadores.
        
        CRÍTICO:
        - path_index se incrementa SOLO si se movió exitosamente
        - steps_without_moving se resetea SOLO si se movió
        - if_change debe calcularse ANTES de actualizar posición
        
        Parámetros:
        nueva_x, nueva_y : int
            Nueva posición propuesta
        """
        if not self.activo:
            return
        
        # Detectar si hubo cambio ANTES de actualizar posición
        old_pos = (self.pos_x, self.pos_y)
        new_pos = (nueva_x, nueva_y)
        self.if_change = (old_pos != new_pos)
        
        # ========================================
        # VALIDACIÓN: Detectar saltos extraños (anti-teletransporte)
        # ========================================
        if self.if_change:
            # Distancia Manhattan
            dist = abs(nueva_x - self.pos_x) + abs(nueva_y - self.pos_y)
            
            # Un movimiento normal es 1 (ortogonal) o 2 (diagonal)
            # Si es > 2, algo está mal
            if dist > 2:
                # OPCIÓN: Forzar recalculación si el salto es muy grande
                if dist > 3:
                    # Salto excesivo, limpiar ruta
                    self.current_path = None
                    self.path_index = 0
                    self.all_calculated_paths = []
        
        # Actualizar posición
        self.pos_x = nueva_x
        self.pos_y = nueva_y
        
        if self.if_change:
            # ✅ SE MOVIÓ EXITOSAMENTE
            self.steps_without_moving = 0
            
            # Guardar en historial de trayectoria
            self.trajectory_history.append((nueva_x, nueva_y))
            
            # ========================================
            # Incrementar path_index solo si fue correcto
            # ========================================
            if self.current_path and len(self.current_path) > 0:
                expected_pos = None
                if self.path_index < len(self.current_path):
                    expected_pos = self.current_path[self.path_index]
                
                if expected_pos and new_pos == expected_pos:
                    # ✅ Movimiento correcto según la ruta
                    self.path_index += 1
                else:
                    # ⚠ Se desvió de la ruta planificada
                    # Esto puede pasar por conflictos con otros agentes
                    
                    # Verificar si la nueva posición está en alguna parte de la ruta
                    if new_pos in self.current_path:
                        # Buscar índice
                        try:
                            new_index = self.current_path.index(new_pos)
                            # Solo actualizar si está ADELANTE
                            if new_index > self.path_index:
                                self.path_index = new_index + 1
                            else:
                                # Se movió hacia atrás o está en el mismo lugar, mantener índice
                                if new_index == self.path_index:
                                    self.path_index += 1
                                # Si está atrás, no avanzar
                        except ValueError:
                            # No está en la ruta, avanzar índice de todas formas
                            if self.path_index < len(self.current_path):
                                self.path_index += 1
                    else:
                        # No está en la ruta, avanzar índice de todas formas
                        if self.path_index < len(self.current_path):
                            self.path_index += 1
            
            # Reducir ansiedad
            reduction = max(1, int(self.ansiedad * 0.1))
            self.ansiedad = max(0, self.ansiedad - reduction)
            
        else:
            # ❌ NO SE MOVIÓ (quedó en el mismo lugar)
            self.steps_without_moving += 1
            
            # NO incrementar path_index
            # La ruta sigue siendo válida, simplemente no pudo avanzar este paso
            
            # Aumentar ansiedad
            increase = min(5, 1 + (self.steps_without_moving // 2))
            self.ansiedad = min(100, self.ansiedad + increase)
        
        # Verificar si llegó a puerta (valor = 0)
        if self.floor_field is not None:
            try:
                if self.floor_field.valores[self.pos_y, self.pos_x] == 0:
                    self.activo = False
                    # Limpiar rutas
                    self.current_path = None
                    self.all_calculated_paths = []
                    self.path_index = 0
            except (IndexError, AttributeError):
                pass
    
    def _movimiento_greedy_floor_field(self) -> Tuple[int, int]:
        """
        Fallback: movimiento greedy tradicional usando floor field.
        
        Usar cuando:
        - No hay PathSelector
        - Falla el pathfinding
        - Modo de emergencia
        
        Lógica: Moverse al vecino con menor valor de floor_field (más cerca de la puerta).
        
        Returns:
        Tuple[int, int]
            Posición propuesta (x, y)
        """
        if self.floor_field is None:
            # Sin floor_field, quedarse en su lugar
            return (self.pos_x, self.pos_y)
        
        # Obtener valor actual
        try:
            mejor_valor = self.floor_field.valores[self.pos_y, self.pos_x]
        except (IndexError, AttributeError):
            return (self.pos_x, self.pos_y)
        
        mejor_pos = (self.pos_x, self.pos_y)
        
        # Revisar vecinos (4 direcciones: N, S, E, O)
        direcciones = [(0, 1), (1, 0), (0, -1), (-1, 0)]
        
        for dx, dy in direcciones:
            nx = self.pos_x + dx
            ny = self.pos_y + dy
            
            # Verificar límites
            if (0 <= nx < self.floor_field.width and 
                0 <= ny < self.floor_field.height):
                try:
                    v = self.floor_field.valores[ny, nx]
                    # Valor válido: < 500 (no es obstáculo)
                    # Preferir valores menores (más cerca de puerta)
                    if v < 500 and v < mejor_valor:
                        mejor_valor = v
                        mejor_pos = (nx, ny)
                except (IndexError, AttributeError):
                    continue
        
        return mejor_pos
    
    def _encontrar_puerta_mas_cercana(self) -> Optional[Tuple[int, int]]:
        """
        Encuentra la puerta más cercana al agente.
        
        Returns:
        Tuple[int, int] o None
            Posición de la puerta más cercana, o None si no hay puertas
        """
        if self.floor_field is None or not hasattr(self.floor_field, 'puertas'):
            return None
        
        if not self.floor_field.puertas:
            return None
        
        # Encontrar puerta con menor distancia Manhattan
        min_dist = float('inf')
        puerta_cercana = None
        
        for puerta in self.floor_field.puertas:
            dist = abs(self.pos_x - puerta[0]) + abs(self.pos_y - puerta[1])
            if dist < min_dist:
                min_dist = dist
                puerta_cercana = puerta
        
        return puerta_cercana


def mover_agentes_con_conflictos(agentes: List[AgentExtendido], 
                                 goals: Optional[Dict[int, Tuple[int, int]]] = None) -> Dict:
    """
    Mueve todos los agentes resolviendo conflictos.
    
    FLUJO:
    1. Cada agente propone movimiento (proponer_movimiento)
    2. Detectar conflictos (varios → misma celda)
    3. Resolver conflictos:
       - Prioridad: 'rapido' > 'lento'
       - Si empate: random
       - Ganador: ejecuta mover_a(destino)
       - Perdedores: ejecutan mover_a(posición_actual)
    4. Registrar stats
    
    IMPORTANTE:
    - NUNCA dos agentes en misma celda
    - mover_a() gestiona steps_without_moving automáticamente
    - Registrar conflictos_totales y conflictos_perdidos
    
    Parámetros:
    agentes : List[AgentExtendido]
        Lista de agentes a mover
    goals : Dict[int, Tuple[int, int]], opcional
        Diccionario {agente_id: goal} con objetivos específicos por agente
        
    Returns:
    Dict
        Estadísticas del movimiento:
        - 'movidos': número de agentes que se movieron
        - 'conflictos': número de conflictos detectados
        - 'resueltos': número de conflictos resueltos
    """
    if not agentes:
        return {'movidos': 0, 'conflictos': 0, 'resueltos': 0}
    
    # Paso 1: Cada agente propone su movimiento
    propuestas = {}  # {agente_id: (x, y)}
    agent_positions = {}  # {(x, y): [agente_id, ...]}
    
    # Calcular posiciones actuales
    for agente in agentes:
        if agente.activo and agente.pos_x is not None and agente.pos_y is not None:
            pos = (agente.pos_x, agente.pos_y)
            if pos not in agent_positions:
                agent_positions[pos] = []
            agent_positions[pos].append(agente.id)
    
    # Obtener propuestas de movimiento
    for agente in agentes:
        if not agente.activo:
            continue
        
        # Obtener goal específico si existe
        goal = None
        if goals and agente.id in goals:
            goal = goals[agente.id]
        
        # Proponer movimiento
        destino = agente.proponer_movimiento(goal, agent_positions)
        propuestas[agente.id] = destino
    
    # Paso 2: Detectar conflictos
    destinos_agentes = {}  # {(x, y): [agente_id, ...]}
    for agente_id, destino in propuestas.items():
        if destino not in destinos_agentes:
            destinos_agentes[destino] = []
        destinos_agentes[destino].append(agente_id)
    
    # Paso 3: Resolver conflictos y mover
    movidos = 0
    conflictos_totales = 0
    conflictos_resueltos = 0
    
    # Crear diccionario de agentes por ID para acceso rápido
    agentes_dict = {agente.id: agente for agente in agentes}
    
    # Procesar cada destino
    for destino, agentes_ids in destinos_agentes.items():
        if len(agentes_ids) == 1:
            # Sin conflicto: mover directamente
            agente_id = agentes_ids[0]
            agente = agentes_dict[agente_id]
            if agente.activo:
                agente.mover_a(*destino)
                movidos += 1
        else:
            # CONFLICTO: varios agentes quieren la misma celda
            conflictos_totales += 1
            
            # Ordenar agentes por prioridad:
            # 1. El más cercano a la meta (menor valor floor_field) tiene prioridad
            # 2. Si empate: 'rapido' > 'lento'
            # 3. Si empate: random
            agentes_conflicto = [agentes_dict[aid] for aid in agentes_ids if aid in agentes_dict]
            
            def get_priority(agente):
                # Prioridad 1: Valor floor_field (menor = más cerca de meta)
                if agente.floor_field is not None:
                    try:
                        floor_value = agente.floor_field.valores[agente.pos_y, agente.pos_x]
                    except (IndexError, AttributeError):
                        floor_value = 500  # Valor alto si hay error
                else:
                    floor_value = 500
                
                # Prioridad 2: Tipo (rapido > lento)
                tipo_priority = 0 if agente.tipo == 'rapido' else 1
                
                # Prioridad 3: Random (para desempatar)
                random_priority = random.random()
                
                return (floor_value, tipo_priority, random_priority)
            
            agentes_conflicto.sort(key=get_priority)
            
            # El primero gana, los demás se quedan
            ganador = agentes_conflicto[0]
            perdedores = agentes_conflicto[1:]
            
            # Mover ganador
            if ganador.activo:
                ganador.mover_a(*destino)
                movidos += 1
                ganador.conflictos_totales += 1
            
            # Perdedores se quedan en su lugar (mover_a a posición actual)
            for perdedor in perdedores:
                if perdedor.activo:
                    perdedor.mover_a(perdedor.pos_x, perdedor.pos_y)
                    perdedor.conflictos_totales += 1
                    perdedor.conflictos_perdidos += 1
            
            conflictos_resueltos += 1
    
    return {
        'movidos': movidos,
        'conflictos': conflictos_totales,
        'resueltos': conflictos_resueltos
    }
