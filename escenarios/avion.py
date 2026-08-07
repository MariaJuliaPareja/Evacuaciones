# escenarios/avion.py
#simula un avión 
width = 9
height = 30
k_puertas = 2

# Distancia configurable de las puertas respecto a los extremos del pasillo.
# Valores más pequeños las acercan al centro; valores más grandes las empujan hacia los extremos.
# El valor por defecto 0 coloca las puertas en los extremos reales del pasillo.
distancia_puertas = 0
x_pasillo = width // 2  # columna central del pasillo

y_delantera = height - 1 - distancia_puertas
y_trasera = distancia_puertas

# Dos puertas realistas: una en el extremo frontal (arriba) y otra en el extremo trasero (abajo).
# Ambas quedan centradas en el eje X del pasillo, en lugar de las cuatro puertas del medio.
puertas = [
    (x_pasillo, y_delantera),
    (x_pasillo, y_trasera),
]

obstaculos = [
    # fila 1
    (1,1),(2,1),(3,1),(5,1),(6,1),(7,1),
    # fila 3
    (1,3),(2,3),(3,3),(5,3),(6,3),(7,3),
    # fila 5
    (1,5),(2,5),(3,5),(5,5),(6,5),(7,5),
    # fila 7
    (1,7),(2,7),(3,7),(5,7),(6,7),(7,7),
    # fila 9
    (1,9),(2,9),(3,9),(5,9),(6,9),(7,9),
    # fila 11
    (1,11),(2,11),(3,11),(5,11),(6,11),(7,11),
    # fila 13
    (1,13),(2,13),(3,13),(5,13),(6,13),(7,13),
    # fila 17
    (1,17),(2,17),(3,17),(5,17),(6,17),(7,17),
    # fila 19
    (1,19),(2,19),(3,19),(5,19),(6,19),(7,19),
    # fila 21
    (1,21),(2,21),(3,21),(5,21),(6,21),(7,21),
    # fila 23
    (1,23),(2,23),(3,23),(5,23),(6,23),(7,23),
    # fila 25
    (1,25),(2,25),(3,25),(5,25),(6,25),(7,25),
    # fila 27
    (1,27),(2,27),(3,27),(5,27),(6,27),(7,27),
    # fila 29
    (1,29),(2,29),(3,29),(5,29),(6,29),(7,29),
    ]

agentes = [
    (1,2),
    (2,2),
    (3,2),
    (5,2),
    (6,2),
    (7,2),
    (1,4),
    (2,4),
    (3,4),
    (5,4),
    (6,4),
    (7,4),
    (1,6),
    (2,6),
    (3,6),
    (5,6),
    (6,6),
    (7,6),
    (1,8),
    (2,8),
    (3,8),
    (5,8),
    (6,8),
    (7,8),
    (1,10),
    (2,10),
    (3,10),
    (5,10),
    (6,10),
    (7,10),
    (1,12),
    (2,12),
    (3,12),
    (5,12),
    (6,12),
    (7,12),
    (1,18),
    (2,18),
    (3,18),
    (5,18),
    (6,18),
    (7,18),
    (1,20),
    (2,20),
    (3,20),
    (5,20),
    (6,20),
    (7,20),
    (1,22),
    (2,22),
    (3,22),
    (5,22),
    (6,22),
    (7,22),
    (1,24),
    (2,24),
    (3,24),
    (5,24),
    (6,24),
    (7,24),
    (1,26),
    (2,26),
    (3,26),
    (5,26),
    (6,26),
    (7,26),
    (1,28),
    (2,28),
    (3,28),
    (5,28),
    (6,28),
    (7,28),
]
