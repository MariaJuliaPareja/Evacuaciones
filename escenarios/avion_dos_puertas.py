# Escenario de avión con dos puertas front/atrás y distancia configurable.

width = 9
height = 30
door_distance = 4

obstaculos = [
    # filas con asientos (ejemplo tomado del diseño anterior)
    (1,1),(2,1),(3,1),(5,1),(6,1),(7,1),
    (1,3),(2,3),(3,3),(5,3),(6,3),(7,3),
    (1,5),(2,5),(3,5),(5,5),(6,5),(7,5),
    (1,7),(2,7),(3,7),(5,7),(6,7),(7,7),
    (1,9),(2,9),(3,9),(5,9),(6,9),(7,9),
    (1,11),(2,11),(3,11),(5,11),(6,11),(7,11),
    (1,13),(2,13),(3,13),(5,13),(6,13),(7,13),
    (1,17),(2,17),(3,17),(5,17),(6,17),(7,17),
    (1,19),(2,19),(3,19),(5,19),(6,19),(7,19),
    (1,21),(2,21),(3,21),(5,21),(6,21),(7,21),
    (1,23),(2,23),(3,23),(5,23),(6,23),(7,23),
    (1,25),(2,25),(3,25),(5,25),(6,25),(7,25),
    (1,27),(2,27),(3,27),(5,27),(6,27),(7,27),
    (1,29),(2,29),(3,29),(5,29),(6,29),(7,29),
]


def get_config(d: float | None = None) -> dict:
    """
    Retorna la configuración para una separación de puertas d.

    Ahora las puertas están en la misma columna (centro en X) y separadas
    a lo largo del eje Y alrededor del centro del pasillo. `d` controla la
    separación (número de celdas) entre las dos puertas.
    """
    distancia = int(round(float(d))) if d is not None else int(door_distance)
    distancia = max(1, min(height - 1, distancia))

    x_mid = width // 2
    y_mid = height // 2

    # Distribuir la separación alrededor del centro: una puerta arriba, otra abajo.
    half = distancia // 2
    if distancia % 2 == 0:
        y_back = max(0, y_mid - half)
        y_front = min(height - 1, y_mid + half)
    else:
        y_back = max(0, y_mid - half)
        y_front = min(height - 1, y_mid + half + 1)

    # Asegurar que las puertas no coincidan y estén dentro de bordes.
    if y_front <= y_back:
        y_front = min(height - 1, y_back + 1)

    return {
        "width": width,
        "height": height,
        "puertas": [(x_mid, y_back), (x_mid, y_front)],
        "obstaculos": list(obstaculos),
        "door_distance": distancia,
    }


puertas = get_config()["puertas"]