![WLLVM](img/dragon128x128.png?raw_true)Whole Program LLVM

[![License: MIT](https://img.shields.io/badge/License-MIT-blueviolet.svg)](https://opensource.org/licenses/MIT)
[![PyPI version](https://badge.fury.io/py/wllvm.svg)](https://badge.fury.io/py/wllvm)
[![Build Status](https://travis-ci.org/SRI-CSL/whole-program-llvm.svg?branch=master)](https://travis-ci.org/SRI-CSL/whole-program-llvm)
[![PyPI Statistics](https://img.shields.io/pypi/dm/wllvm.svg)](https://pypistats.org/packages/wllvm)


Introduction
------------

This project, WLLVM, provides tools for building whole-program (or
whole-library) LLVM bitcode files from an unmodified C or C++
source package. It currently runs on `*nix` platforms such as Linux,
FreeBSD, and Mac OS X.

WLLVM provides python-based compiler wrappers that work in two
steps. The wrappers first invoke the compiler as normal. Then, for
each object file, they call a bitcode compiler to produce LLVM
bitcode. The wrappers also store the location of the generated bitcode
file in a dedicated section of the object file.  When object files are
linked together, the contents of the dedicated sections are
concatenated (so we don't lose the locations of any of the constituent
bitcode files). After the build completes, one can use a WLLVM
utility to read the contents of the dedicated section and link all of
the bitcode into a single whole-program bitcode file. This utility
works for both executable and native libraries.

This two-phase build process is necessary to be a drop-in replacement
for gcc or g++ in any build system.  Using the LTO framework in gcc
and the gold linker plugin works in many cases, but fails in the
presence of static libraries in builds.  WLLVM's approach has the
distinct advantage of generating working binaries, in case some part
of a build process requires that.

WLLVM works with either clang or the gcc dragonegg plugin. If you are not interested in dragonegg support,
and speed is an issue for you, you may want to try out [gllvm.](https://github.com/SRI-CSL/gllvm)

Installation
------------

As of August 2016 WLLVM is now a pip package. You can just do:

    pip install wllvm

or

    sudo pip install wllvm

depending on your machine's permissions.


Tutorial
=======
If you want to develop or use the development version:

```
git clone https://github.com/travitch/whole-program-llvm
cd whole-program-llvm
```

Now you need to install WLLVM. You can either install
globally on your system in develop mode:

```
sudo pip install -e .
```

or install WLLVM into a virtual python environment
in develop mode to avoid installing globally:

```
virtualenv venv
source venv/bin/activate
pip install -e .
```



Usage
-----

WLLVM includes four python executables: `wllvm` for compiling C code
and `wllvm++` for compiling C++, an auxiliary tool `extract-bc` for
extracting the bitcode from a build product (object file, executable, library
or archive), and a sanity checker, `wllvm-sanity-checker` for detecting
configuration oversights.

Three environment variables must be set to use these wrappers:

 * `LLVM_COMPILER` should be set to either `dragonegg` or `clang`.
 * `LLVM_GCC_PREFIX` should be set to the prefix for the version of gcc that should
   be used with dragonegg.  This can be empty if there is no prefix.  This variable is
   not used if `$LLVM_COMPILER == clang`.
 * `LLVM_DRAGONEGG_PLUGIN` should be the full path to the dragonegg plugin.  This
   variable is not used if `$LLVM_COMPILER == clang`.

Once the environment is set up, just use `wllvm` and `wllvm++` as your C
and C++ compilers, respectively.


In addition to the above environment variables the following can be optionally used:

 * `LLVM_CC_NAME` can be set if your clang compiler is not called `clang` but
    something like `clang-3.7`. Similarly `LLVM_CXX_NAME` can be used to describe
    what the C++ compiler is called. Note that in these sorts of cases, the environment
    variable `LLVM_COMPILER` should still be set to `clang` not `clang-3.7` etc.
    We also pay attention to the environment variables `LLVM_LINK_NAME` and `LLVM_AR_NAME` in an
    analagous way,  since they too get adorned with suffixes in various Linux distributions.

 * `LLVM_COMPILER_PATH` can be set to the absolute path to the folder that
   contains the compiler and other LLVM tools such as `llvm-link` to be used.
   This prevents searching for the compiler in your PATH environment variable.
   This can be useful if you have different versions of clang on your system
   and you want to easily switch compilers without tinkering with your PATH
   variable.
   Example `LLVM_COMPILER_PATH=/home/user/llvm_and_clang/Debug+Asserts/bin`.

* `WLLVM_CONFIGURE_ONLY` can be set to anything. If it is set, `wllvm`
   and `wllvm++` behave like a normal C or C++ compiler. They do not
   produce bitcode.  Setting `WLLVM_CONFIGURE_ONLY` may prevent
   configuration errors caused by the unexpected production of hidden
   bitcode files. It is sometimes required when configuring a build.





Building a bitcode module with clang
------------------------------------

    export LLVM_COMPILER=clang

    tar xf pkg-config-0.26.tar.gz
    cd pkg-config-0.26
    CC=wllvm ./configure
    make

This should produce the executable `pkg-config`. To extract the bitcode:

    extract-bc pkg-config

which will produce the bitcode module `pkg-config.bc`.


Tutorials
---------

A gentler set of instructions on building apache in a vagrant Ubuntu 14.04 can be found
[here,](doc/tutorial.md) and for Ubuntu 16.04 [here.](doc/tutorial-ubuntu-16.04.md)

Building a bitcode module with dragonegg
----------------------------------------

    export LLVM_COMPILER=dragonegg
    export LLVM_GCC_PREFIX=llvm-
    export LLVM_DRAGONEGG_PLUGIN=/unsup/llvm-2.9/lib/dragonegg.so

    tar xf pkg-config-0.26.tar.gz
    cd pkg-config-0.26
    CC=wllvm ./configure
    make

Again, this should produce the executable `pkg-config`. To extract the bitcode:

    extract-bc pkg-config

which will produce the bitcode module `pkg-config.bc`.


Building bitcode archive
------------------------

    export LLVM_COMPILER=clang
    tar -xvf bullet-2.81-rev2613.tgz
    mkdir bullet-bin
    cd bullet-bin
    CC=wllvm CXX=wllvm++ cmake ../bullet-2.81-rev2613/
    make

    # Produces src/LinearMath/libLinearMath.bca
    extract-bc src/LinearMath/libLinearMath.a

Note that by default extracting bitcode from an archive produces
an archive of bitcode. You can also extract the bitcode directly into a module.

    extract-bc -b src/LinearMath/libLinearMath.a

produces `src/LinearMath/libLinearMath.a.bc`.



Building an Operating System
----------------------------

To see how to build freeBSD 10.0 from scratch check out this
[guide.](doc/tutorial-freeBSD.md)


Configuring without building bitcode
------------------------------------

Sometimes it is necessary to disable the production of bitcode.
Typically this is during configuration, where the production
of unexpected files can confuse the configure script. For this
we have a flag `WLLVM_CONFIGURE_ONLY` which can be used as
follows:

    WLLVM_CONFIGURE_ONLY=1 CC=wllvm ./configure
    CC=wllvm make


Building a bitcode archive then extracting the bitcode
------------------------------------------------------

    export LLVM_COMPILER=clang
    tar xvfz jansson-2.7.tar.gz
    cd jansson-2.7
    CC=wllvm ./configure
    make
    mkdir bitcode
    cp src/.libs/libjansson.a bitcode
    cd bitcode
    extract-bc libjansson.a
    llvm-ar x libjansson.bca
    ls -la


Preserving bitcode files in a store
--------------------------------

Sometimes it can be useful to preserve the bitcode files produced in a
build, either to prevent deletion or to retrieve it later. If the
environment variable `WLLVM_BC_STORE` is set to the absolute path of
an existing directory,
then WLLVM will copy the produced bitcode file into that directory.
The name of the copied bitcode file is the hash of the path to the
original bitcode file.  For convenience, when using both the manifest
feature of `extract-bc` and the store, the manifest will contain both
the original path, and the store path.

Cross-Compilation
-----------------

To support cross-compilation WLLVM supports the `-target` triple used by clang.
More information can be found
[here.](https://clang.llvm.org/docs/CrossCompilation.html#target-triple)

Additionally, WLLVM leverages `objcopy` for some of its heavy lifting. When
cross-compiling you must ensure to use the appropriate `objcopy` for the target
architecture. The `BINUTILS_TARGET_PREFIX` environment variable can be used to
set the objcopy of choice, for example, `arm-linux-gnueabihf`.

LTO Support
-----------

In some situations it is desirable to pass certain flags to clang in the step that
produces the bitcode. This can be fulfilled by setting the
`LLVM_BITCODE_GENERATION_FLAGS` environment variable to the desired
flags, for example `"-flto -fwhole-program-vtables"`.

Debugging
---------

The WLLVM tools can show various levels of output to aid with debugging.
To show this output set the `WLLVM_OUTPUT_LEVEL` environment
variable to one of the following levels:

 * `ERROR`
 * `WARNING`
 * `INFO`
 * `DEBUG`

For example:
```
    export WLLVM_OUTPUT_LEVEL=DEBUG
```
Output will be directed to the standard error stream, unless you specify the
path of a logfile via the `WLLVM_OUTPUT_FILE` environment variable.

For example:
```
    export WLLVM_OUTPUT_FILE=/tmp/wllvm.log
```


Sanity Checking
---------------

Too many environment variables? Try doing a sanity check:

```
wllvm-sanity-checker
```
it might point out what is wrong.


License
-------

WLLVM is released under the MIT license. See the file `LICENSE` for [details.](LICENSE)
