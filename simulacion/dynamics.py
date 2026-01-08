from agent_extendido import AgentExtendido, mover_agentes_con_conflictos
import pickle
import sys

try:
    from floor_field import Floor_field
    FLOOR_FIELD_DISPONIBLE = True
except:
    FLOOR_FIELD_DISPONIBLE = False


# SIMULACIÓN SIMPLE

def simular_simple(num_pasos=10):
    """
    Movimiento oscilatorio manual.
    """
    # Limpiar
    AgentExtendido.instances = []
    AgentExtendido.history = []
    
    # Crear 5 agentes
    [AgentExtendido() for _ in range(5)]
    
    # Posiciones iniciales (como tu código original)
    AgentExtendido.instances[0].pos_x = 5
    AgentExtendido.instances[0].pos_y = 5
    AgentExtendido.instances[1].pos_x = 3
    AgentExtendido.instances[1].pos_y = 5
    AgentExtendido.instances[2].pos_x = 3
    AgentExtendido.instances[2].pos_y = 5
    AgentExtendido.instances[3].pos_x = 5
    AgentExtendido.instances[3].pos_y = 3
    AgentExtendido.instances[4].pos_x = 5
    AgentExtendido.instances[4].pos_y = 3
    
    print(f"5 agentes creados")
    print("Agente 0: (5,5) - quieto")
    print("Agentes 1-2: (3,5) - oscilan X")
    print("Agentes 3-4: (5,3) - oscilan Y")
    
    AgentExtendido.stores()
    
    # Loop oscilatorio
    incr = 1
    print(f"\nEjecutando {num_pasos} pasos...")
    
    for it in range(num_pasos):
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
    
    # Añadir config
    AgentExtendido.history.append({
        "size_x": 10,
        "size_y": 10,
        "obstacles": [(i, 0) for i in range(10)]
    })
    
    # Guardar
    with open("historia.pkl", 'wb') as f:
        pickle.dump(AgentExtendido.history, f)
    
    print(f"\nListo: historia.pkl ({num_pasos} pasos)")
    print(f"Visualizar: python visualizador_interactivo.py historia.pkl")

# SIMULACIÓN CON FLOOR FIELD

def simular_evacuacion(escenario='basico'):
    """
    Simulación con floor_field y movimiento automático.
    """
    if not FLOOR_FIELD_DISPONIBLE:
        print("\nfloor_field.py no disponible")
        return
    
    # Configuraciones
    configs = {
        'basico': {
            'size': (10, 10),
            'puertas': [(0, 4), (0, 5)],
            'obstaculos': [],
            'num_agentes': 5
        },
        'obstaculos': {
            'size': (12, 10),
            'puertas': [(0, 4), (0, 5)],
            'obstaculos': [(6, 4), (6, 5), (6, 6)],
            'num_agentes': 8
        },
        'sala': {
            'size': (12, 10),
            'puertas': [(0, 6), (0, 7)],
            'obstaculos': [
                (3,2),(3,3),(3,6),(3,7),
                (5,2),(5,3),(5,6),(5,7),
                (7,2),(7,3),(7,6),(7,7),
                (9,2),(9,3),(9,6),(9,7)
            ],
            'num_agentes': 16
        }
    }
    
    config = configs[escenario]
    width, height = config['size']
    
    print("\n" + "="*60)
    print(f"SIMULACIÓN: {escenario.upper()}")
    print("="*60)
    
    # Limpia
    AgentExtendido.instances = []
    AgentExtendido.history = []
    ff = Floor_field(width, height, config['puertas'], config['obstaculos'])
    
    print(f"Escenario {width}x{height}")
    print(f"Puertas: {config['puertas']}")
    print(f"Obstáculos: {len(config['obstaculos'])}")
    
    # Crear agentes (60% vivos, 40% menos_vivos)
    import random
    num_vivos = int(config['num_agentes'] * 0.6)
    
    for i in range(num_vivos):
        AgentExtendido(agent_type='vivo', floor_field=ff)
    
    for i in range(config['num_agentes'] - num_vivos):
        AgentExtendido(agent_type='menos_vivo', floor_field=ff)
    
    # Posiciones aleatorias en mitad derecha
    for agent in AgentExtendido.instances:
        agent.pos_x = random.randint(width//2, width-2)
        agent.pos_y = random.randint(1, height-2)
        
        while (agent.pos_x, agent.pos_y) in config['obstaculos']:
            agent.pos_x = random.randint(width//2, width-2)
            agent.pos_y = random.randint(1, height-2)
    
    print(f"{config['num_agentes']} agentes ({num_vivos} vivos)")
    
    AgentExtendido.stores()
    
    # Simular hasta evacuar todos
    paso = 0
    max_pasos = 100
    
    print(f"\nSimulando evacuación...")
    
    while any(a.activo for a in AgentExtendido.instances) and paso < max_pasos:
        stats = mover_agentes_con_conflictos(AgentExtendido.instances)
        AgentExtendido.stores()
        paso += 1
        activos = sum(1 for a in AgentExtendido.instances if a.activo)
        if paso % 10 == 0:
            print(f"  Paso {paso}: {activos} activos")
    
    print(f"\nEvacuación completa en {paso} pasos")
    # Añadir config
    AgentExtendido.history.append({
        "size_x": width,
        "size_y": height,
        "obstacles": config['obstaculos'],
        "puertas": config['puertas']
    })
    
    # Guardar
    archivo = f"historia_{escenario}.pkl"
    with open(archivo, 'wb') as f:
        pickle.dump(AgentExtendido.history, f)
    
    print(f"Archivo: {archivo}")
    print(f"Visualizar: python visualizador_interactivo.py {archivo}")


def menu():
    """Menú interactivo"""
    print("\nOPCIONES:")
    print("  1. Simple (oscilatorio)")
    print("  2. Evacuación básica" + ("" if FLOOR_FIELD_DISPONIBLE else "requiere floor_field.py"))
    print("  3. Con obstáculos" + ("" if FLOOR_FIELD_DISPONIBLE else "requiere floor_field.py"))
    print("  4. Sala de clases" + ("" if FLOOR_FIELD_DISPONIBLE else "requiere floor_field.py"))
    print("  5. Salir")
    print()
    
    opcion = input("Elige (1-5): ").strip()
    
    if opcion == '1':
        simular_simple()
    elif opcion == '2':
        simular_evacuacion('basico')
    elif opcion == '3':
        simular_evacuacion('obstaculos')
    elif opcion == '4':
        simular_evacuacion('sala')
    elif opcion == '5':
        print("Saliendo...")
    else:
        print("Opción inválida")

# MAIN

if __name__ == "__main__":
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == '--simple':
            simular_simple()
        elif cmd == '--evacuacion':
            simular_evacuacion('basico')
        elif cmd == '--obstaculos':
            simular_evacuacion('obstaculos')
        elif cmd == '--sala':
            simular_evacuacion('sala')
        else:
            print(f"Uso: python dynamics.py [--simple|--evacuacion|--obstaculos|--sala]")
    else:
        menu()






