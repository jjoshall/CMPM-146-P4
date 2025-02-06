# Heuristic Optimization in autoHTN.py
The heuristic in autoHTN.py optimizes HTN planning by pruning inefficient branches and preventing redundant actions. It follows these key rules:
1. Avoid Duplicate Tool Creation - Skips crafting tools if already owned.
2. Optimize Wood Gathering - Avoids making a wooden axe unless >5 wood is needed.
3. Optimize Stone Pickaxe Creation - Skips crafting unless explicitly required or >5 cobblestone is needed.
4. Prevent Infinite Loops - Stops cyclic dependencies in tool requirements.
