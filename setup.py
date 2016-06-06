from setuptools import setup, find_packages
import setuptools.command.test


class TestCommand(setuptools.command.test.test):
    """Setuptools test command explicitly using test discovery."""
    # see http://stackoverflow.com/a/23443087/1889401

    def _test_args(self):
        yield 'discover'
        yield from super(TestCommand, self)._test_args()


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
    cmdclass={
        'test': TestCommand,
    },
)
