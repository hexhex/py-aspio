from pyparsing import alphas, alphanums, nums, CaselessKeyword, Group, Optional, ZeroOrMore, Word, Literal
from .input import InputAccessor, InputIteration, InputPredicate, InputSpecification


# Common syntax elements
predicate_name = Word(alphas, alphanums).setName('predicate name')
py_identifier = Word(alphas, alphanums).setName('python identifier')
var = Word(alphas, alphanums).setName('variable')
integer = Word(nums).setName('integer').setParseAction(lambda t: int(t[0]))
INPUT = CaselessKeyword('INPUT').suppress()
FOR = CaselessKeyword('for').suppress()
IN = CaselessKeyword('in').suppress()
OUTPUT = CaselessKeyword('OUTPUT').suppress()
lpar = Literal('(').suppress()
rpar = Literal(')').suppress()
lbracket = Literal('[').suppress()
rbracket = Literal(']').suppress()
lbrace = Literal('{').suppress()
rbrace = Literal('}').suppress()
dot = Literal('.').suppress()
comma = Literal(',').suppress()
semicolon = Literal(';').suppress()


def InputSyntax():
    """Syntax of the INPUT statement."""
    # Accessing objects, some examples:
    # - just access a variable directly:            node
    # - access a field on a variable:               node.label
    # - accessing a fixed index in a collection:    some_tuple[3]
    # - chainable:                                  node.neighbors[2].label
    field_accessor = dot + py_identifier
    index_accessor = lbracket + integer + rbracket
    accessor = var('var') + Group(ZeroOrMore(field_accessor | index_accessor))('path')
    #
    accessor.setParseAction(lambda t: InputAccessor(t.var, t.path))

    # Iterating over objects, some examples:
    # - iterate over elements:                          for node in nodes
    # - iterate over indices and elements of a list:    for (i, m) in node.neighbors
    # - iterate over keys and elements of a dictionary: for (k, v) in some_dict
    iteration_element = var('elem')
    iteration_index_and_element = lpar + var('idx') + comma + var('elem') + rpar
    iteration = FOR + (iteration_element | iteration_index_and_element) + IN + accessor('accessor')
    iterations = Group(ZeroOrMore(iteration))
    #
    iteration.setParseAction(lambda t: InputIteration(t.get('idx'), t.get('elem'), t.get('accessor')))
    # Note: t.get(n) returns None if n doesn't exist while t.n would return an empty string

    predicate_args = Group(Optional(accessor + ZeroOrMore(comma + accessor) + Optional(comma)))
    predicate_spec = predicate_name('pred') + lpar + predicate_args('args') + rpar + iterations('iters') + semicolon
    predicate_specs = Group(ZeroOrMore(predicate_spec))
    #
    predicate_spec.setParseAction(lambda t: InputPredicate(t.name, t.args, t.iters))

    # TODO: Types? yes or no?
    input_arg = var
    input_args = Group(Optional(input_arg + ZeroOrMore(comma + input_arg) + Optional(comma)))

    input_statement = INPUT + lpar + input_args('args') + rpar + lbrace + predicate_specs('preds') + rbrace
    #
    input_statement.setParseAction(lambda t: InputSpecification(t.args, t.preds))

    return input_statement


def OutputSyntax():
    """Syntax of a single OUTPUT statement."""
    # TODO
    return CaselessKeyword('OUTPUT')


def Syntax():
    """Syntax of the whole I/O mapping specification: One INPUT statement and multiple OUTPUT statements in any order."""
    i = InputSyntax().setResultsName('input')
    o = OutputSyntax().setResultsName('output')
    s = i & ZeroOrMore(o)
    # collect input and output
    # s.setParseAction(lambda t: TODO)
    return s


def EmbeddedSyntax():
    """Syntax of the whole I/O mapping specification, embedded in ASP comments starting with '%!'."""
    s = Syntax()
    # TODO:
    # Use .ignore() to ignore everything before %! and after %!.....%
    # Careful: skip over % in quoted strings!
    # might need LineStart()
    s.ignore()
    return s


def parse(syntax, string):
    # try:
        result = syntax.parseString(string, parseAll=True)
        return result[0]
    # except: TODO
