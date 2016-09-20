import unittest
from collections import defaultdict
from io import StringIO
from ..input import InputSpec, FactAccumulator


class TestAccumulator(FactAccumulator):
    def __init__(self):
        self.facts = defaultdict(set)

    def add_fact(self, predicate, args):
        # print(predicate, list(args))
        self.facts[predicate].add(tuple(args))


class TestInput(unittest.TestCase):

    def test_input_mapping(self):
        xs = [(0, 0), (1, 2), ('abc', 'def'), (7, 'x')]
        ys = {
            0: 1,
            'abc': 'xyz',
            3: 'zzz'
        }
        acc = TestAccumulator()
        spec = InputSpec.parse(r'''
            INPUT (xs, ys) {
                p(x[0], x[1]) for x in set xs;      % a comment about the spec
                p2(a, b) for (a, b) in set xs;      % tuple unpacking
                q(y) for x in xs for y in x;
                r(xs[2][1]);
                empty();
                seq(i, x[0]) for (i, x) in sequence xs;
                seq2(i, a) for (i, (a, _)) in sequence xs;
                dict(value, key) for (key, value) in dictionary ys;
                str(ys["abc"]);
            } % comment at the end''')
        expected_result = {
            'p': set(xs),
            'p2': set(xs),
            'q': set((y,) for x in xs for y in x),
            'r': set([('def',)]),  # Note: need to wrap the tuple in an iterable, because set() will iterate over its argument
            'empty': set([tuple()]),
            'seq': set((i, x[0]) for (i, x) in enumerate(xs)),
            'seq2': set((i, x[0]) for (i, x) in enumerate(xs)),
            'dict': set((v, k) for (k, v) in ys.items()),
            'str': set([('xyz',)]),
        }
        spec.perform_mapping([xs, ys], acc)
        self.assertEqual(acc.facts, expected_result)

    def test_tuple_unpacking(self):
        xs = [('a', 3), ('b', 4), ('c', 5)]
        spec = InputSpec.parse(r'''
            INPUT (xs) {
                p(v[0], v[1]) for v in sequence xs;
                q(i, xy) for (i, xy) in sequence xs;
                r(i, x, y) for (i, (x, y)) in sequence xs;
            }
        ''')
        # TODO
