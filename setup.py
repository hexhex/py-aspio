from setuptools import setup, find_packages
import setuptools.command.test


class TestCommand(setuptools.command.test.test):
    """Setuptools test command explicitly using test discovery."""
    # from http://stackoverflow.com/a/23443087/1889401

    def _test_args(self):
        yield 'discover'
        for arg in super(TestCommand, self)._test_args():
            yield arg


setup(
    name='dlvhex',
    version='0.0.1',
    description='',  # TODO
    url='',  # TODO

    packages=find_packages(exclude=['*.tests', '*.tests.*', 'tests.*', 'tests']),

    requires='pyparsing',  # TODO

    author='Jakob Rath',
    author_email='jakob.rath@student.tuwien.ac.at',
    license='MIT',

    test_suite='dlvhex.tests',
    cmdclass={
        'test': TestCommand,
    },
)
