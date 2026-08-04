# Simulacion de Evacuaciones

Repositorio para simular evacuaciones en grilla con agentes de dos tipos (`rapido` y `lento`) y navegación con:

- `floor field` (greedy)
- `PathSelector` con A*
- resolución de conflictos entre agentes

## Ejecucion recomendada (demo)

Desde la raiz del proyecto:

```bash
python simulacion/grilla/dynamics.py --sala
```

Este comando genera:

- `historia_sala.pkl` (historial serializado)
- resultados reales en `salidas/demo/`:
  - un CSV por paso
  - un grafico PNG de evolucion de evacuacion

## Otros escenarios

```bash
python simulacion/grilla/dynamics.py --evacuacion
python simulacion/grilla/dynamics.py --obstaculos
python simulacion/grilla/dynamics.py --flujos
```

## Estructura relevante

- `simulacion/grilla/dynamics.py`: entrypoint principal de simulacion.
- `simulacion/grilla/floor_field.py`: campo de distancias a puertas.
- `simulacion/agent_extendido.py`: logica de agentes y conflictos.
- `simulacion/nodos/path_selector.py`: A*, rutas alternativas y recálculo.
- `escenarios/`: escenarios de simulacion.
- `experimento/`: barridos y graficos de analisis.
- `salidas/demo/`: salidas listas para mostrar.
- `salidas/experimentos/`: salidas de barridos y figuras.
- `legacy/`: scripts antiguos o fuera del flujo principal.

## Dependencias

Python 3.10+ y paquetes:

```bash
pip install numpy matplotlib networkx pillow
```