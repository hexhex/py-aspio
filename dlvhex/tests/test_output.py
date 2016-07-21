import unittest
from ..output import OutputSpec
from ..program import Program
from ..errors import CircularReferenceError, DuplicateKeyError, InvalidIndicesError, UndefinedNameError


class TestOutput(unittest.TestCase):

    def test_do_not_leak_variables(self):
        # not sure what it should raise, but it must be an error
        # (currently AssertionError while mapping, later an UndefinedNameError would be better at parsing time)
        with self.assertRaises(BaseException):
            result = Program(code=r'''
                %! OUTPUT {
                %!  a = (X),
                %!  b = set { predicate: p(X); content: (X, &a); }
                %! }
                p(1). p(2).
                ''').solve_one()
            result.get('b')

    def test_cycle_detection(self):
        spec = OutputSpec.parse(r'''
            OUTPUT {
                x = &y,
                y = &x,
            }
        ''')
        with self.assertRaises(CircularReferenceError):
            r = spec.prepare_mapping({}, None)
            r.get_object('x')

    def test_undefined_toplevel_names(self):
        result = Program(code=r'%! OUTPUT { x = 25 }').solve_one()
        self.assertEqual(result.get('x'), 25)
        self.assertEqual(result.x, 25)
        with self.assertRaises(UndefinedNameError):
            result.get('xxx')
        with self.assertRaises(AttributeError):
            result.xxx

    def test_sequence(self):
        xs = Program(code=r'''
            p(abc, 1).
            p(def, 0).
            p(xyz, 2).

            %! OUTPUT {
            %!  xs = sequence { predicate: p(X, I); content: X; index: I; }
            %! }
        ''').solve_one().xs
        assert xs == ['def', 'abc', 'xyz']

    def test_sequence_with_invalid_indices(self):
        # missing index
        with self.assertRaises(InvalidIndicesError):
            Program(code=r'''
                p(def, 0).
                p(xyz, 2).

                %! OUTPUT {
                %!  xs = sequence { predicate: p(X, I); content: X; index: I; }
                %! }
            ''').solve_one().xs
        # duplicate index
        with self.assertRaises(InvalidIndicesError):
            Program(code=r'''
                p(abc, 1).
                p(def, 0).
                p(xyz, 1).

                %! OUTPUT {
                %!  xs = sequence { predicate: p(X, I); content: X; index: I; }
                %! }
            ''').solve_one().xs

    def test_dictionary(self):
        d = Program(code=r'''
            p(abc, 1).
            p(def, 0).
            p(xyz, 2).

            %! OUTPUT {
            %!  d = dictionary { predicate: p(K, V); content: V; key: K; }
            %! }
        ''').solve_one().d
        assert d == {'def': 0, 'abc': 1, 'xyz': 2}

    def test_dictionary_with_duplicate_keys(self):
        with self.assertRaises(DuplicateKeyError):
            Program(code=r'''
                p(abc, 1).
                p(abc, 0).
                p(xyz, 2).

                %! OUTPUT {
                %!  d = dictionary { predicate: p(K, V); content: V; key: K; }
                %! }
            ''').solve_one().d

    def test_argument_subset(self):
        class IdentityTuple:
            '''Contains a tuple, but tests equality by instance identity.'''
            def __init__(self, *contents):
                self.contents = tuple(contents)
        assert IdentityTuple(1) != IdentityTuple(1)
        program = Program(code=r'''
            % Three facts with the same first argument
            p(1, 2).
            p(1, 3).
            p(1, 4).

            %! OUTPUT {
            %!  % Here, we only extract the first argument.
            %!  % Since it is the same in all three p-facts, we will get only one result object.
            %!  % We use IdentityTuple to make sure the deduplication is not performed after the mapping by the 'set' container.
            %!  xs = set { predicate: p(X, Y); content: IdentityTuple(X); }
            %! }
        ''')
        # TODO: Are these the semantics we want?
        # Maybe we should use all referenced variables in the rule head, except if suppressed (variable name '_' for unused arguments, like in ASP)
        program.register('IdentityTuple', IdentityTuple)
        with program.solve().xs as xss:
            for xs in xss:
                assert len(xs) == 1  # one object in the mapped 'xs' result
