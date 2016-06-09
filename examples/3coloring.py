#!/usr/bin/env python3

import dlvhex
import os.path as p


class Node:
    def __init__(self, label):
        self.label = label


def main():
    dlvhex.debug = True

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

    rs = prog.solve(nodes, edges, cache=True)
    print(rs)
    for i, x in enumerate(rs):
        print(i, repr(x), repr(x.num), repr(x.s))

    for x in rs.color2:
        print(repr(x))

    for ans in prog(nodes, edges):
        print(ans)


if __name__ == '__main__':
    main()
