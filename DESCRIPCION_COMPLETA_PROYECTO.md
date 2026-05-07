# Descripcion Completa del Proyecto (actualizada)

## Objetivo

Simular evacuaciones en grilla 2D con agentes heterogéneos y navegación combinada:

- `floor field` para guía base.
- `PathSelector` con A* para planificación de rutas.
- resolución de conflictos por celda y prioridad de agente.

## Flujo principal de ejecución

1. Se carga un escenario desde `escenarios/`.
2. Se construye el campo de distancias en `simulacion/grilla/floor_field.py`.
3. Se inicializan agentes en `simulacion/agent_extendido.py`.
4. Se actualizan rutas y pesos dinámicos con `simulacion/nodos/path_selector.py`.
5. El motor `simulacion/grilla/dynamics.py` ejecuta pasos, resuelve conflictos y guarda resultados.

## Entry points reales

- `simulacion/grilla/dynamics.py` (principal para demo y corridas directas).
- `experimento/barrido_propuesta1.py` (barrido paramétrico).
- `experimento/barrido_herd.py` (métricas de herd/cascadas).

## Output de resultados

Al ejecutar `dynamics.py`, se generan:

- archivo PKL de historia (`historia_<escenario>.pkl`),
- CSV y gráfico en `salidas/demo/`.

Esto deja una salida inmediata para reporte y presentación.

## Estructura actual recomendada

- `simulacion/grilla/dynamics.py`: orquestación de simulación.
- `simulacion/grilla/floor_field.py`: cálculo de distancias.
- `simulacion/agent_extendido.py`: estado y movimiento de agentes.
- `simulacion/nodos/path_selector.py`: A*, rutas alternativas, recálculo.
- `escenarios/`: definición de mapas, obstáculos, puertas y posiciones iniciales.
- `experimento/`: scripts de análisis y visualización agregada.
- `salidas/demo/`: salidas finales de corrida.
- `salidas/experimentos/`: resultados de barridos y figuras.
- `salidas/tests/`: artefactos visuales de validación.
- `legacy/`: código antiguo o fuera del flujo principal.

## Notas de mantenimiento

- El código en `legacy/` se conserva como referencia histórica y no forma parte del flujo principal.
- Para presentaciones o demos rápidas, usar `--sala` en `dynamics.py`.
- Si se agrega un escenario nuevo, mantener el mismo contrato de configuración (ancho, alto, puertas, obstáculos, agentes).

