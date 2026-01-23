# Sistema de Visualización de Evacuación - Documentación (DESACTUALIZADA)
## Descripción General
Este sistema proporciona una plataforma completa para simular y visualizar evacuaciones con clasificación de agentes. Los agentes se clasifican como "rapidos" (verde) o "lentos" (rojo), con priorización en conflictos. 
## Características Principales
- Escalable y Modular: Código separado en módulos independientes
- Clasificación de Agentes: Sistema rapido (verde) / lento (rojo)
- Priorización en Conflictos: Los "rapidos" tienen prioridad
- Contador de Conflictos: Atributo en cada agente
- Gráfico Temporal: Compara rapidos vs lentos en el tiempo
- Película Paso a Paso: Animación completa de la simulación
- Guardado PKL: Con posición, tipo, ansiedad, conflictos
- Visualizador Separado: No está en el código de compilación
- Visualización gráfica con matplotlib
- Comentarios: Código ampliamente documentado
## Opciones disponibles:
Opción 1: Simulación individual con proporción configurable
Opción 2: Estudio paramétrico (múltiples simulaciones)
## Ejemplo de flujo:
1. Selecciona escenario (avión, sala de clases, etc.)
2. Define proporción de agentes "rapidos" (ej: 0.5 = 50%)
3. El sistema ejecuta y guarda datos en archivo PKL
### Visualizar Resultados
bashpython visualizador.py datos/simulacion_20260106_153045.pkl
O desde Python:
pythonfrom visualizador import VisualizadorSimulacion
#### Cargar datos
viz = VisualizadorSimulacion('datos/simulacion_20260106_153045.pkl')
#### Mostrar resumen estadístico
viz.mostrar_resumen()
#### Crear animación (película paso a paso)
viz.crear_animacion(guardar_video=True, nombre_video='mi_simulacion.mp4')
#### Gráfico de evacuación temporal
viz.grafico_evacuacion_temporal(guardar=True)
#### Análisis de conflictos
viz.grafico_conflictos(guardar=True)
#### Generar reporte completo
viz.generar_reporte_completo(directorio_salida='mi_reporte')
#### Gráfico de Evacuación Temporal
Líneas de agentes activos vs evacuados
Separación por tipo (rapidos/lentos)
Porcentaje de evacuación acumulado
## Estructura de Datos PKL
El archivo PKL contiene:
python{
    'configuracion': {
        'width': int,
        'height': int,
        'puertas': [(x, y), ...],
        'obstaculos': [(x, y), ...]
    },
    'historial_agentes': [
        [EstadoAgente(...), ...],  # Paso 0
        [EstadoAgente(...), ...],  # Paso 1
        ...
    ],
    'historial_estadisticas': [
        EstadisticasPaso(...),  # Paso 0
        EstadisticasPaso(...),  # Paso 1
        ...
    ]
}
EstadoAgente incluye:

id, x, y, activo, tipo, conflictos_totales, conflictos_perdidos, ansiedad

EstadisticasPaso incluye:

paso, rapidos_activos, lentos_activos, rapidos_evacuados, lentos_evacuados, conflictos_en_paso, agentes_en_conflicto

## Guía para Modificar el Código
Para cambiar la lógica de movimiento:
Archivo: simulacion/agentes.py
pythondef proponer_movimiento(self):
    """
    MODIFICAR AQUÍ para cambiar cómo los agentes deciden moverse.
    
    Variables disponibles:
    - self.x, self.y: posición actual
    - self.floor_field.valores: matriz de distancias
    - self.tipo: 'rapido' o 'lento'
    - self.ansiedad: nivel de ansiedad
    """
    # ... tu lógica aquí
Para cambiar la resolución de conflictos:
Archivo: simulacion/agentes.py, función mover_agentes()
python# Busca esta sección:
# SISTEMA DE PRIORIZACIÓN:
# 1. Separar agentes por tipo
rapidos = [a for a in lista_agentes if a.tipo == 'rapido']
lentos = [a for a in lista_agentes if a.tipo == 'lento']

# MODIFICAR AQUÍ para cambiar las reglas de priorización
Para agregar nuevas estadísticas:
Archivo: simulacion_logger.py
python@dataclass
class EstadisticasPaso:
    # AGREGAR nuevos campos aquí
    tu_nueva_estadistica: int
Luego actualiza el método registrar_paso() para calcularla.
## Ejemplos de Uso Avanzado
Estudio Paramétrico Personalizado
pythonfrom main_con_visualizacion import ejecutar_simulacion_con_logging
import numpy as np
import matplotlib.pyplot as plt

# Probar diferentes proporciones
proporciones = np.linspace(0.1, 0.9, 9)
tiempos = []

for prop in proporciones:
    pasos, _ = ejecutar_simulacion_con_logging(
        porcentaje_rapidos=prop,
        mostrar_progreso=False
    )
    tiempos.append(pasos)

# Graficar resultados
plt.figure(figsize=(10, 6))
plt.plot(proporciones * 100, tiempos, 'o-', linewidth=2)
plt.xlabel('Porcentaje de agentes "rapidos" (%)')
plt.ylabel('Tiempo de evacuación (pasos)')
plt.title('Efecto de la proporción de agentes en el tiempo de evacuación')
plt.grid(True, alpha=0.3)
plt.show()
Comparar Múltiples Simulaciones
pythonfrom visualizador import VisualizadorSimulacion
import matplotlib.pyplot as plt

archivos = [
    'datos/simulacion_p0.20_sim1.pkl',
    'datos/simulacion_p0.50_sim1.pkl',
    'datos/simulacion_p0.80_sim1.pkl'
]

fig, axes = plt.subplots(1, 3, figsize=(18, 5))

for i, archivo in enumerate(archivos):
    viz = VisualizadorSimulacion(archivo)
    stats = viz.historial_estadisticas
    
    pasos = [s.paso for s in stats]
    rapidos_evac = [s.rapidos_evacuados for s in stats]
    
    axes[i].plot(pasos, rapidos_evac)
    axes[i].set_title(f'Simulación {i+1}')
    axes[i].set_xlabel('Paso')
    axes[i].set_ylabel('Vivos evacuados')
    axes[i].grid(True, alpha=0.3)

plt.tight_layout()
plt.show()
## Dependencias
bash# Instalar dependencias necesarias
pip install numpy matplotlib pickle5
## Para extender el sistema:
Nuevas métricas: Modificar simulacion_logger.py
Nuevas visualizaciones: Agregar métodos a VisualizadorSimulacion
Nuevos tipos de agentes: Modificar lógica en agentes.py
Nuevos escenarios: Crear archivo en simulacion/escenarios/
Desarrollado por: Miguel Acevedo, Emilia Partarrieu y Sistema de Visualización
Fecha: Enero 2026
Versión: 2.0