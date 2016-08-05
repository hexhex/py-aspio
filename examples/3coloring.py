#!/usr/bin/env python3

import dlvhex
import logging
import os.path as p

# Enable debug messages from dlvhex
dlvhex.log.addHandler(logging.StreamHandler())
dlvhex.log.setLevel(logging.DEBUG)

class Node:
    def __init__(self, label):
        self.label = label


dlvhex.register_dict(globals())


def main():
    asp_file = p.join(p.dirname(p.realpath(__file__)), '3coloring.dl')

    prog = dlvhex.Program(filename=asp_file)

    na = Node('a')
    nb = Node('b')
    nc = Node('c')
    nodes = [na, nb, nc]
    edges = {
        na: [nb, nc],
        nb: [nc]
    }

    with prog.solve(nodes, edges, cache=True) as results:
        print(results)
        for i, x in enumerate(results):
            print(i, repr(x), repr(x.num), repr(x.s))

        for x in results.color2:
            print(repr(x))

    for ans in prog.solve(nodes, edges):
        print(ans)


if __name__ == '__main__':
    main()
