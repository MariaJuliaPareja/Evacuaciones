# escenarios/escenario_base_v2_cerca.py
# Aquí, las personas rápidas están mas cerca de la puerta
width = 7
height = 7
k_puertas = 1
puertas = [(0,3)]
obstaculos = []

agentes = [
    (1,1,2), # Rápidos mas cerca de la puerta
    (1,3,2), 
    (2,1,2),
    (2,2,2),
    (2,4,2),
    (3,1,1), # Lentos mas lejos de la puerta
    (3,3,1),
    (4,1,1),
    (4,2,1),
    (4,4,1),
]
