# main_iterado.py, por Miguel Acevedo y Emilia Partarrieu 12/25
from simulacion.floor_field import Floor_field
from simulacion.agentes import Agente, mover_agentes
from simulacion.funciones import *

def main():
    """
    Con este main podemos estudiar la posición optima de k puertas con k natural tal que
    el tiempo de evacuación sea mínimo. Esto lo hacemos recorriendo todas las combinaciones
    posibles para posicionar las puertas en el floor field.
    """
    esc = cargar_escenario()
    
    mejor_tiempo = float('inf')
    mejor_config = []

    # iteramos sobre todas las combinaciones de puertas de tamaño k
    for puertas in generar_combinaciones_puertas(esc.width, esc.height, esc.k_puertas):

        tiempo = correr_simulacion(esc, puertas)

   #     print(f"Puertas {puertas} -> tiempo: {tiempo}")

        if tiempo < mejor_tiempo:
            mejor_tiempo = tiempo
            mejor_config = [puertas]
        elif tiempo == mejor_tiempo:
            mejor_config.append(puertas)

    print("\n-----------------------------------")
    print(" Mejor configuración encontrada:")
    print("-------------------------------------")
    print(f"Puertas: {mejor_config}")
    print(f"Tiempo mínimo de evacuación: {mejor_tiempo} pasos")


if __name__ == "__main__":
    main()
