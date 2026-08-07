width = 12
height = 10
door_distance = 1

obstaculos = [
    (3,2),(3,3),
    (3,6),(3,7),
    (5,2),(5,3),
    (5,6),(5,7),
    (7,2),(7,3),
    (7,6),(7,7),
    (9,2),(9,3),
    (9,6),(9,7),
]


def get_config(d: float | None = None) -> dict:
    """Retorna la configuración del escenario para una separación de puertas d."""
    distancia = int(round(float(d))) if d is not None else int(door_distance)
    distancia = max(1, min(height - 2, distancia))

    y_center = height // 2
    y1 = max(1, min(height - 2, y_center - distancia // 2))
    y2 = min(height - 2, y1 + distancia)
    if y2 <= y1:
        y2 = min(height - 2, y1 + 1)

    return {
        "width": width,
        "height": height,
        "puertas": [(0, y1), (0, y2)],
        "obstaculos": list(obstaculos),
        "door_distance": distancia,
    }


puertas = get_config()["puertas"]
