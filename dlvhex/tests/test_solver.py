import gc
import re
import unittest
import warnings
import weakref
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

    def test_resource_destruction(self):
            with warnings.catch_warnings(record=True) as w:
                # Set up warnings filter (only catch ResourceWarning)
                warnings.resetwarnings()
                warnings.simplefilter('ignore')
                warnings.simplefilter('always', ResourceWarning)

                prog = Program(code=r'''
                    p(abc, 1).
                    p(abc2, 1).
                    p(abc3, 1).
                    p(abc4, 1).
                    p(abc5, 1).
                    p(abc6, 1).
                    p(abcd, 0).
                    p(xyz, 2).
                    % Generates a large number of answer sets
                    q(X) v r(X) v s(X) v t(X) v u(X) :- p(X, _).

                    %! OUTPUT {
                    %!  d = dictionary { query: p(K, V); content: V; key: K; }
                    %! }
                ''')
                r = prog.solve()
                # Create weak references to objects that should be destructed
                refs = [weakref.ref(x) for x in (
                    r,
                    r.answer_sets,
                    r.answer_sets.lines,
                    r.answer_sets.lines.process,
                    r.answer_sets.lines.process.stdin,
                    r.answer_sets.lines.process.stdout,
                    r.answer_sets.lines.process.stderr,
                    r.answer_sets.lines.stderr_capture_thread
                )]
                # Remove reference to results object and invoke garbage collection
                del r
                gc.collect()
                # Check that all objects have been destroyed by looking at the weak references
                for ref in refs:
                    self.assertIsNone(ref())
                # Make sure we didn't get any ResourceWarnings
                if w and str(w[-1]):
                    self.fail('ResourceWarning was issued during test')
