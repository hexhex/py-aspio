=========
py-dlvhex
=========

Python integration of the `dlvhex solver <http://www.kr.tuwien.ac.at/research/systems/dlvhex/>`_.


Dependencies
============

* `dlvhex2 <https://github.com/hexhex/core>`_

* python 3.5+

* pyparsing



Installation (for development)
==============================

::

    git clone https://github.com/JakobR/py-dlvhex py-dlvhex
    cd py-dlvhex
    python3 setup.py develop



Running the tests
=================

::

    python3 setup.py test



Running the typechecker
=======================

Install the ``mypy-lang`` package first (e.g. ``pip3 install mypy-lang``).
To run the typechecker::

    mypy -p dlvhex
