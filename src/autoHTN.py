import pyhop
import json

def check_enough (state, ID, item, num):
	if getattr(state,item)[ID] >= num: return []
	return False

def produce_enough (state, ID, item, num):
	return [('produce', ID, item), ('have_enough', ID, item, num)]

pyhop.declare_methods ('have_enough', check_enough, produce_enough)

def produce (state, ID, item):
	return [('produce_{}'.format(item), ID)]

pyhop.declare_methods ('produce', produce)

def make_method (name, rule):
	def method (state, ID):
		subtasks = []

		#1: For everything in "Requires", check if we have required tools
		if "Requires" in rule:
			for req_item, req_amt in rule["Requires"].items():
				if getattr(state, req_item)[ID] < req_amt:
					subtasks.append(('have_enough', ID, req_item, req_amt))

		#2: For everything in "Consumes", check if we have enough ingredients
		if "Consumes" in rule:
			for c_item, c_amt in rule["Consumes"].items():
				subtasks.append(('have_enough', ID, c_item, c_amt))

		#3 Apply the subtasks
		subtasks.append(('op_' + name, ID))

		return subtasks

	return method

def declare_methods (data):
	# some recipes are faster than others for the same product even though they might require extra tools
	# sort the recipes so that faster recipes go first
	methods = {}

	# Get recipes and sort them by time (shortest first)
	sorted_recipes = sorted(data['Recipes'].items(), key=lambda r: r[1]['Time'])			

	# Iterate over the sorted recipes and create methods for each
	for recipe_name, rule in sorted_recipes:
		produced_items = rule['Produces']

		for item in produced_items:
			# Create a method for each recipe
			new_method = make_method(recipe_name, rule)

			# Add to list of methods for the item
			if item in methods:
				methods[item].append(new_method)
			else:
				methods[item] = [new_method]
	
	# Declare the methods
	for item, method_list in methods.items():
		pyhop.declare_methods(f'produce_{item}', *method_list)

def make_operator (rule):
	def operator (state, ID):
		#1: Check if we have enough time
		if state.time[ID] < rule['Time']:
			return False
		
		#2: Check the "Requires" field
		if "Requires" in rule:
			for req_item, req_amount in rule['Requires'].items():
				if getattr(state, req_item)[ID] < req_amount:
					return False
				
		#3: Check the "Consumes" field
		if "Consumes" in rule:
			for c_item, c_amount in rule['Consumes'].items():
				if getattr(state, c_item)[ID] < c_amount:
					return False

		#4: If all checks pass, apply the recipe
		# Reduce time
		state.time[ID] -= rule['Time']

		# Consume items
		if "Consumes" in rule:
			for c_item, c_amount in rule['Consumes'].items():
				getattr(state, c_item)[ID] -= c_amount

		# Produce items
		for p_item, p_amount in rule['Produces'].items():
			getattr(state, p_item)[ID] += p_amount

		return state
	return operator

def declare_operators (data):
	ops = []
	for recipe_name, rule in data['Recipes'].items():
		op = make_operator(rule)

		# Give the operator a name
		op.__name__ = 'op_' + recipe_name
		ops.append(op)

	pyhop.declare_operators(*ops)


def add_heuristic (data, ID):
	# prune search branch if heuristic() returns True
	# do not change parameters to heuristic(), but can add more heuristic functions with the same parameters: 
	# e.g. def heuristic2(...); pyhop.add_check(heuristic2)
	def heuristic (state, curr_task, tasks, plan, depth, calling_stack):
		# your code here
		return False # if True, prune this branch

	pyhop.add_check(heuristic)


def set_up_state (data, ID, time=0):
	state = pyhop.State('state')
	state.time = {ID: time}

	for item in data['Items']:
		setattr(state, item, {ID: 0})

	for item in data['Tools']:
		setattr(state, item, {ID: 0})

	for item, num in data['Initial'].items():
		setattr(state, item, {ID: num})

	return state

def set_up_goals (data, ID):
	goals = []
	for item, num in data['Goal'].items():
		goals.append(('have_enough', ID, item, num))

	return goals

if __name__ == '__main__':
	rules_filename = 'crafting.json'

	with open(rules_filename) as f:
		data = json.load(f)

	state = set_up_state(data, 'agent', time=239) # allot time here
	goals = set_up_goals(data, 'agent')

	declare_operators(data)
	declare_methods(data)
	add_heuristic(data, 'agent')

	# pyhop.print_operators()
	# pyhop.print_methods()

	# Hint: verbose output can take a long time even if the solution is correct; 
	# try verbose=1 if it is taking too long
	pyhop.pyhop(state, goals, verbose=3)
	# pyhop.pyhop(state, [('have_enough', 'agent', 'cart', 1),('have_enough', 'agent', 'rail', 20)], verbose=3)
