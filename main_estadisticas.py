# main_estadisticas.py, por Miguel Acevedo y Emilia Partarrieu
from simulacion.floor_field import Floor_field 
from simulacion.agentes import Agente, mover_agentes
from simulacion.funciones import *
import matplotlib.pyplot as plt
import numpy as np

def ejecutar_una_simulacion(esc):
    """Ejecuta una sola vez y retorna las listas de conteo"""
    campo = Floor_field(esc.width, esc.height, esc.puertas, esc.obstaculos)
    agentes = [Agente(x, y, campo, velocidad=v) for (x, y, v) in esc.agentes]
    
    v_max = max(a.velocidad for a in agentes)
    v_min = min(a.velocidad for a in agentes)

    conteo_r = []
    conteo_l = []
    
    paso = 0
    while any(a.activo for a in agentes):
        activos_r = sum(1 for a in agentes if a.activo and a.velocidad == v_max)
        activos_l = sum(1 for a in agentes if a.activo and a.velocidad == v_min)
        
        conteo_r.append(activos_r)
        conteo_l.append(activos_l)
        
        mover_agentes(agentes)
        paso += 1
        if paso > 5000: break 

    return conteo_r, conteo_l, v_max, v_min

def main_estadisticas(n_simulaciones=100):
    esc = cargar_escenario()
    nombre_escenario = esc.__name__.split('.')[-1]
    
    todos_los_rapidos = []
    todos_los_lentos = []
    v_max, v_min = 0, 0

    print(f"Corriendo {n_simulaciones} simulaciones para '{nombre_escenario}'...")

    for i in range(n_simulaciones):
        r, l, v_max, v_min = ejecutar_una_simulacion(esc)
        todos_los_rapidos.append(r)
        todos_los_lentos.append(l)
        if (i + 1) % 10 == 0:
            print(f"Progreso: {i + 1}/{n_simulaciones}")

    # Procesamiento para promediar 
    # Encontramos la duración máxima de todas las simulaciones
    max_pasos = max(len(s) for s in todos_los_rapidos)

    # Rellenamos con ceros las simulaciones que terminaron antes (padding)
    def normalizar_y_promediar(lista_de_listas, largo):
        matriz = np.zeros((len(lista_de_listas), largo))
        for i, sim in enumerate(lista_de_listas):
            matriz[i, :len(sim)] = sim
        return np.mean(matriz, axis=0)

    promedio_r = normalizar_y_promediar(todos_los_rapidos, max_pasos)
    promedio_l = normalizar_y_promediar(todos_los_lentos, max_pasos)
    pasos_eje_x = np.arange(max_pasos)

    # Gráfico 
    plt.figure(figsize=(10, 6))
    plt.plot(pasos_eje_x, promedio_r, label=f"Rápidos (Promedio, v={v_max})", color='blue')
    plt.plot(pasos_eje_x, promedio_l, label=f"Lentos (Promedio, v={v_min})", color='red')

    plt.title(f"Evacuación Promedio: {nombre_escenario} ({n_simulaciones} iteraciones)", fontsize=14)
    plt.xlabel("Tiempo (Pasos)", fontsize=12)
    plt.ylabel("Promedio de Agentes Activos", fontsize=12)
    plt.grid(True, alpha=0.3)
    plt.legend()
    
    nombre_img = f"promedio_activos_{nombre_escenario}.png"
    plt.savefig(nombre_img)
    print(f"\nGráfico final guardado como: {nombre_img}")
    plt.show()

if __name__ == "__main__":
    main_estadisticas(5) 
