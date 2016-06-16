import unittest
import re
from ..program import Program
from ..solver import SolverError


class TestSolver(unittest.TestCase):

    def test_solver_error(self):
        with self.assertRaises(SolverError) as cm:
            prog = Program(code='p(a, ).')  # the second argument to p is missing
            with prog.solve() as results:
                next(iter(results))  # we have to actually iterate over the result to see any errors
        ex = cm.exception
        self.assertNotIn(ex.returncode, [None, 0])
        self.assertRegex(ex.stderr, re.compile('syntax error', re.IGNORECASE))
