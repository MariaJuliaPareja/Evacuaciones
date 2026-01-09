# agentes.py clase de agentes, por Miguel Acevedo y Emilia Partarrieu 12/25
# Modificación del 09/01/2026 para compatibilidad con visualizador
import numpy as np
import random

class Agente:
    agentes = []
    def __init__(self, x, y, floor_field, velocidad=None):
        self.x = x
        self.y = y
        self.floor_field = floor_field
        self.activo = True  # cambiará a False cuando el agente llegue a la puerta
        self.if_changes = False # cambiará a True cada vez que el agente se mueva
        self.victorias = 0
        self.conflictos = 0
        self.tiempo_evacuacion = 0 
        self.ansiedad = 0 
        self.velocidad = velocidad if velocidad is not None else random.choice([1, 2]) # 1 Lento, 2 Rápido        # Asignación automática de tipo para el visualizador:
        # Velocidad 2 = 'vivo' (Verde), Velocidad 1 = 'menos_vivo' (Rojo)
        self.tipo = 'vivo' if self.velocidad == 2 else 'menos_vivo'
        self.id = len(Agente.agentes)
        Agente.agentes.append(self)
        
    # ALIAS TEMPORAL PARA COMPATIBILIDAD CON VISUALIZADOR
    @property
    def pos_x(self): return self.x
    
    @property
    def pos_y(self): return self.y

    @property
    def conflictos_totales(self): return self.conflictos

    @property
    def conflictos_perdidos(self):
        return self.conflictos - self.victorias  
    
    @property
    def derrotas(self): # Alias adicional que ya tenías
        return self.conflictos - self.victorias  
        
    def proponer_movimiento(self, ocupadas):
        """
        Retorna la mejor celda candidata a moverse (nx, ny) para cada agente,
        sin mover todavía al agente.
        """
        if not self.activo:
            return (self.x, self.y)

        pasos = [
            (0, 1), (1, 0), (0, -1), (-1, 0),
            (1, 1), (1, -1), (-1, 1), (-1, -1)
        ]
        
        mejor_valor = self.floor_field.valores[self.y, self.x]  
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

        if len(mejores) > 1:
            # Filtramos los que cumplen la distancia de Manhattan == 1 (ortogonales)
            ortogonales = [
                (nx, ny) for (nx, ny) in mejores 
                if abs(nx - self.x) + abs(ny - self.y) == 1
            ]
            
            # Si hay opciones ortogonales, nos quedamos solo con esas
            if ortogonales:
                mejores = ortogonales          
        
        # si hay varias celdas igual de buenas, i.e. la lista "mejores", elige una al azar
        destino = random.choice(mejores)

        # si está ocupado, me quedo quieto
        if destino != (self.x, self.y) and destino in ocupadas:
            return (self.x, self.y)
        return destino
    
    def moverse(self, nueva_pos):
        """
        Mueve el agente a la posición nueva (si sigue activo).
        """
        if not self.activo:
            return
        
        # aquí verificamos si la nueva posición es distinta a la actual
        self.if_changes = (self.x, self.y) != nueva_pos
        
        self.x, self.y = nueva_pos  # nueva_pos se definirá en el mover_agentes para resolver conflictos
        if self.floor_field.valores[self.y, self.x] == 0: # Si llega a una puerta (valor = 0)
            self.activo = False # deja de estar activo


def mover_agentes(agentes):
    """
    Calcula y ejecuta los movimientos de todos los agentes evitando colisiones.
    Retorna un diccionario de estadísticas para el visualizador.
    """
    posiciones_ocupadas = {(a.x, a.y) for a in agentes if a.activo}
    
    # Diccionario para capturar estadísticas del paso actual
    stats_paso = {
        'conflictos_totales': 0,
        'agentes_en_conflicto': 0
    }
    
    for agente in agentes:
        if agente.activo:
            agente.tiempo_evacuacion += 1
            agente.if_changes = False 
            
    # Luego todos proponen su movimiento
    propuestas = {} 
    for agente in agentes:
        if agente.activo:  
            destino = agente.proponer_movimiento(posiciones_ocupadas)
            propuestas.setdefault(destino, []).append(agente)
            
    # Resolución de conflictos:
    for destino, lista_agentes in propuestas.items():
        if len(lista_agentes) == 1:
            lista_agentes[0].moverse(destino)
        else:
            # Registrar conflicto para el visualizador
            stats_paso['conflictos_totales'] += 1
            stats_paso['agentes_en_conflicto'] += len(lista_agentes)
            
            for a in lista_agentes:
                a.conflictos += 1 
                
            # Mayor velocidad --> Mayor posibilidad de ganar
            pesos = [a.velocidad for a in lista_agentes]
            elegido = random.choices(lista_agentes, weights=pesos, k=1)[0] 
            elegido.victorias += 1 
            elegido.moverse(destino)
            
            for otro in lista_agentes:
                if otro != elegido:
                    otro.moverse((otro.x, otro.y))  # el otro se queda quieto
                    
    return stats_paso 
