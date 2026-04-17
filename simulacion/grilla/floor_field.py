# floor_field.py clase de Floor Field por Miguel Acevedo y Emilia Partarrieu, 12/25
import numpy as np
from collections import deque  # para hacer búsqueda tipo BFS

class Floor_field:
  
    def __init__(self, width, height, puertas, obstaculos):
 
        self.width = width
        self.height = height
        self.puertas = puertas
        self.obstaculos = obstaculos or []
        self.valores = self._calcular_floor_field()  #guarda los valores de las entradas de la matriz 

    def _calcular_floor_field(self):
              
        matriz = np.full((self.height, self.width), np.inf) #llenamos con infinitos
        cola = deque()
        # Marcar el contorno como paredes cambiando infinitos por 500 (excepto las puertas)
        for y in range(self.height):
            for x in range(self.width):
                if (x == 0 or x == self.width -1 or y == 0 or y == self.height -1 ):
                    if (x, y) not in self.puertas:
                        matriz[y, x] = 500 # pared
                    else:
                        matriz[y, x] = np.inf  
        # se inicializan las puertas con distancia 0
        for (x, y) in self.puertas:
            matriz[y, x] = 0
            cola.append((x, y))

        # desplazamientos posibles
        pasos = [(0,1), (1,0), (0,-1), (-1,0), (1,1), (1,-1), (-1,1), (-1,-1)]

        # se marcan los obstaculos como inaccesibles con 500 como las paredes
        for (ox, oy) in self.obstaculos:
            matriz[oy, ox] = 500

        # bucle principal bfs
        while cola:
            x, y = cola.popleft()
            for dx, dy in pasos:
                nx, ny = x + dx, y + dy
                # chequeamos limites del mapa
                if 1 <= nx < self.width -1  and 1 <= ny < self.height -1 :
                    if ( 500 > matriz[ny, nx] > matriz[y, x] + (1.5 if abs(dx) + abs(dy) == 2 else 1) ) or matriz[ny, nx] == np.inf :
                        costo = 1.5 if abs(dx) + abs(dy) == 2 else 1
                        matriz[ny, nx] = matriz[y, x] + costo
                        cola.append((nx, ny))               
        return matriz

    def valor_en(self, x, y):
        """Retorna el valor de distancia en la posicion (x, y)"""
        return self.valores[y, x]

    def mostrar(self):
        """Imprime el campo de distancias"""
        print(np.round(self.valores, 1))

 
