========
py-aspio
========

The ASP interface to object-oriented programs, implemented in Python.


Dependencies
============

* An ASP Solver, currently only `dlvhex 2.6+ <https://github.com/hexhex/core>`_ is supported

* `Python 3.5+ <https://www.python.org/>`_

* `pyparsing <https://pypi.python.org/pypi/pyparsing>`_



Installation (for py-aspio development)
=======================================

Clone the repository and install the package in development mode:

::

    git clone https://github.com/hexhex/py-aspio py-aspio
    cd py-aspio
    python3 setup.py develop



Running the tests
=================

::

    python3 setup.py test



Running the typechecker
=======================

Install the ``mypy-lang`` package first (e.g. ``pip3 install mypy-lang``).
To run the typechecker::

    mypy -p aspio
