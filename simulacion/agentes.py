#agentes.py clase de agentes, por Miguel Acevedo y Emilia Partarrieu 12/25
# Actualizado con sistema de clasificación vivo/menos_vivo y contador de conflictos
import numpy as np
import random

class Agente:
    """
    Clase que representa un agente en la simulación de evacuación.
        Atributos:
        x, y : int
            Posición actual del agente en la grilla
        floor_field : Floor_field
            Referencia al campo de piso que guía el movimiento
        activo : bool
            True si el agente aún está en la habitación, False si ya evacuó
        tipo : str
            'vivo' o 'menos_vivo' - determina la prioridad en conflictos
        conflictos_totales : int
            Contador de conflictos en los que ha participado el agente
        conflictos_perdidos : int
            Contador de conflictos que ha perdido (no se pudo mover)
        ansiedad : int
            Nivel de ansiedad del agente (puede implementarse para lógica futura)
    """
    def __init__(self, x, y, floor_field, tipo='vivo'):
        self.x = x
        self.y = y
        self.floor_field = floor_field
        self.activo = True  # cambiar a False cuando el agente llegue a la puerta
        
        # Nuevos atributos para el sistema de clasificación y tracking
        self.tipo = tipo  # vivo o menos_vivo
        self.conflictos_totales = 0  # Total de conflictos en los que participó
        self.conflictos_perdidos = 0  # Conflictos donde no ganó el movimiento
        self.ansiedad = 0  # Nivel de ansiedad A IMPLEMENTAR
        
    def proponer_movimiento(self):
        """
        Retorna la mejor celda candidata a moverse (nx, ny) para cada agente,
        sin mover al agente.
        """
        if not self.activo:
            return (self.x, self.y)

        pasos = [
            (0, 1), (1, 0), (0, -1), (-1, 0),
            (1, 1), (1, -1), (-1, 1), (-1, -1)
        ]
        
        mejor_valor = self.floor_field.valores[self.y, self.x]   #esta deberia llamarse valor_actual 
        mejores = [(self.x, self.y)]  # lista por si hay empates

        for dx, dy in pasos:
            nx, ny = self.x + dx, self.y + dy
            if 0 <= nx < self.floor_field.width and 0 <= ny < self.floor_field.height: # limites mapa
                v = self.floor_field.valores[ny, nx] # sacamos el valor de las casillas cercanas
                if v < mejor_valor: # si el valor es menor que el actual
                    mejor_valor = v # es el mejor valor 
                    mejores = [(nx, ny)] #agrego la posicion de mejor valor a la lista mejores
                elif np.isclose(v, mejor_valor):  # si sigo mirando y existe otra como la anterior
                    mejores.append((nx, ny)) # tambien la agrego a la lista de mejores 
        
        # si hay varias celdas igual de buenas, i.e. la lista "mejores", elige una al azar
        return random.choice(mejores)

    def moverse(self, nueva_pos):
        """
        Mueve el agente a la posicion nueva (si sigue activo).
        """
        if not self.activo:
            return
        
        self.x, self.y = nueva_pos  # nueva_pos se define en el main para resolver conflictos
        if self.floor_field.valores[self.y, self.x] == 0: # Si llega a una puerta (valor = 1)
            self.activo = False # deja de estar activo


def mover_agentes(agentes):
    """
    Calcula y ejecuta los movimientos de todos los agentes evitando colisiones.
    
    Reglas actualizadas:
        - Cada agente propone un movimiento según el floor_field
        - Si varios agentes quieren la misma celda:
            1. Se da prioridad a los agentes 'vivos' sobre los 'menos_vivos'
            2. Si hay empate de tipo, se elige uno al azar (AQUÍ SE DEBE IMPLEMENTAR LA ANSIEDAD como FACTOR determinante)
        - Los que no ganan el conflicto se quedan quietos
        - Se registran todos los conflictos en los contadores de cada agente
    Parámetros:
        agentes : list
            Lista de objetos Agente que participan en la simulación
    Retorna:
        dict : Estadísticas del paso de tiempo
            - conflictos_totales: número total de celdas con conflicto
            - 'agentes_en_conflicto': número de agentes involucrados en conflictos
    """

    propuestas = {}
    
    for agente in agentes:
        if agente.activo:  # Solo los agentes activos proponen movimiento
            destino = agente.proponer_movimiento()  # Obtiene la mejor celda según floor_field
            propuestas.setdefault(destino, []).append(agente)
    
    # Paso 2: Resolver conflictos con sistema de priorización
    estadisticas = {
        'conflictos_totales': 0,
        'agentes_en_conflicto': 0
    }
    
    for destino, lista_agentes in propuestas.items():
        if len(lista_agentes) == 1:
            # No hay conflicto: el único agente se mueve sin problemas
            lista_agentes[0].moverse(destino)
        else:
            # HAY CONFLICTO: múltiples agentes quieren la misma celda
            estadisticas['conflictos_totales'] += 1
            estadisticas['agentes_en_conflicto'] += len(lista_agentes)
            
            # Registrar el conflicto en todos los agentes involucrados
            for agente in lista_agentes:
                agente.conflictos_totales += 1
            
            # SISTEMA DE PRIORIZACIÓN:
            # 1. Separar agentes por tipo
            vivos = [a for a in lista_agentes if a.tipo == 'vivo']
            menos_vivos = [a for a in lista_agentes if a.tipo == 'menos_vivo']
            
            # 2. Determinar el ganador según prioridad
            if vivos:
                # Si hay al menos un agente 'vivo', elegir entre ellos
                elegido = random.choice(vivos)
            else:
                # Si solo hay agentes 'menos_vivo', elegir entre ellos
                elegido = random.choice(menos_vivos)
            
            # 3. Ejecutar el movimiento del ganador
            elegido.moverse(destino)
            
            # 4. Los perdedores se quedan en su posición y se registra su pérdida
            for otro in lista_agentes:
                if otro != elegido:
                    otro.conflictos_perdidos += 1
                    otro.moverse((otro.x, otro.y))  # Se queda en su lugar
    
    return estadisticas
