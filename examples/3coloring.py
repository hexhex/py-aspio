#!/usr/bin/env python3

import dlvhex
import logging
import os.path as p
from collections import namedtuple

# Enable debug messages from dlvhex
dlvhex.log.addHandler(logging.StreamHandler())
dlvhex.log.setLevel(logging.DEBUG)


Node = namedtuple('Node', ['label'])
ColoredNode = namedtuple('ColoredNode', ['label', 'color'])
Arc = namedtuple('Arc', ['start', 'end'])

dlvhex.register_dict(globals())


def main():
    asp_file = p.join(p.dirname(p.realpath(__file__)), '3coloring.dl')

    prog = dlvhex.Program(filename=asp_file)

    na = Node('a')
    nb = Node('b')
    nc = Node('c')
    nodes = [na, nb, nc]
    arcs = [
        Arc(na, nb),
        Arc(na, nc),
        Arc(nb, nc)
    ]

    for i, colored_nodes in enumerate(prog.solve(nodes, arcs).all_colored_nodes):
        print('Answer set {0}:\t{1!r}'.format(i + 1, sorted(colored_nodes)))

if __name__ == '__main__':
    main()
