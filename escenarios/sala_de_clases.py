# escenarios/sala_de_clases.py
#simula una sala de clases 
width = 12
height = 10
k_puertas = 2
puertas = [(0,6),(0,7)]

obstaculos = [
    (3,2),(3,3),
    (3,6),(3,7),
    (5,2),(5,3),
    (5,6),(5,7),
    (7,2),(7,3),
    (7,6),(7,7),
    (9,2),(9,3),
    (9,6),(9,7)
]

agentes = [
    {"pos": (4, 2), "tipo": "rapido"},
    {"pos": (4, 3), "tipo": "rapido"},
    {"pos": (4, 6), "tipo": "rapido"},
    {"pos": (4, 7), "tipo": "rapido"},
    {"pos": (6, 2), "tipo": "rapido"},
    {"pos": (6, 3), "tipo": "rapido"},
    {"pos": (6, 6), "tipo": "rapido"},
    {"pos": (6, 7), "tipo": "rapido"},
    {"pos": (8, 2), "tipo": "lento"},
    {"pos": (8, 3), "tipo": "lento"},
    {"pos": (8, 6), "tipo": "lento"},
    {"pos": (8, 7), "tipo": "lento"},
    {"pos": (10, 2), "tipo": "lento"},
    {"pos": (10, 3), "tipo": "lento"},
    {"pos": (10, 6), "tipo": "lento"},
    {"pos": (10, 7), "tipo": "lento"},
]
