
from typing import Self, Optional, Tuple
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
                 path_selector = None): #NODO
        """
        Inicializa agente extendido.
        Parámetros:
        type : str
            Tipo de agente
        agent_type : str
            'vivo' o 'menos_vivo' - para priorización en conflictos
        floor_field : Floor_field, opcional
            Campo de piso para navegación inteligente
        """

        self.id: int = len(AgentExtendido.instances)
        self.agent_type: str = type
        self.pos_x: int | None = None 
        self.pos_y: int | None = None 
        self.if_change: bool = False
        self.tipo: str = agent_type  # 'vivo' o 'menos_vivo'
        self.activo: bool = True  # False cuando evacua
        self.floor_field = floor_field  # Para navegación inteligente
        self.conflictos_totales: int = 0
        self.conflictos_perdidos: int = 0
        self.ansiedad: int = 0   
        # NODOS
        self.path_selector = path_selector  
        self.ruta_planificada = None  
        self.pasos_desde_recalculo = 0  
        self.usa_enrutamiento_inteligente = (path_selector is not None)  
        AgentExtendido.instances.append(self)
    
    
    @classmethod
    def stores(cls) -> None:
        """Guarda snapshot del estado actual"""
        # Hacer copia profunda de los agentes para preservar su estado
        snapshot = [copy.deepcopy(agent) for agent in cls.instances]
        cls.history.append(snapshot)
    
    def proponer_movimiento(self) -> Tuple[int, int]: #PARA LOS NODOS
        """
        Logica para mover agente EN NODO
        """
 
        if not self.activo or self.pos_x is None or self.pos_y is None:
            return (self.pos_x, self.pos_y)
        
        if self.usa_enrutamiento_inteligente:
            return self._movimiento_con_path_selector()
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

    def _movimiento_con_path_selector(self) -> Tuple[int, int]: #MOVIMIENTO EN NODO
        """
        Movimiento inteligente usando PathSelector con A*.
        Estrategia:
        1. Si no tiene ruta o debe recalcular -> calcular con A*
        2. Seguir ruta planificada
        3. Si ruta falla -> fallback a greedy
        """
        pos_actual = (self.pos_x, self.pos_y)
        # ¿Necesita calcular/recalcular ruta? CAMBIAR LOGICA DE RUTA
        if (self.ruta_planificada is None or
            len(self.ruta_planificada) <= 1 or
            self.path_selector.debe_recalcular_ruta(self, self.ruta_planificada)):
            # Encontrar mejor puerta
            puertas = self.floor_field.puertas
            mejor_puerta = self.path_selector.encontrar_mejor_puerta(pos_actual, puertas)
            # Calcular ruta con A*
            self.ruta_planificada = self.path_selector.encontrar_ruta_a_star(
                pos_actual, 
                mejor_puerta
            )
            
            self.pasos_desde_recalculo = 0
            
            # Si no se encontró ruta, usar greedy como fallback
            if self.ruta_planificada is None:
                return self._movimiento_greedy_floor_field()
        
        # Seguir la ruta planificada
        if self.ruta_planificada and len(self.ruta_planificada) > 1:
            # El siguiente nodo en la ruta
            siguiente = self.ruta_planificada[1]
            
            # Avanzar en la ruta
            self.ruta_planificada.pop(0)
            self.pasos_desde_recalculo += 1
            
            return siguiente
        
        # Fallback
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
        self.if_change = (nueva_x != self.pos_x or nueva_y != self.pos_y)
        
        # Actualizar posición
        self.pos_x = nueva_x
        self.pos_y = nueva_y
        
        # Verificar si llegó a la salida (valor = 0 en floor_field)
        if self.floor_field is not None:
            if self.floor_field.valores[self.pos_y, self.pos_x] == 0:
                self.activo = False
    
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
