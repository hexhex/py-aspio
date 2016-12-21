Packaging
=========

See https://packaging.python.org/distributing/#packaging-your-project.

1. First make sure the correct git branch is checked out, and all incomplete changes are stashed.

2. To prepare a new release:
   1. Update the version number in ``setup.py``.
   2. Commit (``Prepare release 1.2.3``?)
   3. Add tag: ``git tag v1.2.3``.

3. Create a source distribution:::

    python3 setup.py sdist

4. Create a binary distribution (note that we don't support Python 2, so we should not build a universal wheel):::

    python3 setup.py bdist_wheel

5. Upload to PyPI:::

   twine upload dist/*
