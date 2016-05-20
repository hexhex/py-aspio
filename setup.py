from setuptools import setup, find_packages

setup(
    name = 'dlvhex',
    version = '0.0.1',
    description = '',  # TODO
    url = '',  # TODO

    packages = find_packages(exclude=['*.tests', '*.tests.*', 'tests.*', 'tests']),

    requires = 'pyparsing',  # TODO

    author = 'Jakob Rath',
    author_email = 'jakob.rath@student.tuwien.ac.at',
    license = 'MIT',
)
