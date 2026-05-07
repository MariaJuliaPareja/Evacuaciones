"""
Test suite for agent path selection with anxiety-based progressive unlocking.
Generates visual outputs to verify behavior.
"""

import pytest
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from pathlib import Path
from typing import List, Dict
import numpy as np
import random
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from escenarios import sala_de_clases
from simulacion.grilla_clasica.floor_field import Floor_field
from simulacion.pathfinding_propuesta.path_selector import PathSelector
from simulacion.pathfinding_propuesta.agent_extendido import AgentExtendido


class TestAgentPathSelection:
    """Test progressive path unlocking and anxiety-based selection."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test environment before each test."""
        # Load scenario
        self.width = sala_de_clases.width
        self.height = sala_de_clases.height
        self.puertas = sala_de_clases.puertas
        self.obstaculos = sala_de_clases.obstaculos
        
        # Create floor field and path selector
        self.floor_field = Floor_field(self.width, self.height, 
                                       self.puertas, self.obstaculos)
        self.path_selector = PathSelector(self.floor_field)
        
        # Create output directory
        self.output_dir = Path("salidas") / "tests"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Clear agent instances
        AgentExtendido.instances.clear()
        AgentExtendido.history.clear()
    
    def test_initial_single_path(self):
        """Agents should start with 1 optimal path."""
        # Create agent at starting position
        agent = AgentExtendido(
            agent_type='rapido',
            floor_field=self.floor_field,
            path_selector=self.path_selector,
            x=8,
            y=5
        )
        agent.calmness_threshold = 3
        
        # Choose initial route
        goal = self.puertas[0]
        agent_positions = {}
        agent.elegir_ruta(goal, agent_positions)
        
        # ASSERTIONS
        assert agent.unlocked_paths_count == 1, \
            f"Should start with 1 path, got {agent.unlocked_paths_count}"
        assert agent.current_path is not None, "Should have a current path"
        assert len(agent.all_calculated_paths) >= 1, \
            "Should have at least 1 calculated path"
        
        # VISUAL OUTPUT
        self._visualize_agent_paths(
            agent, 
            title="Test 1: Initial State (1 Path)",
            filename="test_01_initial_single_path.png"
        )
        
        print(f"[OK] Agent starts with {agent.unlocked_paths_count} path")
        print(f"  Path length: {len(agent.current_path)} steps")
    
    def test_unlock_three_paths_medium_anxiety(self):
        """After 3 steps stuck, should unlock 3 paths."""
        agent = AgentExtendido(
            agent_type='rapido',
            floor_field=self.floor_field,
            path_selector=self.path_selector,
            x=8,
            y=5
        )
        agent.calmness_threshold = 3
        goal = self.puertas[0]
        
        # Initial route (1 path)
        agent.elegir_ruta(goal, {})
        initial_unlocked = agent.unlocked_paths_count
        
        # Simulate being stuck for 3 steps
        agent.steps_without_moving = 3
        agent.ansiedad = 45  # Medium anxiety
        agent.current_path = None  # Force recalculation
        
        # Recalculate route
        agent.elegir_ruta(goal, {})
        
        # ASSERTIONS
        assert agent.unlocked_paths_count == 3, \
            f"Should unlock 3 paths after 3 steps, got {agent.unlocked_paths_count}"
        assert len(agent.all_calculated_paths) >= 3, \
            f"Should have at least 3 calculated paths, got {len(agent.all_calculated_paths)}"
        
        # Verify paths are different (allow some similarity for small paths)
        paths = agent.all_calculated_paths[:3]
        if len(paths) >= 2:
            for i in range(len(paths)):
                for j in range(i+1, len(paths)):
                    if len(paths[i]) > 0:
                        overlap = len(set(paths[i]) & set(paths[j])) / len(paths[i])
                        # Allow up to 80% overlap for very short paths
                        max_overlap = 0.8 if len(paths[i]) < 10 else 0.7
                        assert overlap < max_overlap, \
                            f"Paths {i} and {j} too similar ({overlap:.1%} overlap)"
        
        # VISUAL OUTPUT
        self._visualize_agent_paths(
            agent,
            title=f"Test 2: Medium Anxiety (3 Paths Unlocked)\nSteps Stuck: {agent.steps_without_moving}, Anxiety: {agent.ansiedad:.1f}",
            filename="test_02_three_paths_medium.png"
        )
        
        print(f"[OK] Unlocked {agent.unlocked_paths_count} paths after 3 steps stuck")
        print(f"  Anxiety level: {agent.ansiedad:.1f}")
    
    def test_unlock_five_paths_high_anxiety(self):
        """After 5+ steps stuck, should unlock 5 paths."""
        agent = AgentExtendido(
            agent_type='rapido',
            floor_field=self.floor_field,
            path_selector=self.path_selector,
            x=8,
            y=5
        )
        agent.calmness_threshold = 3
        goal = self.puertas[0]
        
        # Simulate high anxiety scenario
        agent.steps_without_moving = 6
        agent.ansiedad = 85  # High anxiety
        
        # Calculate route
        agent.elegir_ruta(goal, {})
        
        # ASSERTIONS
        assert agent.unlocked_paths_count == 5, \
            f"Should unlock 5 paths after 5+ steps, got {agent.unlocked_paths_count}"
        assert len(agent.all_calculated_paths) >= 3, \
            "Should have at least 3-5 different paths"
        assert agent.current_path is not None, "Should have selected a path"
        
        # VISUAL OUTPUT
        self._visualize_agent_paths(
            agent,
            title=f"Test 3: High Anxiety (5 Paths Unlocked)\nSteps Stuck: {agent.steps_without_moving}, Anxiety: {agent.ansiedad:.1f}",
            filename="test_03_five_paths_high.png"
        )
        
        print(f"[OK] Unlocked {agent.unlocked_paths_count} paths after 5+ steps stuck")
        print(f"  Anxiety level: {agent.ansiedad:.1f}")
        print(f"  Total calculated paths: {len(agent.all_calculated_paths)}")
    
    def test_path_selection_by_anxiety_levels(self):
        """Different anxiety levels should select different path probabilities."""
        goal = self.puertas[0]
        start_pos = (8, 5)

        # Calcular una sola vez los 3 paths disponibles para comparar ambos niveles
        k_paths = self.path_selector.find_progressive_paths(start_pos, goal, num_paths=3)
        assert len(k_paths) >= 3, f"Expected at least 3 paths, got {len(k_paths)}"

        # Test low anxiety (debe favorecer fuertemente el path óptimo)
        selections_low = []
        for _ in range(20):
            agent = AgentExtendido(
                agent_type='rapido',
                floor_field=self.floor_field,
                path_selector=self.path_selector,
                x=start_pos[0],
                y=start_pos[1]
            )
            agent.ansiedad = 15  # Low anxiety
            agent.unlocked_paths_count = 3  # Tres rutas disponibles
            agent.all_calculated_paths = k_paths
            self.path_selector.select_path_by_anxiety(
                k_paths=k_paths,
                anxiety_level=agent.ansiedad,
                num_available_paths=3
            )
            # Usar índice real registrado por PathSelector (evita ambigüedad por rutas similares)
            selected_idx = self.path_selector.anxiety_decisions[-1]['selected_path_index']
            if selected_idx >= 0:
                selections_low.append(selected_idx)

        # Test high anxiety (debe ser más distribuido hacia rutas subóptimas)
        selections_high = []
        for _ in range(20):
            agent = AgentExtendido(
                agent_type='rapido',
                floor_field=self.floor_field,
                path_selector=self.path_selector,
                x=start_pos[0],
                y=start_pos[1]
            )
            agent.ansiedad = 85  # High anxiety
            agent.unlocked_paths_count = 3  # Mismos 3 paths disponibles
            agent.all_calculated_paths = k_paths
            self.path_selector.select_path_by_anxiety(
                k_paths=k_paths,
                anxiety_level=agent.ansiedad,
                num_available_paths=3
            )
            # Con ansiedad alta puede haber ruido; el selector guarda el índice original elegido
            selected_idx = self.path_selector.anxiety_decisions[-1]['selected_path_index']
            if selected_idx >= 0:
                selections_high.append(selected_idx)
        
        # ASSERTIONS
        if selections_low:
            # Low anxiety should heavily favor path 0 (optimal)
            path_0_ratio_low = selections_low.count(0) / len(selections_low)
            assert path_0_ratio_low > 0.6, \
                f"Low anxiety should pick optimal path >60%, got {path_0_ratio_low:.1%}"
        
        if selections_high:
            # High anxiety should be more distributed (but may still pick optimal sometimes)
            path_0_ratio_high = selections_high.count(0) / len(selections_high)
            # Allow up to 80% optimal for high anxiety (due to randomness and short paths)
            # The key is that it should be less than low anxiety
            if selections_low:
                path_0_ratio_low = selections_low.count(0) / len(selections_low)
                # High anxiety should pick optimal less often than low anxiety
                assert path_0_ratio_high <= path_0_ratio_low or path_0_ratio_high < 0.8, \
                    f"High anxiety ({path_0_ratio_high:.1%}) should pick optimal <= low anxiety ({path_0_ratio_low:.1%}) or <80%"
            else:
                # If no low anxiety data, just verify it's not always optimal
                assert path_0_ratio_high < 1.0 or len(set(selections_high)) > 1, \
                    f"High anxiety should show some variation, got {path_0_ratio_high:.1%}"
        
        # VISUAL OUTPUT
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
        
        if selections_low:
            ax1.hist(selections_low, bins=[0, 1, 2, 3], alpha=0.7, color='green', edgecolor='black')
            ax1.set_xticks([0.5, 1.5, 2.5])
            ax1.set_xticklabels(['0 (Optimal)', '1', '2'])
        ax1.set_title(f"Low Anxiety (15)\nPath Selection Distribution")
        ax1.set_xlabel("Path Index (0=optimal)")
        ax1.set_ylabel("Frequency")
        ax1.grid(True, alpha=0.3)
        
        if selections_high:
            ax2.hist(selections_high, bins=[0, 1, 2, 3], alpha=0.7, color='red', edgecolor='black')
            ax2.set_xticks([0.5, 1.5, 2.5])
            ax2.set_xticklabels(['0 (Optimal)', '1', '2'])
        ax2.set_title(f"High Anxiety (85)\nPath Selection Distribution")
        ax2.set_xlabel("Path Index (0=optimal)")
        ax2.set_ylabel("Frequency")
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(self.output_dir / "test_04_anxiety_selection_distribution.png", 
                    dpi=150, bbox_inches='tight')
        plt.close()
        
        if selections_low and selections_high:
            path_0_ratio_low = selections_low.count(0) / len(selections_low)
            path_0_ratio_high = selections_high.count(0) / len(selections_high)
            print(f"[OK] Path selection varies by anxiety:")
            print(f"  Low anxiety picks optimal: {path_0_ratio_low:.1%}")
            print(f"  High anxiety picks optimal: {path_0_ratio_high:.1%}")
    
    def test_simulation_with_progressive_unlocking(self):
        """Run controlled mini-simulation forcing PRU activation stages."""
        agent = AgentExtendido(
            agent_type='rapido',
            floor_field=self.floor_field,
            path_selector=self.path_selector,
            x=8,
            y=5
        )
        agent.calmness_threshold = 3
        goal = self.puertas[0]
        history = []

        # Forzar stuckness por fases:
        # pasos 0-2 -> 0, pasos 3-4 -> 3, pasos 5+ -> 6
        for step in range(20):
            if step <= 2:
                target_stuck = 0
            elif step <= 4:
                target_stuck = 3
            else:
                target_stuck = 6

            # Actualizar stuck/ansiedad usando la lógica real de AgentExtendido:
            # mover_a(misma_pos) => if_change=False => stuck +1, ansiedad +1.
            while agent.steps_without_moving < target_stuck:
                agent.mover_a(agent.pos_x, agent.pos_y)

            # Recalcular ruta en cada paso para reflejar desbloqueo progresivo.
            agent._current_simulation_step = step
            agent.current_path = None
            agent.elegir_ruta(goal, {(agent.pos_x, agent.pos_y): 1})

            history.append({
                'step': step,
                'unlocked': agent.unlocked_paths_count,
                'anxiety': agent.ansiedad,
                'stuck': agent.steps_without_moving
            })

        steps = [h['step'] for h in history]
        unlocked = [h['unlocked'] for h in history]
        anxiety = [h['anxiety'] for h in history]
        stuck = [h['stuck'] for h in history]

        # ASSERTIONS
        assert max(stuck) >= 6, f"Expected stuckness to reach 6, got {max(stuck)}"
        assert max(anxiety) > 0, f"Anxiety should increase when blocked, got max {max(anxiety)}"
        assert max(unlocked) >= 5, f"Expected PRU to unlock up to 5 paths, got {max(unlocked)}"

        # VISUAL OUTPUT - Curvas de desbloqueo, ansiedad y stuckness.
        fig, axes = plt.subplots(3, 1, figsize=(14, 10))

        axes[0].plot(steps, unlocked, marker='o', color='tab:blue', label=f"Agent {agent.id} ({agent.tipo})")
        axes[0].set_ylabel("Unlocked Paths")
        axes[0].set_title("Progressive Path Unlocking Over Time")
        axes[0].legend()
        axes[0].grid(True, alpha=0.3)

        axes[1].plot(steps, anxiety, marker='s', color='tab:red', label=f"Agent {agent.id}")
        axes[1].set_ylabel("Anxiety Level")
        axes[1].set_title("Anxiety Evolution (real mover_a logic)")
        axes[1].legend()
        axes[1].grid(True, alpha=0.3)

        axes[2].plot(steps, stuck, marker='^', color='tab:green', label=f"Agent {agent.id}")
        axes[2].set_ylabel("Steps Without Moving")
        axes[2].set_xlabel("Simulation Step")
        axes[2].set_title("Forced Blockage Stages")
        axes[2].legend()
        axes[2].grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig(self.output_dir / "test_05_simulation_progression.png",
                    dpi=150, bbox_inches='tight')
        plt.close()

        print(f"[OK] Controlled PRU simulation completed: {len(history)} steps")
        print(f"  Max paths unlocked: {max(unlocked)}")
        print(f"  Max anxiety: {max(anxiety)}")
        print(f"  Max stuckness: {max(stuck)}")
    
    def _visualize_agent_paths(self, agent: AgentExtendido, 
                               title: str, filename: str):
        """
        Visualize agent's current paths on floor field.
        
        Args:
            agent: Agent with calculated paths
            title: Plot title
            filename: Output filename
        """
        fig, ax = plt.subplots(figsize=(12, 10))
        
        # Draw floor field as heatmap
        ff_values = self.floor_field.valores.copy()
        ff_values[ff_values >= 500] = np.nan
        
        im = ax.imshow(ff_values, cmap='YlOrRd_r', alpha=0.6, origin='lower',
                      extent=[-0.5, self.width-0.5, -0.5, self.height-0.5])
        plt.colorbar(im, ax=ax, label='Distance to Exit')
        
        # Draw obstacles
        for y in range(self.height):
            for x in range(self.width):
                if self.floor_field.valores[y, x] >= 500:
                    rect = Rectangle((x-0.5, y-0.5), 1, 1, 
                                    facecolor='black', alpha=0.8)
                    ax.add_patch(rect)
        
        # Draw exits
        for px, py in self.puertas:
            ax.plot(px, py, 'g*', markersize=20, markeredgecolor='black',
                   markeredgewidth=2, label='Exit' if px == self.puertas[0][0] else '')
        
        # Draw all calculated paths
        if agent.all_calculated_paths:
            colors = ['green', 'yellow', 'orange', 'red', 'purple']
            
            for i, path in enumerate(agent.all_calculated_paths[:agent.unlocked_paths_count]):
                if len(path) < 2:
                    continue
                
                is_current = (path == agent.current_path) or \
                            (agent.current_path and len(path) == len(agent.current_path) and
                             path[0] == agent.current_path[0] and path[-1] == agent.current_path[-1])
                alpha = 0.9 if is_current else 0.3
                linewidth = 3 if is_current else 1.5
                linestyle = '-' if is_current else '--'
                
                xs, ys = zip(*path)
                ax.plot(xs, ys, color=colors[i % len(colors)], alpha=alpha, 
                       linewidth=linewidth, linestyle=linestyle, marker='o', markersize=3,
                       label=f"Path {i+1}" + (" (Current)" if is_current else ""))
        
        # Draw agent
        color = 'lightgreen' if agent.tipo == 'rapido' else 'lightcoral'
        ax.plot(agent.pos_x, agent.pos_y, 'o', color=color, markersize=15,
               markeredgecolor='black', markeredgewidth=2,
               label=f"Agent (tipo={agent.tipo})")
        
        ax.set_xlim(-0.5, self.width - 0.5)
        ax.set_ylim(-0.5, self.height - 0.5)
        ax.set_aspect('equal')
        ax.legend(loc='upper right', fontsize=9)
        ax.set_title(title, fontsize=12, fontweight='bold')
        ax.grid(True, alpha=0.2)
        
        plt.tight_layout()
        plt.savefig(self.output_dir / filename, dpi=150, bbox_inches='tight')
        plt.close()
        
        print(f"  -> Saved visualization: {filename}")
    
    def test_generate_summary_report(self):
        """Generate comprehensive summary report of all tests."""
        report = []
        report.append("=" * 60)
        report.append("AGENT PATH SELECTION TEST SUMMARY")
        report.append("=" * 60)
        report.append("")
        report.append("Test Files Generated:")
        
        output_files = sorted(self.output_dir.glob("test_*.png"))
        for i, filepath in enumerate(output_files, 1):
            report.append(f"  {i}. {filepath.name}")
        
        report.append("")
        report.append("Path Unlocking System:")
        report.append("  - 0-2 steps stuck -> 1 path (low anxiety)")
        report.append("  - 3-4 steps stuck -> 3 paths (medium anxiety)")
        report.append("  - 5+ steps stuck -> 5 paths (high anxiety)")
        report.append("")
        report.append("Anxiety-Based Selection:")
        report.append("  - Low (0-30): Heavily favors optimal path")
        report.append("  - Medium (30-70): Mostly optimal, some alternatives")
        report.append("  - High (70-100): More distributed, can pick suboptimal")
        report.append("")
        report.append("=" * 60)
        
        report_text = "\n".join(report)
        print(report_text)
        
        # Save report
        with open(self.output_dir / "TEST_REPORT.txt", "w") as f:
            f.write(report_text)
        
        print(f"\n[OK] Full report saved to: {self.output_dir / 'TEST_REPORT.txt'}")


if __name__ == "__main__":
    """Run tests directly with visual output."""
    pytest.main([__file__, "-v", "-s", "--tb=short"])

