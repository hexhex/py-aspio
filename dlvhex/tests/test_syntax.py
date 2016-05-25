import unittest
from ..syntax import InputSyntax, parse
from ..input import InputSpecification


class TestSyntax(unittest.TestCase):

    def test_valid_input(self):
        spec = parse(InputSyntax(), '''
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
        ''')
        self.assertTrue(isinstance(spec, InputSpecification))

    # def test_invalid_input(self):
    #     with self.assertRaises(ParseException):
    #         parse(InputSyntax(), 'INPUT { }')
