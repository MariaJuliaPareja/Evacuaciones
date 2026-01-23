"""
test_path_selector_integration.py
Integration tests for PathSelector system with AgentExtendido.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from escenarios.escenario_base import width, height, puertas, obstaculos
from simulacion.grilla.floor_field import Floor_field
from simulacion.nodos.path_selector import PathSelector
from simulacion.agent_extendido import AgentExtendido


def test_path_selector_escenario_base():
    """
    TEST 1: PathSelector with base scenario
    Verifies that PathSelector can be created and finds paths correctly.
    """
    ff = Floor_field(width, height, puertas, obstaculos)
    ps = PathSelector(ff)
    
    # Verify graph was built correctly
    assert ps.grafo is not None, "Graph should be created"
    assert len(ps.grafo.nodes()) > 0, "Graph should have nodes"
    assert len(ps.grafo.edges()) > 0, "Graph should have edges"
    
    # Verify A* finds path
    start = (8, 9)
    goal = puertas[0]
    path = ps.encontrar_ruta_a_star(start, goal)
    
    assert path is not None, "A* should find a path"
    assert len(path) > 0, "Path should not be empty"
    assert path[0] == start, f"Path should start at {start}, got {path[0]}"
    assert path[-1] == goal, f"Path should end at {goal}, got {path[-1]}"
    
    # Verify path is valid (consecutive cells)
    for i in range(len(path) - 1):
        current = path[i]
        next_cell = path[i + 1]
        dx = abs(current[0] - next_cell[0])
        dy = abs(current[1] - next_cell[1])
        assert dx <= 1 and dy <= 1, f"Path should have consecutive cells, got {current} -> {next_cell}"


def test_k_paths_diferentes():
    """
    TEST 2: K-paths generates different paths
    Verifies that find_k_paths generates multiple distinct paths.
    """
    ff = Floor_field(width, height, puertas, obstaculos)
    ps = PathSelector(ff)
    
    start = (16, 18)
    goal = puertas[0]
    k_paths = ps.find_k_paths(start, goal, k=3)
    
    # Verify it found at least 2 paths (might not find 3 if scenario is simple)
    assert len(k_paths) >= 2, f"Should find at least 2 paths, got {len(k_paths)}"
    
    # Verify all paths are valid
    for i, path in enumerate(k_paths):
        assert path is not None, f"Path {i} should not be None"
        assert len(path) > 0, f"Path {i} should not be empty"
        assert path[0] == start, f"Path {i} should start at {start}"
        assert path[-1] == goal, f"Path {i} should end at {goal}"
    
    # Verify they are different (compare first two paths)
    if len(k_paths) >= 2:
        path1_set = set(k_paths[0])
        path2_set = set(k_paths[1])
        
        # Calculate overlap
        intersection = path1_set & path2_set
        union = path1_set | path2_set
        
        if len(union) > 0:
            overlap = len(intersection) / len(union)
            # Allow some overlap but paths should be different
            assert overlap < 0.7, f"Paths should be different, overlap is {overlap:.2%}"
        
        # Verify paths have different lengths or different cells
        if len(k_paths[0]) == len(k_paths[1]):
            # If same length, they should have different cells
            assert path1_set != path2_set, "Paths should have different cells"


def test_seleccion_por_ansiedad():
    """
    TEST 3: Selection by anxiety
    Verifies that select_path_by_anxiety chooses paths based on anxiety level.
    """
    ff = Floor_field(width, height, puertas, obstaculos)
    ps = PathSelector(ff)
    
    start = (10, 10)
    goal = puertas[0]
    k_paths = ps.find_k_paths(start, goal, k=3)
    
    assert len(k_paths) >= 1, "Should find at least one path"
    
    # Low anxiety always chooses the first (optimal) path
    for _ in range(10):
        selected = ps.select_path_by_anxiety(k_paths, anxiety_level=20)
        assert selected is not None, "Selected path should not be None"
        assert selected == k_paths[0], f"Low anxiety should always choose optimal path, got index {k_paths.index(selected) if selected in k_paths else 'N/A'}"
    
    # High anxiety has variability
    selections = []
    for _ in range(50):
        selected = ps.select_path_by_anxiety(k_paths, anxiety_level=85)
        assert selected is not None, "Selected path should not be None"
        if selected in k_paths:
            selections.append(k_paths.index(selected))
        else:
            # Path might have noise added, check if it's similar to one of the paths
            # For now, just verify it's a valid path
            assert len(selected) > 0, "Selected path should not be empty"
    
    # Should have used more than one path (if we got valid indices)
    if selections:
        unique_selections = set(selections)
        assert len(unique_selections) > 1, f"High anxiety should use multiple paths, got {unique_selections}"
    
    # Test optimal anxiety (30-70) - should have some variability
    optimal_selections = []
    for _ in range(30):
        selected = ps.select_path_by_anxiety(k_paths, anxiety_level=50)
        assert selected is not None, "Selected path should not be None"
        if selected in k_paths:
            optimal_selections.append(k_paths.index(selected))
    
    # Optimal anxiety should prefer optimal but allow others
    if optimal_selections:
        optimal_count = optimal_selections.count(0)
        optimal_rate = optimal_count / len(optimal_selections)
        # Should prefer optimal (70% probability) but allow others
        assert optimal_rate > 0.5, f"Optimal anxiety should prefer optimal path, got {optimal_rate:.2%}"


def test_agent_usa_path_selector():
    """
    TEST 4: Integration with AgentExtendido
    Verifies that AgentExtendido correctly uses PathSelector.
    """
    # Clear instances for clean test
    AgentExtendido.instances = []
    
    ff = Floor_field(width, height, puertas, obstaculos)
    ps = PathSelector(ff)
    
    # Create agent with PathSelector
    agent = AgentExtendido(
        agent_type='vivo',
        floor_field=ff,
        path_selector=ps,
        x=10,
        y=10
    )
    
    # Verify agent was created correctly
    assert agent.path_selector is not None, "Agent should have path_selector"
    assert agent.usa_enrutamiento_inteligente, "Agent should use intelligent routing"
    assert agent.pos_x == 10, "Agent x position should be 10"
    assert agent.pos_y == 10, "Agent y position should be 10"
    
    # Set up agent positions (simulating other agents)
    agent_positions = {(10, 11): 1, (11, 10): 2}
    goal = puertas[0]
    
    # Agent must choose route
    agent.elegir_ruta(goal, agent_positions)
    
    # Verify route was chosen
    assert agent.current_path is not None, "Agent should have a current path"
    assert len(agent.current_path) > 0, "Current path should not be empty"
    assert agent.current_path[0] == (agent.pos_x, agent.pos_y), "Path should start at agent position"
    assert agent.current_path[-1] == goal, f"Path should end at goal {goal}"
    
    # Verify alternative paths were calculated
    assert len(agent.alternative_paths) >= 1, f"Should have at least 1 alternative path, got {len(agent.alternative_paths)}"
    
    # Verify path_index was reset
    assert agent.path_index == 0, "Path index should be reset to 0"
    assert agent.steps_without_moving == 0, "Steps without moving should be reset to 0"
    
    # Test that agent can propose movement
    movimiento = agent.proponer_movimiento(goal=goal, agent_positions=agent_positions)
    assert movimiento is not None, "Agent should propose a movement"
    assert isinstance(movimiento, tuple), "Movement should be a tuple"
    assert len(movimiento) == 2, "Movement should be (x, y)"
    
    # Clean up
    AgentExtendido.instances = []


def test_blockage_detection():
    """
    TEST 5: Blockage detection system
    Verifies that should_recalculate correctly detects blockages.
    """
    ff = Floor_field(width, height, puertas, obstaculos)
    ps = PathSelector(ff)
    
    start = (10, 10)
    goal = puertas[0]
    
    # Get a path first
    path = ps.encontrar_ruta_a_star(start, goal)
    assert path is not None, "Should find a path"
    
    # Test: No blockage - should not recalculate
    agent_positions = {}
    should_recalc = ps.should_recalculate(
        agent_pos=start,
        current_path=path,
        path_index=0,
        agent_positions=agent_positions,
        steps_without_moving=0
    )
    assert not should_recalc, "Should not recalculate with no blockage"
    
    # Test: Immediate blockage (>= 2 agents in next cell)
    if len(path) > 1:
        next_cell = path[1]
        agent_positions[next_cell] = 2
        should_recalc = ps.should_recalculate(
            agent_pos=start,
            current_path=path,
            path_index=0,
            agent_positions=agent_positions,
            steps_without_moving=0
        )
        assert should_recalc, "Should recalculate with immediate blockage"
    
    # Test: Stagnation (steps_without_moving >= 3)
    agent_positions = {}
    should_recalc = ps.should_recalculate(
        agent_pos=start,
        current_path=path,
        path_index=0,
        agent_positions=agent_positions,
        steps_without_moving=3
    )
    assert should_recalc, "Should recalculate after stagnation"
    
    # Test: Invalid path (path_index >= len(path))
    should_recalc = ps.should_recalculate(
        agent_pos=start,
        current_path=path,
        path_index=len(path),
        agent_positions=agent_positions,
        steps_without_moving=0
    )
    assert should_recalc, "Should recalculate with invalid path index"


def test_path_cost_calculation():
    """
    TEST 6: Path cost calculation
    Verifies that get_path_cost correctly calculates path costs.
    """
    ff = Floor_field(width, height, puertas, obstaculos)
    ps = PathSelector(ff)
    
    start = (10, 10)
    goal = puertas[0]
    path = ps.encontrar_ruta_a_star(start, goal)
    
    assert path is not None, "Should find a path"
    
    # Test cost without congestion
    agent_positions = {}
    cost_no_congestion = ps.get_path_cost(path, agent_positions)
    assert cost_no_congestion > 0, "Path cost should be positive"
    
    # Test cost with congestion
    agent_positions = {path[5]: 2, path[10]: 1}  # Add congestion at some cells
    cost_with_congestion = ps.get_path_cost(path, agent_positions)
    assert cost_with_congestion > cost_no_congestion, "Cost should increase with congestion"
    
    # Test that cost is reasonable (should be at least path length)
    assert cost_no_congestion >= len(path) * 0.5, f"Cost should be reasonable, got {cost_no_congestion}"


if __name__ == "__main__":
    # Run tests if executed directly
    pytest.main([__file__, "-v"])

