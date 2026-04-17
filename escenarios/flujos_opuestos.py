# escenarios/flujos_opuestos.py
# Dos grupos cruzados: A sale por la izquierda, B por la derecha.

width, height = 30, 12
k_puertas = 2
puertas_A = [(0, 6)]          # salida izquierda (destino grupo A)
puertas_B = [(29, 6)]         # salida derecha (destino grupo B)
puertas = puertas_A + puertas_B
obstaculos = []
agentes_A = [(24, y) for y in range(2, 10)]   # grupo A, empieza a la derecha
agentes_B = [(5, y) for y in range(2, 10)]    # grupo B, empieza a la izquierda
agentes = agentes_A + agentes_B
