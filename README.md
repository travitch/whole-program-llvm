
[![Build Status](https://travis-ci.org/SRI-CSL/whole-program-llvm.svg?branch=master)](https://travis-ci.org/SRI-CSL/whole-program-llvm)


Introduction
============

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
bitcode files). After the build completes, one can use an WLLVM
utility to read the contents of the dedicated section and link all of
the bitcode into a single whole-program bitcode file. This utility
works for both executable and native libraries.

Currently, WLLVM works with either clang or the gcc dragonegg plugin.

This two-phase build process is necessary to be a drop-in replacement
for gcc or g++ in any build system.  Using the LTO framework in gcc
and the gold linker plugin works in many cases, but fails in the
presence of static libraries in builds.  WLLVM's approach has the
distinct advantage of generating working binaries, in case some part
of a build process requires that.


Usage
=====

WLLVM includes two python executables: `wllvm` for compiling C code
and `wllvm++` for C++, and an auxiliary tool `extract-bc`.

Three environment variables must be set to use these wrappers:

 * `LLVM_COMPILER` should be set to either 'dragonegg' or 'clang'.
 * `LLVM_GCC_PREFIX` should be set to the prefix for the version of gcc that should
   be used with dragonegg.  This can be empty if there is no prefix.  This variable is
   not used if `$LLVM_COMPILER == clang`.
 * `LLVM_DRAGONEGG_PLUGIN` should be the full path to the dragonegg plugin.  This
   variable is not used if `$LLVM_COMPILER == clang`.

Once the environment is set up, just use `wllvm` and `wllvm++` as your C
and C++ compilers, respectively.

In addition to the above environment variables the following can be optionally used:

 * `LLVM_COMPILER_PATH` can be set to the absolute path to the folder that
   contains the compiler and other LLVM tools such as `llvm-link` to be used.
   This prevents searching for the compiler in your PATH environment variable.
   This can be useful if you have different versions of clang on your system
   and you want to easily switch compilers without tinkering with your PATH
   variable.
   Example `LLVM_COMPILER_PATH=/home/user/llvm_and_clang/Debug+Asserts/bin`.

* `WLLVM_CONFIGURE_ONLY` can be set to anything. If it is set, `wllvm`
   and `wllvm++` behave like a normal C or C++ compiler. They do not
   the produce bitcode.  Setting `WLLVM_CONFIGURE_ONLY` may prevent
   configuration errors caused by the unexpected production of hidden
   bitcode files.


Building a bitcode module with clang
====================================

    export LLVM_COMPILER=clang

    tar xf pkg-config-0.26.tar.gz
    cd pkg-config-0.26
    CC=wllvm ./configure
    make

    # Produces pkg-config.bc
    extract-bc pkg-config

Building a bitcode module with dragonegg
========================================

    export LLVM_COMPILER=dragonegg
    export LLVM_GCC_PREFIX=llvm-
    export LLVM_DRAGONEGG_PLUGIN=/unsup/llvm-2.9/lib/dragonegg.so

    tar xf pkg-config-0.26.tar.gz
    cd pkg-config-0.26
    CC=wllvm ./configure
    make

    # Produces pkg-config.bc
    extract-bc pkg-config


Building bitcode archive
========================

    export LLVM_COMPILER=clang
    tar -xvf bullet-2.81-rev2613.tgz
    mkdir bullet-bin
    cd bullet-bin
    CC=wllvm CXX=wllvm++ cmake ../bullet-2.81-rev2613/
    make

    # Produces src/LinearMath/libLinearMath.bca
    extract-bc src/LinearMath/libLinearMath.a


Building an Operating System
============================

To see how to build freeBSD 10.0 from scratch check out this 
[guide.](../master/README-freeBSD.md)


Configuring without building bitcode
================================


    WLLVM_CONFIGURE_ONLY=1 CC=wllvm ./configure
    CC=wllvm make


Debugging
=========

The WLLVM tools can show various levels of output to aid with debugging.
To show this output set WLLVM_OUTPUT to one of the following levels:

 * `CRITICAL`
 * `ERROR`
 * `WARNING`
 * `INFO`
 * `DEBUG`

For example

    export WLLVM_OUTPUT=DEBUG

License
=======

WLLVM is released under the MIT license. See the file `LICENSE` for details.
