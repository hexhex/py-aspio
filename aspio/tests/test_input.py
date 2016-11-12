import unittest
from collections import defaultdict
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
        zs = set(xs)
        acc = TestAccumulator()
        spec = InputSpec.parse(r'''
            INPUT (xs, ys, zs) {
                p(x[0], x[1]) for x in zs;      % a comment about the spec
                p2(a, b) for (a, b) in zs;      % tuple unpacking
                q(y) for x in zs for (_,y) in x;
                r(xs[2][1]);
                empty();
                seq(i, x[0]) for (i, x) in xs;
                seq2(i, a) for (i, (a, _)) in xs;
                dict(value, key) for (key, value) in ys;
                str(ys["abc"]);
                -neg(xs[0][0], xs[0][1]);
            } % comment at the end''')
        expected_result = {
            'p': set(xs),
            'p2': set(xs),
            'q': {(y,) for x in xs for y in x},
            'r': {('def',)},
            'empty': {tuple()},
            'seq': {(i, x[0]) for (i, x) in enumerate(xs)},
            'seq2': {(i, x[0]) for (i, x) in enumerate(xs)},
            'dict': {(v, k) for (k, v) in ys.items()},
            'str': {('xyz',)},
            '-neg': {(0, 0)},
        }
        spec.perform_mapping([xs, ys, zs], acc)
        # Assert the same predicates were generated, i.e. compare the keys
        self.assertSetEqual(set(acc.facts), set(expected_result))
        # Compare generated facts
        for pred in expected_result:
            self.assertSetEqual(acc.facts[pred], expected_result[pred], msg='for predicate {0!r}'.format(pred))
