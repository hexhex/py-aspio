# Load ASP program and input/output specifications from file
prog = aspio.Program(filename='coloring.dl')

# Iterate over all answer sets
for result in prog.solve(nodes, edges):
    print(result.colored_nodes)

# Shortcut if only one variable is needed (note prefix "each_")
for cns in prog.solve(nodes, edges).each_colored_nodes:
    print(cns)

# Compute a single answer set
result = prog.solve_one(nodes, edges)
if result is not None: print(result.colored_nodes)
else: print('no answer set exists')
