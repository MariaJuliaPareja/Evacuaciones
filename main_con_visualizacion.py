
"""
Este main ejecuta simulaciones de evacuación con el nuevo sistema de
clasificación de agentes (vivos/menos_vivos) y guarda todos los datos
para posterior visualización.

CARACTERÍSTICAS:
- Clasifica agentes como 'vivos' o 'menos_vivos'
- Registra todos los datos en cada paso
- Guarda archivo PKL para visualización posterior
- Prioriza agentes 'vivos' en conflictos
- Rastrea conflictos por agente

"""

import sys
import os
import numpy as np
from pathlib import Path

# Agregar el directorio del proyecto al path
sys.path.insert(0, '/mnt/project')
sys.path.insert(0, '/home/claude')

from simulacion.floor_field import Floor_field 
from simulacion.agentes import Agente, mover_agentes
from simulacion.funciones import cargar_escenario
from simulacion_logger import SimulacionLogger


def ejecutar_simulacion_con_logging(
    porcentaje_vivos: float = 0.5, # SE PUEDE CAMBIAR LA PROPORCION DE AGENTES VIVOS
    nombre_salida: str = None,
    mostrar_progreso: bool = True
):
    """
    Ejecuta una simulación completa con registro de datos.
    
    Esta función:
    1. Carga el escenario seleccionado por el usuario
    2. Crea agentes clasificados como 'vivos' o 'menos_vivos'
    3. Ejecuta la simulación registrando cada paso
    4. Guarda todos los datos en un archivo PKL
    
    Parámetros:
    porcentaje_vivos : float, optional (default=0.5)
        Proporción de agentes que serán clasificados como 'vivos'
        El resto serán 'menos_vivos'
        Valor entre 0.0 y 1.0
    nombre_salida : str, optional (default=None)
        Nombre del archivo PKL de salida
        Si es None, se genera automáticamente
    mostrar_progreso : bool, optional (default=True)
        Si True, muestra información durante la simulación
    
    Retorna:
    tuple : (pasos_totales, nombre_archivo_pkl)
        - pasos_totales: número de pasos que tomó la evacuación
        - nombre_archivo_pkl: ruta del archivo guardado
    """
    print("\n" + "="*70)
    print("SIMULACIÓN DE EVACUACIÓN CON SISTEMA DE CLASIFICACIÓN")
    print("="*70 + "\n")
    
    # 1. CARGAR ESCENARIO
    print("Paso 1: Selección de escenario")
    esc = cargar_escenario()
    
    # 2. CREAR FLOOR FIELD
    print("\nPaso 2: Generando campo de piso (floor field)...")
    campo = Floor_field(esc.width, esc.height, esc.puertas, esc.obstaculos)
    print("Floor field generado")
    
    # 3. CREAR AGENTES CON CLASIFICACIÓN
    print(f"\nPaso 3: Creando agentes (proporción vivos: {porcentaje_vivos*100:.0f}%)...")
    
    agentes = []
    total_agentes = len(esc.agentes)
    num_vivos = int(total_agentes * porcentaje_vivos)
    
    # Asignar tipos aleatoriamente
    tipos = ['vivo'] * num_vivos + ['menos_vivo'] * (total_agentes - num_vivos)
    np.random.shuffle(tipos)
    
    for idx, ((x, y), tipo) in enumerate(zip(esc.agentes, tipos)):
        agente = Agente(x, y, campo, tipo=tipo)
        agentes.append(agente)
    
    print(f"Creados {len(agentes)} agentes:")
    print(f"  • Vivos: {num_vivos} ({num_vivos/total_agentes*100:.1f}%)")
    print(f"  • Menos vivos: {total_agentes - num_vivos} ({(1-porcentaje_vivos)*100:.1f}%)")
    
    # 4. INICIALIZAR LOGGER
    print("\n📝Pas4: Inicializando sistema de registro...")
    logger = SimulacionLogger(
        width=esc.width,
        height=esc.height,
        puertas=esc.puertas,
        obstaculos=esc.obstaculos
    )
    print("Logger inicializado")
    
    # 5. EJECUTAR SIMULACIÓN
    print("\nPaso 4: Ejecutando simulación...")
    print("-" * 70)
    
    pasos = 0
    agentes_activos_inicial = sum(a.activo for a in agentes)
    
    while any(a.activo for a in agentes):
        # Mover agentes y obtener estadísticas del movimiento
        stats_movimiento = mover_agentes(agentes)
        
        # Registrar el estado actual
        logger.registrar_paso(agentes, pasos, stats_movimiento)
        
        # Mostrar progreso cada 10 pasos
        if mostrar_progreso and pasos % 10 == 0:
            activos = sum(a.activo for a in agentes)
            evacuados = agentes_activos_inicial - activos
            progreso = (evacuados / agentes_activos_inicial) * 100
            print(f"  Paso {pasos:4d} | Activos: {activos:3d} | "
                  f"Evacuados: {evacuados:3d} | Progreso: {progreso:5.1f}%")
        
        pasos += 1
        
        # Límite de seguridad para evitar loops infinitos
        if pasos > 10000:
            print("\nADVERTENCIA: Se alcanzó el límite de pasos (10000)")
            break
    
    print("-" * 70)
    print(f"\nSimulación completada en {pasos} pasos")
    
    # 6. GUARDAR DATOS
    print("\nPaso 6: Guardando datos...")
    
    if nombre_salida is None:
        # Generar nombre automático con timestamp
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nombre_salida = f"datos/simulacion_{timestamp}.pkl"
    
    logger.guardar_pkl(nombre_salida)
    
    # 7. MOSTRAR RESUMEN
    print("\n" + "="*70)
    print("  RESUMEN DE LA SIMULACIÓN")
    print("="*70)
    resumen = logger.obtener_resumen()
    print(f"\nTiempo de evacuación: {resumen['pasos_totales']} pasos")
    print(f"Agentes evacuados:")
    print(f"• Vivos: {resumen['vivos_evacuados']}")
    print(f"• Menos vivos: {resumen['menos_vivos_evacuados']}")
    print(f"Conflictos totales: {resumen['conflictos_totales']}")
    print(f"• Promedio por paso: {resumen['conflictos_totales']/resumen['pasos_totales']:.2f}")
    
    print("\n" + "="*70)
    print(f"\nPara visualizar los resultados, ejecuta:")
    print(f"python visualizador.py {nombre_salida}")
    print("\n" + "="*70 + "\n")
    
    return pasos, nombre_salida


def ejecutar_multiples_simulaciones(
    num_simulaciones: int = 5,
    proporciones_vivos: list = None
):
    """
    Ejecuta múltiples simulaciones con diferentes proporciones de agentes.
    Útil para estudiar el efecto de la proporción de agentes 'vivos'
    en el tiempo de evacuación y el número de conflictos.  
    Parámetros:
    num_simulaciones : int, optional (default=5)
        Número de simulaciones a ejecutar por cada proporción
    proporciones_vivos : list, optional (default=None)
        Lista de proporciones a probar
        Si es None, usa [0.2, 0.4, 0.5, 0.6, 0.8]
    
    Retorna:
    dict : Resultados de todas las simulaciones
    """
    if proporciones_vivos is None:
        proporciones_vivos = [0.2, 0.4, 0.5, 0.6, 0.8]
    
    resultados = {
        'proporciones': [],
        'tiempos_promedio': [],
        'tiempos_std': [],
        'archivos': []
    }
    
    print("\n" + "="*70)
    print("ESTUDIO PARAMÉTRICO: EFECTO DE LA PROPORCIÓN DE AGENTES VIVOS")
    print("="*70 + "\n")
    
    for proporcion in proporciones_vivos:
        print(f"\n{'='*70}")
        print(f"Proporción de vivos: {proporcion*100:.0f}%")
        print(f"{'='*70}")
        
        tiempos = []
        archivos = []
        
        for i in range(num_simulaciones):
            print(f"\nSimulación {i+1}/{num_simulaciones}")
            
            nombre = f"datos/parametrico_p{proporcion:.2f}_sim{i+1}.pkl"
            pasos, archivo = ejecutar_simulacion_con_logging(
                porcentaje_vivos=proporcion,
                nombre_salida=nombre,
                mostrar_progreso=False
            )
            
            tiempos.append(pasos)
            archivos.append(archivo)
        
        # Estadísticas
        tiempo_promedio = np.mean(tiempos)
        tiempo_std = np.std(tiempos)
        
        resultados['proporciones'].append(proporcion)
        resultados['tiempos_promedio'].append(tiempo_promedio)
        resultados['tiempos_std'].append(tiempo_std)
        resultados['archivos'].extend(archivos)
        
        print(f"\nResultados para proporción {proporcion*100:.0f}%:")
        print(f"• Tiempo promedio: {tiempo_promedio:.1f} ± {tiempo_std:.1f} pasos")
        print(f"• Tiempos: {tiempos}")
    
    # Resumen final
    print("\n" + "="*70)
    print("RESUMEN DEL ESTUDIO PARAMÉTRICO")
    print("="*70 + "\n")
    
    for prop, tiempo, std in zip(resultados['proporciones'],
                                  resultados['tiempos_promedio'],
                                  resultados['tiempos_std']):
        print(f"  {prop*100:4.0f}% vivos: {tiempo:6.1f} ± {std:4.1f} pasos")
    
    # Encontrar la mejor proporción
    idx_mejor = np.argmin(resultados['tiempos_promedio'])
    mejor_prop = resultados['proporciones'][idx_mejor]
    mejor_tiempo = resultados['tiempos_promedio'][idx_mejor]
    
    print(f"\nMejor proporción: {mejor_prop*100:.0f}% vivos")
    print(f"Tiempo de evacuación: {mejor_tiempo:.1f} pasos")
    
    print("\n" + "="*70 + "\n")
    
    return resultados


if __name__ == "__main__":
    print("\nSIMULADOR DE EVACUACIÓN CON VISUALIZACIÓN\n")
    print("Selecciona el modo de ejecución:")
    print("1) Simulación individual")
    print("2) Estudio paramétrico (múltiples simulaciones)")
    print("3) Salir")
    
    opcion = input("\nOpción (1-3): ").strip()
    
    if opcion == '1':
        print("\n--- Modo: Simulación Individual ---")
        prop = input("Proporción de agentes 'vivos' (0.0-1.0) [default=0.5]: ").strip()
        
        try:
            prop = float(prop) if prop else 0.5
            prop = max(0.0, min(1.0, prop))  # Limitar entre 0 y 1
        except ValueError:
            prop = 0.5
            print(f"Valor inválido, usando default: {prop}")
        
        pasos, archivo = ejecutar_simulacion_con_logging(porcentaje_vivos=prop)
        
    elif opcion == '2':
        print("\n--- Modo: Estudio Paramétrico ---")
        num = input("Número de simulaciones por proporción [default=3]: ").strip()
        
        try:
            num = int(num) if num else 3
        except ValueError:
            num = 3
            print(f"Valor inválido, usando default: {num}")
        
        resultados = ejecutar_multiples_simulaciones(num_simulaciones=num)
        
    else:
        print("\n¡Hasta luego!")