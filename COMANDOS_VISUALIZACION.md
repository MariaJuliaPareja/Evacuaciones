# 🎯 Comandos para Visualizar el Sistema de Nodos y Selección de Rutas

## 🎬 0. Visualizador Interactivo con Animación (NUEVO)

### Comando:
```bash
python simulacion\nodos\visualizar_animacion_rutas.py
```

**Características:**
- ✅ Animación paso a paso como una película
- ✅ Controles para retroceder y adelantar frames
- ✅ Muestra rutas cuando se calculan (líneas punteadas)
- ✅ Muestra rutas cuando se recalculan (líneas sólidas destacadas)
- ✅ Colores según nivel de ansiedad (verde/amarillo/rojo)
- ✅ Indicadores visuales de recalculación
- ✅ Slider para saltar a cualquier paso
- ✅ Botón Play/Pause para reproducir automáticamente

**Qué muestra:**
- Agentes moviéndose siguiendo sus rutas planificadas
- Cálculo de nuevas rutas cuando se necesitan
- Recalculación de rutas cuando hay bloqueos o estancamiento
- Rutas completas dibujadas con colores según ansiedad
- Estadísticas en tiempo real (paso actual, agentes activos, rutas calculadas/recalculadas)

**Controles:**
- **< Anterior**: Retroceder un paso
- **Play/Pause**: Reproducir/pausar animación automática
- **Siguiente >**: Avanzar un paso
- **Slider**: Saltar a cualquier paso de la simulación

---

## 📊 1. Visualizar el Grafo de Nodos

### Comando:
```bash
cd simulacion\nodos
python visualizar_grafo.py
```

**Genera:**
- `grafo_nodos_sobre_grilla.png` - Visualización del grafo completo
- `ruta_a_star_ejemplo.png` - Ejemplo de ruta A* calculada

**Qué muestra:**
- Floor field original con valores de distancia a puertas
- Grafo de nodos (cada celda válida = nodo)
- Conexiones entre nodos (aristas del grafo)
- Puertas y obstáculos marcados
- Ejemplo de ruta A* desde punto inicial hasta puerta

---

## 🎨 2. Visualizar Selección de Rutas por Ansiedad

### Comando:
```bash
cd simulacion\nodos
python demo_path_selector_mejorado.py
```

**Genera:**
- `rutas_ansiedad_baja.png` - Rutas para ansiedad baja (0-30)
- `rutas_ansiedad_media.png` - Rutas para ansiedad óptima (30-70)
- `rutas_ansiedad_alta.png` - Rutas para ansiedad alta (70-100)

**Qué muestra:**
- 3 rutas alternativas calculadas (óptima, media, subóptima)
- Ruta seleccionada según nivel de ansiedad
- Colores diferentes para cada ruta
- Estadísticas de selección y diversidad de rutas

---

## 🔍 3. Ver Cómo Funciona la Selección de Rutas (Paso a Paso)

### Comando:
```bash
python -c "from simulacion.nodos.path_selector import PathSelector; from simulacion.grilla.floor_field import Floor_field; from escenarios.escenario_base import width, height, puertas, obstaculos; ff = Floor_field(width, height, puertas, obstaculos); ps = PathSelector(ff); start = (10, 10); goal = puertas[0]; print('=== PROCESO DE SELECCIÓN ==='); print(f'Inicio: {start}, Destino: {goal}'); k_paths = ps.find_k_paths(start, goal, k=3); print(f'Rutas encontradas: {len(k_paths)}'); [print(f'  Ruta {i+1}: {len(p)} celdas') for i, p in enumerate(k_paths)]; selected = ps.select_path_by_anxiety(k_paths, 75.0); print(f'Ruta seleccionada (ansiedad 75): {len(selected)} celdas'); ps.print_report()"
```

**Qué muestra:**
- Proceso completo de selección de ruta
- Cálculo de rutas alternativas
- Selección basada en ansiedad
- Estadísticas del PathSelector

---

## 📈 4. Visualización Detallada del Proceso Completo

### Crear archivo `ver_proceso_rutas.py`:
```python
from simulacion.nodos.path_selector import PathSelector
from simulacion.grilla.floor_field import Floor_field
from escenarios.escenario_base import width, height, puertas, obstaculos

ff = Floor_field(width, height, puertas, obstaculos)
ps = PathSelector(ff)

start = (8, 9)
goal = puertas[0]

print('='*60)
print('PROCESO COMPLETO DE SELECCIÓN DE RUTA')
print('='*60)

print('\n[PASO 1] Construcción del grafo')
print(f'   Nodos: {ps.grafo.number_of_nodes()}')
print(f'   Aristas: {ps.grafo.number_of_edges()}')

print('\n[PASO 2] Cálculo de ruta óptima con A*')
path1 = ps.encontrar_ruta_a_star(start, goal)
print(f'   Ruta encontrada: {len(path1)} celdas')
print(f'   Nodos explorados: {ps.stats["nodes_explored"][-1]}')

print('\n[PASO 3] Búsqueda de rutas alternativas (k-paths)')
k_paths = ps.find_k_paths(start, goal, k=3)
print(f'   Rutas alternativas encontradas: {len(k_paths)}')
for i, path in enumerate(k_paths):
    print(f'   - Ruta {i+1}: {len(path)} celdas')

print('\n[PASO 4] Selección basada en ansiedad')
anxiety = 75.0
selected = ps.select_path_by_anxiety(k_paths, anxiety)
selected_idx = k_paths.index(selected) if selected in k_paths else -1
print(f'   Ansiedad del agente: {anxiety}')
print(f'   Ruta seleccionada: Ruta {selected_idx+1} ({len(selected)} celdas)')

print('\n[PASO 5] Verificación de necesidad de recálculo')
agent_positions = {(goal[0], goal[1]): 2}  # Simular bloqueo
should_recalc = ps.should_recalculate(
    agent_pos=start,
    current_path=selected,
    path_index=0,
    agent_positions=agent_positions,
    steps_without_moving=0,
    anxiety_level=anxiety
)
print(f'   ¿Debe recalcular?: {should_recalc}')

print('\n[PASO 6] Estadísticas finales')
ps.print_report()
```

### Ejecutar:
```bash
python ver_proceso_rutas.py
```

---

## 🎬 5. Visualizar Rutas en Simulación Guardada

### Comando:
```python
from simulacion.grilla.visualizador import VisualizadorSimulacion

# Cargar simulación guardada
viz = VisualizadorSimulacion('datos/demo_simulacion.pkl')

# Visualizar rutas en un frame específico
viz.visualizar_rutas_agentes(frame_index=10, output_file='rutas_frame_10.png')

# Crear animación con rutas visibles
viz.crear_animacion(show_paths=True, guardar_video=True, nombre_video='simulacion_con_rutas.mp4')

# Animación interactiva con rutas
viz.crear_animacion_interactiva(show_paths=True)
```

---

## 🧪 6. Ejecutar Tests de Integración

### Comando:
```bash
# Todos los tests
python -m pytest tests/test_path_selector_integration.py -v

# Test específico
python -m pytest tests/test_path_selector_integration.py::test_seleccion_por_ansiedad -v
```

---

## 📋 Resumen: Cómo Funciona la Selección de Rutas

### Proceso paso a paso:

1. **Construcción del grafo:**
   - Cada celda válida (no pared/obstáculo) = nodo
   - Conexiones entre celdas adyacentes = aristas
   - Pesos: 1.0 (ortogonal), 1.5 (diagonal)

2. **Cálculo de ruta óptima (A*):**
   - Usa heurística euclidiana
   - Encuentra camino más corto desde inicio hasta puerta
   - Guarda en caché para reutilización

3. **Búsqueda de rutas alternativas (k-paths):**
   - Calcula 3 rutas diferentes
   - Penaliza celdas ya usadas en rutas anteriores
   - Valida que rutas sean diferentes (>30% celdas distintas)

4. **Selección basada en ansiedad:**
   - **Baja (0-30):** Siempre ruta óptima
   - **Óptima (30-70):** 70% óptima, 20% media, 10% subóptima
   - **Alta (70-100):** 30% óptima, 30% media, 40% subóptima + posible ruido

5. **Detección de bloqueos:**
   - Verifica si debe recalcular ruta
   - Condiciones: bloqueo inmediato, estancamiento, cerca de meta bloqueado

6. **Estadísticas:**
   - Registra todas las decisiones
   - Calcula métricas de rendimiento
   - Genera reportes detallados

---

## 🚀 Comandos Rápidos (Copy-Paste)

```bash
# Ver grafo de nodos
cd simulacion\nodos
python visualizar_grafo.py

# Ver selección por ansiedad
cd simulacion\nodos
python demo_path_selector_mejorado.py

# Ver estadísticas rápidas
python -c "from simulacion.nodos.path_selector import PathSelector; from simulacion.grilla.floor_field import Floor_field; from escenarios.escenario_base import *; ps = PathSelector(Floor_field(width, height, puertas, obstaculos)); ps.encontrar_ruta_a_star((8,9), puertas[0]); ps.print_report()"
```

---

## 📁 Archivos Generados

Después de ejecutar los comandos:

- `grafo_nodos_sobre_grilla.png` - Grafo completo
- `ruta_a_star_ejemplo.png` - Ejemplo de ruta A*
- `rutas_ansiedad_baja.png` - Rutas para ansiedad baja
- `rutas_ansiedad_media.png` - Rutas para ansiedad media
- `rutas_ansiedad_alta.png` - Rutas para ansiedad alta

Todos se guardan en `simulacion/nodos/`
