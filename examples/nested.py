#!/usr/bin/env python3
import aspio

program = aspio.Program(code=r'''
    p(1).
    p(2).

    q(1, a).
    q(1, b).
    q(1, c).
    q(2, x).
    q(2, y).
    q(3, no).

    %!  OUTPUT {
    %!      result = set {
    %!          query: p(X);
    %!          content: (int(X), set { query: q(X, Y); content: Y; });
    %!      };
    %!  }
''')
# %!  OUTPUT {
# %!      ys(X) = set { query: q(X, Y); content: Y; }
# %!      result = set {
# %!          query: p(X);
# %!          content: (int(X), ys(X));
# %!      }
# %!  }

expected_result = frozenset({
    (1, frozenset({'a', 'b', 'c'})),
    (2, frozenset({'x', 'y'})),
})

for (i, result) in enumerate(program.solve().each_result):
    print('Answer set {0!s}:'.format(i + 1))
    print('Result         : {0!r}'.format(result))
    print('Expected result: {0!r}'.format(expected_result))
