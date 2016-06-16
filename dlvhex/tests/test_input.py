import unittest
from collections import defaultdict
from io import StringIO
from ..input import InputSpec, FactAccumulator, StreamAccumulator


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
                q(y) for x in xs for y in x;
                r(xs[2][1]);
                empty();
                seq(i, x[0]) for (i, x) in sequence xs;
                dict(value, key) for (key, value) in mapping ys;
                % str(ys["abc"]);
            } % comment at the end''')
        # TODO: Allow access to string keys too! dict['abc']
        expected_result = {
            'p': set(xs),
            'q': set((y,) for x in xs for y in x),
            'r': set([('def',)]),  # Note: need to wrap the tuple in an iterable, because set() will iterate over its argument
            'empty': set([tuple()]),
            'seq': set((i, x[0]) for (i, x) in enumerate(xs)),
            'dict': set((v, k) for (k, v) in ys.items())
        }
        spec.perform_mapping([xs, ys], acc)
        self.assertEqual(acc.facts, expected_result)

    def test_stream_accumulator(self):
        def sa_map(pred, args):
            s = StringIO()
            acc = StreamAccumulator(s)
            acc.add_fact(pred, args)
            return s.getvalue().strip()
        self.assertEqual(sa_map('pred', tuple()), 'pred().')
        self.assertEqual(sa_map('p', ("abc",)), 'p("abc").')
        self.assertEqual(sa_map('p', (1, 2, 'xy"z', 3)), r'p(1,2,"xy\"z",3).')
