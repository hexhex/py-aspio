import unittest
from ..output import OutputSpec
from ..program import Program
from ..errors import CircularReferenceError, DuplicateKeyError, InvalidIndicesError, UndefinedNameError


class TestOutput(unittest.TestCase):

    def test_undefined_variables(self):
        with self.assertRaises(UndefinedNameError):
            OutputSpec.parse(r'''
                OUTPUT {
                    a = (X);
                    b = set { query: p(X); content: (X, &a); };
                }
            ''')
        with self.assertRaises(UndefinedNameError):
            OutputSpec.parse(r'''
                OUTPUT {
                    b = set { query: p(X); content: (X, int(Y)); };
                }
            ''')

    def test_cycle_detection(self):
        spec = OutputSpec.parse(r'''
            OUTPUT {
                x = &y;
                y = &x;
            }
        ''')
        with self.assertRaises(CircularReferenceError):
            r = spec.prepare_mapping({}, None)
            r.get_object('x')

    def test_undefined_toplevel_names(self):
        result = Program(code=r'%! OUTPUT { x = 25; }').solve_one()
        self.assertEqual(result.get('x'), 25)
        self.assertEqual(result.x, 25)
        with self.assertRaises(UndefinedNameError):
            result.get('xxx')
        with self.assertRaises(AttributeError):
            result.xxx

    def test_simple_set(self):
        xs = Program(code=r'''
            p(a). p(b). p(c).
            %! OUTPUT { xs = set { p/1 }; }
        ''').solve_one().xs
        self.assertSetEqual(xs, {'a', 'b', 'c'})

        xs = Program(code=r'''
            p(a, x). p(b, y). p(c, z).
            %! OUTPUT { xs = set { p/2 }; }
        ''').solve_one().xs
        self.assertSetEqual(xs, {('a', 'x'), ('b', 'y'), ('c', 'z')})

        xs = Program(code=r'''
            p(1). p(2). p(3).
            %! OUTPUT { xs = set { p/1 -> int }; }
        ''').solve_one().xs
        self.assertSetEqual(xs, {1, 2, 3})

        xs = Program(code=r'''
            p("/usr", "bin"). p("/usr/local", "bin").
            %! OUTPUT { xs = set { p/2 -> pathlib.Path }; }
        ''').solve_one().xs
        from pathlib import Path
        self.assertSetEqual(xs, {Path("/usr/bin"), Path("/usr/local/bin")})

    def test_sequence(self):
        xs = Program(code=r'''
            p(abc, 1).
            p(def, 0).
            p(xyz, 2).

            %! OUTPUT {
            %!  xs = sequence { query: p(X, I); content: X; index: I; };
            %! }
        ''').solve_one().xs
        self.assertSequenceEqual(xs, ['def', 'abc', 'xyz'])

    def test_sequence_with_invalid_indices(self):
        # missing index
        with self.assertRaises(InvalidIndicesError):
            Program(code=r'''
                p(def, 0).
                p(xyz, 2).

                %! OUTPUT {
                %!  xs = sequence { query: p(X, I); content: X; index: I; };
                %! }
            ''').solve_one().xs
        # duplicate index
        with self.assertRaises(InvalidIndicesError):
            Program(code=r'''
                p(abc, 1).
                p(def, 0).
                p(xyz, 1).

                %! OUTPUT {
                %!  xs = sequence { query: p(X, I); content: X; index: I; };
                %! }
            ''').solve_one().xs
        # index is not an integer
        with self.assertRaises(InvalidIndicesError):
            Program(code=r'''
                p(def, 0).
                p(xyz, no).

                %! OUTPUT {
                %!  xs = sequence { query: p(X, I); content: X; index: I; };
                %! }
            ''').solve_one().xs

    def test_dictionary(self):
        d = Program(code=r'''
            p(abc, 1).
            p(def, 0).
            p(xyz, 2).

            %! OUTPUT {
            %!  d = dictionary { query: p(K, V); content: int(V); key: K; };
            %! }
        ''').solve_one().d
        self.assertDictEqual(dict(d), {'def': 0, 'abc': 1, 'xyz': 2})

    def test_dictionary_with_duplicate_keys(self):
        with self.assertRaises(DuplicateKeyError):
            Program(code=r'''
                p(abc, 1).
                p(abc, 0).
                p(xyz, 2).

                %! OUTPUT {
                %!  d = dictionary { query: p(K, V); content: V; key: K; };
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
            %!  xs = set { query: p(X, _); content: IdentityTuple(X); };
            %! }
        ''')
        program.register(IdentityTuple)
        with program.solve().all_xs as xss:
            for xs in xss:
                self.assertEqual(len(xs), 1)  # one object in the mapped 'xs' result

    def test_query_constants(self):
        result = Program(code=r'''
            p(a, 1). p(a, 2).
            p("a", 3).
            p(5, 6).
            %!  OUTPUT {
            %!      x = set { query: p(a, X); content: int(X); };
            %!      y = set { query: p("a", X); content: int(X); };
            %!      z = set { query: p(5, X); content: int(X); };
            %!  }
        ''').solve_one()
        self.assertSetEqual(result.x, {1, 2})
        self.assertSetEqual(result.y, {3})
        self.assertSetEqual(result.z, {6})

    def test_nested_container(self):
        d = Program(code=r'''
            p(a, 1). p(a, 2).
            p(c, 3).

            %! OUTPUT {
            %!  d = dictionary {
            %!          query: p(K, _);
            %!          key: K;
            %!          content: set { query: p(K, V); content: int(V); };
            %!      };
            %! }
        ''').solve_one().d
        self.assertDictEqual(dict(d), {'a': {1, 2}, 'c': {3}})
