import re
from contextlib import contextmanager
from typing import MutableMapping, Tuple  # noqa
from pyparsing import (  # type: ignore
    alphas,
    alphanums,
    nums,
    restOfLine,
    srange,
    CaselessKeyword,
    Forward,
    Group,
    Keyword,
    Literal,
    Optional,
    ParseException,
    ParserElement,
    QuotedString,
    Word,
    ZeroOrMore,
)
from . import asp
from . import input as i
from . import output as o

__all__ = [
    'parse_input_spec',
    'parse_output_spec',
    'parse_spec',
    'parse_embedded_spec',
    'parse_answer_set',
]


@contextmanager
def PyParsingDefaultWhitespaceChars(whitespace_chars):
    '''Set the given whitespace_chars as pyparsing's default whitespace chars while the context manager is active.

    Since ParserElement.DEFAULT_WHITE_CHARS is a global variable, this method is not thread-safe (but no pyparsing parser construction is thread-safe for the same reason anyway).
    '''
    # A possible solution to this problem:
    # Since the pyparsing code is basically a single big file, we could just copy it (under aspio/vendor or something like that) and have our own "private" version of pyparsing. (TODO: think about this some more and maybe do it)
    previous_whitespace_chars = ParserElement.DEFAULT_WHITE_CHARS
    ParserElement.setDefaultWhitespaceChars(whitespace_chars)
    yield
    ParserElement.setDefaultWhitespaceChars(previous_whitespace_chars)


DEFAULT_WHITESPACE_CHARS = ' \n\t\r'  # this is the same as pyparsing's default


def ignore_comments(parser):
    '''Ignore comments (starting with '%' and continuing until the end of the same line) on the given parser (ParserElement instance).'''
    comment = '%' + restOfLine
    parser.ignore(comment)
    return parser


# Common syntax elements
with PyParsingDefaultWhitespaceChars(DEFAULT_WHITESPACE_CHARS):
    alphas_lowercase = srange('[a-z]')
    alphas_uppercase = srange('[A-Z]')
    predicate_name = (Optional('-') + Word(alphas_lowercase, alphanums + '_')).setParseAction(''.join).setName('predicate name')
    # Currently we only support ASCII identifiers for the python side.
    # Python (starting with version 3.0) supports additional characters in identifiers, see https://docs.python.org/3/reference/lexical_analysis.html#identifiers
    # It would be nice to support the same set, but it's not absolutely necessary.
    py_identifier = Word(alphas + '_', alphanums + '_').setName('python identifier')
    py_qualified_identifier = Word(alphas + '_', alphanums + '_.').setName('qualified python identifier')
    integer = (Optional('-') + Word(nums)).setName('integer').setParseAction(lambda t: int(t[0]))
    positive_integer = Word(nums).setName('integer').setParseAction(lambda t: int(t[0]))
    lpar = Literal('(').suppress()
    rpar = Literal(')').suppress()
    lbracket = Literal('[').suppress()
    rbracket = Literal(']').suppress()
    lbrace = Literal('{').suppress()
    rbrace = Literal('}').suppress()
    langle = Literal('<').suppress()
    rangle = Literal('>').suppress()
    dot = Literal('.').suppress()
    comma = Literal(',').suppress()
    colon = Literal(':').suppress()
    semicolon = Literal(';').suppress()
    equals = Literal('=').suppress()
    amp = Literal('&').suppress()
    slash = Literal('/').suppress()
    rightarrow = Literal('->').suppress()

# TODO
# Improve error messages of all parsers!
# See http://blog.ezyang.com/2014/05/parsec-try-a-or-b-considered-harmful/ and check how much of that applies here.
# Also: http://stackoverflow.com/questions/33708817/parser-errors-pattern-for-generating-error-handling-automatically (-> "PEG" parser?)


def RawInputSpecParser():
    '''Syntax of the INPUT statement (and nothing else).'''
    with PyParsingDefaultWhitespaceChars(DEFAULT_WHITESPACE_CHARS):
        INPUT = CaselessKeyword('INPUT').suppress()
        FOR = CaselessKeyword('for').suppress()
        IN = CaselessKeyword('in').suppress()

        target = Forward()
        anonymous_var = Keyword('_')
        # Keywords cannot be used as variable names (we still allow "INPUT" as it never occurs inside the spec)
        input_keyword = FOR | IN
        var = (~input_keyword + ~anonymous_var + Word(alphas + '_', alphanums + '_')).setName('variable')
        tuple_match = lpar + target + ZeroOrMore(comma + target) + Optional(comma) + rpar
        # The target of an assignment, supporting tuple unpacking as a simple form of pattern matching in addition to plain variables
        target << (anonymous_var | var | tuple_match)
        #
        anonymous_var.setParseAction(lambda: i.AnonymousVariable())
        var.setParseAction(lambda t: i.Variable(str(t[0])))
        tuple_match.setParseAction(lambda t: i.TupleMatch(t))

        # Accessing objects, some examples:
        # - just access a variable directly:            node
        # - access a field on a variable:               node.label
        # - accessing a fixed index in a collection:    some_tuple[3]
        # - chainable:                                  node.neighbors[2].label
        field_accessor = dot + py_identifier('name')
        subscript = integer | QuotedString('"', escChar='\\')
        subscript_accessor = lbracket + subscript('key') + rbracket
        accessor = var('var') + Group(ZeroOrMore(field_accessor | subscript_accessor))('path')
        #
        field_accessor.setParseAction(lambda t: i.Attribute(t.name))
        subscript_accessor.setParseAction(lambda t: i.Subscript(t.key))
        accessor.setParseAction(lambda t: i.Accessor(t.var, t.path))

        # Iterating over objects
        iteration = FOR + target('target') + IN + accessor('accessor')
        iterations = Group(ZeroOrMore(iteration))
        #
        iteration.setParseAction(lambda t: i.Iteration(t.target, t.accessor))

        predicate_args = Group(Optional(accessor + ZeroOrMore(comma + accessor) + Optional(comma)))
        predicate_spec = predicate_name('pred') + lpar + predicate_args('args') + rpar + iterations('iters') + semicolon
        predicate_specs = Group(ZeroOrMore(predicate_spec))
        #
        predicate_spec.setParseAction(lambda t: i.Predicate(t.pred, t.args, t.iters))

        # Allow optional types, e.g., Set<Node> etc.
        input_type = Forward()
        input_type << (py_qualified_identifier('type_name') + Group(Optional(langle + input_type + ZeroOrMore(comma + input_type) + rangle))('type_args'))
        input_arg = Group((input_type('type') + var('name')) | var('name'))
        input_args = Group(Optional(input_arg + ZeroOrMore(comma + input_arg) + Optional(comma)))

        input_statement = INPUT + lpar + input_args('args') + rpar + lbrace + predicate_specs('preds') + rbrace
        #
        input_statement.setParseAction(lambda t: i.InputSpec((x.name for x in t.args), t.preds))
        return input_statement


def InputSpecParser():
    '''Syntax of the INPUT statement (supports comments starting with '%').'''
    with PyParsingDefaultWhitespaceChars(DEFAULT_WHITESPACE_CHARS):
        return ignore_comments(RawInputSpecParser())


def RawOutputSpecParser():
    '''Syntax of the OUTPUT statement (and nothing else).'''
    with PyParsingDefaultWhitespaceChars(DEFAULT_WHITESPACE_CHARS):
        OUTPUT = CaselessKeyword('OUTPUT').suppress()
        QUERY = CaselessKeyword('query').suppress()
        INDEX = CaselessKeyword('index').suppress()
        KEY = CaselessKeyword('key').suppress()
        CONTENT = CaselessKeyword('content').suppress()
        SET = CaselessKeyword('set').suppress()
        SEQUENCE = CaselessKeyword('sequence').suppress()
        DICTIONARY = CaselessKeyword('dictionary').suppress()
        NOT = CaselessKeyword('not').suppress()

        constant = integer | QuotedString('"', escChar='\\')
        constant.setParseAction(lambda t: o.Constant(t[0]))  # not strictly necessary to wrap this, but it simplifies working with the syntax tree

        asp_variable_name = Word(alphas_uppercase, alphanums + '_')
        asp_variable_anonymous = Keyword('_')
        asp_variable = asp_variable_anonymous | asp_variable_name
        asp_variable_expr = asp_variable_name.copy()
        #
        asp_variable_name.setParseAction(lambda t: asp.Variable(t[0]))
        asp_variable_anonymous.setParseAction(lambda t: asp.AnonymousVariable())
        asp_variable_expr.setParseAction(lambda t: o.Variable(t[0]))

        # TODO:
        # Instead of explicitly marking references with '&', we might just define a convention as follows:
        #   * Output names start with lowercase characters
        #   * ASP variables start with uppercase characters (as they do in actual ASP code)
        reference = amp + py_identifier
        reference.setParseAction(lambda t: o.Reference(t[0]))  # to distinguish from literal string values

        # Note: must be able to distinguish between unquoted and quoted constants
        asp_constant_symbol = Word(alphas_lowercase, alphanums + '_')
        asp_quoted_string = QuotedString('"', escChar='\\')
        asp_quoted_string.setParseAction(lambda t: asp.QuotedConstant(t[0]))
        term = (asp_constant_symbol | asp_quoted_string | asp_variable | positive_integer).setResultsName('terms', listAllMatches=True)
        terms = Optional(term + ZeroOrMore(comma + term))
        classical_atom = predicate_name('predicate') + Optional(lpar + terms + rpar)
        # Builtin atoms
        builtin_op_binary = (Literal('=') | '==' | '!=' | '<>' | '<' | '<=' | '>' | '>=' | '#succ').setResultsName('predicate')
        builtin_atom_binary = term + builtin_op_binary + term
        builtin_atom_binary_prefix = builtin_op_binary + lpar + term + comma + term + rpar
        builtin_atom = builtin_atom_binary | builtin_atom_binary_prefix
        #
        body_atom = classical_atom | builtin_atom
        pos_body_atom = body_atom.copy()
        neg_body_atom = NOT + body_atom
        pos_body_atom.setParseAction(lambda t: asp.Literal(t.predicate, tuple(t.terms), False))
        neg_body_atom.setParseAction(lambda t: asp.Literal(t.predicate, tuple(t.terms), True))
        body_literal = neg_body_atom | pos_body_atom
        #
        asp_query = Group(body_literal + ZeroOrMore(comma + body_literal))
        asp_query.setParseAction(lambda t: asp.Query(tuple(t[0])))

        expr = Forward()

        # TODO: Instead of semicolon, we could use (semicolon | FollowedBy(rbrace)) to make the last semicolon optional (but how would that work with asp_query...)
        query_clause = QUERY + colon + asp_query('query') + semicolon
        content_clause = CONTENT + colon + expr('content') + semicolon
        index_clause = INDEX + colon + asp_variable_expr('index') + semicolon
        key_clause = KEY + colon + expr('key') + semicolon
        #
        simple_set_spec = SET + lbrace + predicate_name('predicate') + slash + positive_integer('arity') + Optional(rightarrow + py_qualified_identifier('constructor')) + rbrace
        set_spec = SET + lbrace + (query_clause & content_clause) + rbrace
        # TODO: add clause like "at_missing_index: skip;", "at_missing_index: 0;", "at_missing_index: None;"
        sequence_spec = SEQUENCE + lbrace + (query_clause & content_clause & index_clause) + rbrace
        dictionary_spec = DICTIONARY + lbrace + (query_clause & content_clause & key_clause) + rbrace
        expr_collection = set_spec | simple_set_spec | sequence_spec | dictionary_spec
        #
        simple_set_spec.setParseAction(lambda t: o.ExprSimpleSet(t.predicate, t.arity, t.get('constructor')))
        set_spec.setParseAction(lambda t: o.ExprSet(t.query, t.content))
        sequence_spec.setParseAction(lambda t: o.ExprSequence(t.query, t.content, t.index))
        dictionary_spec.setParseAction(lambda t: o.ExprDictionary(t.query, t.content, t.key))

        expr_obj_args = Group(Optional(expr + ZeroOrMore(comma + expr) + Optional(comma)))
        expr_obj = Optional(py_qualified_identifier, default=None)('constructor') + lpar + expr_obj_args('args') + rpar
        #
        expr_obj.setParseAction(lambda t: o.ExprObject(t.constructor, t.args))

        # Note: "|" always takes the first match, that's why we have to parse variable names after obj (otherwise "variable name" might consume the identifier of expr_obj)
        expr << (constant | expr_collection | expr_obj | reference | asp_variable_expr)

        named_output_spec = py_identifier('name') + equals + expr('expr') + semicolon
        output_statement = OUTPUT + lbrace + ZeroOrMore(named_output_spec) + rbrace
        #
        named_output_spec.setParseAction(lambda t: (t.name, t.expr))
        output_statement.setParseAction(lambda t: o.OutputSpec(t))
        return output_statement


def OutputSpecParser():
    '''Syntax of the OUTPUT statement (supports comments starting with '%').'''
    with PyParsingDefaultWhitespaceChars(DEFAULT_WHITESPACE_CHARS):
        return ignore_comments(RawOutputSpecParser())


def RawSpecParser():
    '''Syntax of the whole I/O mapping specification: One INPUT statement and one OUTPUT statement in any order. This parser does not support comments.'''
    with PyParsingDefaultWhitespaceChars(DEFAULT_WHITESPACE_CHARS):
        i = RawInputSpecParser().setResultsName('input')
        o = RawOutputSpecParser().setResultsName('output')
        p = Optional(i) & Optional(o)
        # Note: t.get(n) returns None if n doesn't exist while t.n would return an empty string
        p.setParseAction(lambda t: (t.get('input'), t.get('output')))  # TODO
        return p


def SpecParser():
    '''Syntax of the whole I/O mapping specification: One INPUT statement and one OUTPUT statement in any order. This parser supports comments starting with '%'.'''
    with PyParsingDefaultWhitespaceChars(DEFAULT_WHITESPACE_CHARS):
        return ignore_comments(RawOutputSpecParser())


class EmbeddedSpecParser:
    '''Syntax of the whole I/O mapping specification, embedded in ASP comments starting with '%!'.'''
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

    spec_parser = RawSpecParser()

    # TODO:
    # A reasonable simplification might be to only allow %! comments for input specification at the start of a line,
    # i.e. only some whitespace may be before %! comments, and no ASP code.
    embedded_re = re.compile(r'''
        ^  # Start of each line (in MULTILINE mode)
        # The ASP part before comments
        (?:
            [^\n%"]  # anything except newlines, comment start, and quotes
            |
            # Quoted string: any char except newlines/backslash/quotes, or backslash escape sequences
            " (?: [^\n\\"] | \\. )* "
        )*
        %\!                     # Our specification language is embedded in special %! comments
        (?P<spec> [^\n%]* )     # The part we want to extract
        (?: %.* )?              # Comments in the specification language also start with % (like regular ASP comments)
        $  # end of each line (in MULTILINE mode)
    ''', re.MULTILINE | re.VERBOSE)

    @classmethod
    def extractFromString(cls, string):
        return '\n'.join(m.group('spec') for m in cls.embedded_re.finditer(string))

    def parseString(self, string, *, parseAll=True):
        return (_parse(type(self).spec_parser, type(self).extractFromString(string)),)


def AnswerSetParser():
    '''Parse the answer set from a single line of dlvhex2's output.'''
    with PyParsingDefaultWhitespaceChars(DEFAULT_WHITESPACE_CHARS):
        # As per the specification, we always return constants as strings. Conversion has to be performed explicitly with int(). See also `asp.RawAnswerSet` type.
        str_integer = Word(nums).setName('integer')
        quoted_string = QuotedString(quoteChar='"', escChar='\\')
        constant_symbol = Word(alphas_lowercase, alphanums + '_')
        arg = str_integer | quoted_string | constant_symbol
        fact = predicate_name('pred') + Group(Optional(lpar + arg + ZeroOrMore(comma + arg) + rpar))('args')
        answer_set = lbrace + Optional(fact + ZeroOrMore(comma + fact)) + rbrace  # + LineEnd()
        #
        fact.setParseAction(lambda t: (t.pred, tuple(t.args)))

        def collect_facts(t) -> asp.RawAnswerSet:
            d = {}  # type: MutableMapping[str, List[Tuple[str, ...]]]
            for (pred, args) in t:
                if pred not in d:
                    d[pred] = [args]
                    # Note:
                    # Technically we should use a set instead of a list here,
                    # but the ASP solver already performs the deduplication for us
                    # so there is no need to check for collisions again.
                    #
                    # Note:
                    # dlvhex2 differentiates between abc and "abc",
                    # but on the python side they are represented by the same string 'abc'.
                    # It is the responsibility of the ASP programmer to ensure quoted and
                    # non-quoted strings aren't mixed (this library only generates quoted
                    # strings during input mapping).
                    #
                    # What we could do:
                    # * Wrap unquoted constants in a class (so the "common" case of quoted constants is as before)
                    # * Or, probably better: Issue a warning if quoted and unquoted constants are mixed (maybe check this only in debug mode)
                else:
                    d[pred].append(args)
            return d  # type: ignore
        answer_set.setParseAction(collect_facts)
        return answer_set


def _parse(parser, string):
    try:
        result = parser.parseString(string, parseAll=True)
        return result[0]
    except ParseException:
        raise
    # except:
    #     pass  # TODO


class LazyInit:
    def __init__(self, constructor):
        self._lazy_constructor = constructor
        self._lazy_obj = None

    @property
    def lazy_obj(self):
        if self._lazy_obj is None:
            self._lazy_obj = self._lazy_constructor()
        return self._lazy_obj

    def __getattr__(self, name):
        return getattr(self.lazy_obj, name)


input_spec_parser = LazyInit(InputSpecParser)
output_spec_parser = LazyInit(OutputSpecParser)
spec_parser = LazyInit(SpecParser)
embedded_spec_parser = LazyInit(EmbeddedSpecParser)
answer_set_parser = LazyInit(AnswerSetParser)


def parse_input_spec(string):
    return _parse(input_spec_parser, string)


def parse_output_spec(string):
    return _parse(output_spec_parser, string)


def parse_spec(string):
    return _parse(spec_parser, string)


def parse_embedded_spec(string):
    return _parse(embedded_spec_parser, string)


def parse_answer_set(string: str) -> asp.RawAnswerSet:
    return _parse(answer_set_parser, string)
