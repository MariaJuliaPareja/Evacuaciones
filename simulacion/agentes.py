#agentes.py clase de agentes, por Miguel Acevedo y Emilia Partarrieu 12/25
#Modificación del 07/01/2026
import numpy as np
import random

class Agente:
    agentes = []
    def __init__(self, x, y, floor_field, velocidad= None):
        self.x = x
        self.y = y
        self.floor_field = floor_field
        self.activo = True  # cambiará a False cuando el agente llegue a la puerta
        self.if_changes = False # cambiará a True cada vez que el agente se mueva
        self.victorias = 0
        self.conflictos = 0
        self.tiempo_evacuacion = 0 
        self.velocidad = velocidad if velocidad is not None else random.choice([1, 2]) #1 Lento, 2 Rápido
        self.id = len(Agente.agentes)
        Agente.agentes.append(self)
        
    @property
    def derrotas(self):
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
        if (self.x, self.y) != nueva_pos:
            self.if_changes = True
        else:
            self.if_changes = False
        
        self.x, self.y = nueva_pos  # nueva_pos se definirá en el main para resolver conflictos
        if self.floor_field.valores[self.y, self.x] == 0: # Si llega a una puerta (valor = 1)
            self.activo = False # deja de estar activo


def mover_agentes(agentes):
    """
    Calcula y ejecuta los movimientos de todos los agentes evitando colisiones.
    Reglas:
    - Registramos las ocupadas
    - Cada agente propone un movimiento.
    - Si varios quieren la misma celda, se elige con random pesado por velocidades.
    - Los demás se quedan quietos.
    """
    posiciones_ocupadas = {(a.x, a.y) for a in agentes if a.activo}
    
    for agente in agentes:
        if agente.activo:
            agente.tiempo_evacuacion += 1
             # Reiniciado de if_changes: Por defecto, asumimos que no se ha movido en este nuevo turno
            agente.if_changes = False 
            
    # Luego todos proponen su movimiento
    propuestas = {} # creamos un diccionario vacío, las claves serán las posiciones de destino y los valores el agente que quiere ir a ese destino.
    for agente in agentes:
        if agente.activo:  # para cada agente activo
            destino = agente.proponer_movimiento(posiciones_ocupadas) # destino es la posicion que quiere agente (nx, ny)
            propuestas.setdefault(destino, []).append(agente)
            
        """
        para cada destino, appendeamos en una lista inicialmente vacia los agentes
        que quieren moverse a ese destino. esto nos da un diccionario propuestas
        donde cada destino toma el valor de una lista con los agentes que desean ir ahí. 
        """
    # el resultado de esta sección de código es un diccionario llamado propuestas

    # Resolución de conflictos:
    # y contadores (victoria y conflictos)
    for destino, lista_agentes in propuestas.items():
        if len(lista_agentes) == 1:
            lista_agentes[0].moverse(destino)
        else:
            for a in lista_agentes:
                a.conflictos += 1 
            # Mayor velocidad --> Mayor posibilidad de ganar
            pesos = [a.velocidad for a in lista_agentes]
            elegido = random.choices(lista_agentes, weights=pesos, k=1)[0] # Random con pesos
            elegido.victorias += 1 
            elegido.moverse(destino)
            for otro in lista_agentes:
                if otro != elegido:
                    otro.moverse((otro.x, otro.y))  # el otro se queda quieto (cede el paso)
