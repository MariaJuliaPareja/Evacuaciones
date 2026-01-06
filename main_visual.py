# main_visual.py, por Miguel Acevedo y Emilia Partarrieu 12/25
from simulacion.floor_field import Floor_field 
from simulacion.agentes import Agente, mover_agentes
from simulacion.funciones import *
import matplotlib.pyplot as plt

def main():
    """Función principal que ejecuta la simulación visualizándola en la terminal"""
    esc = cargar_escenario()
    
    campo = Floor_field(esc.width, esc.height, esc.puertas, esc.obstaculos)

    agentes = [Agente(x, y, campo) for (x, y) in esc.agentes]
    
    pasos = 0
    
    while any(a.activo for a in agentes):
        mostrar_matriz(campo, agentes)
        guardar_frame(campo, agentes, pasos)
        mover_agentes(agentes)
        pasos += 1
        time.sleep(0.2)

    mostrar_matriz(campo, agentes)
    print(f" los {len(agentes)} agentes llegaron a la puerta en {pasos} pasos.")
 

    #---------- Imagen de la matriz (campo de piso) obtenida
    fig, ax = plt.subplots(figsize=(12, 12))
    ax.axis("off")

    tabla = plt.table(
        cellText=np.round(campo.valores, 1),
        loc="center",
        cellLoc="center")
    tabla.auto_set_font_size(False)
    tabla.set_fontsize(15)
    #   tabla.scale(1.2, 1.2)
    for (row, col), cell in tabla.get_celld().items():
        if campo.valores[row, col] == 500:
            cell.set_facecolor("black")
            cell.get_text().set_color("white")
        else:
            cell.set_facecolor("white")
            
        cell.set_width(1/esc.width)
        cell.set_height(1/esc.height)
        
    plt.title("Matriz de Floor Field (valores numéricos)", pad=20)

    plt.savefig("floor_field.png", dpi= 300, bbox_inches="tight" )

    plt.show()
    return pasos 


if __name__ == "__main__":
    N = 1  # cantidad de ejecuciones, cambiar a gusto. 
    resultados = []

    for i in range(N):
        print(f"\n--- Ejecución {i+1}/{N} ---")
        pasos = main()   # ejecuta el main y recibe los pasos
        resultados.append(pasos)

    promedio = sum(resultados) / len(resultados)

    print("---------------------------------")
    print("      Resultados Finales:")
    print("---------------------------------")
    print(f"Pasos de cada ejecución: {resultados}")
    print(f"Promedio de pasos en {N} ejecuciones: {promedio:.2f}")
