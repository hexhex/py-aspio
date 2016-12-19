from setuptools import setup, find_packages

setup(
    name='aspio',
    version='0.0.1',
    description='ASP interface to object-oriented programs',
    long_description='This library simplifies integration of Answer Set Programming into Python applications.',
    url='https://github.com/hexhex/py-aspio',

    packages=find_packages(exclude=['*.tests', '*.tests.*', 'tests.*', 'tests']),

    install_requires=[
        'pyparsing >= 2.1.4',
    ],

    author='Jakob Rath',
    author_email='jakob.rath@student.tuwien.ac.at',
    license='MIT',

    test_suite='aspio.tests',

    # A list of classifiers can be found at
    # https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        'Development Status :: 3 - Alpha',

        'Intended Audience :: Developers',
        'Intended Audience :: Science/Research',
        'Topic :: Scientific/Engineering :: Artificial Intelligence',

        'License :: OSI Approved :: MIT License',

        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
    ],
)
