Introduction
============

This is a small python-based wrapper around a GCC-compatible compiler
to make it easy to build whole-program (or whole-library) LLVM bitcode
files.  The idea is that it first invokes the compiler as normal to
build a real object file.  It then invokes a bitcode compiler to
generate the corresponding bitcode, recording the location of the
bitcode file in an ELF section of the actual object file.

When object files are linked together, the contents of non-special ELF
sections are just concatenated (so we don't lose the locations of any
of the constituent bitcode files).

This package contains an extra utility, extract-bc, to read the
contents of this ELF section and link all of the bitcode into a single
whole-program bitcode file. This utility can also be used on built
native static libraries to generate LLVM bitcode archives.

This two-phase build process is slower and more elaborate than normal,
but in practice is necessary to be a drop-in replacement for gcc in
any build system.  Approaches using the LTO framework in gcc and the
gold linker plugin work for many cases, but fail in the presence of
static libraries in builds.  This approach has the distinct advantage
of generating working binaries, in case some part of a build process
actually requires that.

Currently, this package only works using clang or the dragonegg plugin
with gcc 4.5 (with the required patch for dragonegg).

Usage
=====

There are three environment variables that must be set to use this
wrapper script:

 * `LLVM_COMPILER` should be set to 'dragonegg' or 'clang'.
 * `LLVM_GCC_PREFIX` should be set to the prefix for the version of gcc that should
   be used with dragonegg.  This can be empty if there is no prefix.  This variable is
   not used if `$LLVM_COMPILER == clang`.
 * `LLVM_DRAGONEGG_PLUGIN` should be the full path to the dragonegg plugin.  This
   variable is not used if `$LLVM_COMPILER == clang`.

Once the environment is set up, just use wllvm and wllvm++ as your C
and C++ compilers, respectively.

In addition to the above environment variables the following can be optionally used:

 * `LLVM_COMPILER_PATH` can be set to the absolute path to the folder that
   contains the compiler and other LLVM tools such as `llvm-link` to be used.
   This prevents searching for the compiler in your PATH environment variable.
   This can be useful if you have different versions of clang on your system
   and you want to easily switch compilers without tinkering with your PATH
   variable.
   Example `LLVM_COMPILER_PATH=/home/user/llvm_and_clang/Debug+Asserts/bin`.

Example building bitcode module
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

Example building bitcode archive
================================

    export LLVM_COMPILER=clang
    tar -xvf bullet-2.81-rev2613.tgz
    mkdir bullet-bin
    cd bullet-bin
    CC=wllvm CXX=wllvm++ cmake ../bullet-2.81-rev2613/
    make

    # Produces src/LinearMath/libLinearMath.bca
    extract-bc src/LinearMath/libLinearMath.a

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
