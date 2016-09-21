#!/usr/bin/env python3
from collections import namedtuple
from pathlib import Path
import logging
import aspio

# Enable debug messages from py-aspio
aspio.log.addHandler(logging.StreamHandler())
aspio.log.setLevel(logging.DEBUG)

Node = namedtuple('Node', ['label'])
ColoredNode = namedtuple('ColoredNode', ['label', 'color'])
Arc = namedtuple('Arc', ['start', 'end'])

aspio.register_dict(globals())


def main():
    # Load ASP program and input/output specifications from file
    asp_file = Path(__file__).with_name('3coloring.dl')
    prog = aspio.Program(filename=asp_file)

    # Some sample data
    a = Node('a')
    b = Node('b')
    c = Node('c')
    nodes = {a, b, c}
    arcs = {
        Arc(a, b),
        Arc(a, c),
        Arc(b, c)
    }

    # Iterate over all answer sets
    for result in prog.solve(nodes, arcs):
        print(result.colored_nodes)

    # A shortcut if only one output variable is needed
    for colored_nodes in prog.solve(nodes, arcs).each_colored_nodes:
        print(colored_nodes)

    # Compute a single answer set, or return None if no answer set exists
    result = prog.solve_one(nodes, arcs)
    if result is not None:
        print(result.colored_nodes)
        print(result.labels_by_color)
    else:
        print('no answer set')

if __name__ == '__main__':
    main()
