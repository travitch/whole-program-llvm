# from distutils.core import setup
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
from wllvm.util import wllvm_version
    
setup(
    name='wllvm',
    version=wllvm_version, 
    description='Whole Program LLVM',
    long_description=long_description,
    url='https://github.com/SRI-CSL/whole-program-llvm',
    author='Ian A. Mason, ...',
    author_email='iam@csl.sri.com',
    

    packages=find_packages(exclude=['test']),
    
    entry_points = {
        'console_scripts': [
            'wllvm = wllvm.wllvm:main',
            'wllvm++ = wllvm.wllvm++:main',
            'wllvm-sanity-checker = wllvm.wllvm-sanity-checker:main',
            'extract-bc = wllvm.extract-bc:main',
        ],
    },


    
    license='MIT',
    
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Natural Language :: English',
        'Intended Audience :: Developers',
        'Topic :: System :: Distributed Computing',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
    ],
)
