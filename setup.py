from setuptools import setup, find_packages
import os
import glob

from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, 'README.rst'), encoding='utf-8') as f:
    long_description = f.read()

# use the in house version number so we stay in synch with ourselves.
from wllvm.version import wllvm_version

setup(
    name='wllvm',
    version=wllvm_version,
    description='Whole Program LLVM',
    long_description=long_description,
    url='https://github.com/SRI-CSL/whole-program-llvm',
    author='Ian A. Mason, Tristan Ravitch, Dan Liew, Bruno Dutertre, Benjamin Schubert, Berkeley Churchill, Marko Dimjasevic, Will Dietz, Fabian Mager, Ben Liblit, Andrew Santosa, Tomas Kalibera, Loic  Gelle, Joshua Cranmer, Alexander Bakst, Miguel Arroyo.',
    author_email='iam@csl.sri.com',


    include_package_data=True,

    packages=find_packages(),

    entry_points = {
        'console_scripts': [
            'wllvm-as = wllvm.as:main',
            'wllvm = wllvm.wllvm:main',
            'wllvm++ = wllvm.wllvmpp:main',
            'wfortran = wllvm.wfortran:main',
            'wllvm-sanity-checker = wllvm.sanity:main',
            'extract-bc = wllvm.extractor:main',
        ],
    },

    license='MIT',

    classifiers=[
        'Development Status :: 4 - Beta',
        'Natural Language :: English',
        'Intended Audience :: Science/Research',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Compilers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Operating System :: MacOS',
        'Operating System :: POSIX :: Linux',
        'Operating System :: POSIX :: BSD',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
    ],
)
