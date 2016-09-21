from setuptools import setup, find_packages

setup(
    name='aspio',
    version='0.0.1',
    description='ASP interface to object-oriented programs',
    url='https://github.com/hexhex/py-aspio',

    packages=find_packages(exclude=['*.tests', '*.tests.*', 'tests.*', 'tests']),

    install_requires=[
        'pyparsing >= 2.1.4',
    ],

    author='Jakob Rath',
    author_email='jakob.rath@student.tuwien.ac.at',
    license='MIT',

    test_suite='aspio.tests',
)
