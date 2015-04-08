
[![Build Status](https://travis-ci.org/SRI-CSL/whole-program-llvm.svg?branch=master)](https://travis-ci.org/SRI-CSL/whole-program-llvm)


Introduction
============

This project, WLLVM,  provides tools for building whole-program (or
whole-library) LLVM bitcode files from an unmodified `C` or `C++`
source package. It currently runs on `*nix` platforms such as Linux,
FreeBSD, and Mac OS X.

WLLVM provides python-based compiler wrappers that first
invoke the compiler as normal to build a real object file.  The wrapper then
invokes a bitcode compiler to generate the corresponding bitcode, and
records the location of the bitcode file in a dedicated section of the actual
object file.
When object files are linked together, the contents of the dedicated 
sections are concatenated (so we don't lose the locations of any
of the constituent bitcode files). After the build process is finished,
an WLLVM utility reads the
contents of the dedicated section and links all of the bitcode into a single
whole-program bitcode file. This utility can also be used when building
native libraries to generate corresponding LLVM bitcode archives.

Currently, WLLVM works with either `clang` or the `gcc` dragonegg plugin.





This two-phase build process is slower and more elaborate than normal,
but in practice is necessary to be a drop-in replacement for gcc in
any build system.  Approaches using the LTO framework in gcc and the
gold linker plugin work for many cases, but fail in the presence of
static libraries in builds.  This approach has the distinct advantage
of generating working binaries, in case some part of a build process
actually requires that.


Usage
=====

The project provides a two wrappers, `wllvm`, for `CC` and `wllvm++`, for `CXX`
and an auxillary tool `extract-bc`.


Three environment variables must be set to use these wrappers:

 * `LLVM_COMPILER` should be set to 'dragonegg' or 'clang'.
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

*  `WLLVM_CONFIGURE_ONLY` can be set to anything, when set `wllvm` and `wllvm++`
   will not carry out the second phase that involves the production of bitcode.
   This may prevent configuration errors being cause by the unexpected production
   of the hidden bitcode files.

Building a bitcode module with clang
===============================

    export LLVM_COMPILER=clang

    tar xf pkg-config-0.26.tar.gz
    cd pkg-config-0.26
    CC=wllvm ./configure
    make

    # Produces pkg-config.bc
    extract-bc pkg-config

Building a bitcode module with dragonegg
===============================

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
================================

    export LLVM_COMPILER=clang
    tar -xvf bullet-2.81-rev2613.tgz
    mkdir bullet-bin
    cd bullet-bin
    CC=wllvm CXX=wllvm++ cmake ../bullet-2.81-rev2613/
    make

    # Produces src/LinearMath/libLinearMath.bca
    extract-bc src/LinearMath/libLinearMath.a

Example building an Operating System
================================

To see how to build freeBSD 10.0 from scratch check out the guide 
[here.](../master/README-freeBSD.md)


Example configuring without building bitcode
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
