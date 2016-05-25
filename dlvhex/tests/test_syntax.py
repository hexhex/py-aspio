import unittest
from ..syntax import InputSyntax, parse, ParseException
from ..input import InputSpecification


class TestSyntax(unittest.TestCase):

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
                node(n.label) for n in nodes;
                edge(n.label, m.label, m.prop[3]) for n in nodes for (i, m) in n.neighbors;
            }
            ''',
            'INPUT(){}',
            'INPUT(x){}',
            'INPUT(){p();}',
        ]
        for valid_input in valid_inputs:
            spec = parse(InputSyntax(), valid_input)
            self.assertTrue(isinstance(spec, InputSpecification))

    def test_invalid_input(self):
        invalid_inputs = [
            'INPUT { }',  # no argument list
            'INPUT ( )',  # no body
            'INPUT (x,y,z) { p(x, y) q(z) }',  # no semicolon after predicates
        ]
        for invalid_input in invalid_inputs:
            with self.assertRaises(ParseException):
                parse(InputSyntax(), invalid_input)
