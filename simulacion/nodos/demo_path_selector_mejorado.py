"""
demo_path_selector_mejorado.py
Demonstrates the complete PathSelector system with anxiety-based routing.
"""

import sys
import os
import matplotlib.pyplot as plt

# Add parent directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

try:
    from escenarios.sala_de_clases import width, height, puertas, obstaculos, agentes
    from simulacion.grilla.floor_field import Floor_field
    from simulacion.nodos.path_selector import PathSelector
except ImportError as e:
    print(f"Import error: {e}")
    print("Creating mock data for demonstration...")
    
    # Mock data if imports fail
    width, height = 20, 20
    puertas = [(18, 18)]
    obstaculos = [(5, 5), (5, 6), (6, 5), (6, 6), 
                  (10, 10), (10, 11), (11, 10), (11, 11)]
    agentes = [(2, 2)]


def visualize_paths(ff, k_paths, selected_path, anxiety_level, filename):
    """
    Visualizes the 3 alternative paths and the selected one.
    
    Args:
        ff: Floor_field object
        k_paths: List of 3 alternative paths
        selected_path: The selected path
        anxiety_level: Anxiety level for title
        filename: Output filename
    """
    # Map anxiety level to category
    if anxiety_level <= 30:
        anxiety_category = "Low Anxiety (0-30)"
    elif anxiety_level <= 70:
        anxiety_category = "Optimal Anxiety (30-70)"
    else:
        anxiety_category = "High Anxiety (70-100)"
    
    fig, ax = plt.subplots(figsize=(12, 10))
    
    # Create grid background
    for y in range(height):
        for x in range(width):
            # Draw grid cells
            ax.add_patch(plt.Rectangle((x-0.5, y-0.5), 1, 1, 
                                      fill=True, alpha=0.05, 
                                      edgecolor='gray', linewidth=0.5))
    
    # Obstacles
    for ox, oy in obstaculos:
        ax.add_patch(plt.Rectangle((ox-0.5, oy-0.5), 1, 1, 
                                  fill=True, color='black', alpha=0.7))
    
    # Doors
    for px, py in puertas:
        ax.add_patch(plt.Rectangle((px-0.5, py-0.5), 1, 1, 
                                  fill=True, color='green', alpha=0.8))
    
    # The 3 paths in different colors
    colors = ['green', 'orange', 'purple']
    labels = ['Optimal', 'Medium', 'Suboptimal']
    
    for i, (path, color, label) in enumerate(zip(k_paths, colors, labels)):
        if len(path) > 0:
            xs, ys = zip(*path)
            ax.plot(xs, ys, color=color, linewidth=3, 
                   label=label, alpha=0.7, marker='o', markersize=4,
                   linestyle='--' if i > 0 else '-')
    
    # Highlight the selected path
    if selected_path and len(selected_path) > 0:
        xs, ys = zip(*selected_path)
        ax.plot(xs, ys, color='red', linewidth=5, 
               label='Selected', alpha=0.8, marker='s', markersize=6)
    
    # Start and end points
    if len(k_paths) > 0 and len(k_paths[0]) > 0:
        start_x, start_y = k_paths[0][0]
        ax.plot(start_x, start_y, 'bo', markersize=15, label='Start', alpha=0.8)
        
        for px, py in puertas:
            ax.plot(px, py, 'g^', markersize=15, label='Door', alpha=0.8)
    
    ax.set_xlim(-0.5, width - 0.5)
    ax.set_ylim(-0.5, height - 0.5)
    ax.set_aspect('equal')
    ax.invert_yaxis()  # Matplotlib has inverted y-axis
    
    # Create title with anxiety info
    title = f'A* Alternative Routes - {len(k_paths)} paths\n'
    title += f'Anxiety Level: {anxiety_level} ({anxiety_category})'
    
    if selected_path:
        title += f'\nSelected Path Length: {len(selected_path)}'
    
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.set_xlabel('X Coordinate')
    ax.set_ylabel('Y Coordinate')
    ax.grid(True, alpha=0.3)
    
    # Custom legend to avoid duplicates
    handles, labels = ax.get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    ax.legend(by_label.values(), by_label.keys(), loc='upper right')
    
    # Save figure
    output_dir = os.path.dirname(__file__)
    output_path = os.path.join(output_dir, filename)
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"Saved visualization to: {output_path}")
    plt.close()


def main():
    """Main demonstration function"""
    print("=" * 60)
    print("DEMONSTRATION: PathSelector with Anxiety-Based Routing")
    print("=" * 60)
    
    try:
        # Setup
        print("\n1. Loading scenario from escenarios/...")
        ff = Floor_field(width, height, puertas, obstaculos)
        ps = PathSelector(ff)
        
        # Start and goal positions
        start = agentes[0] if isinstance(agentes[0], tuple) else (2, 2)
        goal = puertas[0]
        
        print(f"Start position: {start}")
        print(f"Goal position: {goal}")
        print(f"Floor field size: {width}x{height}")
        
        # Simulate different anxiety levels
        anxiety_levels = [20, 50, 85]  # Mild, Optimal, High
        filenames = ['rutas_ansiedad_baja.png', 
                    'rutas_ansiedad_media.png', 
                    'rutas_ansiedad_alta.png']
        
        for anxiety_level, filename in zip(anxiety_levels, filenames):
            print(f"\n{'='*40}")
            print(f"ANXIETY LEVEL: {anxiety_level}")
            print(f"{'='*40}")
            
            # Find 3 alternative paths
            print("Finding 3 alternative paths...")
            k_paths = ps.find_k_paths(start, goal, k=3)
            
            print(f"Paths found: {len(k_paths)}")
            for i, path in enumerate(k_paths):
                print(f"  Path {i+1}: Length = {len(path)} cells")
            
            # Select based on anxiety
            print("Selecting path based on anxiety...")
            selected_path = ps.select_path_by_anxiety(k_paths, anxiety_level)
            
            # Report statistics
            print(f"\nPATH SELECTION RESULT:")
            print(f"Anxiety Level: {anxiety_level}")
            print(f"Selected Path Index: {k_paths.index(selected_path) if selected_path in k_paths else 'N/A'}")
            print(f"Selected Path Length: {len(selected_path)}")
            
            # Calculate path diversity
            if len(k_paths) >= 2:
                # Simple diversity measure: compare first two paths
                set1 = set(k_paths[0])
                set2 = set(k_paths[1])
                common = len(set1.intersection(set2))
                total = len(set1.union(set2))
                diversity = 1 - (common / total) if total > 0 else 0
                print(f"Path diversity (between optimal and medium): {diversity:.2%}")
            
            # Visualize
            print(f"\nGenerating visualization: {filename}")
            visualize_paths(ff, k_paths, selected_path, anxiety_level, filename)
        
        # Demonstrate blockage detection
        print(f"\n{'='*40}")
        print("BLOCKAGE DETECTION DEMONSTRATION")
        print(f"{'='*40}")
        
        # Simulate a blocked scenario
        agent_positions = {goal: 3}  # 3 agents at the goal
        print(f"Simulating blockage at goal: {goal}")
        
        should_recalc = ps.should_recalculate(
            agent_pos=start,
            current_path=k_paths[0] if k_paths else [],
            path_index=0,
            agent_positions=agent_positions,
            steps_without_moving=0
        )
        
        print(f"Should recalculate route? {should_recalc}")
        
        # Show cache statistics
        print(f"\n{'='*40}")
        print("CACHE STATISTICS")
        print(f"{'='*40}")
        print(f"Total calls: {ps.stats.get('calls', 0)}")
        print(f"Cache hits: {ps.stats.get('cache_hits', 0)}")
        print(f"Cache hit rate: {(ps.stats.get('cache_hits', 0) / ps.stats.get('calls', 1) * 100):.1f}%")
        
        print(f"\n{'='*60}")
        print("DEMONSTRATION COMPLETED SUCCESSFULLY")
        print(f"{'='*60}")
        print("\nGenerated files:")
        for filename in filenames:
            filepath = os.path.join(os.path.dirname(__file__), filename)
            print(f"  - {filepath}")
        
    except Exception as e:
        print(f"\nError during demonstration: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

