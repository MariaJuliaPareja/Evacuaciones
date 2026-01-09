# escenarios/escenario_base_v1_arriba.py

width = 18
height = 20
k_puertas = 1
puertas = [(0,9)]
obstaculos = []

columnas = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]
filas = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18]
agentes = [(x, y, 1 if y <= 9 else 2) for y in filas for x in columnas]
