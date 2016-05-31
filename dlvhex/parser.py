from pyparsing import alphas, alphanums, nums, CaselessKeyword, Group, Optional, ZeroOrMore, Word, Literal, Forward, ParseException  # type: ignore
from . import input as i
import re


# TODO: There might be a problem with pyparsing's ParseElement.setDefaultWhitespaceChars() (global state that can be set by everyone that uses pyparsing…)
#       A problem might occur if the user of this library also uses pyparsing and modifies the default whitespace chars.
#       Investigate this.


# Common syntax elements
predicate_name = Word(alphas, alphanums).setName('predicate name')
py_identifier = Word(alphas, alphanums).setName('python identifier')
py_qualified_identifier = Word(alphas, alphanums).setName('qualified python identifier')  # TODO: allow dots for modules
var = Word(alphas, alphanums).setName('variable')
integer = Word(nums).setName('integer').setParseAction(lambda t: int(t[0]))
INPUT = CaselessKeyword('INPUT').suppress()
FOR = CaselessKeyword('for').suppress()
IN = CaselessKeyword('in').suppress()
OUTPUT = CaselessKeyword('OUTPUT').suppress()
PREDICATE = CaselessKeyword('predicate').suppress()
CONTAINER = CaselessKeyword('container').suppress()
SET = CaselessKeyword('set').suppress()
SEQUENCE = CaselessKeyword('sequence').suppress()
MAPPING = CaselessKeyword('mapping').suppress()
INDEX = CaselessKeyword('index').suppress()
KEY = CaselessKeyword('key').suppress()
CONTENT = CaselessKeyword('content').suppress()
CLASS = CaselessKeyword('class').suppress()
ARGUMENTS = CaselessKeyword('arguments').suppress()
lpar = Literal('(').suppress()
rpar = Literal(')').suppress()
lbracket = Literal('[').suppress()
rbracket = Literal(']').suppress()
lbrace = Literal('{').suppress()
rbrace = Literal('}').suppress()
dot = Literal('.').suppress()
comma = Literal(',').suppress()
semicolon = Literal(';').suppress()
equals = Literal('=').suppress()


def InputSpecParser():
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
    accessor.setParseAction(lambda t: i.InputAccessor(t.var, t.path))

    # Iterating over objects, some examples:
    # - iterate over elements:                          for node in nodes
    # - iterate over indices and elements of a list:    for (i, m) in node.neighbors
    # - iterate over keys and elements of a dictionary: for (k, v) in some_dict
    iteration_element = var('elem')
    iteration_assoc_and_element = lpar + var('assoc') + comma + var('elem') + rpar
    set_iteration = FOR + iteration_element + IN + Optional(SET) + accessor('accessor')     # TODO: Ambiguity? Is "set" the SET keyword or a variable named "set"? (should be unambiguous since we can look at the following token? variable could be named "for" too). We could just forbid variable names that are keywords.
    sequence_iteration = FOR + iteration_assoc_and_element + IN + SEQUENCE + accessor('accessor')
    mapping_iteration = FOR + iteration_assoc_and_element + IN + MAPPING + accessor('accessor')
    iteration = sequence_iteration | mapping_iteration | set_iteration
    iterations = Group(ZeroOrMore(iteration))
    #
    set_iteration.setParseAction(lambda t: i.InputSetIteration(t.elem, t.accessor))
    sequence_iteration.setParseAction(lambda t: i.InputSequenceIteration(t.assoc, t.elem, t.accessor))
    mapping_iteration.setParseAction(lambda t: i.InputMappingIteration(t.assoc, t.elem, t.accessor))
    # Note: t.get(n) returns None if n doesn't exist while t.n would return an empty string

    predicate_args = Group(Optional(accessor + ZeroOrMore(comma + accessor) + Optional(comma)))
    predicate_spec = predicate_name('pred') + lpar + predicate_args('args') + rpar + iterations('iters') + semicolon
    predicate_specs = Group(ZeroOrMore(predicate_spec))
    #
    predicate_spec.setParseAction(lambda t: i.InputPredicate(t.pred, t.args, t.iters))

    # TODO: Types? yes or no?
    input_arg = var
    input_args = Group(Optional(input_arg + ZeroOrMore(comma + input_arg) + Optional(comma)))

    input_statement = INPUT + lpar + input_args('args') + rpar + lbrace + predicate_specs('preds') + rbrace
    #
    input_statement.setParseAction(lambda t: i.InputSpecification(t.args, t.preds))

    return input_statement


def OutputSpecParser():
    """Syntax of a single OUTPUT statement."""
    # # TODO: Order of clauses should be arbitrary
    # # TODO: Some clauses are optional
    # output_spec = Forward()

    # arg = py_identifier | output_spec
    # args = Group(Optional(arg + ZeroOrMore(comma + arg) + Optional(comma)))
    # object_spec = CLASS + equals + py_qualified_identifier + comma + ARGUMENTS + equals + args

    # content = integer | (py_qualified_identifier + lpar + Group(Optional(integer + ZeroOrMore(comma + integer) + Optional(comma))) + rpar)
    # set_spec = CONTAINER + equals + SET
    # list_spec = CONTAINER + equals + SEQUENCE + comma + INDEX + equals + integer
    # dict_spec = CONTAINER + equals + MAPPING + comma + KEY + equals + content
    # container_spec = PREDICATE + equals + predicate_name + comma + (set_spec | list_spec | dict_spec) + comma + CONTENT + equals + content

    # output_spec << (lbrace + (container_spec | object_spec) + rbrace)
    # output_statement = OUTPUT + py_identifier + output_spec
    # return output_statement
    return OUTPUT


def SpecParser():
    """Syntax of the whole I/O mapping specification: One INPUT statement and multiple OUTPUT statements in any order."""
    i = InputSpecParser().setResultsName('input')
    o = OutputSpecParser().setResultsName('output')
    p = ZeroOrMore(o) + Optional(i) + ZeroOrMore(o)   # TODO: Check if this works when both are named 'output'
    # collect input and output
    p.setParseAction(lambda t: 12345)  # TODO
    return p


class EmbeddedSpecParser:
    """Syntax of the whole I/O mapping specification, embedded in ASP comments starting with '%!'."""
    # I tried doing this part with pyparsing too, so the whole parsing can be performed in a single pass without an intermediate string representation.
    # However, I was not able to make it work yet, so I am using a simple regex-based implementation at the moment.
    # Most likely problem with the pyparsing attempt: automatic handling of whitespace combined with LineStart() and LineEnd()
    # See also: http://pyparsing.wikispaces.com/share/view/18478063
    # The old attempt:
    #     p = SpecParser()
    #     asp_quoted_string = QuotedString('"', escChar='\\')
    #     asp_end = LineEnd() | '%!' | ('%' + ZeroOrMore(CharsNotIn('\n')) + LineEnd())       # '%!' must be before the regular comments since the '|' operator matches the first subexpression (MatchFirst)
    #     asp_line = LineStart() + ZeroOrMore(CharsNotIn('"%') | asp_quoted_string) + asp_end
    #     p.ignore(asp_line)
    #     return p
    #
    # This seems to work better, although neither LineStart() nor LineEnd() will match if the line starts with whitespace
    # (presumably because the parser by default skips as much whitespace as possible after parsing a token):
    #    asp_quoted_string = QuotedString('"', escChar='\\')
    #    asp_end = LineEnd().leaveWhitespace() | '%!' | ('%' + ZeroOrMore(CharsNotIn('\n')) + LineEnd().leaveWhitespace())       # '%!' must be before the regular comments since the '|' operator matches the first subexpression (MatchFirst)
    #    asp_line = (LineStart().leaveWhitespace() | LineEnd().leaveWhitespace()) + ZeroOrMore(CharsNotIn('"%\n') | asp_quoted_string) + asp_end
    #    p.ignore(asp_line)
    #
    # This seems to work quite well (implementation of comments inside %! part is still missing though, would be an ignore on SpecParser()):
    #    ParserElement.setDefaultWhitespaceChars(' \t\r')
    #    p = ZeroOrMore(Word(printables))
    #    # p.setWhitespaceChars(' \t\r')  # TODO: What to do with '\r'?
    #    linebreak = White('\n')
    #    asp_quoted_string = QuotedString('"', escChar='\\')
    #    asp_end = FollowedBy(linebreak) | '%!' | ('%' + ZeroOrMore(CharsNotIn('\n')) + FollowedBy(linebreak))       # '%!' must be before the regular comments since the '|' operator matches the first subexpression (MatchFirst)
    #    asp_line = (linebreak | StringStart()) + ZeroOrMore(CharsNotIn('"%\n') | asp_quoted_string) + asp_end
    #    p.ignore(asp_line)
    #    p.ignore(linebreak)

    spec_parser = SpecParser()

    embedded_re = re.compile(r'''
        ^  # Start of each line (in MULTILINE mode)
        # The ASP part before comments
        (
            [^\n%"]  # anything except newlines, comment start, and quotes
            |
            # Quoted string: any char except newlines/backslash/quotes, or backslash escape sequences
            " ( [^\n\\"] | \\. )* "
        )*
        %\!                     # Our specification language is embedded in special %! comments
        (?P<spec>[^\n%]*)       # The part we want to extract
        (%.*)?                  # Comments in the specification language also start with % (like regular ASP comments)
        $  # end of each line (in MULTILINE mode)
    ''', re.MULTILINE | re.VERBOSE)

    @classmethod
    def extractFromString(cls, string):
        return '\n'.join(m.group('spec') for m in cls.embedded_re.finditer(string))

    def parseString(self, string, *, parseAll=True):
        return (parse(type(self).spec_parser, type(self).extractFromString(string)),)


def AnswerSetParser():
    # TODO: extract answer sets from dlvhex' output.
    pass


def parse(parser, string):
    try:
        result = parser.parseString(string, parseAll=True)
        return result[0]
    except ParseException:
        # rethrow
        raise
    # except:
    #     pass  # TODO


# def _parse(parser, parse_fn, parse_arg):
#     try:
#         result = parse_fn(parser, parse_arg, parseAll=True)
#         # result = parser.parseFile(file_or_filename, parseAll=True)
#         # result = parser.parseString(string, parseAll=True)
#         return result[0]
#     except ParseException:
#         # rethrow
#         raise
#     # except:
#     #     pass  # TODO
# def parseFile(parser, file_or_filename):
#     return _parse(parser, parser.parseFile, file_or_filename)
# def parseString(parser, string):
#     return _parse(parser, parser.parseString, string)
