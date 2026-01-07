# escenarios/escenario_base_v2_cerca.py
# Aquí, las personas rápidas están mas cerca de la puerta
width = 7
height = 7
k_puertas = 1
puertas = [(0,3)]
obstaculos = []

agentes = [
    (1,1,1), # Lentos mas cerca de la puerta
    (1,3,1), 
    (2,1,1),
    (2,2,1),
    (2,4,1),
    (3,1,2), # Rápidos mas lejos de la puerta
    (3,3,2),
    (4,1,2),
    (4,2,2),
    (4,4,2),
]
