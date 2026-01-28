# Comandos para Ejecutar Casos de Prueba de Rutas

Este documento explica cómo usar `visualizar_animacion_rutas.py` para ejecutar diferentes casos de prueba que demuestran la lógica de `agent_extendido.py`.

## Uso Básico

```bash
# Ejecutar con menú interactivo
python simulacion/nodos/visualizar_animacion_rutas.py

# Ejecutar caso específico directamente
python simulacion/nodos/visualizar_animacion_rutas.py 1
python simulacion/nodos/visualizar_animacion_rutas.py 2
python simulacion/nodos/visualizar_animacion_rutas.py 3
python simulacion/nodos/visualizar_animacion_rutas.py 4
python simulacion/nodos/visualizar_animacion_rutas.py 5  # Todos los casos
```

## Correcciones Implementadas

### ✅ Problema de Agentes Estancados
- **Corregido**: Los agentes ahora se crean solo en posiciones válidas con caminos hacia las puertas
- **Validación**: Se verifica que las posiciones tengan valores válidos en el floor_field (< 500)
- **Vecinos**: Se asegura que cada posición tenga al menos un vecino válido
- **Priorización**: Se prefieren posiciones lejos de las puertas para que tengan que moverse

### ✅ Estadísticas de Desbloqueo y Ansiedad
- **Contadores**: Se registran las veces que se desbloquean 3 y 5 rutas
- **Historial**: Se guarda la ansiedad promedio por paso
- **Visualización**: Gráficos en tiempo real muestran la evolución

## Casos de Prueba Disponibles

### Caso 1: Desbloqueo Progresivo de Rutas

**Comando:**
```bash
python simulacion/nodos/visualizar_animacion_rutas.py 1
```

**Descripción:**
- Demuestra cómo los agentes desbloquean más rutas cuando se atascan
- **0-2 pasos atascado**: 1 ruta (ruta óptima)
- **3-4 pasos atascado**: 3 rutas desbloqueadas
- **5+ pasos atascado**: 5 rutas desbloqueadas

**Qué observar:**
- Etiquetas "1P", "3P", "5P" en los agentes muestran cuántas rutas tienen desbloqueadas
- Las rutas alternativas aparecen con transparencia reducida
- La ruta actual se muestra con línea sólida y mayor opacidad

### Caso 2: Selección por Ansiedad

**Comando:**
```bash
python simulacion/nodos/visualizar_animacion_rutas.py 2
```

**Descripción:**
- Muestra cómo diferentes niveles de ansiedad afectan la selección de rutas
- **Baja ansiedad (0-30)**: Prefiere ruta óptima (verde)
- **Ansiedad óptima (30-70)**: Balance entre rutas (amarillo)
- **Alta ansiedad (70-100)**: Más variabilidad, puede elegir rutas subóptimas (rojo)

**Qué observar:**
- Colores de rutas según ansiedad del agente
- Agentes con alta ansiedad pueden elegir rutas más largas
- La distribución de selección de rutas varía según ansiedad

### Caso 3: Bloqueos y Recalculación

**Comando:**
```bash
python simulacion/nodos/visualizar_animacion_rutas.py 3
```

**Descripción:**
- Escenario con muchos agentes para generar bloqueos frecuentes
- Los agentes se bloquean entre sí
- Se activa recalculación automática cuando detectan bloqueos
- Se desbloquean más rutas progresivamente cuando están atascados

**Qué observar:**
- Asteriscos rojos (*) indican cuando un agente recalcula su ruta
- Los agentes cambian de ruta cuando detectan bloqueos
- El número de rutas desbloqueadas aumenta con el tiempo atascado

### Caso 4: Rápidos vs Lentos

**Comando:**
```bash
python simulacion/nodos/visualizar_animacion_rutas.py 4
```

**Descripción:**
- Comparación de comportamiento entre agentes rápidos y lentos
- **Agentes rápidos**: Prioridad en conflictos, color verde claro
- **Agentes lentos**: Pueden quedar atascados más tiempo, color coral claro
- Diferentes estrategias de desbloqueo según tipo

**Qué observar:**
- Los agentes rápidos (verde claro) ganan más conflictos
- Los agentes lentos (coral claro) pueden acumular más ansiedad
- Diferentes patrones de desbloqueo según tipo de agente

### Caso 5: Estadísticas de Desbloqueo y Ansiedad

**Comando:**
```bash
python simulacion/nodos/visualizar_animacion_rutas.py 5
```

**Descripción:**
- Muestra recuento de casos donde se desbloquean 3 rutas
- Muestra recuento de casos donde se desbloquean 5 rutas
- Evolución de la ansiedad promedio en tiempo real
- Gráficos de estadísticas en tiempo real

**Qué observar:**
- **Gráfico superior derecho**: Número de agentes con 3 y 5 rutas desbloqueadas por paso
- **Gráfico inferior derecho**: Ansiedad promedio a lo largo del tiempo
- **Panel de información**: Contadores totales de desbloqueos (3P y 5P)
- Los agentes ahora se crean en posiciones válidas y no se quedan estancados

### Caso 6: Ansiedad Creciente

**Comando:**
```bash
python simulacion/nodos/visualizar_animacion_rutas.py 6
```

**Descripción:**
- Demuestra cómo la ansiedad aumenta cuando los agentes se atascan
- Relación entre pasos sin moverse y ansiedad
- Desbloqueo progresivo basado en ansiedad acumulada

**Qué observar:**
- Los agentes empiezan con ansiedad baja (10)
- La ansiedad aumenta cuando están atascados
- Más pasos atascados = más ansiedad = más rutas desbloqueadas

### Caso 7: Todos los Casos

**Comando:**
```bash
python simulacion/nodos/visualizar_animacion_rutas.py 7
```

**Descripción:**
- Ejecuta todos los casos secuencialmente
- Cierra cada ventana para continuar al siguiente caso
- Útil para ver una demostración completa del sistema

## Controles de la Visualización

### Botones
- **Previous**: Retroceder un paso
- **Play/Pause**: Reproducir o pausar la animación
- **Next**: Avanzar un paso

### Sliders
- **Step Slider**: Saltar a cualquier paso de la simulación
- **Speed Slider**: Ajustar velocidad de animación (100-2000 ms por frame)

### Teclado
- **← (Left Arrow)**: Retroceder un paso
- **→ (Right Arrow)**: Avanzar un paso
- **Space**: Reproducir/pausar animación

## Información Mostrada

### En el Gráfico
- **Rutas actuales**: Líneas sólidas con mayor opacidad
- **Rutas alternativas**: Líneas punteadas con menor opacidad
- **Agentes rápidos**: Círculos verde claro
- **Agentes lentos**: Círculos coral claro
- **Etiquetas "XP"**: Número de rutas desbloqueadas (1P, 3P, 5P)
- **Asterisco rojo (*)**: Indica recalculación de ruta

### En el Panel de Información
- **Step**: Paso actual / Total de pasos
- **Active**: Número de agentes activos
- **Avg Anxiety**: Ansiedad promedio de agentes activos
- **Unlocked**: Número de agentes con 3P y 5P desbloqueadas en este paso
- **Total**: Contadores acumulados de veces que se desbloquean 3P y 5P

### En los Gráficos de Estadísticas (Caso 5)
- **Gráfico "Paths Unlocked per Step"**: 
  - Línea naranja: Agentes con 3 rutas desbloqueadas
  - Línea roja: Agentes con 5 rutas desbloqueadas
- **Gráfico "Average Anxiety Over Time"**:
  - Línea púrpura: Ansiedad promedio
  - Línea verde punteada: Umbral de ansiedad baja (30)
  - Línea roja punteada: Umbral de ansiedad alta (70)

## Leyenda de Colores

### Por Ansiedad
- **Verde**: Ansiedad baja (0-30) - Prefiere ruta óptima
- **Amarillo**: Ansiedad óptima (30-70) - Balance entre rutas
- **Rojo**: Ansiedad alta (70-100) - Más variabilidad

### Por Tipo de Agente
- **Verde claro**: Agente rápido (prioridad en conflictos)
- **Coral claro**: Agente lento (puede quedar atascado)

### Por Tipo de Ruta
- **Línea sólida**: Ruta actual que está siguiendo el agente
- **Línea punteada**: Rutas alternativas desbloqueadas

## Ejemplos de Uso

### Ejemplo 1: Ver desbloqueo progresivo
```bash
python simulacion/nodos/visualizar_animacion_rutas.py 1
```
Observa cómo los agentes empiezan con 1 ruta y desbloquean más cuando se atascan.

### Ejemplo 2: Comparar ansiedades
```bash
python simulacion/nodos/visualizar_animacion_rutas.py 2
```
Compara cómo agentes con diferentes ansiedades seleccionan rutas diferentes.

### Ejemplo 3: Ver recalculación en acción
```bash
python simulacion/nodos/visualizar_animacion_rutas.py 3
```
Observa cómo los agentes recalculan rutas cuando detectan bloqueos.

### Ejemplo 4: Ver estadísticas de desbloqueo
```bash
python simulacion/nodos/visualizar_animacion_rutas.py 5
```
Observa gráficos en tiempo real de desbloqueos y ansiedad.

### Ejemplo 5: Ver ansiedad creciente
```bash
python simulacion/nodos/visualizar_animacion_rutas.py 6
```
Observa cómo la ansiedad aumenta cuando los agentes se atascan.

### Ejemplo 6: Demostración completa
```bash
python simulacion/nodos/visualizar_animacion_rutas.py 7
```
Ejecuta todos los casos para ver una demostración completa del sistema.

## Notas Técnicas

- Los agentes usan `calmness_threshold=3` por defecto
- El sistema calcula hasta 5 rutas pero solo usa las desbloqueadas
- La selección de rutas es probabilística basada en ansiedad
- Los agentes aumentan ansiedad cuando están atascados
- Los agentes reducen ansiedad cuando se mueven exitosamente

## Troubleshooting

### Error: "No module named 'simulacion'"
Asegúrate de ejecutar desde el directorio raíz del proyecto:
```bash
cd D:\Practicas_Verano\Codigo
python simulacion/nodos/visualizar_animacion_rutas.py 1
```

### La ventana no aparece
- Verifica que no esté minimizada
- Revisa que matplotlib esté configurado correctamente
- Intenta ejecutar con `python -u` para ver errores

### La animación es muy rápida/lenta
- Usa el slider "Speed" para ajustar la velocidad
- Valores más bajos = más rápido
- Valores más altos = más lento

