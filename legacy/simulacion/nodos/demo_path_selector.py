# demo_path_selector.py
"""
Demo del sistema de enrutamiento inteligente con A*.
Muestra:
1. Comparación: con/sin path selector
2. Estadísticas de recálculos
3. Reducción de tiempo de evacuación
"""

import sys
sys.path.append('..')

from simulacion.floor_field import Floor_field
from simulacion.agent_extendido import AgentExtendido, mover_agentes_con_conflictos
from simulacion.path_selector import PathSelector
import escenarios.sala_de_clases as escenario
import matplotlib.pyplot as plt
import numpy as np

def simular_evacuacion(usar_path_selector=False, verbose=True):
    """
    Simula evacuación con o sin path selector.
    
    Returns:
    tiempo_evacuacion : int
    estadisticas : dict
    """
    # Setup
    ff = Floor_field(escenario.width, escenario.height, 
                     escenario.puertas, escenario.obstaculos)
    
    # Crear path selector si se solicita
    path_selector = PathSelector(ff, umbral_recalculo=0.6) if usar_path_selector else None
    
    # Crear agentes
    AgentExtendido.instances = []
    AgentExtendido.history = []
    
    # 60% rapidos, 40% lentos
    num_rapidos = int(len(escenario.agentes) * 0.6)
    
    for i, (x, y) in enumerate(escenario.agentes):
        agent_type = 'rapido' if i < num_rapidos else 'lento'
        agente = AgentExtendido(
            agent_type=agent_type,
            floor_field=ff,
            path_selector=path_selector
        )
        agente.pos_x = x
        agente.pos_y = y
    
    AgentExtendido.stores()
    
    # Simular
    paso = 0
    max_pasos = 200
    
    if verbose:
        modo = "CON PathSelector (A*)" if usar_path_selector else "SIN PathSelector (greedy)"
        print(f"\n{'='*60}")
        print(f"SIMULACIÓN {modo}")
        print(f"{'='*60}")
    
    while any(a.activo for a in AgentExtendido.instances) and paso < max_pasos:
        # Actualizar métricas dinámicas
        if path_selector:
            path_selector.actualizar_metricas(AgentExtendido.instances)
            path_selector.actualizar_pesos_grafo()
        
        # Mover agentes
        stats = mover_agentes_con_conflictos(AgentExtendido.instances)
        AgentExtendido.stores()
        
        paso += 1
        
        if verbose and paso % 20 == 0:
            activos = sum(1 for a in AgentExtendido.instances if a.activo)
            print(f"  Paso {paso}: {activos} agentes activos")
    
    # Estadísticas finales
    stats = {
        'tiempo_evacuacion': paso,
        'agentes_totales': len(escenario.agentes),
        'todos_evacuados': not any(a.activo for a in AgentExtendido.instances)
    }
    
    if path_selector:
        stats.update(path_selector.obtener_estadisticas())
    
    if verbose:
        print(f"\nEvacuación completada en {paso} pasos")
        if path_selector:
            print(f"  - Rutas calculadas: {stats['rutas_calculadas']}")
            print(f"  - Recálculos por congestión: {stats['num_recalculos']}")
            print(f"  - Densidad promedio: {stats['densidad_promedio']:.3f}")
    
    return paso, stats

def comparar_metodos(num_simulaciones=10):
    """
    Compara evacuación con/sin path selector.
    """
    print("COMPARACIÓN: PathSelector (A*) vs Floor Field Greedy")    
    tiempos_sin_ps = []
    tiempos_con_ps = []
    
    for i in range(num_simulaciones):
        print(f"\n--- Simulación {i+1}/{num_simulaciones} ---")
        
        # Sin path selector
        t_sin, _ = simular_evacuacion(usar_path_selector=False, verbose=False)
        tiempos_sin_ps.append(t_sin)
        
        # Con path selector
        t_con, _ = simular_evacuacion(usar_path_selector=True, verbose=False)
        tiempos_con_ps.append(t_con)
        
        print(f"Sin PS: {t_sin} pasos | Con PS: {t_con} pasos | Mejora: {t_sin - t_con} pasos")
    
    # Resultados
    print("RESULTADOS")
    promedio_sin = np.mean(tiempos_sin_ps)
    promedio_con = np.mean(tiempos_con_ps)
    mejora = promedio_sin - promedio_con
    mejora_pct = (mejora / promedio_sin) * 100
    
    print(f"Promedio SIN PathSelector:  {promedio_sin:.1f} ± {np.std(tiempos_sin_ps):.1f} pasos")
    print(f"Promedio CON PathSelector:  {promedio_con:.1f} ± {np.std(tiempos_con_ps):.1f} pasos")
    print(f"\nMEJORA: {mejora:.1f} pasos ({mejora_pct:.1f}%)")
    
    # Visualizar
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    
    # Gráfico 1: Comparación por simulación
    x = np.arange(num_simulaciones)
    ax1.plot(x, tiempos_sin_ps, 'o-', label='Sin PathSelector', color='red', alpha=0.7)
    ax1.plot(x, tiempos_con_ps, 's-', label='Con PathSelector (A*)', color='green', alpha=0.7)
    ax1.set_xlabel('Simulación')
    ax1.set_ylabel('Tiempo de Evacuación (pasos)')
    ax1.set_title('Comparación Individual')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # Gráfico 2: Box plot
    ax2.boxplot([tiempos_sin_ps, tiempos_con_ps], 
                labels=['Sin PS', 'Con PS (A*)'])
    ax2.set_ylabel('Tiempo de Evacuación (pasos)')
    ax2.set_title('Distribución de Tiempos')
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('comparacion_path_selector.png', dpi=150)
    print(f"\nGráfico guardado: comparacion_path_selector.png")
    plt.show()

if __name__ == "__main__":
    # Demo simple
    print("DEMO: Sistema de Enrutamiento Inteligente con A*")
    
    # Simulación individual con detalles
    tiempo, stats = simular_evacuacion(usar_path_selector=True, verbose=True)
    
    # Comparación múltiple
    comparar_metodos(num_simulaciones=5)
