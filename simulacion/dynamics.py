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
    
    # Posiciones iniciales - asegurar que no haya dos agentes en la misma celda
    AgentExtendido.instances[0].pos_x = 5
    AgentExtendido.instances[0].pos_y = 5
    AgentExtendido.instances[1].pos_x = 3
    AgentExtendido.instances[1].pos_y = 5
    AgentExtendido.instances[2].pos_x = 4  # Cambiado de (3,5) a (4,5) para evitar duplicado
    AgentExtendido.instances[2].pos_y = 5
    AgentExtendido.instances[3].pos_x = 5
    AgentExtendido.instances[3].pos_y = 3
    AgentExtendido.instances[4].pos_x = 6  # Cambiado de (5,3) a (6,3) para evitar duplicado
    AgentExtendido.instances[4].pos_y = 3
    
    print(f"5 agentes creados")
    print("Agente 0: (5,5) - quieto")
    print("Agente 1: (3,5) - oscila X")
    print("Agente 2: (4,5) - oscila X")
    print("Agente 3: (5,3) - oscila Y")
    print("Agente 4: (6,3) - oscila Y")
    
    # Verificar que todos los agentes tienen posiciones válidas
    for i, agent in enumerate(AgentExtendido.instances):
        if agent.pos_x is None or agent.pos_y is None:
            print(f"ADVERTENCIA: Agente {i} no tiene posición asignada")
    
    AgentExtendido.stores()
    
    # Loop oscilatorio con verificación de colisiones
    incr = 1
    print(f"\nEjecutando {num_pasos} pasos...")
    
    for it in range(num_pasos):
        # Agente 0 se queda quieto
        AgentExtendido.instances[0].if_change = False
        
        # Calcular nuevas posiciones primero
        nuevas_posiciones = {}
        nuevas_posiciones[1] = (AgentExtendido.instances[1].pos_x + incr, AgentExtendido.instances[1].pos_y)
        nuevas_posiciones[2] = (AgentExtendido.instances[2].pos_x + (-incr), AgentExtendido.instances[2].pos_y)
        nuevas_posiciones[3] = (AgentExtendido.instances[3].pos_x, AgentExtendido.instances[3].pos_y + incr)
        nuevas_posiciones[4] = (AgentExtendido.instances[4].pos_x, AgentExtendido.instances[4].pos_y + (-incr))
        
        # Verificar colisiones y aplicar movimientos solo si no hay conflicto
        posiciones_ocupadas = {
            (AgentExtendido.instances[0].pos_x, AgentExtendido.instances[0].pos_y): 0
        }
        
        # Aplicar movimientos en orden, evitando colisiones
        for agente_id in [1, 2, 3, 4]:
            nueva_pos = nuevas_posiciones[agente_id]
            if nueva_pos not in posiciones_ocupadas:
                # Movimiento válido
                AgentExtendido.instances[agente_id].pos_x = nueva_pos[0]
                AgentExtendido.instances[agente_id].pos_y = nueva_pos[1]
                AgentExtendido.instances[agente_id].if_change = True
                posiciones_ocupadas[nueva_pos] = agente_id
            else:
                # Colisión detectada, agente se queda quieto
                AgentExtendido.instances[agente_id].if_change = False
        
        AgentExtendido.stores()
        incr *= -1
    
    # Añadir config con puertas para evacuación
    AgentExtendido.history.append({
        "size_x": 10,
        "size_y": 10,
        "obstacles": [(i, 0) for i in range(10)],
        "puertas": [(0, 4), (0, 5)]  # Agregar puertas en el lado izquierdo
    })
    
    # Guardar
    with open("historia.pkl", 'wb') as f:
        pickle.dump(AgentExtendido.history, f)
    
    print(f"\nListo: historia.pkl ({num_pasos} pasos)")
    print(f"Visualizar: python visualizador.py historia.pkl")

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
    
    # Posiciones aleatorias en mitad derecha - asegurar que no haya dos agentes en la misma celda
    posiciones_ocupadas = set()
    for agent in AgentExtendido.instances:
        intentos = 0
        max_intentos = 100
        while intentos < max_intentos:
            agent.pos_x = random.randint(width//2, width-2)
            agent.pos_y = random.randint(1, height-2)
            pos = (agent.pos_x, agent.pos_y)
            
            # Verificar que no esté en un obstáculo ni ocupado por otro agente
            if pos not in config['obstaculos'] and pos not in posiciones_ocupadas:
                posiciones_ocupadas.add(pos)
                break
            intentos += 1
        
        if intentos >= max_intentos:
            print(f"ADVERTENCIA: No se pudo asignar posición única al agente {agent.id}")
    
    print(f"{config['num_agentes']} agentes ({num_vivos} vivos)")
    
    # Verificar que todos los agentes tienen posiciones válidas
    for i, agent in enumerate(AgentExtendido.instances):
        if agent.pos_x is None or agent.pos_y is None:
            print(f"ADVERTENCIA: Agente {i} no tiene posición asignada")
    
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
    print(f"Visualizar: python visualizador.py {archivo}")


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






