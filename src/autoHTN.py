import pyhop
import json
import time
from typing import Dict, List, Tuple

# Basic helper functions for checking and producing items
def check_enough(state, ID, item, num):
    """Check if we have enough of a specific item.
    Returns empty list if we have enough (success), False otherwise."""
    if getattr(state, item)[ID] >= num: return []
    return False

def produce_enough(state, ID, item, num):
    """Creates a sequence of tasks to produce an item and verify we have enough.
    First produces the item, then checks if we have enough."""
    return [('produce', ID, item), ('have_enough', ID, item, num)]

# Declare the basic methods to pyhop
pyhop.declare_methods('have_enough', check_enough, produce_enough)

def produce(state, ID, item):
    """Creates a task to produce a specific item using its recipe."""
    return [('produce_{}'.format(item), ID)]

pyhop.declare_methods('produce', produce)

def make_method(name, rule):
    """Creates an HTN method for producing an item based on crafting rules.
    
    Args:
        name: Name of the recipe
        rule: Dictionary containing recipe requirements and outputs
    """
    def method(state, ID):
        # Define priority order for gathering materials
        order = ['bench', 'furnace', 'ingot', 'ore', 'coal', 'cobble', 'stick', 'plank', 'wood', 
                'iron_axe', 'stone_axe', 'wooden_axe', 'iron_pickaxe', 'wooden_pickaxe', 'stone_pickaxe']
        
        # Combine both required tools and consumed materials
        needs = rule.get('Requires', {}) | rule.get('Consumes', {})
        
        # Create list to store subtasks
        subtasks = []
        
        # Sort items by their priority in the order list
        items = sorted(needs.items(), key=lambda x: order.index(x[0]))
        
        # Add subtask for each required item
        for item, amount in items:
            subtasks.append(('have_enough', ID, item, amount))
            
        # Finally, add the actual crafting operation
        subtasks.append((("op_" + name).replace(' ', '_'), ID))
        
        return subtasks
    return method

def declare_methods(data):
    """Declares all crafting methods to pyhop, sorted by time efficiency.
    
    Args:
        data: Dictionary containing all recipes and crafting rules
    """
    # Dictionary to store methods grouped by product
    methods = {}
    
    # Process each recipe
    for recipe_name, recipe_info in data['Recipes'].items():
        cur_time = recipe_info['Time']
        m = make_method(recipe_name, recipe_info)
        m.__name__ = recipe_name.replace(' ', '_')
        
        # Get the product name from the recipe
        cur_m = ("produce_" + list(recipe_info['Produces'].keys())[0]).replace(' ', '_')
        
        # Group methods by what they produce
        if cur_m not in methods:
            methods[cur_m] = [(m, cur_time)]
        else:
            methods[cur_m].append((m, cur_time))
    
    # Declare methods to pyhop, sorted by time (faster methods first)
    for m, info in methods.items():
        methods[m] = sorted(info, key=lambda x: x[1])
        pyhop.declare_methods(m, *[method[0] for method in methods[m]])

def make_operator(rule):
    """Creates a pyhop operator that represents a primitive crafting action.
    
    Args:
        rule: Dictionary containing recipe requirements and effects
    """
    def operator(state, ID):
        # First check: Do we have enough time?
        if state.time[ID] < rule['Time']:
            return False
            
        # Second check: Do we have required tools?
        if 'Requires' in rule:
            for item, amount in rule['Requires'].items():
                if getattr(state, item)[ID] < amount:
                    return False
                    
        # Third check: Do we have materials to consume?
        if 'Consumes' in rule:
            for item, amount in rule['Consumes'].items():
                if getattr(state, item)[ID] < amount:
                    return False
        
        # If all checks pass, execute the crafting:
        
        # 1. Use up time
        state.time[ID] -= rule['Time']
        
        # 2. Consume materials
        if 'Consumes' in rule:
            for item, amount in rule['Consumes'].items():
                cur_val = getattr(state, item)
                setattr(state, item, {ID: cur_val[ID] - amount})
        
        # 3. Produce new items
        for item, amount in rule['Produces'].items():
            cur_val = getattr(state, item)
            setattr(state, item, {ID: cur_val[ID] + amount})
            
        return state
    return operator

def declare_operators(data):
    """Creates and declares all operators to pyhop based on recipes.
    
    Args:
        data: Dictionary containing all recipes and crafting rules
    """
    ops = []
    for recipe_name, recipe_info in data['Recipes'].items():
        op = make_operator(recipe_info)
        op.__name__ = ("op_" + recipe_name).replace(' ', '_')
        ops.append(op)
    pyhop.declare_operators(*ops)

def add_heuristic(data, ID):
    """Adds search optimization heuristics to pyhop.
    Returns True to prune a search branch, False to continue exploring.
    
    Args:
        data: Dictionary containing crafting rules
        ID: Agent identifier
    """
    def heuristic(state, curr_task, tasks, plan, depth, calling_stack):
        # 1. Prevent duplicate tool creation
        if curr_task[0] == 'produce' and curr_task[2] in data['Tools']:
            if getattr(state, curr_task[2])[ID] > 0:
                return True
                
        # 2. Optimize wood gathering (don't make axe unless needed)
        if curr_task[0] == 'produce_wooden_axe':
            wood_needed = sum([task[3] for task in tasks if len(task) > 3 and task[2] == 'wood'])
            if wood_needed < 5 and 'wooden_axe' not in data['Goal']:
                return True
                
        # 3. Optimize stone pickaxe creation
        if curr_task[0] == 'produce_stone_pickaxe':
            if 'stone_pickaxe' not in data['Goal']:
                cobble_needed = sum([task[3] for task in tasks if len(task) > 3 and task[2] == 'cobble'])
                if cobble_needed < 5:
                    return True
                    
        # 4. Prevent infinite cycles in tool requirements
        if curr_task[0] == 'have_enough' and curr_task[2] in data['Tools']:
            if tasks.count(curr_task) > 1:
                return True
                
        return False
    
    pyhop.add_check(heuristic)

def set_up_state(data, test_case, ID, time=0):
    """Initialize the game state with items, tools, and initial resources.
    
    Args:
        data: Dictionary containing crafting rules
        test_case: Dictionary containing initial state
        ID: Agent identifier
        time: Time limit for crafting
    """
    state = pyhop.State('state')
    state.time = {ID: time}
    
    # Initialize everything to zero first
    for item in data['Items']:
        setattr(state, item, {ID: 0})
    for item in data['Tools']:
        setattr(state, item, {ID: 0})
    
    # Set initial quantities from test case
    for item, num in test_case['Initial'].items():
        setattr(state, item, {ID: num})
            
    return state

def set_up_goals(test_case, ID):
    """Convert goal state into planning goals.
    
    Args:
        test_case: Dictionary containing goal state
        ID: Agent identifier
    """
    return [('have_enough', ID, item, num) 
            for item, num in test_case['Goal'].items()]

def main():
    # Define all test cases
    test_cases = {
        'a': {"Initial": {"plank": 1}, "Goal": {"plank": 1}, "Time": 0},
        'b': {"Initial": {}, "Goal": {"plank": 1}, "Time": 300},
        'c': {"Initial": {"plank": 3, "stick": 2}, "Goal": {"wooden_pickaxe": 1}, "Time": 10},
        'd': {"Initial": {}, "Goal": {"iron_pickaxe": 1}, "Time": 100},
        'e': {"Initial": {}, "Goal": {"cart": 1, "rail": 10}, "Time": 175},
        'f': {"Initial": {}, "Goal": {"cart": 1, "rail": 20}, "Time": 250}
    }
    
    # Load crafting rules
    with open('crafting.json') as f:
        data = json.load(f)
        
    # Run each test case
    for case_name, test_case in test_cases.items():
        print(f"\n{'='*20} Test Case {case_name} {'='*20}")
        
        # Setup the problem
        state = set_up_state(data, test_case, 'agent', test_case['Time'])
        goals = set_up_goals(test_case, 'agent')
        
        # Reset planner for each test case
        declare_operators(data)
        declare_methods(data)
        add_heuristic(data, 'agent')
        
        # Print problem details
        print(f"Initial State: {test_case['Initial']}")
        print(f"Goals: {test_case['Goal']}")
        print(f"Time Limit: {test_case['Time']}\n")
        
        # Run planner and report result
        solution = pyhop.pyhop(state, goals, verbose=1)
        success = solution is not False
        print(f"Test Case {case_name}: {'SUCCESS' if success else 'FAILURE'}\n")

if __name__ == '__main__':
    main()