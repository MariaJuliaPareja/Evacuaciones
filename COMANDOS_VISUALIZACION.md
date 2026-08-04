# Comandos de Visualizacion y Pruebas

Guia actualizada para la estructura separada:

- `simulacion/pathfinding_propuesta/`
- `simulacion/grilla_clasica/`

## 1) Correr simulacion principal y generar resultados reales

```bash
python simulacion/grilla/dynamics.py --sala
```

Salida esperada:

- `historia_sala.pkl`
- `salidas/demo/*.csv`
- `salidas/demo/*.png`

## 2) Visualizador interactivo de rutas

```bash
python simulacion/nodos/visualizar_animacion_rutas.py
```

Muestra movimiento de agentes, rutas recalculadas y estados de ansiedad.

## 3) Visualizar grafo y ruta A*

```bash
python simulacion/nodos/visualizar_grafo.py
```

Genera:

- `simulacion/nodos/grafo_nodos_sobre_grilla.png`
- `simulacion/nodos/ruta_a_star_ejemplo.png`

## 4) Demo de seleccion de rutas por ansiedad

```bash
python simulacion/nodos/demo_path_selector_mejorado.py
```

Genera figuras de rutas para ansiedad baja/media/alta.

## 5) Probar PathSelector desde consola (comando corto)

```bash
python -c "from simulacion.pathfinding_propuesta.path_selector import PathSelector; from simulacion.grilla_clasica.floor_field import Floor_field; from escenarios.escenario_base import width, height, puertas, obstaculos; ff = Floor_field(width, height, puertas, obstaculos); ps = PathSelector(ff); p = ps.encontrar_ruta_a_star((8,9), puertas[0]); print('Ruta encontrada:', len(p) if p else 0); ps.print_report()"
```

## 6) Ejecutar tests actualizados

```bash
python -m pytest tests/test_path_selector_integration.py -v
python -m pytest tests/test_agent_path_selection_visual.py -v
```

## 7) Archivos generados habituales

- `salidas/demo/` (salidas de demo listas para presentación)
- `salidas/experimentos/figuras/` (figuras de barridos experimentales)
- `salidas/tests/` (salidas de pruebas visuales)
