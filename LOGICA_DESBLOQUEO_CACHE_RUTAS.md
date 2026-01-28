# Lógica del Sistema de Desbloqueo Progresivo y Caché de Rutas

## Tabla de Contenidos
1. [Introducción](#introducción)
2. [Sistema de Desbloqueo Progresivo](#sistema-de-desbloqueo-progresivo)
3. [Caché de Rutas](#caché-de-rutas)
4. [Integración de Sistemas](#integración-de-sistemas)
5. [Selección de Rutas por Ansiedad](#selección-de-rutas-por-ansiedad)
6. [Flujo Completo del Sistema](#flujo-completo-del-sistema)
7. [Ejemplos Prácticos](#ejemplos-prácticos)
8. [Optimizaciones y Consideraciones](#optimizaciones-y-consideraciones)

---

## Introducción

El sistema de evacuación implementa dos mecanismos clave para optimizar el movimiento de agentes:

1. **Desbloqueo Progresivo de Caminos**: Los agentes comienzan con una sola ruta óptima y desbloquean más rutas alternativas (3 o 5) cuando se encuentran atascados, basándose en su nivel de "estancamiento" (`steps_without_moving`).

2. **Caché de Rutas**: Almacena rutas previamente calculadas para evitar recalcularlas innecesariamente, mejorando significativamente el rendimiento.

Estos sistemas trabajan en conjunto para proporcionar navegación eficiente y adaptable.

---

## Sistema de Desbloqueo Progresivo

### Concepto Fundamental

El desbloqueo progresivo permite que los agentes adapten su estrategia de navegación según su situación:

- **Estado Normal (1 ruta)**: El agente usa solo la ruta óptima, minimizando cálculos.
- **Estado de Preocupación (3 rutas)**: Cuando el agente está atascado, desbloquea rutas alternativas.
- **Estado de Pánico (5 rutas)**: En situaciones críticas, el agente tiene acceso a todas las rutas disponibles.

### Función `calculate_unlocked_paths()`

```python
def calculate_unlocked_paths(self, steps_without_moving: int, 
                             calmness_threshold: int = 3) -> int:
    """
    Calcula cuántas rutas deben desbloquearse basándose en el estancamiento.
    
    Lógica:
    - 0-2 pasos atascado: 1 ruta (ansiedad baja, tranquilo)
    - 3-4 pasos atascado: 3 rutas (ansiedad media, preocupado)
    - 5+ pasos atascado: 5 rutas (ansiedad alta, pánico)
    """
    if steps_without_moving < calmness_threshold:
        return 1
    elif steps_without_moving < calmness_threshold + 2:
        return 3
    else:
        return 5
```

### Parámetro `calmness_threshold`

**Valor por defecto: 3**

**Razones de diseño:**
- **Sensibilidad adecuada**: Detecta estancamiento real sin ser demasiado sensible a retrasos temporales
- **Balance eficiencia/responsividad**: No recalcula demasiado frecuentemente, pero responde cuando es necesario
- **Evita falsos positivos**: Un umbral muy bajo (< 2) causaría recalculaciones innecesarias por bloqueos temporales normales
- **Detección oportuna**: Un umbral muy alto (> 5) haría que los agentes esperen demasiado antes de buscar alternativas

### Progresión 1→3→5

La progresión de rutas desbloqueadas está diseñada para:

1. **Eficiencia (1 ruta)**:
   - Reduce el costo computacional inicial
   - Los agentes que pueden moverse libremente no necesitan alternativas
   - Minimiza la sobrecarga de cálculo de rutas

2. **Balance (3 rutas)**:
   - Ofrece alternativas suficientes sin abrumar al agente
   - Permite evitar bloqueos locales manteniendo eficiencia
   - Proporciona flexibilidad sin sacrificar demasiado rendimiento

3. **Flexibilidad Máxima (5 rutas)**:
   - Máxima exploración cuando el agente está severamente atascado
   - Permite considerar rutas subóptimas que podrían ser más viables
   - Útil en situaciones de alta congestión

### Diagrama de Progresión

```
Pasos sin moverse:  0    1    2    3    4    5    6    7    8+
                    │    │    │    │    │    │    │    │    │
Rutas desbloqueadas: 1    1    1    3    3    5    5    5    5
                    │    │    │    │    │    │    │    │    │
Estado:          Tranquilo    Preocupado    Pánico
```

---

## Caché de Rutas

### Concepto

El caché almacena rutas previamente calculadas para evitar recalcularlas cuando múltiples agentes necesitan rutas similares o cuando un agente necesita recalcular su ruta.

### Estructura del Caché

```python
# En PathSelector.__init__()
self.path_cache = {}  # Diccionario: {(start, goal): path}

# Clave del caché: tupla (start, goal)
cache_key = (start, goal)  # Ejemplo: ((10, 5), (0, 6))

# Valor del caché: lista de tuplas representando la ruta
cached_path = [(10, 5), (9, 5), (8, 5), ..., (0, 6)]
```

### Uso del Caché en `encontrar_ruta_a_star()`

```python
def encontrar_ruta_a_star(self, origen, meta, usar_cache=True):
    """
    Encuentra ruta usando A* con soporte para caché.
    """
    cache_key = (origen, meta)
    
    # Verificar caché
    if usar_cache and cache_key in self.path_cache:
        self.stats['cache_hits'] += 1
        return self.path_cache[cache_key].copy()  # Retornar copia
    
    # Calcular ruta usando A*
    ruta = self._a_star_search(origen, meta)
    
    # Guardar en caché si se encontró ruta
    if ruta and usar_cache:
        self.path_cache[cache_key] = ruta.copy()
    
    return ruta
```

### Ventajas del Caché

1. **Rendimiento**: Evita recalcular rutas idénticas múltiples veces
2. **Consistencia**: Múltiples agentes con el mismo origen y destino obtienen la misma ruta óptima
3. **Eficiencia de memoria**: Las rutas se almacenan como listas simples de tuplas

### Limitaciones y Consideraciones

1. **Rutas estáticas**: El caché asume que el entorno no cambia (obstáculos fijos)
2. **Congestión dinámica**: El caché no considera la congestión actual de agentes
3. **Invalidación**: El caché se limpia manualmente con `reset_statistics()`

### Estadísticas del Caché

```python
self.stats = {
    'calls': 0,           # Total de llamadas a encontrar_ruta_a_star
    'cache_hits': 0,      # Rutas encontradas en caché
    'cache_size': len(self.path_cache)  # Tamaño actual del caché
}
```

**Tasa de aciertos del caché**: `cache_hit_rate = cache_hits / calls`

---

## Integración de Sistemas

### Flujo en `AgentExtendido.elegir_ruta()`

El método `elegir_ruta()` integra ambos sistemas:

```python
def elegir_ruta(self, goal: tuple, agent_positions: Dict[tuple, int]):
    """
    Elige o recalcula ruta usando desbloqueo progresivo y caché.
    """
    # 1. Verificar si necesita recalcular
    needs_recalc = (
        self.current_path is None or
        self.path_selector.should_recalculate(...)
    )
    
    if needs_recalc:
        # 2. Calcular cuántas rutas desbloquear
        self.unlocked_paths_count = self.path_selector.calculate_unlocked_paths(
            steps_without_moving=self.steps_without_moving,
            calmness_threshold=self.calmness_threshold
        )
        
        # 3. Encontrar todas las rutas (hasta 5)
        # ESTRATEGIA: Calcular 5 rutas siempre, pero solo usar las desbloqueadas
        self.all_calculated_paths = self.path_selector.find_progressive_paths(
            start=(self.pos_x, self.pos_y),
            goal=goal,
            num_paths=5  # Siempre calcular 5
        )
        
        # 4. Seleccionar ruta basándose en ansiedad
        # Solo considerar las primeras 'unlocked_paths_count' rutas
        self.current_path = self.path_selector.select_path_by_anxiety(
            k_paths=self.all_calculated_paths,
            anxiety_level=self.ansiedad,
            num_available_paths=self.unlocked_paths_count  # ← CLAVE
        )
```

### Estrategia de Cálculo: "Calcular 5, Usar Solo las Desbloqueadas"

**¿Por qué calcular 5 rutas si solo se usan 1-3?**

1. **Preparación para el futuro**: Si el agente se atasca más, ya tiene las rutas calculadas
2. **Eficiencia**: Evita recalcular cuando `steps_without_moving` aumenta
3. **Visualización**: Permite mostrar todas las rutas posibles en la visualización
4. **Análisis**: Facilita el análisis posterior de decisiones

**Trade-off**: Más cálculo inicial vs. menos recalculaciones futuras

### Función `find_progressive_paths()`

```python
def find_progressive_paths(self, start: tuple, goal: tuple, 
                           num_paths: int, penalty_factor: float = 0.5) -> List[List[tuple]]:
    """
    Encuentra rutas alternativas progresivas (1, 3, o 5).
    
    Internamente usa find_k_paths() pero registra estadísticas específicas.
    """
    if num_paths not in [1, 3, 5]:
        raise ValueError(f"num_paths must be 1, 3, or 5, got {num_paths}")
    
    # Registrar estadísticas de desbloqueo
    self.stats['paths_unlocked_by_level'][num_paths] += 1
    
    # Usar find_k_paths para calcular las rutas
    return self.find_k_paths(start, goal, k=num_paths, penalty_factor=penalty_factor)
```

### Función `find_k_paths()`

Esta función encuentra `k` rutas alternativas usando penalizaciones:

```python
def find_k_paths(self, start, goal, k=3, penalty_factor=0.5):
    """
    Encuentra k rutas alternativas desde start hasta goal.
    
    Algoritmo:
    1. Path 1: A* normal (ruta óptima) - USA CACHÉ
    2. Paths 2-k: A* con penalizaciones para celdas ya usadas - SIN CACHÉ
    
    Por qué Path 1 usa caché pero Paths 2-k no:
    - Path 1 es la ruta óptima estándar, puede ser reutilizada
    - Paths 2-k dependen de penalizaciones dinámicas, no pueden usar caché
    """
    paths_found = []
    penalty_costs = {}  # {(x,y): veces_usada}
    
    # Path 1: Ruta óptima usando A* con CACHÉ
    path1 = self.encontrar_ruta_a_star(start, goal, usar_cache=True)
    
    if path1 is None:
        return []  # No hay camino posible
    
    paths_found.append(path1)
    
    # Actualizar penalizaciones con la primera ruta
    for cell in path1:
        penalty_costs[cell] = penalty_costs.get(cell, 0) + 1
    
    # Paths 2 a k: Rutas alternativas con penalizaciones (SIN CACHÉ)
    for path_num in range(2, k + 1):
        # Buscar ruta con penalizaciones modificadas
        # No puede usar caché porque las penalizaciones son dinámicas
        path = self._find_path_with_penalties(start, goal, penalty_costs)
        
        if path is None:
            break  # No se encontraron más rutas
        
        # Validar que la ruta sea diferente (>30% celdas diferentes)
        is_different = self._validate_path_difference(path, paths_found)
        
        if is_different:
            paths_found.append(path)
            # Actualizar penalizaciones
            for cell in path:
                penalty_costs[cell] = penalty_costs.get(cell, 0) + 1
    
    return paths_found
```

### Interacción Caché vs. Penalizaciones

**Path 1 (Óptima)**:
- ✅ Usa caché: `encontrar_ruta_a_star(start, goal, usar_cache=True)`
- Rápido si ya fue calculado antes
- Consistente entre agentes

**Paths 2-5 (Alternativas)**:
- ❌ No usa caché: `encontrar_ruta_a_star(start, goal, usar_cache=False)`
- Requiere cálculo completo porque las penalizaciones son dinámicas
- Cada cálculo puede producir rutas diferentes según penalizaciones acumuladas

---

## Selección de Rutas por Ansiedad

### Función `select_path_by_anxiety()`

Una vez que se tienen las rutas calculadas, el sistema selecciona cuál usar basándose en el nivel de ansiedad del agente.

### Parámetro `num_available_paths`

Este parámetro es **crucial** para el sistema de desbloqueo progresivo:

```python
def select_path_by_anxiety(self, k_paths: List[List[tuple]], 
                          anxiety_level: float,
                          num_available_paths: int = None) -> List[tuple]:
    """
    Selecciona una ruta de las disponibles basándose en ansiedad.
    
    Args:
        k_paths: Lista de todas las rutas calculadas (hasta 5)
        anxiety_level: Nivel de ansiedad del agente (0-100)
        num_available_paths: Número de rutas desbloqueadas (1, 3, o 5)
                            Si es None, usa todas las rutas en k_paths
    """
    # Solo considerar las primeras num_available_paths rutas
    if num_available_paths is not None:
        available_paths = k_paths[:num_available_paths]
    else:
        available_paths = k_paths
```

**Ejemplo**:
- `k_paths` = [ruta1, ruta2, ruta3, ruta4, ruta5]  # 5 rutas calculadas
- `unlocked_paths_count` = 3  # Solo 3 rutas desbloqueadas
- `available_paths` = [ruta1, ruta2, ruta3]  # Solo estas se consideran

### Distribución de Probabilidades por Ansiedad

#### Baja Ansiedad (0-30)
- **Comportamiento**: Siempre selecciona la ruta óptima (índice 0)
- **Razón**: Agentes tranquilos prefieren la ruta más corta/eficiente
- **Distribución**: [100%, 0%, 0%, 0%, 0%]

#### Ansiedad Óptima (30-70)
- **Comportamiento**: Distribución probabilística con preferencia por rutas óptimas
- **Con 3 rutas**: [70%, 20%, 10%]
- **Con 5 rutas**: [50%, 20%, 15%, 10%, 5%]
- **Razón**: Balance entre eficiencia y exploración

#### Alta Ansiedad/Pánico (70-100)
- **Comportamiento**: Distribución más uniforme, puede seleccionar rutas subóptimas
- **Con 3 rutas**: [30%, 30%, 40%]
- **Con 5 rutas**: [20%, 20%, 20%, 20%, 20%] (uniforme)
- **Razón**: Agentes en pánico exploran más opciones, incluso subóptimas
- **Ruido adicional**: 10% de probabilidad de añadir ruido a la ruta seleccionada

### Tabla de Distribuciones

| Ansiedad | Rutas Disponibles | Distribución de Probabilidades |
|----------|-------------------|-------------------------------|
| 0-30     | 1                 | [100%]                        |
| 0-30     | 3                 | [100%, 0%, 0%]                |
| 0-30     | 5                 | [100%, 0%, 0%, 0%, 0%]        |
| 30-70    | 1                 | [100%]                        |
| 30-70    | 3                 | [70%, 20%, 10%]               |
| 30-70    | 5                 | [50%, 20%, 15%, 10%, 5%]      |
| 70-100   | 1                 | [100%]                        |
| 70-100   | 3                 | [30%, 30%, 40%]               |
| 70-100   | 5                 | [20%, 20%, 20%, 20%, 20%]     |

---

## Flujo Completo del Sistema

### Diagrama de Flujo Principal

```
┌─────────────────────────────────────────────────────────────┐
│  Agente necesita elegir/actualizar ruta                      │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
        ┌───────────────────────────────┐
        │ ¿Necesita recalcular?        │
        │ (should_recalculate)         │
        └───────┬───────────────────────┘
                │
        ┌───────┴───────┐
        │               │
       SÍ              NO
        │               │
        ▼               ▼
┌───────────────┐  ┌──────────────┐
│ Continuar con │  │ Recalcular   │
│ ruta actual   │  │ ruta          │
└───────────────┘  └──────┬───────┘
                          │
                          ▼
        ┌─────────────────────────────────┐
        │ Calcular rutas desbloqueadas    │
        │ calculate_unlocked_paths()      │
        │ Basado en steps_without_moving   │
        └───────────────┬─────────────────┘
                        │
        ┌───────────────┴───────────────┐
        │                               │
        ▼                               ▼
┌──────────────────┐          ┌──────────────────┐
│ steps < 3: 1 ruta │          │ steps >= 3:     │
│ steps < 5: 3 rutas│          │ steps >= 5:     │
│ steps >= 5: 5 rutas│          │ 5 rutas         │
└────────┬──────────┘          └────────┬─────────┘
         │                              │
         └──────────────┬───────────────┘
                        │
                        ▼
        ┌───────────────────────────────┐
        │ find_progressive_paths()       │
        │ Calcular hasta 5 rutas         │
        │ (usa find_k_paths internamente)│
        └───────────────┬───────────────┘
                        │
                        ▼
        ┌───────────────────────────────┐
        │ Path 1: A* con CACHÉ          │
        │ Paths 2-5: A* con penalizaciones│
        │ (sin caché, dinámico)          │
        └───────────────┬───────────────┘
                        │
                        ▼
        ┌───────────────────────────────┐
        │ select_path_by_anxiety()      │
        │ Considerar solo rutas         │
        │ desbloqueadas                 │
        └───────────────┬───────────────┘
                        │
                        ▼
        ┌───────────────────────────────┐
        │ Guardar ruta seleccionada     │
        │ en current_path                │
        │ Guardar todas en              │
        │ all_calculated_paths           │
        └───────────────────────────────┘
```

### Flujo Detallado: Ejemplo Paso a Paso

#### Escenario: Agente se mueve normalmente → se atasca → desbloquea rutas

**Paso 0: Estado Inicial**
```
Agente en posición (10, 5)
Goal: (0, 6)
steps_without_moving = 0
unlocked_paths_count = 1
```

**Paso 1: Primera elección de ruta**
```
1. needs_recalc = True (no tiene ruta)
2. calculate_unlocked_paths(0) → 1 ruta
3. find_progressive_paths(start, goal, num_paths=5)
   - Calcula 5 rutas pero solo usa 1
   - Path 1 usa caché (si existe)
   - Paths 2-5 se calculan pero no se usan
4. select_path_by_anxiety(k_paths, anxiety=25, num_available_paths=1)
   - Solo considera ruta[0] (óptima)
   - Selecciona ruta[0] (100% probabilidad)
5. current_path = ruta[0]
   all_calculated_paths = [ruta0, ruta1, ruta2, ruta3, ruta4]
```

**Paso 2-4: Agente se mueve normalmente**
```
- Sigue current_path
- steps_without_moving = 0 (se resetea al moverse)
- unlocked_paths_count sigue siendo 1
```

**Paso 5: Agente se atasca**
```
- Intenta moverse pero hay bloqueo
- steps_without_moving = 1
- ansiedad aumenta ligeramente
```

**Paso 6-7: Más bloqueos**
```
- steps_without_moving = 2, luego 3
- ansiedad sigue aumentando
```

**Paso 8: Recalcular (steps_without_moving = 3)**
```
1. needs_recalc = True (steps_without_moving >= 3)
2. calculate_unlocked_paths(3) → 3 rutas
3. find_progressive_paths(start, goal, num_paths=5)
   - Reutiliza rutas ya calculadas si es posible
   - O recalcula si la posición cambió
4. select_path_by_anxiety(k_paths, anxiety=45, num_available_paths=3)
   - Considera solo [ruta0, ruta1, ruta2]
   - Distribución: [70%, 20%, 10%]
   - Probablemente selecciona ruta0, pero puede seleccionar ruta1 o ruta2
5. current_path = ruta seleccionada
   unlocked_paths_count = 3
```

**Paso 9-10: Más bloqueos**
```
- steps_without_moving = 4, luego 5
- ansiedad alta (70+)
```

**Paso 11: Recalcular (steps_without_moving = 5)**
```
1. needs_recalc = True
2. calculate_unlocked_paths(5) → 5 rutas
3. find_progressive_paths(start, goal, num_paths=5)
   - Todas las rutas ya están calculadas
   - Puede reutilizar o recalcular según posición
4. select_path_by_anxiety(k_paths, anxiety=85, num_available_paths=5)
   - Considera todas las rutas [ruta0, ruta1, ruta2, ruta3, ruta4]
   - Distribución uniforme: [20%, 20%, 20%, 20%, 20%]
   - Puede seleccionar cualquier ruta
   - 10% probabilidad de añadir ruido
5. current_path = ruta seleccionada (posiblemente subóptima)
   unlocked_paths_count = 5
```

---

## Ejemplos Prácticos

### Ejemplo 1: Agente que nunca se atasca

```
Timeline:
Paso 0: steps=0 → unlocked=1 → calcula 5, usa 1 → selecciona ruta óptima
Paso 1: steps=0 → unlocked=1 → continúa con ruta actual
Paso 2: steps=0 → unlocked=1 → continúa con ruta actual
...
Paso 10: Evacua exitosamente

Resultado:
- Solo calculó rutas una vez (en paso 0)
- Siempre usó ruta óptima
- Eficiencia máxima
```

### Ejemplo 2: Agente que se atasca moderadamente

```
Timeline:
Paso 0: steps=0 → unlocked=1 → calcula 5, usa 1
Paso 1-2: Se mueve normalmente
Paso 3-5: Se atasca (steps=1,2,3)
Paso 6: steps=3 → unlocked=3 → recalcula → usa 3 rutas
Paso 7: Se mueve exitosamente → steps=0
Paso 8-15: Continúa con ruta actual
Paso 16: Evacua

Resultado:
- Calculó rutas 2 veces
- Desbloqueó 3 rutas una vez
- Encontró alternativa exitosa
```

### Ejemplo 3: Agente severamente atascado

```
Timeline:
Paso 0: steps=0 → unlocked=1 → calcula 5, usa 1
Paso 1-4: Se atasca progresivamente (steps=1,2,3,4)
Paso 5: steps=4 → unlocked=3 → recalcula → usa 3 rutas
Paso 6-8: Sigue atascado (steps=5,6,7)
Paso 9: steps=7 → unlocked=5 → recalcula → usa 5 rutas
Paso 10: Selecciona ruta subóptima pero viable
Paso 11-20: Sigue ruta alternativa
Paso 21: Evacua

Resultado:
- Calculó rutas 3 veces
- Progresó: 1 → 3 → 5 rutas
- Usó ruta subóptima pero efectiva
```

### Ejemplo 4: Múltiples agentes con mismo origen/destino

```
Escenario: 5 agentes en (10,5), todos van a (0,6)

Agente 1 (Paso 0):
- Calcula rutas: Path 1 usa CACHÉ (primera vez, no hay caché)
- Guarda en caché: {(10,5), (0,6)} → ruta_optima

Agente 2 (Paso 0):
- Calcula rutas: Path 1 usa CACHÉ → HIT! ✅
- Reutiliza ruta_optima del caché
- Paths 2-5 se calculan sin caché (penalizaciones)

Agente 3 (Paso 0):
- Path 1: CACHÉ HIT ✅
- Paths 2-5: Sin caché

Resultado:
- Cache hit rate: 80% (4 de 5 agentes reutilizaron Path 1)
- Ahorro computacional significativo
```

---

## Optimizaciones y Consideraciones

### Optimización 1: Caché Selectivo

**Problema**: Paths 2-5 no pueden usar caché porque dependen de penalizaciones dinámicas.

**Solución actual**: Solo Path 1 usa caché.

**Alternativa futura**: Implementar caché de rutas alternativas con claves que incluyan penalizaciones:
```python
cache_key = (start, goal, tuple(sorted(penalty_costs.items())))
```

### Optimización 2: Pre-cálculo de Rutas

**Estrategia actual**: Calcular 5 rutas siempre, usar solo las desbloqueadas.

**Ventajas**:
- Preparación para futuros desbloqueos
- Evita recalculaciones cuando `steps_without_moving` aumenta

**Desventajas**:
- Cálculo inicial más costoso
- Puede calcular rutas que nunca se usarán

**Alternativa**: Calcular solo las rutas necesarias:
```python
# Calcular solo las rutas desbloqueadas
num_to_calculate = unlocked_paths_count
all_paths = find_progressive_paths(start, goal, num_paths=num_to_calculate)
```

**Trade-off**: Menos cálculo inicial vs. más recalculaciones futuras.

### Optimización 3: Invalidación Inteligente del Caché

**Problema actual**: El caché nunca se invalida automáticamente.

**Escenarios donde debería invalidarse**:
- Obstáculos dinámicos (futuro)
- Cambios en el floor_field
- Después de N pasos de simulación

**Implementación sugerida**:
```python
def invalidate_cache_if_needed(self, simulation_step: int, max_cache_age: int = 100):
    """
    Invalida el caché si es muy antiguo.
    """
    if simulation_step % max_cache_age == 0:
        self.path_cache.clear()
        self.logger.info(f"Cache invalidated at step {simulation_step}")
```

### Consideración 4: Memoria del Caché

**Tamaño típico del caché**:
- Número de pares (start, goal) únicos
- En una simulación con 10 agentes y 2 puertas: ~20 entradas
- Cada entrada: ~10-20 tuplas (dependiendo de la distancia)
- Memoria total: ~1-5 KB (insignificante)

**Límite recomendado**: No necesario para simulaciones pequeñas/medianas.

### Consideración 5: Thread Safety (Futuro)

Si se implementa paralelización:
- El caché debe ser thread-safe
- Usar `threading.Lock()` o estructuras thread-safe
- Considerar cachés separados por thread con sincronización periódica

---

## Métricas y Estadísticas

### Estadísticas del Sistema

```python
# En PathSelector
self.stats = {
    'calls': 0,                              # Total de llamadas
    'cache_hits': 0,                        # Aciertos del caché
    'paths_unlocked_by_level': {            # Desbloqueos por nivel
        1: 0,   # Veces que se desbloqueó 1 ruta
        3: 0,   # Veces que se desbloqueó 3 rutas
        5: 0    # Veces que se desbloqueó 5 rutas
    },
    'recalculations_by_anxiety': {           # Recalculaciones por ansiedad
        'low': 0,      # Ansiedad 0-30
        'medium': 0,   # Ansiedad 30-70
        'high': 0      # Ansiedad 70-100
    }
}
```

### Métricas Clave

1. **Tasa de aciertos del caché**: `cache_hits / calls`
   - Ideal: >50% en simulaciones con múltiples agentes
   - Indica eficiencia del sistema de caché

2. **Distribución de desbloqueos**: `paths_unlocked_by_level`
   - Muestra cuántas veces se desbloquearon 1, 3, o 5 rutas
   - Útil para entender el comportamiento de los agentes

3. **Recalculaciones por ansiedad**: `recalculations_by_anxiety`
   - Muestra si los agentes con alta ansiedad recalculan más
   - Puede indicar problemas de congestión

---

## Resumen Ejecutivo

### Puntos Clave

1. **Desbloqueo Progresivo**:
   - Comienza con 1 ruta (eficiente)
   - Desbloquea 3 rutas cuando está atascado (balance)
   - Desbloquea 5 rutas cuando está severamente atascado (flexibilidad)

2. **Caché de Rutas**:
   - Almacena rutas óptimas para reutilización
   - Solo Path 1 usa caché (paths alternativas son dinámicas)
   - Mejora significativamente el rendimiento

3. **Integración**:
   - Ambos sistemas trabajan juntos
   - El desbloqueo determina cuántas rutas usar
   - El caché optimiza el cálculo de rutas

4. **Selección por Ansiedad**:
   - Agentes tranquilos: siempre ruta óptima
   - Agentes preocupados: distribución probabilística
   - Agentes en pánico: distribución uniforme, puede usar rutas subóptimas

### Ventajas del Sistema

✅ **Eficiencia**: Reduce cálculos innecesarios
✅ **Adaptabilidad**: Se ajusta a la situación del agente
✅ **Rendimiento**: Caché mejora velocidad significativamente
✅ **Flexibilidad**: Permite exploración cuando es necesario
✅ **Escalabilidad**: Funciona bien con muchos agentes

### Áreas de Mejora Futura

🔮 **Caché de rutas alternativas**: Incluir penalizaciones en claves
🔮 **Invalidación automática**: Limpiar caché periódicamente
🔮 **Pre-cálculo adaptativo**: Calcular solo rutas necesarias
🔮 **Análisis predictivo**: Predecir bloqueos antes de que ocurran

---

## Referencias de Código

- **PathSelector**: `simulacion/nodos/path_selector.py`
  - `calculate_unlocked_paths()`: Línea 1302
  - `find_progressive_paths()`: Línea ~1250
  - `find_k_paths()`: Línea 454
  - `encontrar_ruta_a_star()`: Línea ~300
  - `select_path_by_anxiety()`: Línea ~1180

- **AgentExtendido**: `simulacion/agent_extendido.py`
  - `elegir_ruta()`: Línea ~190
  - Atributos de desbloqueo: Líneas 68-82

- **Visualización**: `simulacion/nodos/visualizar_animacion_rutas.py`
  - `_update_plot()`: Visualiza rutas desbloqueadas
  - `_simular()`: Simula con desbloqueo progresivo

---

*Documento generado para explicar el sistema de desbloqueo progresivo y caché de rutas del simulador de evacuación.*


