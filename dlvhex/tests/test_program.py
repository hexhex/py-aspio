import unittest
from ..program import Program


class TestOutput(unittest.TestCase):

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
