import unittest
from collections import defaultdict
from io import StringIO
from ..input import InputSpecification, StreamAccumulator


class TestAccumulator:
    def __init__(self):
        self.facts = defaultdict(set)

    def add_fact(self, predicate, args):
        # print(predicate, list(args))
        self.facts[predicate].add(tuple(args))


class TestMapping(unittest.TestCase):

    def test_mapping(self):
        xs = [(0, 0), (1, 2), ('abc', 'def'), (7, 'x')]
        acc = TestAccumulator()
        spec = InputSpecification.parse(r'''
            INPUT (xs) {
                p(x[0], x[1]) for x in xs;
                q(y) for x in xs for y in x;
                r(xs[2][1]);
                empty();
            }''')
        expected_result = {
            'p': set(xs),
            'q': set((y,) for x in xs for y in x),
            'r': set([('def',)]),  # Note: need to wrap the tuple in an iterable, because set() will iterate over its argument
            'empty': set([tuple()]),
        }
        spec.perform_mapping([xs], acc)
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
