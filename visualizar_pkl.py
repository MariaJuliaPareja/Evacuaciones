"""
Script rápido para visualizar archivos PKL de simulación.
Uso: python visualizar_pkl.py [archivo.pkl] [modo]
"""

import sys
import os
from pathlib import Path

# Add simulacion to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from simulacion.grilla.visualizador import VisualizadorSimulacion

def main():
    """Visualizar archivo PKL."""
    
    # Buscar archivos PKL disponibles
    datos_dir = Path("datos")
    pkl_files = list(datos_dir.glob("*.pkl")) if datos_dir.exists() else []
    
    if len(sys.argv) > 1:
        archivo = sys.argv[1]
    elif pkl_files:
        # Usar el más reciente
        archivo = str(max(pkl_files, key=lambda p: p.stat().st_mtime))
        print(f"Usando archivo más reciente: {archivo}")
    else:
        print("ERROR: No se encontraron archivos PKL en 'datos/'")
        print("\nArchivos PKL disponibles:")
        for pkl in pkl_files:
            print(f"  - {pkl}")
        print("\nUso: python visualizar_pkl.py <archivo.pkl>")
        return
    
    modo = sys.argv[2] if len(sys.argv) > 2 else 'interactivo'
    
    print("=" * 60)
    print("VISUALIZADOR DE SIMULACIÓN")
    print("=" * 60)
    print(f"Archivo: {archivo}")
    print(f"Modo: {modo}")
    print("=" * 60)
    
    try:
        # Cargar visualizador
        viz = VisualizadorSimulacion(archivo)
        
        # Mostrar resumen
        print("\n[INFO] Resumen de la simulación:")
        viz.mostrar_resumen()
        
        # Ejecutar según modo
        if modo == 'interactivo':
            print("\n[INFO] Abriendo visualización interactiva...")
            print("  - Usa los controles para navegar")
            print("  - Activa 'show_paths' para ver rutas multinivel")
            viz.crear_animacion_interactiva(show_paths=True)
        
        elif modo == 'animacion':
            print("\n[INFO] Creando animación...")
            viz.crear_animacion(show_paths=True, guardar_video=True, 
                              nombre_video='simulacion_con_rutas.mp4')
        
        elif modo == 'graficos':
            print("\n[INFO] Generando gráficos...")
            viz.grafico_evacuacion_temporal(guardar=True)
            viz.grafico_conflictos(guardar=True)
            print("  -> Gráficos guardados")
        
        elif modo == 'completo':
            print("\n[INFO] Ejecutando visualización completa...")
            viz.crear_animacion_interactiva(show_paths=True)
            viz.grafico_evacuacion_temporal(guardar=True)
            viz.grafico_conflictos(guardar=True)
        
        elif modo == 'rutas':
            print("\n[INFO] Visualizando rutas multinivel...")
            # Visualizar varios pasos
            for paso in [0, 5, 10, 15, 20]:
                if paso < len(viz.historial_agentes):
                    viz.visualizar_rutas_multinivel(
                        paso_idx=paso, 
                        show_legend=True
                    )
                    print(f"  -> Paso {paso} guardado")
        
        else:
            print(f"\nERROR: Modo '{modo}' no reconocido")
            print("Modos válidos: interactivo, animacion, graficos, completo, rutas")
    
    except Exception as e:
        print(f"\nERROR al cargar/visualizar: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()


