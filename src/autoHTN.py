import pyhop
import json
import time

def check_enough(state, ID, item, num):
	if getattr(state, item)[ID] >= num: return []
	return False

def produce_enough(state, ID, item, num):
	return [('produce', ID, item), ('have_enough', ID, item, num)]

pyhop.declare_methods('have_enough', check_enough, produce_enough)

def produce(state, ID, item):
	return [('produce_{}'.format(item), ID)]

pyhop.declare_methods('produce', produce)

def make_method(name, rule):
	# Creates an HTN method for producing an item based on the crafting rules.
	def method(state, ID):
		subtasks = []

		# Step 1: Check if we have the required tools
		if "Requires" in rule:
			for req_item, req_amt in rule["Requires"].items():
				if getattr(state, req_item)[ID] < req_amt:
					subtasks.append(('have_enough', ID, req_item, req_amt))

		# Step 2: Check if we have enough ingredients (Consumed items)
		if "Consumes" in rule:
			for c_item, c_amt in rule["Consumes"].items():
				subtasks.append(('have_enough', ID, c_item, c_amt))

		# Step 3: Apply the operation (recipe execution)
		subtasks.append(('op_' + name, ID))

		return subtasks

	return method

def declare_methods(data):
	# Reads crafting recipes from JSON and declares methods dynamically.
	methods = {}  # Store methods for each produced item

	# Extract recipes and sort by time efficiency (shortest first)
	sorted_recipes = sorted(data['Recipes'].items(), key=lambda r: r[1]['Time'])

	# Iterate through sorted recipes and create methods
	for recipe_name, rule in sorted_recipes:
		for item in rule['Produces']:
			# Create the method for this item
			new_method = make_method(recipe_name, rule)

			# Add to the list of methods for the item
			if item in methods:
				methods[item].append(new_method)
			else:
				methods[item] = [new_method]

	# Declare the generated methods for each item in Pyhop
	for item, method_list in methods.items():
		pyhop.declare_methods(f'produce_{item}', *method_list)

def make_operator(rule):
	# Creates a Pyhop operator (low-level action) based on a crafting recipe.
	def operator(state, ID):
		# 1: Check if there is enough time
		if state.time[ID] < rule['Time']:
			return False

		# 2: Check "Requires" field
		if "Requires" in rule:
			for req_item, req_amt in rule['Requires'].items():
				if getattr(state, req_item)[ID] < req_amt:
					return False

		# 3: Check "Consumes" field
		if "Consumes" in rule:
			for c_item, c_amt in rule['Consumes'].items():
				if getattr(state, c_item)[ID] < c_amt:
					return False

		# 4: Apply the recipe
		state.time[ID] -= rule['Time']  # Deduct time

		# Consume items
		if "Consumes" in rule:
			for c_item, c_amt in rule['Consumes'].items():
				getattr(state, c_item)[ID] -= c_amt

		# Produce items
		for p_item, p_amt in rule['Produces'].items():
			getattr(state, p_item)[ID] += p_amt

		return state

	return operator

def declare_operators(data):
	# Reads crafting recipes and declares operators dynamically.
	ops = []
	for recipe_name, rule in data['Recipes'].items():
		op = make_operator(rule)

		# Give the operator a meaningful name
		op.__name__ = 'op_' + recipe_name
		ops.append(op)

	pyhop.declare_operators(*ops)

def add_heuristic(data, ID):
	# Prunes search branches based on a heuristic function.
	# Track when search starts
	start_time = time.time()
	def heuristic(state, curr_task, tasks, plan, depth, calling_stack):
		# Heuristic that prevents infinite regression and optimize search
		max_depth = 50 # Maximum depth to search
		time_limit = 30 # Stop searching after 30 seconds

		# 1: Prevent excessive depth
		if depth > max_depth:
			return True
		
		# 2: Stop if seach takes too long
		if time.time() - start_time > time_limit:
			return True
		
		# 3: Prune unproductive branches
		if curr_task[0] == 'produce':
			item = curr_task[2]

			# If item is already being produced in calling_stack, prevent loops
			if item in [task[2] for task in calling_stack if task[0] == 'produce']:
				return True
			
			# If item cannot be obtained within a reasonable time, prune
			if state.time[ID] < 0:
				return True
		return False  # Returning True prunes this branch

	pyhop.add_check(heuristic)

def set_up_state(data, test_data, ID, time=0):
    # Initializes Pyhop state based on crafting.json and the test case.
    state = pyhop.State('state')
    state.time = {ID: time}

    # Initialize items and tools to zero
    for item in data['Items']:
        setattr(state, item, {ID: 0})

    for tool in data['Tools']:
        setattr(state, tool, {ID: 0})

    # Assign initial values from JSON
    if 'Initial' in test_data:
        for item, num in test_data['Initial'].items():
            if hasattr(state, item):  # Ensure it's a valid item/tool
                getattr(state, item)[ID] = num
            else:
                print(f"Warning: '{item}' in test case not found in crafting.json.")

    return state

def set_up_goals(test_data, ID):
	# Creates a list of goals for the planner.
	goals = []
	for item, num in test_data['Goal'].items():
		goals.append(('have_enough', ID, item, num))

	return goals

if __name__ == '__main__':
	test_cases = [
		{"Initial": {"plank": 1}, "Goal": {"plank": 1}, "Time": 0},   # (a)
        {"Initial": {}, "Goal": {"plank": 1}, "Time": 300},           # (b)
        {"Initial": {"plank": 3, "stick": 2}, "Goal": {"wooden_pickaxe": 1}, "Time": 10}, # (c)
        {"Initial": {}, "Goal": {"iron_pickaxe": 1}, "Time": 100},    # (d)
        #{"Initial": {}, "Goal": {"cart": 1, "rail": 10}, "Time": 175},# (e)
        #{"Initial": {}, "Goal": {"cart": 1, "rail": 20}, "Time": 250} # (f)
	]

	rules_filename = 'crafting.json'

	with open(rules_filename) as f:
		data = json.load(f)

	# Declare operators and methods
	declare_operators(data)
	declare_methods(data)

	for i, test in enumerate(test_cases):
		print(f"Test Case {chr(97 + i)}:")

		# Set up initial state and goals
		state = set_up_state(data, test, 'agent', time=test['Time'])
		goals = set_up_goals(test, 'agent')

		# Add heuristic to prune search branches
		add_heuristic(data, 'agent')

		print(f"Initial State: {state.__dict__}")
		print(f"Goals: {goals}\n")

		# Run the planner
		solution = pyhop.pyhop(state, goals, verbose=3)

		# Print the solution
		if solution is not False:
			print(f"Test Case {chr(97 + i)} Solved\n")
		else:
			print(f"Test Case {chr(97 + i)} Failed\n")