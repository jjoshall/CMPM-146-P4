import pyhop
import json

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
	# prune search branch if heuristic() returns True
	# do not change parameters to heuristic(), but can add more heuristic functions with the same parameters: 
	# e.g. def heuristic2(...); pyhop.add_check(heuristic2)
	def heuristic(state, curr_task, tasks, plan, depth, calling_stack):
		# Custom heuristic logic can go here (optional)
		return False  # Returning True prunes this branch

	pyhop.add_check(heuristic)

def set_up_state(data, ID, time=0):
    """Initializes Pyhop state based on a JSON problem description."""
    state = pyhop.State('state')
    state.time = {ID: time}

    # Initialize items and tools to zero
    for item in data['Items']:
        setattr(state, item, {ID: 0})

    for tool in data['Tools']:
        setattr(state, tool, {ID: 0})

    # Assign initial values from JSON
    if 'Initial' in data:
        for item, num in data['Initial'].items():
            setattr(state, item, {ID: num})

    return state

def set_up_goals(data, ID):
	# Creates a list of goals for the planner.
	goals = []
	for item, num in data['Goal'].items():
		goals.append(('have_enough', ID, item, num))

	return goals

if __name__ == '__main__':
	rules_filename = 'crafting.json'

	with open(rules_filename) as f:
		data = json.load(f)

	# If there are multiple problems in the JSON, iterate over them
	if "Problems" in data:
		for i, problem in enumerate(data["Problems"]):
			print(f"\n*** Solving Problem {i + 1} ***\n")
			state = set_up_state(problem, 'agent', time=problem.get('Time', 239))
			goals = set_up_goals(problem, 'agent')

			declare_operators(data)
			declare_methods(data)
			add_heuristic(data, 'agent')

			print(f"Initial State: {state.__dict__}")
			print(f"Goals: {goals}\n")

			# Solve the problem
			pyhop.pyhop(state, goals, verbose=1)
	else:
		state = set_up_state(data, 'agent', time=data.get('Time', 239))
		goals = set_up_goals(data, 'agent')

		declare_operators(data)
		declare_methods(data)
		add_heuristic(data, 'agent')

		print(f"Initial State: {state.__dict__}")
		print(f"Goals: {goals}\n")

		# Solve the problem
		pyhop.pyhop(state, goals, verbose=1)