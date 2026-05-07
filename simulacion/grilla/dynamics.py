import pickle
import sys
import os
import random
import csv
from datetime import datetime

import matplotlib.pyplot as plt

parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Import agent_extendido 
try:
    from simulacion.pathfinding_propuesta.agent_extendido import AgentExtendido, mover_agentes_con_conflictos
except ImportError:

    try:
        from agent_extendido import AgentExtendido, mover_agentes_con_conflictos
    except ImportError:
        raise ImportError("Could not import agent_extendido. Make sure you're running from the project root or simulacion/grilla/ directory.")

# Import floor_field
try:
    from simulacion.grilla_clasica.floor_field import Floor_field
    FLOOR_FIELD_DISPONIBLE = True
except ImportError:
    try:
        from floor_field import Floor_field
        FLOOR_FIELD_DISPONIBLE = True
    except ImportError:
        FLOOR_FIELD_DISPONIBLE = False

# Import PathSelector
try:
    from simulacion.pathfinding_propuesta.path_selector import PathSelector
    PATH_SELECTOR_DISPONIBLE = True
except ImportError:
    try:
        # Fallback: try importing from nodes directory
        nodes_dir = os.path.join(os.path.dirname(__file__), '..', 'nodos')
        if nodes_dir not in sys.path:
            sys.path.insert(0, nodes_dir)
        from path_selector import PathSelector
        PATH_SELECTOR_DISPONIBLE = True
    except ImportError:
        PATH_SELECTOR_DISPONIBLE = False
        print("ADVERTENCIA: PathSelector no disponible. Usando comportamiento legacy.")


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SALIDAS_DEMO_DIR = os.path.join(PROJECT_ROOT, "salidas", "demo")


def _normalizar_agente_escenario(agente_raw):
    """
    Normaliza definición de agente desde escenario.

    Soporta:
    - dict: {"pos": (x, y), "tipo": "rapido"|"lento"}
    - tuple/list: (x, y) con tipo por defecto "lento"
    """
    if isinstance(agente_raw, dict):
        pos = agente_raw.get("pos")
        tipo = agente_raw.get("tipo", "lento")
    elif isinstance(agente_raw, (tuple, list)) and len(agente_raw) >= 2:
        pos = (agente_raw[0], agente_raw[1])
        tipo = "lento"
    else:
        return None

    if not isinstance(pos, (tuple, list)) or len(pos) < 2:
        return None

    x, y = int(pos[0]), int(pos[1])
    tipo = str(tipo).strip().lower()
    if tipo not in ("rapido", "lento"):
        tipo = "lento"
    return (x, y), tipo


def _guardar_resultados_reales(
    nombre_escenario,
    total_agentes,
    activos_por_paso,
    conflictos_por_paso,
    conflictos_rapido_gana_acum=None,
    conflictos_lento_gana_acum=None,
    conflictos_empate_random_acum=None,
):
    os.makedirs(SALIDAS_DEMO_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"{nombre_escenario}_{timestamp}"
    csv_path = os.path.join(SALIDAS_DEMO_DIR, f"{base_name}.csv")
    png_path = os.path.join(SALIDAS_DEMO_DIR, f"{base_name}.png")

    with open(csv_path, "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=[
                "paso",
                "agentes_activos",
                "agentes_evac",
                "conflictos",
                "ratio_evac",
                "conflictos_rapido_gana",
                "conflictos_lento_gana",
                "conflictos_empate_random",
            ],
        )
        writer.writeheader()
        for paso_idx, activos in enumerate(activos_por_paso):
            evacuados = total_agentes - activos
            ratio = evacuados / total_agentes if total_agentes else 0.0
            conflictos = conflictos_por_paso[paso_idx] if paso_idx < len(conflictos_por_paso) else 0
            rapidos_ganan = 0
            lentos_ganan = 0
            empates_random = 0
            if conflictos_rapido_gana_acum is not None and paso_idx < len(conflictos_rapido_gana_acum):
                rapidos_ganan = conflictos_rapido_gana_acum[paso_idx]
            if conflictos_lento_gana_acum is not None and paso_idx < len(conflictos_lento_gana_acum):
                lentos_ganan = conflictos_lento_gana_acum[paso_idx]
            if conflictos_empate_random_acum is not None and paso_idx < len(conflictos_empate_random_acum):
                empates_random = conflictos_empate_random_acum[paso_idx]
            writer.writerow(
                {
                    "paso": paso_idx,
                    "agentes_activos": activos,
                    "agentes_evac": evacuados,
                    "conflictos": conflictos,
                    "ratio_evac": round(ratio, 4),
                    "conflictos_rapido_gana": rapidos_ganan,
                    "conflictos_lento_gana": lentos_ganan,
                    "conflictos_empate_random": empates_random,
                }
            )

    pasos = list(range(len(activos_por_paso)))
    evacuados = [total_agentes - a for a in activos_por_paso]
    plt.figure(figsize=(8, 4.5))
    plt.plot(pasos, evacuados, label="Agentes evacuados", linewidth=2.0)
    plt.plot(pasos, activos_por_paso, label="Agentes activos", linewidth=1.8, alpha=0.85)
    plt.xlabel("Paso")
    plt.ylabel("Cantidad de agentes")
    plt.title(f"Evolucion de evacuacion - {nombre_escenario}")
    plt.grid(alpha=0.25)
    plt.legend()
    plt.tight_layout()
    plt.savefig(png_path, dpi=180)
    plt.close()

    return csv_path, png_path

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

def simular_evacuacion(escenario='basico', usar_path_selector=True, nombre_salida=None):
    """
    Simulación con floor_field y movimiento automático.
    Integra PathSelector para navegación inteligente con A* y selección por ansiedad.
    
    Parámetros:
    escenario : str
        Nombre del escenario ('basico', 'obstaculos', 'sala')
    usar_path_selector : bool
        Si True, usa PathSelector para navegación inteligente (por defecto True)
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
        },
        'base': {
            'size': (18, 20),
            'puertas': [(0, 9), (0, 10)],
            'obstaculos': [],
            'num_agentes': 4
        },
        'avion': {
            'size': (9, 30),
            'puertas': [(0, 14), (0, 15), (8, 14), (8, 15)],
            'obstaculos': [],
            'num_agentes': 72
        }
    }
    
    config = configs[escenario]
    width, height = config['size']
    
    # Si el escenario tiene definición explícita en /escenarios, usarla.
    modulos_escenario = {
        'sala': 'sala_de_clases',
        'base': 'escenario_base',
        'avion': 'avion',
    }
    if escenario in modulos_escenario:
        try:
            modulo = __import__(f"escenarios.{modulos_escenario[escenario]}", fromlist=['*'])
            if hasattr(modulo, 'width') and hasattr(modulo, 'height'):
                config['size'] = (int(modulo.width), int(modulo.height))
            if hasattr(modulo, 'puertas'):
                config['puertas'] = list(modulo.puertas)
            if hasattr(modulo, 'obstaculos'):
                config['obstaculos'] = list(modulo.obstaculos)
            if hasattr(modulo, 'agentes'):
                config['agentes'] = list(modulo.agentes)
                config['num_agentes'] = len(config['agentes'])
        except Exception:
            pass
    
    print("\n" + "="*60)
    print(f"SIMULACION: {escenario.upper()}")
    if usar_path_selector and PATH_SELECTOR_DISPONIBLE:
        print("  Usando PathSelector (A* + selección por ansiedad)")
    else:
        print("  Usando comportamiento legacy (greedy)")
    print("="*60)
    
    # Limpia
    AgentExtendido.instances = []
    AgentExtendido.history = []
    ff = Floor_field(width, height, config['puertas'], config['obstaculos'])
    
    print(f"Escenario {width}x{height}")
    print(f"Puertas: {config['puertas']}")
    print(f"Obstáculos: {len(config['obstaculos'])}")
    
    # Crear PathSelector UNA VEZ al inicio (si está disponible y se solicita)
    path_selector = None
    if usar_path_selector and PATH_SELECTOR_DISPONIBLE:
        try:
            path_selector = PathSelector(ff, umbral_recalculo=0.6, anxiety_thresholds=(30, 70))
            print("PathSelector inicializado")
        except Exception as e:
            print(f"ADVERTENCIA: Error al crear PathSelector: {e}")
            print("  Continuando con comportamiento legacy")
            path_selector = None
    
    if 'agentes' in config and config['agentes']:
        agentes_definidos = config['agentes']
        rapidos = 0
        creados = 0
        posiciones_ocupadas = set()

        for idx, agente_raw in enumerate(agentes_definidos):
            normalizado = _normalizar_agente_escenario(agente_raw)
            if normalizado is None:
                print(f"ADVERTENCIA: Definición de agente inválida en índice {idx}: {agente_raw}")
                continue

            (x, y), tipo = normalizado
            pos = (x, y)
            if pos in config['obstaculos']:
                print(f"ADVERTENCIA: Agente {idx} en obstáculo {pos}; se omite.")
                continue
            if pos in posiciones_ocupadas:
                print(f"ADVERTENCIA: Posición duplicada {pos}; se omite agente {idx}.")
                continue

            posiciones_ocupadas.add(pos)
            AgentExtendido(
                agent_type=tipo,
                floor_field=ff,
                path_selector=path_selector,
                x=x,
                y=y
            )
            creados += 1
            if tipo == 'rapido':
                rapidos += 1

        config['num_agentes'] = creados
        print(f"{creados} agentes ({rapidos} rapidos) [desde escenario]")
    else:
        # Fallback legacy: generar agentes aleatorios con 60/40.
        num_rapidos = int(config['num_agentes'] * 0.6)
        
        # Preparar posiciones iniciales
        posiciones_iniciales = []
        tipos_agentes = []
        posiciones_ocupadas = set()
        
        # Generar posiciones aleatorias en mitad derecha
        for i in range(config['num_agentes']):
            intentos = 0
            max_intentos = 100
            while intentos < max_intentos:
                x = random.randint(width//2, width-2)
                y = random.randint(1, height-2)
                pos = (x, y)
                
                # Verificar que no esté en un obstáculo ni ocupado
                if pos not in config['obstaculos'] and pos not in posiciones_ocupadas:
                    posiciones_ocupadas.add(pos)
                    posiciones_iniciales.append((x, y))
                    # Asignar tipo: primeros num_rapidos son 'rapido', resto 'lento'
                    tipos_agentes.append('rapido' if i < num_rapidos else 'lento')
                    break
                intentos += 1
            
            if intentos >= max_intentos:
                print(f"ADVERTENCIA: No se pudo asignar posición única al agente {i}")
                # Usar posición por defecto si falla
                posiciones_iniciales.append((width-1, height-1))
                tipos_agentes.append('rapido' if i < num_rapidos else 'lento')
        
        # Crear agentes con PathSelector
        for (x, y), tipo in zip(posiciones_iniciales, tipos_agentes):
            AgentExtendido(
                agent_type=tipo,
                floor_field=ff,
                path_selector=path_selector,
                x=x,
                y=y
            )
        
        print(f"{config['num_agentes']} agentes ({num_rapidos} rapidos)")
    
    # Verificar que todos los agentes tienen posiciones válidas
    for i, agent in enumerate(AgentExtendido.instances):
        if agent.pos_x is None or agent.pos_y is None:
            print(f"ADVERTENCIA: Agente {i} no tiene posición asignada")
    
    AgentExtendido.stores()
    
    # Estadísticas principales
    recalculation_stats = {
        'total_recalculations': 0,
        'by_anxiety_level': {'baja': 0, 'media': 0, 'alta': 0},
        'path_lengths': []
    }
    activos_por_paso = [sum(1 for a in AgentExtendido.instances if a.activo)]
    conflictos_por_paso = [0]
    conflictos_rapido_gana_acum = [0]
    conflictos_lento_gana_acum = [0]
    conflictos_empate_random_acum = [0]
    
    # Simular hasta evacuar todos
    paso = 0
    max_pasos = 200
    
    print(f"\nSimulando evacuación...")
    
    while any(a.activo for a in AgentExtendido.instances) and paso < max_pasos:
        # Crear mapa de ocupación antes de proponer movimientos
        agent_positions = {}
        for agent in AgentExtendido.instances:
            if agent.activo and agent.pos_x is not None and agent.pos_y is not None:
                pos = (agent.pos_x, agent.pos_y)
                agent_positions[pos] = agent_positions.get(pos, 0) + 1
        
        # Actualizar métricas dinámicas del PathSelector si está disponible
        if path_selector is not None:
            path_selector.actualizar_metricas(AgentExtendido.instances)
            path_selector.actualizar_pesos_grafo()
        
        # Mover agentes (mover_agentes_con_conflictos ya maneja goal y agent_positions internamente)
        stats = mover_agentes_con_conflictos(AgentExtendido.instances)
        conflictos_por_paso.append(stats.get("conflictos", 0))
        conflictos_rapido_gana_acum.append(
            conflictos_rapido_gana_acum[-1] + stats.get("conflictos_rapido_gana", 0)
        )
        conflictos_lento_gana_acum.append(
            conflictos_lento_gana_acum[-1] + stats.get("conflictos_lento_gana", 0)
        )
        conflictos_empate_random_acum.append(
            conflictos_empate_random_acum[-1] + stats.get("conflictos_empate_random", 0)
        )
        
        # Registrar estadísticas de PathSelector
        if path_selector is not None:
            # Contar recalculaciones por nivel de ansiedad
            for agent in AgentExtendido.instances:
                if agent.activo and agent.usa_enrutamiento_inteligente:
                    # Verificar si recalculó en este paso (path_index reseteado)
                    if agent.current_path and len(agent.current_path) > 0:
                        recalculation_stats['path_lengths'].append(len(agent.current_path))
                        
                        # Categorizar por ansiedad
                        anxiety = agent.ansiedad
                        if anxiety <= 30:
                            category = 'baja'
                        elif anxiety <= 70:
                            category = 'media'
                        else:
                            category = 'alta'
                        
                        # Si el path_index es 0 y tiene ruta, probablemente recalculó
                        if agent.path_index == 0 and agent.steps_without_moving == 0:
                            recalculation_stats['total_recalculations'] += 1
                            recalculation_stats['by_anxiety_level'][category] += 1
        
        AgentExtendido.stores()
        paso += 1
        activos = sum(1 for a in AgentExtendido.instances if a.activo)
        activos_por_paso.append(activos)
        if paso % 10 == 0:
            print(f"  Paso {paso}: {activos} activos")
    
    print(f"\nEvacuacion completa en {paso} pasos")
    
    # Mostrar estadísticas de PathSelector
    if path_selector is not None:
        print("\n" + "-"*60)
        print("ESTADÍSTICAS PATH SELECTOR:")
        print("-"*60)
        ps_stats = path_selector.obtener_estadisticas()
        print(f"  Rutas calculadas: {ps_stats['rutas_calculadas']}")
        print(f"  Cache hit rate: {ps_stats.get('cache_hit_rate', 0):.2%}")
        print(f"  Nodos explorados (promedio): {ps_stats.get('nodes_explored_avg', 0):.1f}")
        
        if recalculation_stats['path_lengths']:
            avg_length = sum(recalculation_stats['path_lengths']) / len(recalculation_stats['path_lengths'])
            print(f"  Longitud promedio de rutas: {avg_length:.1f}")
        
        print(f"\n  Recalculaciones totales: {recalculation_stats['total_recalculations']}")
        print(f"  Por nivel de ansiedad:")
        for level, count in recalculation_stats['by_anxiety_level'].items():
            print(f"    {level}: {count}")
        
        # Estadísticas de ansiedad
        anxiety_stats = path_selector.get_anxiety_statistics()
        if anxiety_stats['total_decisions'] > 0:
            print(f"\n  Decisiones por ansiedad: {anxiety_stats['total_decisions']}")
            print(f"  Distribución: {anxiety_stats['by_category']}")
            print(f"  Tasa de ruido añadido: {anxiety_stats['noise_rate']:.2%}")
    
    # Añadir config
    AgentExtendido.history.append({
        "size_x": width,
        "size_y": height,
        "obstacles": config['obstaculos'],
        "puertas": config['puertas']
    })
    
    # Guardar
    nombre_base = nombre_salida.strip() if isinstance(nombre_salida, str) and nombre_salida.strip() else escenario
    archivo = f"historia_{nombre_base}.pkl"
    with open(archivo, 'wb') as f:
        pickle.dump(AgentExtendido.history, f)
    
    csv_path, png_path = _guardar_resultados_reales(
        nombre_escenario=escenario,
        total_agentes=config["num_agentes"],
        activos_por_paso=activos_por_paso,
        conflictos_por_paso=conflictos_por_paso,
        conflictos_rapido_gana_acum=conflictos_rapido_gana_acum,
        conflictos_lento_gana_acum=conflictos_lento_gana_acum,
        conflictos_empate_random_acum=conflictos_empate_random_acum,
    )
    print(f"\nArchivo PKL: {archivo}")
    print(f"Resultados reales (CSV): {csv_path}")
    print(f"Resultados reales (grafico): {png_path}")


def simular_flujos_opuestos(guardar_pkl=True, nombre_salida="historia_flujos.pkl"):
    """
    Simulación con dos grupos que buscan salidas opuestas (cada uno con su floor field y PathSelector).
    """
    if not FLOOR_FIELD_DISPONIBLE or not PATH_SELECTOR_DISPONIBLE:
        print("\nFloor_field o PathSelector no disponibles; no se puede simular flujos opuestos.")
        return

    _root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if _root not in sys.path:
        sys.path.insert(0, _root)
    from escenarios import flujos_opuestos as esc

    AgentExtendido.instances = []
    AgentExtendido.history = []

    ff_A = Floor_field(esc.width, esc.height, esc.puertas_A, esc.obstaculos)
    ff_B = Floor_field(esc.width, esc.height, esc.puertas_B, esc.obstaculos)

    ps_A = PathSelector(ff_A, umbral_recalculo=0.6, anxiety_thresholds=(30, 70))
    ps_B = PathSelector(ff_B, umbral_recalculo=0.6, anxiety_thresholds=(30, 70))

    grupo_por_id = {}
    goals = {}

    for (x, y) in esc.agentes_A:
        agente = AgentExtendido(
            agent_type='rapido',
            floor_field=ff_A,
            path_selector=ps_A,
            x=x,
            y=y,
        )
        grupo_por_id[agente.id] = 'A'
        goals[agente.id] = esc.puertas_A[0]

    for (x, y) in esc.agentes_B:
        agente = AgentExtendido(
            agent_type='lento',
            floor_field=ff_B,
            path_selector=ps_B,
            x=x,
            y=y,
        )
        grupo_por_id[agente.id] = 'B'
        goals[agente.id] = esc.puertas_B[0]

    todos = AgentExtendido.instances

    AgentExtendido.stores()

    paso = 0
    max_pasos = 300

    activos_por_paso = [sum(1 for a in todos if a.activo)]
    conflictos_por_paso = [0]
    conflictos_rapido_gana_acum = [0]
    conflictos_lento_gana_acum = [0]
    conflictos_empate_random_acum = [0]
    while any(a.activo for a in todos) and paso < max_pasos:
        ps_A.actualizar_metricas(todos)
        ps_A.actualizar_pesos_grafo()
        ps_B.actualizar_metricas(todos)
        ps_B.actualizar_pesos_grafo()

        stats = mover_agentes_con_conflictos(todos, goals=goals)
        conflictos_por_paso.append(stats.get("conflictos", 0))
        conflictos_rapido_gana_acum.append(
            conflictos_rapido_gana_acum[-1] + stats.get("conflictos_rapido_gana", 0)
        )
        conflictos_lento_gana_acum.append(
            conflictos_lento_gana_acum[-1] + stats.get("conflictos_lento_gana", 0)
        )
        conflictos_empate_random_acum.append(
            conflictos_empate_random_acum[-1] + stats.get("conflictos_empate_random", 0)
        )
        AgentExtendido.stores()
        paso += 1
        activos_por_paso.append(sum(1 for a in todos if a.activo))

    AgentExtendido.history.append({
        "size_x": esc.width,
        "size_y": esc.height,
        "obstacles": esc.obstaculos,
        "puertas": esc.puertas,
    })

    if guardar_pkl:
        archivo = os.path.join(_root, nombre_salida)
        with open(archivo, 'wb') as f:
            pickle.dump(AgentExtendido.history, f)
        print(f"\nGuardado: {archivo}")

    evac_a = sum(1 for a in todos if grupo_por_id[a.id] == 'A' and not a.activo)
    evac_b = sum(1 for a in todos if grupo_por_id[a.id] == 'B' and not a.activo)
    n_a = sum(1 for a in todos if grupo_por_id[a.id] == 'A')
    n_b = sum(1 for a in todos if grupo_por_id[a.id] == 'B')

    print("\n" + "=" * 60)
    print("RESUMEN FLUJOS OPUESTOS")
    print("=" * 60)
    print(f"Pasos totales: {paso}")
    print(f"Agentes evacuados grupo A: {evac_a} / {n_a}")
    print(f"Agentes evacuados grupo B: {evac_b} / {n_b}")
    print("=" * 60)
    csv_path, png_path = _guardar_resultados_reales(
        nombre_escenario="flujos_opuestos",
        total_agentes=len(todos),
        activos_por_paso=activos_por_paso,
        conflictos_por_paso=conflictos_por_paso,
        conflictos_rapido_gana_acum=conflictos_rapido_gana_acum,
        conflictos_lento_gana_acum=conflictos_lento_gana_acum,
        conflictos_empate_random_acum=conflictos_empate_random_acum,
    )
    print(f"Resultados reales (CSV): {csv_path}")
    print(f"Resultados reales (grafico): {png_path}")


def menu():
    """Menú interactivo"""
    print("\nOPCIONES:")
    print("  1. Simple (oscilatorio)")
    print("  2. Evacuación básica" + ("" if FLOOR_FIELD_DISPONIBLE else "requiere floor_field.py"))
    print("  3. Con obstáculos" + ("" if FLOOR_FIELD_DISPONIBLE else "requiere floor_field.py"))
    print("  4. Sala de clases" + ("" if FLOOR_FIELD_DISPONIBLE else "requiere floor_field.py"))
    print("  5. Escenario base")
    print("  6. Avión")
    print("  7. Flujos opuestos (A→O1 / B→O2)" + ("" if (FLOOR_FIELD_DISPONIBLE and PATH_SELECTOR_DISPONIBLE) else " (requiere floor_field + path_selector)"))
    print("  8. Salir")
    print()
    
    opcion = input("Elige (1-8): ").strip()
    
    if opcion == '1':
        simular_simple()
    elif opcion == '2':
        simular_evacuacion('basico')
    elif opcion == '3':
        simular_evacuacion('obstaculos')
    elif opcion == '4':
        simular_evacuacion('sala')
    elif opcion == '5':
        simular_evacuacion('base')
    elif opcion == '6':
        simular_evacuacion('avion')
    elif opcion == '7':
        simular_flujos_opuestos()
    elif opcion == '8':
        print("Saliendo...")
    else:
        print("Opción inválida")

# MAIN

if __name__ == "__main__":
    if len(sys.argv) > 1:
        args = sys.argv[1:]
        cmd = args[0]
        nombre_salida = None
        if "--nombre" in args:
            idx_nombre = args.index("--nombre")
            if idx_nombre + 1 >= len(args):
                print("Error: --nombre requiere un valor. Ejemplo: --sala --nombre mi_experimento")
                sys.exit(1)
            nombre_salida = args[idx_nombre + 1]

        if cmd == '--simple':
            simular_simple()
        elif cmd == '--evacuacion':
            simular_evacuacion('basico', nombre_salida=nombre_salida)
        elif cmd == '--obstaculos':
            simular_evacuacion('obstaculos', nombre_salida=nombre_salida)
        elif cmd == '--sala':
            simular_evacuacion('sala', nombre_salida=nombre_salida)
        elif cmd == '--base':
            simular_evacuacion('base', nombre_salida=nombre_salida)
        elif cmd == '--avion':
            simular_evacuacion('avion', nombre_salida=nombre_salida)
        elif cmd == '--flujos':
            nombre_flujos = nombre_salida.strip() if isinstance(nombre_salida, str) and nombre_salida.strip() else "flujos"
            simular_flujos_opuestos(nombre_salida=f"historia_{nombre_flujos}.pkl")
        else:
            print("Uso: python dynamics.py [--simple|--evacuacion|--obstaculos|--sala|--base|--avion|--flujos] [--nombre <nombre_salida>]")
    else:
        menu()






