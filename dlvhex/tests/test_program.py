from io import StringIO
import unittest
from ..program import Program, StreamAccumulator


class TestProgram(unittest.TestCase):

    def test__input_args__expect_none(self):
        prog0 = Program(code=r'p.')
        prog0.solve_one()  # no argument, as expected
        with self.assertRaises(ValueError):
            prog0.solve_one('excess argument')

    def test__input_args__expect_two__got_one(self):
        prog2 = Program(code=r'%! INPUT (x, y) { }')
        prog2.solve_one('one', 'two')  # two arguments, as expected
        with self.assertRaises(ValueError):
            prog2.solve_one('one argument is not enough')
        with self.assertRaises(ValueError):
            prog2.solve_one('three', 'is', 'too much')

    def test__solve_one__without_answerset(self):
        result = Program(code=r'x. :- x.').solve_one()
        self.assertIsNone(result)

    def test_string_escaping(self):
        p = Program(code=r'''
            %! INPUT (str) { p(str); }
            %! OUTPUT { strs = set { query: p(X); content: X; }; }
        ''')
        strings = [
            'abc',
            'a"bc',
            'a\\bc',
            'a\\"bc',
            'abc"',
            '"abc"',
            'a\\\\"b"c',
            '\\abc',
            'abc\\',
        ]
        for string in strings:
            result = p.solve_one(string).strs
            self.assertIn(string, result)
            self.assertEqual(len(result), 1)

    def test_stream_accumulator(self):
        def sa_map(pred, args):
            s = StringIO()
            acc = StreamAccumulator(s)
            acc.add_fact(pred, args)
            return s.getvalue().strip()
        self.assertEqual(sa_map('pred', tuple()), 'pred().')
        self.assertEqual(sa_map('p', ("abc",)), 'p("abc").')
        self.assertEqual(sa_map('p', (1, 2, 'xy"z', 3)), r'p(1,2,"xy\"z",3).')
