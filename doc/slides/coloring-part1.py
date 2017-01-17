from collections import namedtuple
import aspio

# Define classes and create sample data
Node = namedtuple('Node', ['label'])
ColoredNode = namedtuple('ColoredNode', ['label', 'color'])
Edge = namedtuple('Edge', ['first', 'second'])
a, b, c = Node('a'), Node('b'), Node('c')
nodes = {a, b, c}
edges = {Edge(a, b), Edge(a, c), Edge(b, c)}

# Register class names with aspio
aspio.register_dict(globals())

# ... (continued on next slide)
