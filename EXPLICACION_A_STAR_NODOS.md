# Explicacion A* y Nodos (version ejecutiva)

Documento breve para presentacion tecnica del sistema de evacuaciones.

## 1. Que problema resuelve

El proyecto simula evacuacion en una grilla 2D con:

- agentes heterogeneos (`rapido` / `lento`),
- obstaculos y puertas de salida,
- conflictos cuando varios agentes quieren la misma celda.

El objetivo es estudiar tiempo de evacuacion y comportamiento colectivo bajo congestion.

## 2. Arquitectura en una mirada

Capas principales:

- `simulacion/grilla_clasica/floor_field.py`: calcula distancias a salidas.
- `simulacion/pathfinding_propuesta/path_selector.py`: calcula rutas con A*.
- `simulacion/pathfinding_propuesta/agent_extendido.py`: decision y movimiento de agentes.
- `simulacion/grilla/dynamics.py`: orquesta la simulacion paso a paso y exporta resultados.

Entrypoint recomendado:

```bash
python simulacion/grilla/dynamics.py --sala
```

## 3. Flujo de datos real

1. `dynamics.py` carga configuracion del escenario (`size`, `puertas`, `obstaculos`, cantidad de agentes).
2. Se crea `Floor_field` con una matriz de costo/distancia a puertas.
3. Se crea `PathSelector`:
   - transforma celdas validas en un grafo,
   - conecta vecinos (ortogonal y diagonal),
   - aplica A* para rutas.
4. Se crean agentes `AgentExtendido` con referencia al `floor_field` y al `path_selector`.
5. En cada paso de simulacion:
   - se actualizan metricas dinamicas de congestion,
   - se ajustan pesos del grafo,
   - cada agente propone movimiento,
   - se resuelven conflictos de celda,
   - se actualiza estado (activo, ansiedad, atasco, ruta actual).
6. Se guardan resultados:
   - `historia_<escenario>.pkl`
   - CSV y PNG en `salidas/demo/`.

## 4. Como funciona A* en este proyecto

### Representacion

- Nodo: celda `(x, y)` valida.
- Arista: movimiento entre vecinos.
- Peso base:
  - `1.0` ortogonal,
  - `1.5` diagonal.

### Heuristica

Se usa distancia euclidiana para estimar costo restante al objetivo.

### Costo dinamico

No se usa solo distancia geometrica. El peso se ajusta por:

- densidad local,
- velocidad promedio local,
- ansiedad local.

Esto permite que la ruta responda a congestion real, no solo a distancia minima.

## 5. Seleccion de rutas y ansiedad

El `PathSelector` no se limita a una ruta:

- calcula alternativas (`k-paths`),
- penaliza celdas repetidas para promover diversidad,
- selecciona ruta segun ansiedad del agente.

Comportamiento general:

- ansiedad baja: preferencia por ruta optima,
- ansiedad media: mezcla entre ruta optima y alternativas,
- ansiedad alta: mayor variabilidad y exploracion.

## 6. Recalculo de ruta

El sistema recalcula cuando detecta condiciones de bloqueo, por ejemplo:

- ruta invalida,
- estancamiento por varios pasos,
- siguiente celda congestionada,
- bloqueo cerca de la salida.

Esto evita que agentes queden atascados en decisiones antiguas.

## 7. Resolucion de conflictos

Cuando varios agentes proponen la misma celda:

- se aplica criterio de prioridad (distancia a meta y tipo de agente),
- un agente avanza,
- los demas quedan en su posicion y aumentan su presion/ansiedad.

Este mecanismo introduce interaccion realista entre trayectorias.

## 8. Que resultados produce

### Salida de demo

En `salidas/demo/`:

- CSV por paso:
  - agentes activos,
  - evacuados,
  - conflictos,
  - ratio de evacuacion.
- PNG:
  - evolucion temporal de activos vs evacuados.

### Salida experimental

En `salidas/experimentos/`:

- barridos parametricos (`barrido_propuesta1.pkl`, `barrido_herd.pkl`),
- figuras de analisis (`salidas/experimentos/figuras/`).

## 9. Mensaje tecnico para defensa

Puntos clave para explicar en reunion:

- El modelo combina una base clasica (`floor field`) con una capa de planificacion (`A*`).
- La planificacion no es estatica: incorpora congestion y recalculo.
- La toma de decision es heterogenea (ansiedad), lo que evita comportamiento artificialmente uniforme.
- El sistema ya entrega trazabilidad reproducible (CSV/PNG/PKL) lista para mostrar.

## 10. Comandos minimos de uso

```bash
# Simulacion principal para demo
python simulacion/grilla/dynamics.py --sala

# Escenario de flujos opuestos
python simulacion/grilla/dynamics.py --flujos

# Tests de integracion de pathfinding
python -m pytest tests/test_path_selector_integration.py -v
```
#  Explicación Completa: Sistema A* y Nodos

##  Tabla de Contenidos

1. [Visión General](#visión-general)
2. [Arquitectura del Sistema](#arquitectura-del-sistema)
3. [Construcción del Grafo de Nodos](#construcción-del-grafo-de-nodos)
4. [Algoritmo A*](#algoritmo-a)
5. [Funciones Principales](#funciones-principales)
6. [Flujo de Datos](#flujo-de-datos)
7. [Ejemplo Paso a Paso](#ejemplo-paso-a-paso)

---

## Visión General

El sistema de enrutamiento inteligente convierte una **grilla 2D** (floor field) en un **grafo dirigido** donde cada celda válida es un **nodo** y las conexiones entre celdas adyacentes son **aristas**. Luego usa el algoritmo **A*** para encontrar rutas óptimas entre cualquier par de nodos.

### Componentes Principales:

- **Floor Field**: Matriz 2D con valores de distancia a puertas
- **Grafo de Nodos**: Representación en grafo (NetworkX DiGraph)
- **PathSelector**: Clase que gestiona el grafo y ejecuta A*
- **A* Algorithm**: Algoritmo de búsqueda de caminos óptimos

---

##  Arquitectura del Sistema

```
┌─────────────────┐
│  Floor Field    │  Matriz 2D con valores de distancia
│  (width x height)│  Paredes = 500, Puertas = 0
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  PathSelector   │  Convierte floor_field → grafo
│  _build_graph() │  Cada celda válida → nodo
└────────┬────────┘  Conexiones → aristas con pesos
         │
         ▼
┌─────────────────┐
│  Grafo (DiGraph)│  Nodos: (x, y) coordenadas
│  NetworkX       │  Aristas: conexiones con peso
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  A* Algorithm    │  Busca ruta óptima
│  encontrar_ruta  │  origen → destino
└─────────────────┘
```

---

## Construcción del Grafo de Nodos

### 1. Proceso de Conversión

El método `_construir_grafo_nodos_impl()` convierte el floor field en un grafo:

```python
def _construir_grafo_nodos_impl(self) -> nx.DiGraph:
    G = nx.DiGraph()  # Grafo dirigido
    
    # Direcciones posibles (8 direcciones)
    direcciones = [
        (0, 1, 1.0),    # Norte (vertical)
        (1, 0, 1.0),    # Este (horizontal)
        (0, -1, 1.0),   # Sur
        (-1, 0, 1.0),   # Oeste
        (1, 1, 1.5),    # NE (diagonal)
        (1, -1, 1.5),   # SE
        (-1, 1, 1.5),   # NO
        (-1, -1, 1.5)   # SO
    ]
```

### 2. Creación de Nodos

**Criterio para crear un nodo:**
- La celda debe tener `valor < 500` (no es pared ni obstáculo)
- Cada celda válida se convierte en un nodo con coordenadas `(x, y)`

```python
for y in range(height):
    for x in range(width):
        valor = floor_field.valores[y, x]
        
        if valor < 500:  # Celda válida
            # Crear nodo con atributo floor_value
            G.add_node((x, y), floor_value=valor)
```

**Ejemplo:**
```
Grilla 3x3:
[500] [10] [500]   →   Nodos: (1,0), (1,1), (1,2)
[ 5 ] [ 3 ] [ 8 ]   →   (0,1), (1,1), (2,1)
[500] [ 0 ] [500]   →   (1,2) - puerta
```

### 3. Creación de Aristas (Conexiones)

**Criterio para crear una arista:**
- El nodo origen debe ser válido
- El nodo destino debe ser válido (dentro de límites y valor < 500)
- Se conecta en las 8 direcciones posibles

```python
for dx, dy, costo_base in direcciones:
    nx_coord, ny_coord = x + dx, y + dy
    
    # Verificar límites y validez
    if (0 <= nx_coord < width and 0 <= ny_coord < height):
        valor_vecino = floor_field.valores[ny_coord, nx_coord]
        
        if valor_vecino < 500:  # Vecino válido
            # Crear arista con peso
            G.add_edge((x, y), (nx_coord, ny_coord), weight=costo_base)
```

**Pesos de las aristas:**
- **Movimientos ortogonales** (N, S, E, O): peso = **1.0**
- **Movimientos diagonales** (NE, SE, NO, SO): peso = **1.5**

**Ejemplo de conexiones:**
```
Nodo (1,1) se conecta a:
- (1,2) peso=1.0  (Norte)
- (2,1) peso=1.0  (Este)
- (1,0) peso=1.0  (Sur)
- (0,1) peso=1.0  (Oeste)
- (2,2) peso=1.5  (NE diagonal)
- (2,0) peso=1.5  (SE diagonal)
- (0,2) peso=1.5  (NO diagonal)
- (0,0) peso=1.5  (SO diagonal)
```

### 4. Estructura del Grafo Resultante

```python
Grafo = {
    Nodos: {
        (0, 0): {'floor_value': 5},
        (1, 0): {'floor_value': 3},
        (2, 0): {'floor_value': 8},
        ...
    },
    Aristas: {
        ((0,0), (1,0)): {'weight': 1.0},
        ((0,0), (0,1)): {'weight': 1.0},
        ((0,0), (1,1)): {'weight': 1.5},
        ...
    }
}
```

---

## Algoritmo A*

### 1. Conceptos Fundamentales

A* es un algoritmo de búsqueda que encuentra el camino más corto entre dos nodos usando:

- **g(n)**: Costo real desde el inicio hasta el nodo `n`
- **h(n)**: Estimación heurística del costo desde `n` hasta el objetivo
- **f(n) = g(n) + h(n)**: Función de evaluación total

### 2. Implementación en el Código

```python
def encontrar_ruta_a_star(self, origen, meta, usar_cache=True):
    # 1. Verificar caché
    if cache_key in self.path_cache:
        return self.path_cache[cache_key]  # Retornar ruta guardada
    
    # 2. Inicializar estructuras
    open_set = []  # Cola de prioridad (heap)
    heapq.heappush(open_set, (0, 0, origen))
    
    came_from = {}  # Para reconstruir el camino
    g_score = {origen: 0}  # Costo real acumulado
    f_score = {origen: heuristic(origen, meta)}  # Costo estimado total
```

### 3. Bucle Principal de A*

```python
while open_set:
    # 3. Extraer nodo con menor f_score
    _, _, current = heapq.heappop(open_set)
    
    # 4. ¿Llegamos al objetivo?
    if current == meta:
        # Reconstruir camino desde meta hasta origen
        ruta = [current]
        while current in came_from:
            current = came_from[current]
            ruta.append(current)
        ruta.reverse()
        return ruta
    
    # 5. Explorar vecinos
    for vecino in grafo.neighbors(current):
        peso = grafo[current][vecino]['weight']
        tentative_g = g_score[current] + peso
        
        # 6. ¿Es mejor camino?
        if vecino not in g_score or tentative_g < g_score[vecino]:
            came_from[vecino] = current
            g_score[vecino] = tentative_g
            f_score[vecino] = tentative_g + heuristic(vecino, meta)
            
            # Agregar a open_set si no está
            heapq.heappush(open_set, (f_score[vecino], contador, vecino))
```

### 4. Función Heurística

```python
def calculate_heuristic(self, pos1, pos2):
    """
    Distancia euclidiana entre dos puntos.
    Es admisible (nunca sobreestima) y consistente.
    """
    dx = abs(pos1[0] - pos2[0])
    dy = abs(pos1[1] - pos2[1])
    return math.sqrt(dx**2 + dy**2)
```

**Propiedades:**
- **Admisible**: Nunca sobreestima el costo real
- **Consistente**: h(n) ≤ costo(n, n') + h(n') para todos los vecinos

---

## Funciones Principales

### 1. `_build_graph_from_floor_field()`

**Propósito:** Convierte floor field en grafo de nodos.

**Proceso:**
1. Crea grafo dirigido vacío
2. Itera sobre todas las celdas
3. Para cada celda válida (valor < 500):
   - Crea nodo con coordenadas (x, y)
   - Agrega atributo `floor_value`
4. Para cada nodo, conecta a sus 8 vecinos válidos
5. Asigna pesos: 1.0 (ortogonal) o 1.5 (diagonal)

**Retorna:** `nx.DiGraph` con nodos y aristas

---

### 2. `encontrar_ruta_a_star(origen, meta, usar_cache=True)`

**Propósito:** Encuentra ruta óptima usando A*.

**Parámetros:**
- `origen`: Tuple (x, y) - Posición inicial
- `meta`: Tuple (x, y) - Posición objetivo
- `usar_cache`: bool - Si usa caché de rutas

**Proceso:**
1. Verifica caché (si `usar_cache=True`)
2. Valida que origen y meta existan en el grafo
3. Inicializa estructuras A*:
   - `open_set`: Cola de prioridad (heap)
   - `came_from`: Diccionario para reconstruir camino
   - `g_score`: Costos reales acumulados
   - `f_score`: Costos estimados totales
4. Bucle principal:
   - Extrae nodo con menor f_score
   - Si es meta, reconstruye y retorna camino
   - Explora vecinos y actualiza costos
5. Guarda ruta en caché
6. Retorna lista de nodos: `[(x1,y1), (x2,y2), ..., (xn,yn)]`

**Retorna:** `List[Tuple[int, int]]` o `None` si no hay camino

---

### 3. `calculate_heuristic(pos1, pos2)`

**Propósito:** Calcula estimación de distancia entre dos puntos.

**Fórmula:** Distancia euclidiana
```
h = √((x2-x1)² + (y2-y1)²)
```

**Ejemplo:**
```python
pos1 = (0, 0)
pos2 = (3, 4)
h = √(3² + 4²) = √(9 + 16) = √25 = 5.0
```

---

### 4. `find_k_paths(start, goal, k=3)`

**Propósito:** Encuentra k rutas alternativas diferentes.

**Proceso:**
1. Calcula primera ruta con A* normal
2. Para rutas 2 a k:
   - Penaliza celdas usadas en rutas anteriores
   - Ejecuta A* con penalizaciones
   - Valida que la nueva ruta sea diferente (>30% celdas distintas)
3. Retorna lista de k rutas

**Uso:** Permite seleccionar entre múltiples opciones según ansiedad.

---

### 4b. `find_progressive_paths(start, goal, num_paths, penalty_factor=0.5)`

**Propósito:** Encuentra rutas alternativas con sistema progresivo (1, 3, o 5 rutas).

**Parámetros:**
- `start`: Tuple (x, y) - Posición inicial
- `goal`: Tuple (x, y) - Posición objetivo
- `num_paths`: int - Número de rutas a calcular (debe ser 1, 3, o 5)
- `penalty_factor`: float - Factor de penalización para celdas reutilizadas (default: 0.5)

**Proceso:**
1. Valida que `num_paths` sea 1, 3, o 5 (lanza ValueError si no)
2. Actualiza estadísticas de desbloqueo por nivel
3. Llama a `find_k_paths()` con el número solicitado
4. Retorna lista de rutas alternativas

**Uso:** Parte del sistema de desbloqueo progresivo que permite a los agentes tener más opciones cuando están atascados.

**Ejemplo:**
```python
# Calcular 1 ruta (inicial)
paths_1 = ps.find_progressive_paths(start, goal, num_paths=1)

# Calcular 3 rutas (ansiedad media)
paths_3 = ps.find_progressive_paths(start, goal, num_paths=3)

# Calcular 5 rutas (ansiedad alta)
paths_5 = ps.find_progressive_paths(start, goal, num_paths=5)
```

---

### 4c. `calculate_unlocked_paths(steps_without_moving, calmness_threshold=3)`

**Propósito:** Calcula cuántas rutas deben estar desbloqueadas según el tiempo que el agente lleva sin moverse.

**Parámetros:**
- `steps_without_moving`: int - Pasos consecutivos sin moverse
- `calmness_threshold`: int - Umbral base para desbloquear rutas (default: 3)

**Lógica de Desbloqueo:**
```
steps_without_moving < calmness_threshold     → 1 ruta
calmness_threshold ≤ steps < calmness_threshold + 2  → 3 rutas
steps_without_moving ≥ calmness_threshold + 2  → 5 rutas
```

**Ejemplo con calmness_threshold=3:**
- 0-2 pasos atascado → 1 ruta (baja ansiedad)
- 3-4 pasos atascado → 3 rutas (ansiedad media)
- 5+ pasos atascado → 5 rutas (alta ansiedad)

**Razón del diseño:**
- `calmness_threshold=3` fue elegido porque permite detectar estancamiento real sin ser demasiado sensible a bloqueos temporales
- La progresión 1→3→5 proporciona suficiente variedad sin sobrecargar el sistema con demasiadas opciones
- Los agentes empiezan con la ruta óptima y solo exploran alternativas cuando realmente están atascados

**Diagrama de Progresión:**
```
Pasos sin moverse:  0    1    2    3    4    5    6    7+
Rutas desbloqueadas: [1] [1] [1] [3] [3] [5] [5] [5]
                     └─ Baja ansiedad ─┘ └─ Media ─┘ └─ Alta ─┘
```

---

---

### 5. `select_path_by_anxiety(k_paths, anxiety_level, num_available_paths=None)`

**Propósito:** Selecciona una ruta de k_paths según nivel de ansiedad, considerando solo las rutas desbloqueadas.

**Parámetros:**
- `k_paths`: Lista de rutas alternativas
- `anxiety_level`: float - Nivel de ansiedad (0-100)
- `num_available_paths`: int (opcional) - Número de rutas desbloqueadas (1, 3, o 5). Si None, usa todas las rutas en k_paths.

**Lógica:**
- **Ansiedad baja (0-30)**: Siempre ruta óptima (índice 0)
- **Ansiedad óptima (30-70)**: 
  - 70% probabilidad: ruta óptima
  - 20% probabilidad: ruta media
  - 10% probabilidad: ruta subóptima
- **Ansiedad alta (70-100)**:
  - 30% probabilidad: ruta óptima
  - 30% probabilidad: ruta media
  - 40% probabilidad: ruta subóptima
  - 10% probabilidad adicional: añade ruido (movimientos erráticos)

**Comportamiento con num_available_paths:**
- Si se proporciona, solo considera las primeras `num_available_paths` rutas de `k_paths`
- Esto permite que el sistema de desbloqueo progresivo funcione correctamente
- Ejemplo: Si `num_available_paths=3`, solo selecciona de las primeras 3 rutas, incluso si hay 5 calculadas

---

### 6. `should_recalculate(...)`

**Propósito:** Determina si un agente debe recalcular su ruta.

**Condiciones de recálculo:**
1. **Ruta inválida**: `path_index >= len(current_path)`
2. **Estancamiento**: `steps_without_moving >= 3`
3. **Bloqueo inmediato**: Siguiente celda tiene ≥2 agentes
4. **Cerca de meta bloqueado**: Distancia < 3 y no puede avanzar

**Retorna:** `True` si debe recalcular, `False` si continúa

---

### 7. `actualizar_pesos_grafo(alpha, beta, gamma)`

**Propósito:** Actualiza pesos de aristas según métricas dinámicas.

**Fórmula:**
```
peso_final = peso_base × (1 + α×densidad + β×factor_velocidad + γ×ansiedad)
```

**Factores:**
- **Densidad**: Número de agentes en la celda destino
- **Velocidad**: Velocidad promedio (menos_vivos son más lentos)
- **Ansiedad**: Nivel de ansiedad promedio en la celda

**Efecto:** Rutas más congestionadas tienen mayor peso → A* las evita.

---

##  Flujo de Datos

### Flujo Completo de una Búsqueda de Ruta:

```
1. Usuario solicita ruta:
   encontrar_ruta_a_star((5, 5), (0, 9))

2. Verificar caché:
   ¿Existe ruta (5,5)→(0,9) en caché?
   ├─ SÍ → Retornar ruta guardada
   └─ NO → Continuar

3. Validar nodos:
   ¿(5,5) y (0,9) existen en grafo?
   ├─ NO → Retornar None
   └─ SÍ → Continuar

4. Inicializar A*:
   open_set = [(f_score, contador, (5,5))]
   g_score = {(5,5): 0}
   f_score = {(5,5): heuristic((5,5), (0,9))}
   came_from = {}

5. Bucle A*:
   while open_set:
       current = extraer_minimo(open_set)
       
       if current == (0,9):
           reconstruir_camino()
           guardar_en_cache()
           return ruta
       
       for vecino in grafo.neighbors(current):
           peso = grafo[current][vecino]['weight']
           nuevo_g = g_score[current] + peso
           
           if nuevo_g < g_score[vecino]:
               actualizar_costos()
               agregar_a_open_set()

6. Retornar ruta:
   [(5,5), (4,5), (3,5), (2,5), (1,5), (0,5), (0,6), (0,7), (0,8), (0,9)]
```

---

## 📊 Ejemplo Paso a Paso

### Escenario: Grilla 5x5

```
[500] [500] [500] [500] [500]
[500] [ 5 ] [ 3 ] [ 2 ] [500]
[500] [ 6 ] [ 4 ] [ 1 ] [500]
[500] [ 7 ] [ 5 ] [ 0 ] [500]  ← Puerta en (3,3)
[500] [500] [500] [500] [500]
```

### Paso 1: Construcción del Grafo

**Nodos creados:**
```
(1,1), (2,1), (3,1)
(1,2), (2,2), (3,2)
(1,3), (2,3), (3,3) ← Puerta
```

**Aristas ejemplo (nodo (2,2)):**
```
(2,2) → (1,2) peso=1.0  (Oeste)
(2,2) → (3,2) peso=1.0  (Este)
(2,2) → (2,1) peso=1.0  (Norte)
(2,2) → (2,3) peso=1.0  (Sur)
(2,2) → (1,1) peso=1.5  (NO diagonal)
(2,2) → (3,1) peso=1.5  (NE diagonal)
(2,2) → (1,3) peso=1.5  (SO diagonal)
(2,2) → (3,3) peso=1.5  (SE diagonal)
```

### Paso 2: Búsqueda A* desde (1,1) hasta (3,3)

**Iteración 1:**
```
open_set: [(2.83, 0, (1,1))]
current: (1,1)
g_score: {(1,1): 0}
f_score: {(1,1): 2.83}
```

**Iteración 2:**
```
Explorar vecinos de (1,1):
- (2,1): g=1.0, h=2.24, f=3.24
- (1,2): g=1.0, h=2.24, f=3.24
- (2,2): g=1.5, h=1.41, f=2.91 ← Mejor

open_set: [(2.91, 1, (2,2)), (3.24, 2, (2,1)), (3.24, 3, (1,2))]
current: (2,2)
```

**Iteración 3:**
```
Explorar vecinos de (2,2):
- (3,2): g=2.5, h=1.0, f=3.5
- (2,3): g=2.5, h=1.0, f=3.5
- (3,3): g=3.0, h=0.0, f=3.0 ← Meta!

Ruta encontrada: [(1,1), (2,2), (3,3)]
```

### Paso 3: Visualización de la Ruta

```
[500] [500] [500] [500] [500]
[500] [ S ] [   ] [   ] [500]
[500] [   ] [ • ] [   ] [500]
[500] [   ] [   ] [ G ] [500]
[500] [500] [500] [500] [500]

S = Start (1,1)
• = Paso intermedio (2,2)
G = Goal (3,3)
```

---

##  Características Avanzadas

### 1. Caché de Rutas

**Propósito:** Evitar recalcular rutas ya calculadas.

**Implementación:**
```python
self.path_cache = {}  # {(start, goal): path}

# Al calcular ruta:
if (origen, meta) in self.path_cache:
    return self.path_cache[(origen, meta)]  # Cache hit!

# Al encontrar ruta:
self.path_cache[(origen, meta)] = ruta.copy()
```

**Beneficio:** Reduce tiempo de cálculo en simulaciones repetitivas.

---

### 2. Pesos Dinámicos

**Propósito:** Adaptar rutas según condiciones actuales.

**Proceso:**
1. `actualizar_metricas()`: Calcula densidad, velocidad, ansiedad por celda
2. `actualizar_pesos_grafo()`: Modifica pesos de aristas
3. A* usa nuevos pesos → evita áreas congestionadas

**Ejemplo:**
```
Celda (5,5) tiene 3 agentes:
peso_original = 1.0
densidad = 1.0 (máxima)
peso_nuevo = 1.0 × (1 + 1.5×1.0) = 2.5

A* ahora evita esta celda si hay alternativas mejores.
```

---

### 3. K-Paths (Rutas Alternativas)

**Propósito:** Encontrar múltiples rutas diferentes.

**Algoritmo:**
1. Primera ruta: A* normal
2. Rutas siguientes: A* con penalización en celdas ya usadas
3. Validación: Nueva ruta debe tener >30% celdas distintas

**Uso:** Permite selección probabilística según ansiedad.

---

### 3b. Progressive Path Unlocking (Desbloqueo Progresivo)

**Propósito:** Sistema que aumenta el número de rutas disponibles según el tiempo que el agente lleva atascado.

**Cómo funciona:**
1. **Estado inicial**: Agente tiene 1 ruta óptima desbloqueada
2. **Detección de estancamiento**: Se cuenta `steps_without_moving`
3. **Desbloqueo progresivo**:
   - 0-2 pasos: 1 ruta (baja ansiedad)
   - 3-4 pasos: 3 rutas (ansiedad media)
   - 5+ pasos: 5 rutas (alta ansiedad)
4. **Almacenamiento**: Todas las rutas calculadas se guardan en `all_calculated_paths`
5. **Selección**: Solo se selecciona de las rutas desbloqueadas según ansiedad

**Visualización:**
```
Agente atascado 0 pasos:  [Ruta 1] ────────────────→ Meta
                           (1 ruta desbloqueada)

Agente atascado 3 pasos:  [Ruta 1] ────────────────→ Meta
                          [Ruta 2] ────┐
                          [Ruta 3] ────┴───────────→ Meta
                          (3 rutas desbloqueadas)

Agente atascado 5+ pasos: [Ruta 1] ────────────────→ Meta
                          [Ruta 2] ────┐
                          [Ruta 3] ────┼───────────→ Meta
                          [Ruta 4] ────┤
                          [Ruta 5] ────┘
                          (5 rutas desbloqueadas)
```

**Ventajas:**
- Reduce carga computacional inicial (solo calcula lo necesario)
- Proporciona más opciones cuando realmente se necesitan
- Mejora la eficiencia de evacuación en escenarios congestionados

---

## Conexión entre Componentes

### Relación Floor Field → Grafo → A*

```
Floor Field (Matriz 2D)
    │
    │ valores[y,x] < 500 → Celda válida
    │
    ▼
Nodo en Grafo (x, y)
    │
    │ Conexiones a 8 vecinos
    │
    ▼
Aristas con pesos
    │
    │ weight = 1.0 (ortogonal) o 1.5 (diagonal)
    │
    ▼
A* usa pesos para encontrar camino óptimo
    │
    ▼
Ruta: Lista de nodos [(x1,y1), (x2,y2), ...]
```

---

##  Métricas y Estadísticas

El sistema rastrea:

- **`stats['calls']`**: Total de llamadas a A*
- **`stats['cache_hits']`**: Rutas encontradas en caché
- **`stats['nodes_explored']`**: Nodos explorados por búsqueda
- **`stats['recalculations_by_anxiety']`**: Recalculaciones por nivel de ansiedad

**Ejemplo de reporte:**
```
PathSelector REPORT
A* calls: 150
Cache hits: 45
Cache hit rate: 30.0%
Nodes explored (average): 12.5
Unique paths calculated: 25
```

---

## Resumen

1. **Floor Field** → Matriz 2D con distancias a puertas
2. **Grafo de Nodos** → Cada celda válida es un nodo, conexiones son aristas
3. **A*** → Busca ruta óptima usando heurística euclidiana
4. **Caché** → Almacena rutas calculadas para reutilización
5. **Pesos Dinámicos** → Adapta rutas según congestión
6. **K-Paths** → Encuentra rutas alternativas
7. **Selección por Ansiedad** → Elige ruta según estado emocional

El sistema convierte eficientemente una grilla 2D en un grafo navegable y usa A* para encontrar rutas óptimas considerando múltiples factores dinámicos.

