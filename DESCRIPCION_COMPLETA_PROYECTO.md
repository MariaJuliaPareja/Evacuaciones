# 📁 Descripción Completa de Archivos y Rutas del Proyecto

## 🎯 Propósito General
Sistema de simulación y visualización de evacuaciones con agentes inteligentes que utilizan algoritmos de pathfinding (A*) y comportamiento basado en ansiedad.

---

## 📂 Estructura de Directorios y Archivos

### 📄 **Raíz del Proyecto**

#### `README.md`
- **Descripción**: Documentación general del proyecto (marcada como desactualizada)
- **Contenido**: 
  - Descripción del sistema de visualización de evacuación
  - Características principales (agentes vivos/menos_vivos, priorización, conflictos)
  - Ejemplos de uso y flujo de trabajo
  - Estructura de datos PKL
  - Guía para modificar el código
- **Uso**: Referencia general del proyecto

#### `COMANDOS_VISUALIZACION.md`
- **Descripción**: Guía completa de comandos para visualizar el sistema de nodos y selección de rutas
- **Contenido**:
  - Comandos para visualizar grafo de nodos
  - Visualización de rutas por ansiedad
  - Visualizador interactivo con animación
  - Tests de integración
  - Resumen del proceso de selección de rutas
- **Uso**: Referencia rápida para comandos de visualización

#### `EXPLICACION_A_STAR_NODOS.md`
- **Descripción**: Documentación técnica detallada del sistema A* y nodos
- **Contenido**:
  - Visión general del sistema
  - Arquitectura (Floor Field → Grafo → A*)
  - Construcción del grafo de nodos
  - Algoritmo A* explicado
  - Funciones principales y flujo de datos
  - Ejemplos paso a paso
- **Uso**: Documentación técnica para entender el sistema de enrutamiento

---

### 📂 `escenarios/` - Configuraciones de Escenarios

#### `__init__.py`
- **Descripción**: Archivo de inicialización del paquete (vacío)
- **Propósito**: Permite importar escenarios como módulo Python

#### `escenario_base.py`
- **Descripción**: Escenario base simple para pruebas
- **Contenido**:
  - Dimensiones: 18x20 celdas
  - 2 puertas en posición (0,9) y (0,10)
  - Sin obstáculos
  - 4 agentes en posiciones predefinidas
- **Uso**: Escenario de referencia y pruebas básicas

#### `avion.py`
- **Descripción**: Simulación de un avión con asientos y pasillos
- **Contenido**:
  - Dimensiones: 9x30 celdas
  - 4 puertas (2 a cada lado)
  - Obstáculos representando asientos en filas impares
  - Configuración realista de un avión comercial
- **Uso**: Simulación de evacuación de avión

#### `sala_de_clases.py`
- **Descripción**: Simulación de una sala de clases con mesas
- **Contenido**:
  - Dimensiones: 12x10 celdas
  - 2 puertas en el lado izquierdo
  - Obstáculos representando mesas/escritorios
  - Múltiples agentes (estudiantes) en posiciones de asientos
- **Uso**: Simulación de evacuación de aula

---

### 📂 `simulacion/` - Motor de Simulación

#### `__init__.py`
- **Descripción**: Archivo de inicialización del paquete (vacío)
- **Propósito**: Permite importar módulos de simulación como paquete

#### `agent_extendido.py` (438 líneas)
- **Descripción**: Clase principal que representa un agente inteligente
- **Funcionalidades**:
  - **Atributos principales**:
    - `id`: Identificador único
    - `pos_x`, `pos_y`: Posición en la grilla
    - `tipo`: 'rapido' o 'lento' (para priorización)
    - `activo`: Si está evacuando o ya evacuó
    - `ansiedad`: Nivel de ansiedad (0-100)
    - `conflictos_totales`, `conflictos_perdidos`: Tracking de colisiones
  - **Navegación**:
    - `floor_field`: Campo de piso para movimiento greedy
    - `path_selector`: Selector de rutas con A*
    - `current_path`: Ruta planificada actual
    - `path_index`: Posición actual en la ruta
    - `alternative_paths`: Rutas alternativas calculadas
  - **Métodos principales**:
    - `proponer_movimiento()`: Propone siguiente movimiento
    - `elegir_ruta()`: Selecciona/calcula ruta con PathSelector
    - `_movimiento_greedy_floor_field()`: Movimiento basado en floor field
    - `_movimiento_con_path_selector()`: Movimiento usando A*
  - **Gestión de instancias**:
    - `instances`: Lista de clase con todos los agentes
    - `history`: Historial de snapshots
    - `stores()`: Guarda estado actual
- **Uso**: Clase base para todos los agentes en la simulación

---

### 📂 `simulacion/grilla/` - Sistema Basado en Grilla

#### `floor_field.py` (62 líneas)
- **Descripción**: Calcula el campo de piso (distancia a puertas) usando BFS
- **Funcionalidades**:
  - `__init__()`: Inicializa con dimensiones, puertas y obstáculos
  - `_calcular_floor_field()`: Algoritmo BFS que propaga distancias
  - **Valores**:
    - Paredes/obstáculos = 500 (inaccesible)
    - Puertas = 0 (destino)
    - Celdas válidas = distancia (ortogonal=1, diagonal=1.5)
  - `valores`: Matriz NumPy con valores de distancia
- **Uso**: Base para navegación greedy de agentes sin PathSelector

#### `dynamics.py` (391 líneas)
- **Descripción**: Motor principal de simulación paso a paso
- **Funcionalidades**:
  - `simular_simple()`: Simulación básica con movimiento oscilatorio manual
  - `simular_evacuacion()`: Simulación completa con floor field y PathSelector
  - `mover_agentes_con_conflictos()`: Mueve agentes resolviendo conflictos
  - Integración con `SimulacionLogger` para guardar datos
  - Manejo de diferentes escenarios (básico, obstáculos, sala)
  - Soporte para PathSelector opcional
- **Uso**: Ejecuta la simulación completa y coordina todos los componentes

#### `funciones.py` (130 líneas)
- **Descripción**: Funciones auxiliares y utilidades
- **Funcionalidades**:
  - `posibles_puertas()`: Genera todas las posiciones posibles de puertas en el borde
  - `generar_combinaciones_puertas()`: Genera combinaciones de k puertas
  - `cargar_escenario()`: Interfaz para seleccionar escenario interactivamente
  - `mostrar_matriz()`: Visualización en terminal de la simulación
  - `guardar_frame()`: Guarda frame como imagen PNG
  - `correr_simulacion()`: Ejecuta simulación sin visualización
- **Uso**: Utilidades compartidas por diferentes módulos

#### `simulacion_logger.py` (269 líneas)
- **Descripción**: Sistema de logging y persistencia de datos de simulación
- **Clases y Dataclasses**:
  - `EstadoAgente`: Representa estado de un agente (id, x, y, activo, tipo, conflictos, ansiedad)
  - `EstadisticasPaso`: Estadísticas agregadas por paso (vivos activos/evacuados, conflictos)
  - `SimulacionLogger`: Clase principal de logging
- **Funcionalidades**:
  - `registrar_paso()`: Registra estado completo de un paso
  - `log_path_selector_stats()`: Registra estadísticas del PathSelector
  - `guardar_pkl()`: Exporta todos los datos a archivo PKL
  - `obtener_resumen()`: Retorna resumen de la simulación
- **Estructura de datos guardada**:
  - `configuracion`: Dimensiones, puertas, obstáculos
  - `historial_agentes`: Lista de estados por paso
  - `historial_estadisticas`: Estadísticas por paso
  - `path_selector_stats`: Estadísticas de PathSelector (opcional)
- **Uso**: Registra y guarda datos para análisis posterior

#### `visualizador.py` (1034 líneas) ⭐ ARCHIVO PRINCIPAL DE VISUALIZACIÓN
- **Descripción**: Sistema completo de visualización de simulaciones guardadas
- **Clases**:
  - `EstadoAgente`: Dataclass para estado de agente (compatible con logger)
  - `EstadisticasPaso`: Dataclass para estadísticas (compatible con logger)
  - `VisualizadorSimulacion`: Clase principal de visualización
- **Funcionalidades principales**:
  - **Carga de datos**:
    - `__init__()`: Carga archivo PKL y detecta formato automáticamente
    - Soporta múltiples formatos de PKL (legacy y nuevo)
  - **Visualización básica**:
    - `mostrar_resumen()`: Imprime estadísticas en consola
    - `visualizar_paso()`: Muestra un paso específico
  - **Animaciones**:
    - `crear_animacion()`: Crea animación paso a paso (guardable como video)
    - `crear_animacion_interactiva()`: Animación con controles (play/pause, slider)
  - **Gráficos**:
    - `grafico_evacuacion_temporal()`: Gráfico de agentes activos vs evacuados en el tiempo
    - `grafico_conflictos()`: Análisis de conflictos por paso
    - `grafico_ansiedad()`: Distribución y evolución de ansiedad
  - **Rutas**:
    - `visualizar_rutas_agentes()`: Muestra rutas planificadas en un frame
    - Soporte para visualizar `current_path` de agentes
  - **Reportes**:
    - `generar_reporte_completo()`: Genera reporte completo con todos los gráficos
- **Modos de uso**:
  - Línea de comandos: `python visualizador.py archivo.pkl [interactivo|completo]`
  - Desde Python: `viz = VisualizadorSimulacion('archivo.pkl')`
- **Uso**: Visualización y análisis de simulaciones guardadas

#### `pkl/` (subdirectorio)
- **Descripción**: Archivos PKL de ejemplo guardados
- **Archivos**:
  - `historia.pkl`: Simulación básica
  - `historia_obstaculos.pkl`: Simulación con obstáculos
  - `historia_basico.pkl`: Simulación básica alternativa
- **Uso**: Datos de prueba para el visualizador

---

### 📂 `simulacion/nodos/` - Sistema de Enrutamiento con A*

#### `path_selector.py` (1237+ líneas) ⭐ ARCHIVO PRINCIPAL DE PATHFINDING
- **Descripción**: Sistema completo de enrutamiento inteligente con A* y selección por ansiedad
- **Clase principal**: `PathSelector`
- **Funcionalidades principales**:
  - **Construcción del grafo**:
    - `_build_graph_from_floor_field()`: Convierte floor field en grafo NetworkX
    - Cada celda válida = nodo, conexiones adyacentes = aristas
    - Pesos: ortogonal=1.0, diagonal=1.5
  - **Algoritmo A***:
    - `encontrar_ruta_a_star()`: Implementación de A* con heurística euclidiana
    - Caché de rutas para optimización
    - Estadísticas de nodos explorados
  - **Rutas alternativas**:
    - `find_k_paths()`: Encuentra k rutas diferentes (óptima, media, subóptima)
    - Penaliza celdas usadas en rutas anteriores
    - Valida diversidad de rutas (>30% celdas distintas)
  - **Selección por ansiedad**:
    - `select_path_by_anxiety()`: Selecciona ruta según nivel de ansiedad
    - **Baja (0-30)**: Siempre ruta óptima
    - **Óptima (30-70)**: 70% óptima, 20% media, 10% subóptima
    - **Alta (70-100)**: 30% óptima, 30% media, 40% subóptima + posible ruido
  - **Detección de bloqueos**:
    - `should_recalculate()`: Detecta cuándo recalcular ruta
    - Condiciones: bloqueo inmediato (≥2 agentes), estancamiento (≥3 pasos), meta bloqueada
  - **Cálculo de costos**:
    - `get_path_cost()`: Calcula costo de ruta considerando congestión
    - Penaliza celdas con múltiples agentes
  - **Estadísticas**:
    - Tracking de llamadas, cache hits, nodos explorados
    - Recalculaciones por nivel de ansiedad
    - Métricas de rendimiento
- **Uso**: Navegación inteligente para agentes con PathSelector

#### `visualizar_grafo.py` (164 líneas)
- **Descripción**: Visualiza el grafo de nodos construido sobre el floor field
- **Funcionalidades**:
  - `visualizar_grafo_nodos()`: Muestra grafo completo con nodos y aristas
  - `visualizar_ruta_ejemplo()`: Muestra ejemplo de ruta A* calculada
  - Genera imágenes: `grafo_nodos_sobre_grilla.png`, `ruta_a_star_ejemplo.png`
- **Uso**: Visualización del sistema de nodos para debugging y documentación

#### `demo_path_selector.py` (164 líneas)
- **Descripción**: Demo comparativo del sistema PathSelector
- **Funcionalidades**:
  - `simular_evacuacion()`: Simula con/sin PathSelector
  - `comparar_metodos()`: Compara tiempos de evacuación
  - Genera gráficos comparativos: `comparacion_path_selector.png`
- **Uso**: Demostración de mejoras con PathSelector

#### `demo_path_selector_mejorado.py` (232 líneas)
- **Descripción**: Demo completo del sistema de selección de rutas por ansiedad
- **Funcionalidades**:
  - `visualize_paths()`: Visualiza 3 rutas alternativas y la seleccionada
  - `main()`: Demuestra selección para diferentes niveles de ansiedad
  - Genera imágenes:
    - `rutas_ansiedad_baja.png` (ansiedad 0-30)
    - `rutas_ansiedad_media.png` (ansiedad 30-70)
    - `rutas_ansiedad_alta.png` (ansiedad 70-100)
- **Uso**: Demostración visual de selección de rutas por ansiedad

#### `visualizar_animacion_rutas.py` (479 líneas)
- **Descripción**: Visualizador interactivo con animación de rutas
- **Clase**: `VisualizadorAnimacionRutas`
- **Funcionalidades**:
  - `_simular()`: Ejecuta simulación y guarda historial completo
  - `crear_visualizacion_interactiva()`: Crea animación con controles
  - **Controles**:
    - Botones: Anterior, Play/Pause, Siguiente
    - Slider: Saltar a cualquier paso
  - **Visualización**:
    - Muestra agentes moviéndose siguiendo rutas
    - Rutas calculadas (líneas punteadas)
    - Rutas recalculadas (líneas sólidas destacadas)
    - Colores según ansiedad (verde/amarillo/rojo)
    - Indicadores de recalculación
- **Uso**: Visualización interactiva del proceso completo de enrutamiento

#### Archivos PNG generados:
- `grafo_nodos_sobre_grilla.png`: Grafo completo
- `ruta_a_star_ejemplo.png`: Ejemplo de ruta A*
- `rutas_ansiedad_baja.png`: Rutas para ansiedad baja
- `rutas_ansiedad_media.png`: Rutas para ansiedad media
- `rutas_ansiedad_alta.png`: Rutas para ansiedad alta
- `comparacion_path_selector.png`: Comparación con/sin PathSelector

---

### 📂 `datos/` - Datos Guardados

- **Descripción**: Directorio con simulaciones guardadas en formato PKL
- **Archivos**:
  - `simulacion_20260106_140530.pkl`: Simulación guardada con timestamp
  - `demo_simulacion.pkl`: Simulación de demostración
- **Uso**: Datos para análisis y visualización posterior

---

### 📂 `data/` - Recursos Visuales

#### `mapas/`
- **Descripción**: Imágenes de mapas de escenarios
- **Archivos**:
  - `avion.png`: Mapa del avión
  - `sala.png`: Mapa de la sala de clases
  - `sala_optima.png`: Variante de sala
  - `base.png`: Mapa base
  - `raro.png`: Mapa experimental
- **Uso**: Referencias visuales de los escenarios

#### `img/`
- **Descripción**: Frames de videos de visualización guardados
- **Subdirectorios**:
  - `video_cerca/`: Frames de video cercano (frame0.png, frame1.png, etc.)
  - `video_lejos/`: Frames de video lejano (frame0.png hasta frame11.png)
- **Uso**: Frames individuales de animaciones guardadas

#### `grafico_avion.png`
- **Descripción**: Gráfico generado del escenario avión
- **Uso**: Visualización estática de resultados

---

### 📂 `tests/` - Tests

#### `__init__.py`
- **Descripción**: Archivo de inicialización del paquete de tests (vacío)

#### `test_path_selector_integration.py` (295 líneas)
- **Descripción**: Tests de integración para el sistema PathSelector
- **Tests incluidos**:
  1. `test_path_selector_escenario_base()`: Verifica construcción de grafo y A*
  2. `test_k_paths_diferentes()`: Verifica generación de rutas alternativas
  3. `test_seleccion_por_ansiedad()`: Verifica selección basada en ansiedad
  4. `test_agent_usa_path_selector()`: Verifica integración con AgentExtendido
  5. `test_blockage_detection()`: Verifica detección de bloqueos
  6. `test_path_cost_calculation()`: Verifica cálculo de costos
- **Uso**: Ejecutar con `pytest tests/test_path_selector_integration.py -v`

---

### 📂 `demo_reporte/`
- **Descripción**: Directorio para reportes generados (probablemente vacío o con ejemplos)
- **Uso**: Salida de reportes completos generados por el visualizador

---

## 🔄 Flujo de Datos Principal

```
1. ESCENARIO (escenarios/*.py)
   ↓
2. FLOOR FIELD (simulacion/grilla/floor_field.py)
   ↓
3. PATH SELECTOR (simulacion/nodos/path_selector.py)
   - Construye grafo
   - Calcula rutas A*
   ↓
4. AGENTES (simulacion/agent_extendido.py)
   - Usan PathSelector o Floor Field
   - Proponen movimientos
   ↓
5. DYNAMICS (simulacion/grilla/dynamics.py)
   - Ejecuta simulación paso a paso
   - Resuelve conflictos
   ↓
6. LOGGER (simulacion/grilla/simulacion_logger.py)
   - Registra cada paso
   - Guarda en PKL
   ↓
7. VISUALIZADOR (simulacion/grilla/visualizador.py)
   - Carga PKL
   - Genera animaciones y gráficos
```

---

## 📊 Resumen por Categorías

### **Núcleo de Simulación** (Core)
- `simulacion/agent_extendido.py`: Agentes inteligentes
- `simulacion/grilla/dynamics.py`: Motor de simulación
- `simulacion/grilla/floor_field.py`: Campo de piso
- `simulacion/nodos/path_selector.py`: Enrutamiento A*

### **Configuración** (Config)
- `escenarios/*.py`: Escenarios (avión, sala, base)

### **Logging y Persistencia** (Data)
- `simulacion/grilla/simulacion_logger.py`: Sistema de logging
- `datos/*.pkl`: Simulaciones guardadas

### **Visualización** (Visualization)
- `simulacion/grilla/visualizador.py`: Visualizador principal
- `simulacion/nodos/visualizar_*.py`: Visualizadores específicos
- `simulacion/nodos/demo_*.py`: Demos visuales

### **Utilidades** (Utils)
- `simulacion/grilla/funciones.py`: Funciones auxiliares

### **Tests** (Testing)
- `tests/test_path_selector_integration.py`: Tests de integración

### **Documentación** (Docs)
- `README.md`: Documentación general
- `COMANDOS_VISUALIZACION.md`: Guía de comandos
- `EXPLICACION_A_STAR_NODOS.md`: Documentación técnica

---

## 🎯 Archivos Más Importantes

1. **`simulacion/agent_extendido.py`**: Clase base de agentes
2. **`simulacion/nodos/path_selector.py`**: Sistema de enrutamiento inteligente
3. **`simulacion/grilla/visualizador.py`**: Visualización completa
4. **`simulacion/grilla/dynamics.py`**: Motor de simulación
5. **`simulacion/grilla/simulacion_logger.py`**: Persistencia de datos

---

## 📝 Notas Importantes

- El proyecto usa **dos sistemas de navegación**:
  - **Floor Field (greedy)**: Movimiento hacia menor valor
  - **PathSelector (A*)**: Rutas planificadas con recálculo dinámico

- Los agentes tienen **dos tipos**:
  - **'rapido'**: Prioridad en conflictos (verde)
  - **'lento'**: Menor prioridad (rojo)

- El sistema soporta **ansiedad** (0-100) que afecta:
  - Selección de rutas (más ansiedad = rutas más diversas)
  - Posible ruido en movimiento

- Los datos se guardan en **formato PKL** con estructura estándar para compatibilidad con el visualizador.

---

**Última actualización**: Enero 2026
**Desarrollado por**: Miguel Acevedo, Emilia Partarrieu y colaboradores

