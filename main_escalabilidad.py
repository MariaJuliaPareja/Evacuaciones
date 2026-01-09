# main_escalabilidad.py, por Miguel Acevedo y Emilia Partarrieu
from simulacion.floor_field import Floor_field 
from simulacion.agentes import Agente, mover_agentes
import matplotlib.pyplot as plt
import numpy as np

def correr_experimento_lineal():
    # definición del escenario 
    width = 18
    height = 20
    puertas = [(0, 9)]
    obstaculos = []
    
    # todos los agentes posibles
    columnas = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]
    filas = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18]
    agentes_total = [(x, y, 1) for y in filas for x in columnas]
    
    tiempos_totales = []
    cantidad_agentes = list(range(1, len(agentes_total) + 1))

    print(f"Iniciando experimento de escalabilidad. Máximo agentes: {len(agentes_total)}")

    # bucle incremental: 1 agente, luego 2, luego 3 y así ...
    for n in cantidad_agentes:
        # creamos el campo (se puede reusar o recrear)
        campo = Floor_field(width, height, puertas, obstaculos)
        
        # tomamos solo los primeros n agentes de la lista total
        agentes_seleccionados = agentes_total[:n]
        agentes = [Agente(x, y, campo, velocidad=v) for (x, y, v) in agentes_seleccionados]
        
        pasos = 0
        while any(a.activo for a in agentes):
            mover_agentes(agentes)
            pasos += 1
            if pasos > 10000: break # Seguridad por si hay bloqueos
        
        tiempos_totales.append(pasos)
        
        if n % 10 == 0 or n == len(agentes_total):
            print(f"Simulando con {n} agentes... Tiempo total: {pasos} pasos.")

    # graficar
    plt.figure(figsize=(10, 6))
    plt.plot(cantidad_agentes, tiempos_totales, 'o-', color='green', markersize=2, label="Tiempo de evacuación")
    
    # para comparar con la linealidad, trazamos una línea desde el primer punto al último
    plt.plot([cantidad_agentes[0], cantidad_agentes[-1]], 
             [tiempos_totales[0], tiempos_totales[-1]], 
             '--', color='gray', alpha=0.5, label="Referencia lineal")

    plt.title("Escalabilidad del Tiempo de Evacuación", fontsize=14)
    plt.xlabel("Número de Agentes en el Escenario", fontsize=12)
    plt.ylabel("Tiempo Total de Evacuación (Pasos)", fontsize=12)
    plt.grid(True, linestyle=':', alpha=0.7)
    plt.legend()
    
    plt.savefig("analisis_escalabilidad.png")
    print("\nGráfico de escalabilidad guardado como 'analisis_escalabilidad.png'")
    plt.show()

if __name__ == "__main__":
    correr_experimento_lineal()
