#!/usr/bin/env python

VERSION = '0.0'
DESCRIPTION = 'Python module to handle bytecode'


def main():
    try:
        from setuptools import setup
    except ImportError:
        from distutils.core import setup

    with open('README.rst', 'r') as f:
        readme = f.read()

    setup(
        name='bytearound',
        version=VERSION,
        license='Apache 2.0 license',
        description=DESCRIPTION,
        long_description=readme,
        author='Jelle Zijlstra',
        author_email='jelle.zijlstra@gmail.com',
        packages=['bytearound'],
        url='https://github.com/JelleZijlstra/bytearound',
    )


if __name__ == '__main__':
    main()
