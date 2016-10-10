#!/usr/bin/env python3
import aspio

# This program has 3**8 = 6561 answer sets
prog = aspio.Program(code=r'''
    num(1..8).
    a(X) v b(X) v c(X) :- num(X).
''')

try:
    print('NOTE: the results should appear immediately one after the other, not all at once after waiting for some time!')
    for i, result in enumerate(prog.solve()):
        print('Got result {0}.'.format(i + 1))
except Exception as e:
    print('Got error ' + str(type(e)))
