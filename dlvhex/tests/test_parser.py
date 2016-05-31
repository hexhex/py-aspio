import unittest
from ..parser import EmbeddedSpecParser, InputSpecParser, parse, ParseException
from ..input import InputSpecification


class TestParser(unittest.TestCase):

    def test_valid_input(self):
        valid_inputs = [
            '''
            INPUT (
                a,
                obj,
                nodes,
            ) {
                empty();
                simple(obj);
                p(nodes[1].label);
                node(n.label) for n in set nodes;
                edge(n.label, m.label, m.prop[3]) for n in nodes for (i, m) in sequence n.neighbors;
            }
            ''',
            'INPUT(){}',
            'INPUT(x){}',
            'INPUT(){p();}',
        ]
        for valid_input in valid_inputs:
            spec = parse(InputSpecParser(), valid_input)
            self.assertTrue(isinstance(spec, InputSpecification))

    def test_invalid_input(self):
        invalid_inputs = [
            'INPUT { }',  # no argument list
            'INPUT ( )',  # no body
            'INPUT (x,y,z) { p(x, y) q(z) }',  # no semicolon after predicates
        ]
        for invalid_input in invalid_inputs:
            with self.assertRaises(ParseException):
                parse(InputSpecParser(), invalid_input)

    def test_embedded_parser(self):
        valid_embedded_specs = [
            '',
            '% blah\n%! ',
            '%!  ',
            '%! INPUT(){}  OUTPUT',
            '''
                % This is some ASP code with I/O specs
                %! INPUT (xs) {
                %!  p(x) for x in xs;  % a comment inside the spec, should be ignored
                %! }
                q(X) :- p(X).  % bla blah   %! a spec marker inside an ASP comment should be ignored
                q(123). %! OUTPUT
            '''
        ]
        for valid_embedded_spec in valid_embedded_specs:
            try:
                parse(EmbeddedSpecParser(), valid_embedded_spec)
            except ParseException as e:
                self.fail("Error while parsing " + repr(valid_embedded_spec) + ": " + str(e))

    def test_embedded_parser_regex(self):
        result = EmbeddedSpecParser.extractFromString("""
            % a normal asp comment
            % another asp comment  %! this should be IGNORED
            p(abc).    % comment behind predicate
            p(xyz1).
            %! this is what we want to parse
            p(def).   %! behind predicate % IGNORED % IGNORED too
            p("quoted %!\\"string").  %! behind a quoted string containing percent
            q(X):-p(X).
            p("quoted"). % q("quoted but in comment").  %! means: this should be IGNORED.
        """)
        self.assertEqual(result, '\n'.join(
            [
                ' this is what we want to parse',
                ' behind predicate ',
                ' behind a quoted string containing percent',
            ]))
