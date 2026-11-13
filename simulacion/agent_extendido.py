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

from simulacion.colisiones import anotar
from simulacion.reglas_etapa import candidatas, clasificar_rechazo, etapa_de, proponer_destino


class ContadorReemplazos:
    """Conteo de la celda de ruta A*. Sumar enteros no llama al azar."""

    CAUSAS = (
        "ocupada",
        "subiria",
        "no_minimo_libre",
        "no_vecina",
        "no_minimo_absoluto",
    )

    def __init__(self) -> None:
        self.pasos_con_ruta = {1: 0, 2: 0, 3: 0}
        self.conservada = {1: 0, 2: 0, 3: 0}
        self.reemplazada = {1: 0, 2: 0, 3: 0}
        # [CAMBIO] antes: la celda de ruta igual a la posición sumaba en conservada -> ahora: ruta_quedarse, ni conservada ni reemplazada
        self.ruta_quedarse = {1: 0, 2: 0, 3: 0}
        self.causas = {etapa: {causa: 0 for causa in self.CAUSAS} for etapa in (1, 2, 3)}

    def anotar(self, etapa: int, causa: Optional[str]) -> None:
        self.pasos_con_ruta[etapa] += 1
        if causa == "ruta_quedarse":
            self.ruta_quedarse[etapa] += 1
            return
        if causa is None:
            self.conservada[etapa] += 1
            return
        self.reemplazada[etapa] += 1
        self.causas[etapa][causa] += 1

    def sumar(self, otro: "ContadorReemplazos") -> None:
        for etapa in (1, 2, 3):
            self.pasos_con_ruta[etapa] += otro.pasos_con_ruta[etapa]
            self.conservada[etapa] += otro.conservada[etapa]
            self.reemplazada[etapa] += otro.reemplazada[etapa]
            self.ruta_quedarse[etapa] += otro.ruta_quedarse[etapa]
            for causa in self.CAUSAS:
                self.causas[etapa][causa] += otro.causas[etapa][causa]


def sumar_reemplazos(agentes) -> ContadorReemplazos:
    total = ContadorReemplazos()
    for agente in agentes:
        contador = getattr(agente, "reemplazos", None)
        if contador is not None:
            total.sumar(contador)
    return total


class AgentExtendido:
    """
    Agente con PathSelector, A* y desbloqueo progresivo de rutas.
    
    Sistema de desbloqueo basado en estancamiento (calculate_unlocked_paths):
    - 0-2 pasos estancado: 1 ruta
    - 3-4 pasos estancado: 3 rutas
    - 5 o más: 5 rutas
    
    La elección de ruta usa U_I y U_II del agente, no los valores 30 y 70.
    Por encima de U_II el peso sigue al inverso de la longitud y hay 10% de ruido.
    Sin pru_fixed la ansiedad no pasa de 100.
    """
    
    # Atributos de clase para tracking global
    instances: List['AgentExtendido'] = []
    history: List[Dict] = []
    ruta_log: List[Dict] = []
    
    def __init__(
        self,
        agent_type: str,
        floor_field,
        path_selector,
        x: int,
        y: int,
        U_I: int = 10,
        U_II: int = 20,
        k_paths_max: int = 5,
        pru_fixed: bool = False,
        frozen_stress: bool = False,
        reglas_etapa_en_pru: bool = True,
        contar_reemplazos: bool = True,
    ):
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
        k_paths_max : int
            Número máximo de rutas que el agente puede desbloquear (1, 3 o 5)
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
        self.ruta_actual: list[tuple] = []
        self.path_index = 0  # Índice en la ruta actual
        self.all_calculated_paths = []  # Hasta 5 rutas calculadas
        self.unlocked_paths_count = 1  # Start con 1 ruta desbloqueada
        self.ruta_idx_seleccionada = -1
        
        # SISTEMA DE ANSIEDAD (Yerkes-Dodson Law)
        self.U_I = U_I
        self.U_II = U_II
        self.ansiedad = 0
        self.pru_fixed = pru_fixed
        # [CAMBIO] antes: el paso celda a celda de PRU siempre filtraba la ruta con la regla de etapa -> ahora: reglas_etapa_en_pru=False devuelve esa celda o el greedy de 4 vecinos; las corridas oficiales dejan True
        self.reglas_etapa_en_pru = reglas_etapa_en_pru
        # [CAMBIO] antes: no había conteo de reemplazos -> ahora: contar_reemplazos anota por etapa sin consumir números aleatorios
        self.contar_reemplazos = contar_reemplazos
        self.reemplazos = ContadorReemplazos()
        # Congela solo s_i. steps_without_moving y el desbloqueo 1→3→5 siguen.
        self.frozen_stress = frozen_stress
        self.steps_without_moving = 0
        self.calmness_threshold = 3  # Umbral para desbloquear rutas
        self.k_paths_max = max(1, min(5, k_paths_max))
        
        # TRACKING
        self.conflictos_totales = 0
        self.conflictos_perdidos = 0
        
        # Cooldown entre recálculos de ruta.
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
        
        self.recalculated_this_step = False
        
        pos_actual = (self.pos_x, self.pos_y)
        
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
                anxiety_level=None,  # Ya no usar ansiedad para decidir recálculo
                siguiente_celda=self._celda_a_pisar() if self.pru_fixed else None,
            )
        )
        
        # SI NO NECESITA RECALCULAR, SALIR INMEDIATAMENTE
        if not needs_recalc:
            # Ya tiene una ruta válida, mantenerla
            return
        
        # ========================================
        # SI LLEGA AQUÍ, SÍ VA A RECALCULAR
        # ========================================
        
        self.recalculated_this_step = True
        
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
                num_paths=self.k_paths_max
            )
        except (ValueError, Exception):
            try:
                all_paths = self.path_selector.find_k_paths(
                    start=pos_actual,
                    goal=goal,
                    k=min(self.k_paths_max, unlocked_count)
                )
            except Exception:
                all_paths = []
        
        # Verificar que encontramos rutas
        if not all_paths or len(all_paths) == 0:
            # No se encontraron rutas, mantener la actual si existe
            return
        
        # [AUDITORÍA REGLAS PFF] NO APLICA — el estrés elige la ruta A*, no la celda vecina por φ
        selected_path = self.path_selector.select_path_by_anxiety(
            k_paths=all_paths,
            anxiety_level=self.ansiedad,
            num_available_paths=unlocked_count,
            anxiety_thresholds=(self.U_I, self.U_II),
        )
        
        if selected_path is None or len(selected_path) == 0:
            return
        
        # Actualizar ruta
        self.current_path = selected_path
        self.ruta_actual = list(selected_path)
        self.path_index = 0  # Empezar desde el inicio
        self.all_calculated_paths = all_paths
        self.unlocked_paths_count = unlocked_count
        available_paths = all_paths[:unlocked_count]
        self.ruta_idx_seleccionada = next(
            (idx for idx, path in enumerate(available_paths) if path == selected_path),
            -1
        )
        
        # Registrar paso de recalculación para cooldown
        current_step = getattr(self, '_current_simulation_step', 0)
        self.last_recalculation_step = current_step
    
    def _indice_destino(self) -> Optional[int]:
        """Índice de la celda que el agente intenta pisar, sin mover path_index."""
        if not self.current_path:
            return None
        idx = self.path_index
        actual = (self.pos_x, self.pos_y)
        if idx < len(self.current_path) and self.current_path[idx] == actual:
            idx += 1
        if idx >= len(self.current_path):
            return None
        return idx

    def _celda_a_pisar(self) -> Optional[Tuple[int, int]]:
        # [AUDITORÍA REGLAS PFF] NO APLICA — nombra la celda de la ruta; la etapa la acepta o la reemplaza en _aplicar_regla_de_etapa
        idx = self._indice_destino()
        if idx is None:
            return None
        return self.current_path[idx]

    def _conjunto_ocupadas(self, agent_positions) -> set[tuple[int, int]]:
        ocupadas: set[tuple[int, int]] = set()
        if not agent_positions:
            return ocupadas
        for pos, info in agent_positions.items():
            cantidad = len(info) if isinstance(info, (list, tuple, set)) else info
            try:
                cantidad = int(cantidad)
            except (TypeError, ValueError):
                cantidad = 1
            if cantidad > 0:
                ocupadas.add((int(pos[0]), int(pos[1])))
        return ocupadas

    def _aplicar_regla_de_etapa(
        self,
        siguiente: Optional[Tuple[int, int]],
        agent_positions,
    ) -> Tuple[int, int]:
        """Acepta la celda de la ruta solo si la etapa la permite."""
        x, y = int(self.pos_x), int(self.pos_y)
        if self.floor_field is None:
            return (int(siguiente[0]), int(siguiente[1])) if siguiente is not None else (x, y)
        phi = self.floor_field.valores
        ocupadas = self._conjunto_ocupadas(agent_positions)
        etapa = etapa_de(self.ansiedad, self.U_I, self.U_II)
        # [AUDITORÍA REGLAS PFF] CORREGIDO — reglas 1, 2 y 3: la ruta solo pasa si es candidata legal
        # [CAMBIO] antes: se pisaba la siguiente celda de la ruta, o el greedy de 4 vecinos, sin mirar la etapa ni si esa celda era el mínimo -> ahora: si la celda no es candidata (ocupada, cuesta arriba en I/II, o no es el mínimo libre en III) se usa proponer_destino
        # [DUDA] si la celda de la ruta es una candidata legal, PRU la conserva y no sortea; el azar de la etapa II queda dentro de proponer_destino
        if siguiente is not None:
            celda = (int(siguiente[0]), int(siguiente[1]))
            # [CAMBIO] antes: celda de ruta == posición se contaba como conservada y se devolvía -> ahora: el contador anota ruta_quedarse; el return no cambió
            # [DUDA] en etapa I, II y III este return no llama a proponer_destino: el agente se queda aunque la regla tenga una celda libre obligatoria
            if celda == (x, y):
                if self.contar_reemplazos:
                    self.reemplazos.anotar(etapa, "ruta_quedarse")
                return celda
            opciones = candidatas(phi, ocupadas, x, y, etapa)
            aceptada = celda in opciones
            if self.contar_reemplazos:
                # [CAMBIO] antes: el reemplazo no se anotaba -> ahora: se anota la causa sin llamar a random
                causa = None if aceptada else clasificar_rechazo(phi, ocupadas, x, y, etapa, celda)
                self.reemplazos.anotar(etapa, causa)
            if aceptada:
                return celda
        return proponer_destino(phi, ocupadas, x, y, etapa)

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

        siguiente = None
        if self.usa_enrutamiento_inteligente and self.path_selector is not None:
            if agent_positions is None:
                agent_positions = {}
            if goal is None:
                goal = self._encontrar_puerta_mas_cercana()
            if goal is not None:
                self.elegir_ruta(goal, agent_positions)
                ruta_usable = (
                    self.current_path is not None
                    and len(self.current_path) > 0
                    and not (self.path_index >= len(self.current_path) and not self.pru_fixed)
                )
                if ruta_usable:
                    if self.pru_fixed:
                        siguiente = self._celda_a_pisar()
                    else:
                        pos_actual = (self.pos_x, self.pos_y)
                        if (
                            self.path_index < len(self.current_path)
                            and self.current_path[self.path_index] == pos_actual
                        ):
                            self.path_index += 1
                        if self.path_index < len(self.current_path):
                            siguiente = self.current_path[self.path_index]
                    if siguiente is not None:
                        current_step = getattr(self, "_current_simulation_step", 0)
                        unlocked_count_log = self.path_selector.calculate_unlocked_paths(
                            steps_without_moving=self.steps_without_moving,
                            calmness_threshold=self.calmness_threshold,
                        )
                        AgentExtendido.ruta_log.append({
                            "agent_id": id(self),
                            "step": current_step,
                            "unlocked_count": unlocked_count_log,
                            "ruta_idx": self.ruta_idx_seleccionada,
                        })
        # [CAMBIO] antes: el paso siempre pasaba por la regla de etapa -> ahora: con reglas_etapa_en_pru=False se devuelve la celda de la ruta o el greedy de 4 vecinos
        if not self.reglas_etapa_en_pru:
            return self._paso_sin_regla_de_etapa(siguiente)
        return self._aplicar_regla_de_etapa(siguiente, agent_positions)
    
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

        if self.pru_fixed:
            self._mover_a_pru_fixed(nueva_x, nueva_y)
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
            
            # Reducir ansiedad en una unidad por movimiento exitoso
            self.ansiedad = max(0, self.ansiedad - 1)
            
        else:
            self.steps_without_moving += 1
            
            # NO incrementar path_index
            # La ruta sigue siendo válida, simplemente no pudo avanzar este paso
            
            # Aumentar ansiedad en una unidad por bloqueo. Tope 100 en el modo anterior.
            self.ansiedad = min(100, self.ansiedad + 1)
        
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
    
    def _subir_ansiedad(self) -> None:
        if self.frozen_stress:
            return
        if self.pru_fixed:
            self.ansiedad += 1
        else:
            self.ansiedad = min(100, self.ansiedad + 1)

    def _mover_a_pru_fixed(self, nueva_x: int, nueva_y: int) -> None:
        """Movimiento real: sin saltos, y path_index solo si la posición cambió."""
        old = (self.pos_x, self.pos_y)
        new = (nueva_x, nueva_y)
        if old != new and max(abs(new[0] - old[0]), abs(new[1] - old[1])) > 1:
            self.if_change = False
            self.steps_without_moving += 1
            self._subir_ansiedad()
            self.current_path = None
            self.ruta_actual = []
            self.path_index = 0
            self.all_calculated_paths = []
            return

        idx = self._indice_destino()
        self.if_change = old != new
        self.pos_x = nueva_x
        self.pos_y = nueva_y
        if self.if_change:
            self.steps_without_moving = 0
            self.trajectory_history.append(new)
            if idx is not None and self.current_path and new == self.current_path[idx]:
                self.path_index = idx + 1
            elif self.current_path and new in self.current_path:
                encontrado = self.current_path.index(new)
                if encontrado >= self.path_index:
                    self.path_index = encontrado + 1
            if not self.frozen_stress:
                self.ansiedad = max(0, self.ansiedad - 1)
        else:
            self.steps_without_moving += 1
            self._subir_ansiedad()

        if self.floor_field is not None:
            try:
                if self.floor_field.valores[self.pos_y, self.pos_x] == 0:
                    self.activo = False
                    self.current_path = None
                    self.all_calculated_paths = []
                    self.path_index = 0
            except (IndexError, AttributeError):
                pass

    def _paso_sin_regla_de_etapa(self, siguiente: Optional[Tuple[int, int]]) -> Tuple[int, int]:
        # [CAMBIO] antes: no existía el paso previo como alternativa -> ahora: la celda de la ruta se pisa tal cual y, si no hay, el greedy de 4 vecinos
        if siguiente is not None:
            return (int(siguiente[0]), int(siguiente[1]))
        return self._greedy_4_anterior()

    def _greedy_4_anterior(self) -> Tuple[int, int]:
        """Respaldo de antes de la regla de etapa: 4 vecinos y solo si φ baja."""
        # [CAMBIO] antes: este era el respaldo de todas las corridas -> ahora: solo corre si reglas_etapa_en_pru es False
        if self.floor_field is None or self.pos_x is None or self.pos_y is None:
            return (self.pos_x, self.pos_y)
        try:
            mejor_valor = self.floor_field.valores[self.pos_y, self.pos_x]
        except (IndexError, AttributeError):
            return (self.pos_x, self.pos_y)
        mejor_pos = (self.pos_x, self.pos_y)
        for dx, dy in ((0, 1), (1, 0), (0, -1), (-1, 0)):
            nx = self.pos_x + dx
            ny = self.pos_y + dy
            if not (0 <= nx < self.floor_field.width and 0 <= ny < self.floor_field.height):
                continue
            try:
                valor = self.floor_field.valores[ny, nx]
            except (IndexError, AttributeError):
                continue
            if valor < 500 and valor < mejor_valor:
                mejor_valor = valor
                mejor_pos = (nx, ny)
        return mejor_pos

    def _movimiento_greedy_floor_field(self) -> Tuple[int, int]:
        """Respaldo sin ruta. Con la regla de etapa usa el mismo criterio que el PFF."""
        if self.floor_field is None or self.pos_x is None or self.pos_y is None:
            return (self.pos_x, self.pos_y)
        # [AUDITORÍA REGLAS PFF] CORREGIDO — reglas 1, 2 y 3: el respaldo ya no es el mínimo de 4 vecinos
        # [CAMBIO] antes: 4 vecinos, solo si φ bajaba, sin mirar ocupación ni etapa -> ahora: proponer_destino con 8 vecinos, salvo reglas_etapa_en_pru=False
        if not self.reglas_etapa_en_pru:
            return self._greedy_4_anterior()
        return self._aplicar_regla_de_etapa(None, None)
    
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
                                 goals: Optional[Dict[int, Tuple[int, int]]] = None,
                                 registro=None) -> Dict:
    """
    Mueve todos los agentes resolviendo conflictos.
    
    FLUJO:
    1. Cada agente propone movimiento (proponer_movimiento)
    2. Detectar conflictos (varios → misma celda)
    3. Resolver conflictos:
       - Gana el menor (valor de floor field de su celda actual, tipo)
       - tipo vale 0 si es rapido y 1 si es lento
       - Si empatan floor field y tipo: random.choice
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
        return {
            'movidos': 0,
            'conflictos': 0,
            'resueltos': 0,
            'conflictos_rapido_gana': 0,
            'conflictos_lento_gana': 0,
            'conflictos_empate_random': 0,
        }
    
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
    
    # PathSelector.should_recalculate espera conteos {(x,y): n}, no listas de ids.
    agent_position_counts = {pos: len(ids) for pos, ids in agent_positions.items()}

    # Obtener propuestas de movimiento
    for agente in agentes:
        if not agente.activo:
            continue
        
        # Obtener goal específico si existe
        goal = None
        if goals and agente.id in goals:
            goal = goals[agente.id]
        
        # Proponer movimiento
        destino = agente.proponer_movimiento(goal, agent_position_counts)
        propuestas[agente.id] = destino
    
    # Paso 2: Detectar conflictos
    destinos_agentes = {}  # {(x, y): [agente_id, ...]}
    for agente_id, destino in propuestas.items():
        if destino not in destinos_agentes:
            destinos_agentes[destino] = []
        destinos_agentes[destino].append(agente_id)
    
    # [AUDITORÍA REGLAS PFF] NO APLICA — no elige la celda por φ. El perdedor llama mover_a sobre su propia celda y, con pru_fixed, sube 1 de ansiedad. No se cambia la prioridad del ganador.
    # Paso 3: Resolver conflictos y mover, con ocupación compartida del frame.
    # celdas_ocupadas se actualiza al resolver cada grupo para evitar que un
    # agente entre a la celda de otro que perdió un conflicto distinto y se quedó.
    movidos = 0
    conflictos_totales = 0
    conflictos_resueltos = 0
    conflictos_rapido_gana = 0
    conflictos_lento_gana = 0
    conflictos_empate_random = 0
    
    # Crear diccionario de agentes por ID para acceso rápido
    agentes_dict = {agente.id: agente for agente in agentes}

    celdas_ocupadas = {
        (agente.pos_x, agente.pos_y)
        for agente in agentes
        if agente.activo and agente.pos_x is not None and agente.pos_y is not None
    }

    def _prioridad(agente: "AgentExtendido") -> tuple:
        if agente.floor_field is not None:
            try:
                floor_value = agente.floor_field.valores[agente.pos_y, agente.pos_x]
            except (IndexError, AttributeError):
                floor_value = 500
        else:
            floor_value = 500
        tipo_priority = 0 if agente.tipo == "rapido" else 1
        return (floor_value, tipo_priority, agente)

    def _elegir_ganador(candidatos: List["AgentExtendido"]) -> "AgentExtendido":
        nonlocal conflictos_empate_random
        info = [_prioridad(a) for a in candidatos]
        min_floor = min(item[0] for item in info)
        por_floor = [item for item in info if item[0] == min_floor]
        min_tipo = min(item[1] for item in por_floor)
        por_tipo = [item for item in por_floor if item[1] == min_tipo]
        if len(por_tipo) > 1:
            conflictos_empate_random += 1
            return random.choice(por_tipo)[2]
        return por_tipo[0][2]

    def _mover_reclamando(agente: "AgentExtendido", destino: Tuple[int, int]) -> bool:
        """Mueve si destino está libre (o es la celda actual); actualiza ocupación."""
        # [AUDITORÍA REGLAS PFF] NO APLICA — si el destino sigue ocupado se queda y sube la ansiedad; no elige otra celda por φ
        nonlocal movidos
        origen = (agente.pos_x, agente.pos_y)
        dest = (int(destino[0]), int(destino[1]))
        if dest != origen and dest in celdas_ocupadas:
            agente.mover_a(*origen)
            return False
        agente.mover_a(*dest)
        if getattr(agente, "pru_fixed", False):
            real = (agente.pos_x, agente.pos_y)
            if real != origen:
                celdas_ocupadas.discard(origen)
                celdas_ocupadas.add(real)
                movidos += 1
                return True
            return False
        if dest != origen:
            celdas_ocupadas.discard(origen)
            celdas_ocupadas.add(dest)
            movidos += 1
        return True
    
    # Procesar cada destino
    for destino, agentes_ids in destinos_agentes.items():
        dest = (int(destino[0]), int(destino[1]))
        grupo = [
            agentes_dict[aid]
            for aid in agentes_ids
            if aid in agentes_dict and agentes_dict[aid].activo
        ]
        if not grupo:
            continue

        # Elegibles: ya están en dest, o dest no está reclamada en este frame.
        elegibles = [
            a for a in grupo
            if (a.pos_x, a.pos_y) == dest or dest not in celdas_ocupadas
        ]

        if len(grupo) == 1:
            agente = grupo[0]
            if agente in elegibles:
                _mover_reclamando(agente, dest)
            else:
                # Conflicto indirecto: destino aún ocupado por otro agente del frame.
                conflictos_totales += 1
                agente.mover_a(agente.pos_x, agente.pos_y)
                agente.conflictos_totales += 1
                agente.conflictos_perdidos += 1
                conflictos_resueltos += 1
            continue

        # CONFLICTO: varios agentes quieren la misma celda
        conflictos_totales += 1

        if not elegibles:
            anotar(registro, grupo, None, lambda agente: agente.ansiedad)
            for agente in grupo:
                agente.mover_a(agente.pos_x, agente.pos_y)
                agente.conflictos_totales += 1
                agente.conflictos_perdidos += 1
            conflictos_resueltos += 1
            continue

        ganador = _elegir_ganador(elegibles)
        perdedores = [a for a in grupo if a.id != ganador.id]
        anotar(registro, grupo, ganador, lambda agente: agente.ansiedad)

        if ganador.tipo == "rapido" and any(p.tipo == "lento" for p in perdedores):
            conflictos_rapido_gana += 1
        elif ganador.tipo == "lento":
            conflictos_lento_gana += 1

        _mover_reclamando(ganador, dest)
        ganador.conflictos_totales += 1

        for perdedor in perdedores:
            perdedor.mover_a(perdedor.pos_x, perdedor.pos_y)
            perdedor.conflictos_totales += 1
            perdedor.conflictos_perdidos += 1

        conflictos_resueltos += 1
    
    return {
        'movidos': movidos,
        'conflictos': conflictos_totales,
        'resueltos': conflictos_resueltos,
        'conflictos_rapido_gana': conflictos_rapido_gana,
        'conflictos_lento_gana': conflictos_lento_gana,
        'conflictos_empate_random': conflictos_empate_random,
    }
