
import sys
sys.path.insert(0, '/home/claude')
sys.path.insert(0, '/mnt/project')

print("""
╔═══════════════════════════════════════════════════════════════════╗
║                                                                   ║
║     DEMO: SISTEMA DE VISUALIZACIÓN DE EVACUACIÓN                ║
║                                                                   ║
║     Este script demuestra todas las funcionalidades:            ║
║     1. Ejecutar simulación con clasificación de agentes         ║
║     2. Guardar datos en PKL                                      ║
║     3. Cargar y visualizar resultados                           ║
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝
""")

# ============================================================================
# PASO 1: CREAR UNA SIMULACIÓN SIMPLE DE EJEMPLO
# ============================================================================

print("\n" + "="*70)
print("  PASO 1: Creando simulación de ejemplo...")
print("="*70)

# Crear un escenario simple en memoria
class EscenarioDemo:
    """Escenario de demostración simple: habitación 10x10 con 8 agentes"""
    width = 10
    height = 10
    puertas = [(0, 4), (0, 5)]  # Puerta en la pared izquierda
    obstaculos = [
        (5, 3), (5, 4), (5, 5), (5, 6)  # Obstáculo en el centro
    ]
    agentes = [
        (2, 2), (7, 2),  # Fila superior
        (2, 5), (7, 5),  # Fila media
        (2, 8), (7, 8),  # Fila inferior
        (5, 2), (5, 8)   # Columnas laterales
    ]

# Importar módulos necesarios
from simulacion.floor_field import Floor_field 
from simulacion.agentes import Agente, mover_agentes
from simulacion_logger import SimulacionLogger
import numpy as np

# Crear escenario
esc = EscenarioDemo()
print(f"Escenario demo: {esc.width}x{esc.height} con {len(esc.agentes)} agentes")

# Crear floor field
campo = Floor_field(esc.width, esc.height, esc.puertas, esc.obstaculos)
print("Floor field generado")

# Crear agentes (50% vivos, 50% menos vivos)
num_agentes = len(esc.agentes)
num_vivos = num_agentes // 2
tipos = ['vivo'] * num_vivos + ['menos_vivo'] * (num_agentes - num_vivos)
np.random.shuffle(tipos)

agentes = []
for (x, y), tipo in zip(esc.agentes, tipos):
    agentes.append(Agente(x, y, campo, tipo=tipo))

print(f"Agentes creados: {num_vivos} vivos, {num_agentes - num_vivos} menos vivos")

# Inicializar logger
logger = SimulacionLogger(esc.width, esc.height, esc.puertas, esc.obstaculos)
print("Logger inicializado")

# ============================================================================
# PASO 2: EJECUTAR SIMULACIÓN
# ============================================================================

print("\n" + "="*70)
print("PASO 2: Ejecutando simulación...")
print("="*70)

pasos = 0
print("\nProgreso de evacuación:")
print("-" * 70)

while any(a.activo for a in agentes):
    stats = mover_agentes(agentes)
    logger.registrar_paso(agentes, pasos, stats)
    
    if pasos % 5 == 0:
        activos = sum(a.activo for a in agentes)
        print(f"Paso {pasos:3d}: {activos} agentes activos, "
              f"{stats['conflictos_totales']} conflictos")
    
    pasos += 1
    
    if pasos > 1000:
        print("\nLímite de pasos alcanzado")
        break

print("-" * 70)
print(f"\nSimulación completada en {pasos} pasos")

# ============================================================================
# PASO 3: GUARDAR DATOS
# ============================================================================

print("\n" + "="*70)
print("PASO 3: Guardando datos...")
print("="*70)

nombre_archivo = 'datos/demo_simulacion.pkl'
logger.guardar_pkl(nombre_archivo)

# Mostrar resumen
resumen = logger.obtener_resumen()
print(f"\nResumen:")
print(f"• Pasos totales: {resumen['pasos_totales']}")
print(f"• Vivos evacuados: {resumen['vivos_evacuados']}")
print(f"• Menos vivos evacuados: {resumen['menos_vivos_evacuados']}")
print(f"• Conflictos totales: {resumen['conflictos_totales']}")

# ============================================================================
# PASO 4: VISUALIZAR RESULTADOS
# ============================================================================

print("\n" + "="*70)
print("PASO 4: Generando visualizaciones...")
print("="*70)

from visualizador import VisualizadorSimulacion

# Cargar datos
viz = VisualizadorSimulacion(nombre_archivo)
print(f"Datos cargados desde: {nombre_archivo}")

# Mostrar resumen detallado
print("\n--- Resumen Detallado ---")
viz.mostrar_resumen()

# Preguntar al usuario qué visualizaciones quiere ver
print("\n" + "="*70)
print("  ¿Qué visualizaciones deseas ver?")
print("="*70)
print("\n  1) Animación paso a paso (película)")
print("  2) Gráficos de evacuación temporal")
print("  3) Análisis de conflictos")
print("  4) Todo lo anterior")
print("  5) Generar reporte completo y salir")
print("  0) Salir sin visualizar")

try:
    opcion = input("\nOpción (0-5): ").strip()
    
    if opcion == '1' or opcion == '4':
        print("\nGenerando animación...")
        print("   (Cierra la ventana para continuar)")
        viz.crear_animacion(intervalo=300)
    
    if opcion == '2' or opcion == '4':
        print("\nGenerando gráficos de evacuación...")
        viz.grafico_evacuacion_temporal()
    
    if opcion == '3' or opcion == '4':
        print("\nGenerando análisis de conflictos...")
        viz.grafico_conflictos()
    
    if opcion == '5':
        print("\nGenerando reporte completo...")
        viz.generar_reporte_completo(directorio_salida='demo_reporte')
        print("\nReporte guardado en: demo_reporte/")

except KeyboardInterrupt:
    print("\n\nInterrumpido por el usuario")

# ============================================================================
# FINALIZACIÓN
# ============================================================================

print("\n" + "="*70)
print("  DEMO COMPLETADA")
print("="*70)

print(f"""Se ha generado una simulación de demostración completa.

Archivos generados:
   • Datos: {nombre_archivo}
   • Reportes: demo_reporte/ (si se generó)

Para usar el sistema completo:
   1. Ejecuta: python main_con_visualizacion.py
   2. Visualiza: python visualizador.py <archivo.pkl>

Consulta README.md para documentación completa.

""")

print("="*70 + "\n")