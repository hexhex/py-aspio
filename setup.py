from setuptools import setup, find_packages

setup(
    name='dlvhex',
    version='0.0.1',
    description='Python integration of the dlvhex solver',
    url='https://github.com/JakobR/py-dlvhex',

    packages=find_packages(exclude=['*.tests', '*.tests.*', 'tests.*', 'tests']),

    install_requires=[
        'pyparsing >= 2.1.4',
    ],

    author='Jakob Rath',
    author_email='jakob.rath@student.tuwien.ac.at',
    license='MIT',

    test_suite='dlvhex.tests',
)
