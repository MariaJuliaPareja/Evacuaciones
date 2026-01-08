# AgentExtendido de DOS formas:
# 1. MODO SIMPLE: Compatible con dynamics.py (movimiento manual)
# 2. MODO AVANZADO: Con floor_field (movimiento inteligente automático)

from agent_extendido import AgentExtendido, mover_agentes_con_conflictos
import pickle
import sys

# Importar floor_field
try:
    sys.path.insert(0, '/mnt/project')
    from floor_field import Floor_field
    FLOOR_FIELD_DISPONIBLE = True
except:
    FLOOR_FIELD_DISPONIBLE = False
    print("floor_field.py no disponible - solo modo simple")


# MODO 1: SIMPLE

def modo_simple():
    """
    Movimiento manual, sin floor_field.
    """
    # Limpiar para nueva simulación
    AgentExtendido.instances = []
    AgentExtendido.history = []
    
    # Crear 5 agentes 
    [AgentExtendido() for _ in range(5)]
    
    # Posiciones iniciales 
    AgentExtendido.instances[0].pos_x, AgentExtendido.instances[0].pos_y = (5, 5)
    AgentExtendido.instances[1].pos_x, AgentExtendido.instances[1].pos_y = (3, 5)
    AgentExtendido.instances[2].pos_x, AgentExtendido.instances[2].pos_y = (3, 5)
    AgentExtendido.instances[3].pos_x, AgentExtendido.instances[3].pos_y = (5, 3)
    AgentExtendido.instances[4].pos_x, AgentExtendido.instances[4].pos_y = (5, 3)  
    print(f"\nCreados {len(AgentExtendido.instances)} agentes")
    print("Agente 0: (5,5) - Centro, quieto")
    print("Agentes 1-2: (3,5) - Oscilarán en X")
    print("Agentes 3-4: (5,3) - Oscilarán en Y")
    AgentExtendido.stores()
    # Loop con movimiento manual 
    incr: int = 1
    print(f"\nEjecutando 10 pasos con movimiento oscilatorio...")
    
    for it in range(10):
        AgentExtendido.instances[0].if_change = False
        
        AgentExtendido.instances[1].pos_x += incr
        AgentExtendido.instances[1].if_change = True
        
        AgentExtendido.instances[2].pos_x += -incr
        AgentExtendido.instances[2].if_change = True
        
        AgentExtendido.instances[3].pos_y += incr
        AgentExtendido.instances[3].if_change = True
        
        AgentExtendido.instances[4].pos_y += -incr
        AgentExtendido.instances[4].if_change = True
        
        AgentExtendido.stores()
        incr *= -1
        
        print(f"Paso {it+1}/10: Agente 1 en ({AgentExtendido.instances[1].pos_x},{AgentExtendido.instances[1].pos_y})")
    
    # Añadir configuración
    size_x: int = 10
    size_y: int = 10
    list_obstacles: list[tuple[int]] = [(i, 0) for i in range(size_x)]
    AgentExtendido.history.append({"size_x": size_x, "size_y": size_y, "obstacles": list_obstacles})
    
    # Guardar
    output = open("historia_simple.pkl", 'wb')
    pickle.dump(AgentExtendido.history, output)
    output.close()
    
    print(f"\nSimulación completada")
    print(f"Pasos guardados: {len(AgentExtendido.history) - 1}")  
    print(f"Archivo: historia_simple.pkl")
    print(f"Formato: 100% compatible con tu código original")

# MODO 2: AVANZADO (Con floor_field)

def modo_avanzado():
    """
    Modo con características avanzadas:
    - Floor field para navegación inteligente
    - Movimiento automático hacia salidas
    - Resolución de conflictos
    - Priorización vivo/menos_vivo
    """
    if not FLOOR_FIELD_DISPONIBLE:
        print("\nfloor_field.py no disponible")
        return
    
    # Limpiar para nueva simulación
    AgentExtendido.instances = []
    AgentExtendido.history = []
    
    # Definir escenario
    width = 10
    height = 10
    puertas = [(0, 4), (0, 5)]  # Dos puertas en la izquierda
    obstaculos = [(5, 5), (5, 6), (5, 4)]  # Obstáculo en el centro
    
    print(f"\nEscenario: {width}x{height}")
    print(f"Puertas: {puertas}")
    print(f"Obstáculos: {obstaculos}")
    
    # Crear floor field
    ff = Floor_field(width, height, puertas, obstaculos)
    print(f"\nFloor field creado")
    
    # Crear agentes con floor_field
    # 3 agentes 'vivos' (alta prioridad)
    for _ in range(3):
        agent = AgentExtendido(agent_type='vivo', floor_field=ff)
    
    # 2 agentes 'menos_vivos' (baja prioridad)
    for _ in range(2):
        agent = AgentExtendido(agent_type='menos_vivo', floor_field=ff)
    
    # Posiciones iniciales (esquina opuesta a las puertas)
    AgentExtendido.instances[0].pos_x, AgentExtendido.instances[0].pos_y = (8, 8)
    AgentExtendido.instances[1].pos_x, AgentExtendido.instances[1].pos_y = (9, 8)
    AgentExtendido.instances[2].pos_x, AgentExtendido.instances[2].pos_y = (8, 9)
    AgentExtendido.instances[3].pos_x, AgentExtendido.instances[3].pos_y = (9, 9)
    AgentExtendido.instances[4].pos_x, AgentExtendido.instances[4].pos_y = (7, 8)
    AgentExtendido.stores()
    # Loop con movimiento automático
    max_pasos = 50
    paso = 0
    print(f"\nEjecutando simulación con movimiento automático...")
    print(f"Los agentes navegarán hacia las puertas evitando obstáculos")
    
    while any(a.activo for a in AgentExtendido.instances) and paso < max_pasos:
        # Mover todos los agentes automáticamente
        stats = mover_agentes_con_conflictos(AgentExtendido.instances)
        AgentExtendido.stores()
        paso += 1
        activos = sum(1 for a in AgentExtendido.instances if a.activo)
        evacuados = len(AgentExtendido.instances) - activos
        if stats['conflictos_totales'] > 0:
            print(f"  Paso {paso}: {activos} activos, {evacuados} evacuados, "
                  f"{stats['conflictos_totales']} conflictos")
        else:
            print(f"  Paso {paso}: {activos} activos, {evacuados} evacuados")
        
        if evacuados == len(AgentExtendido.instances):
            print(f"\n✓ ¡Todos evacuados en {paso} pasos!")
            break
    
    # Añadir configuraci
    AgentExtendido.history.append({
        "size_x": width,
        "size_y": height,
        "obstacles": obstaculos,
        "puertas": puertas
    })
    
    # Guardar
    output = open("historia_avanzada.pkl", 'wb')
    pickle.dump(AgentExtendido.history, output)
    output.close()
    
    print(f"\nSimulación completada")
    print(f"Pasos: {paso}")
    print(f"Archivo: historia_avanzada.pkl")
    
    # Estadísticas finales
    print(f"\nEstadísticas finales:")
    for agent in AgentExtendido.instances:
        print(f"  {agent.tipo:12} #{agent.id}: "
              f"conflictos={agent.conflictos_totales}, "
              f"perdidos={agent.conflictos_perdidos}")


# MODO 3: HÍBRIDO

def modo_hibrido():
    if not FLOOR_FIELD_DISPONIBLE:
        print("\nModo híbrido requiere floor_field.py")
        return
    # Limpiar
    AgentExtendido.instances = []
    AgentExtendido.history = []
    
    # Crear escenario
    width = 12
    height = 10
    puertas = [(0, 4), (0, 5)]
    obstaculos = [(6, 5)]
    
    ff = Floor_field(width, height, puertas, obstaculos)
    
    # Crear 3 agentes
    for i in range(3):
        agent = AgentExtendido(agent_type='vivo', floor_field=ff)
        agent.pos_x = 10
        agent.pos_y = 3 + i
    
    print(f"\n3 agentes creados en columna derecha")
    
    AgentExtendido.stores()
    
    # PARTE 1: Movimiento MANUAL (primeros 3 pasos)
    print(f"\nPARTE 1: Movimiento manual (3 pasos)")
    for paso in range(3):
        for agent in AgentExtendido.instances:
            agent.pos_x -= 1  # Mover a la izquierda
            agent.if_change = True
        AgentExtendido.stores()
        print(f"  Paso {paso+1}: Todos movidos manualmente a x={AgentExtendido.instances[0].pos_x}")
    
    # PARTE 2: Movimiento AUTOMÁTICO (hasta evacuar)
    print(f"\nPARTE 2: Movimiento automático (con floor_field)")
    paso = 3
    while any(a.activo for a in AgentExtendido.instances) and paso < 30:
        stats = mover_agentes_con_conflictos(AgentExtendido.instances)
        AgentExtendido.stores()
        paso += 1
        activos = sum(1 for a in AgentExtendido.instances if a.activo)
        print(f"  Paso {paso}: {activos} activos")
    
    # Guardar
    AgentExtendido.history.append({
        "size_x": width, "size_y": height,
        "obstacles": obstaculos, "puertas": puertas
    })
    
    output = open("historia_hibrida.pkl", 'wb')
    pickle.dump(AgentExtendido.history, output)
    output.close()
    
    print(f"\n✓ Simulación híbrida completada")
    print(f"  - Archivo: historia_hibrida.pkl")


# MENÚ 

def menu():

    print("\nMODOS DISPONIBLES:")
    print("  1. SIMPLE - dynamics.py")
    print("  2. AVANZADOm - Con floor_field y movimiento inteligente")
    print("  3. HÍBRIDO - Parte manual + parte automática")
    print("  4. TODOS - Ejecuta los 3 modos")
    print("  5. Salir")
    print()
    
    opcion = input("Elige modo (1-5): ").strip()
    
    if opcion == '1':
        modo_simple()
    elif opcion == '2':
        modo_avanzado()
    elif opcion == '3':
        modo_hibrido()
    elif opcion == '4':
        modo_simple()
        modo_avanzado()
        modo_hibrido()
    elif opcion == '5':
        print("\nSaliendo...")
        return
    else:
        print("\nOpción no válida")
        return
    
    print("VISUALIZAR:")
    print("python visualizador_interactivo.py historia_simple.pkl")
    print("python visualizador_interactivo.py historia_avanzada.pkl")
    print("python visualizador_interactivo.py historia_hibrida.pkl")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # Modo por argumentos
        if sys.argv[1] == '--simple':
            modo_simple()
        elif sys.argv[1] == '--avanzado':
            modo_avanzado()
        elif sys.argv[1] == '--hibrido':
            modo_hibrido()
        elif sys.argv[1] == '--todos':
            modo_simple()
            modo_avanzado()
            modo_hibrido()
        else:
            print("Uso: python dynamics_hibrido.py [--simple|--avanzado|--hibrido|--todos]")
    else:
        menu()






