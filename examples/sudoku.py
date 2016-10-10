#!/usr/bin/env python3
from pathlib import Path
from typing import Sequence
import logging
import aspio

aspio.log.addHandler(logging.StreamHandler())
# aspio.log.setLevel(logging.DEBUG)  # Uncomment to enable debug messages from aspio

asp_file = Path(__file__).with_name('sudoku.dl')
program = aspio.Program(filename=asp_file)

# sudoku[y][x] is the number in cell (x,y)
Sudoku = Sequence[Sequence[int]]


def parse_sudoku(string: str) -> Sudoku:
    '''Create sudoku from a string containing exactly 9*9 digits (possibly among other characters that might be used for alignment).'''
    nums = [int(c) for c in string if c.isdigit()]
    grid = [nums[(i * 9):((i + 1) * 9)] for i in range(9)]
    return grid


def format_sudoku(grid: Sudoku) -> str:
    s = ''
    for y, row in enumerate(grid):
        if y > 0 and y % 3 == 0:
            s += '\n'
        for x, num in enumerate(row):
            if x > 0 and x % 3 == 0:
                s += ' '
            s += str(num)
        s += '\n'
    return s


def main():
    grid = parse_sudoku('''

        301 092 000
        056 000 100
        824 100 609

        047 320 800
        000 000 000
        005 061 790

        502 007 461
        003 000 980
        000 480 305

    ''')

    results = program.solve(grid)

    for i, solved_grid in enumerate(results.each_solved_grid):
        print('Solution {0}:\n'.format(i + 1))
        print(format_sudoku(solved_grid))


if __name__ == '__main__':
    main()
