Introduction to WLLVM
=====================

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

This two-phase build process is necessary to be a drop-in replacement
for ``gcc`` or ``g++`` in any build system.  Using the LTO framework in gcc
and the gold linker plugin works in many cases, but fails in the
presence of static libraries in builds.  WLLVM's approach has the
distinct advantage of generating working binaries, in case some part
of a build process requires that.

WLLVM works with either ``clang`` or the ``gcc dragonegg`` plugin.


Usage
-----

WLLVM includes four python executables: ``wllvm`` for compiling C code
and ``wllvm++`` for compiling C++, an auxiliary tool ``extract-bc`` for
extracting the bitcode from a build product (object file, executable, library
or archive), and a sanity checker, ``wllvm-sanity-checker`` for detecting
configuration oversights.

Three environment variables must be set to use these wrappers:

 * ``LLVM_COMPILER`` should be set to either ``dragonegg`` or ``clang``.
 * ``LLVM_GCC_PREFIX`` should be set to the prefix for the version of gcc that should
   be used with dragonegg.  This can be empty if there is no prefix.  This variable is
   not used if ``$LLVM_COMPILER == clang``.
 * ``LLVM_DRAGONEGG_PLUGIN`` should be the full path to the dragonegg plugin.  This
   variable is not used if ``$LLVM_COMPILER == clang``.

Once the environment is set up, just use ``wllvm`` and ``wllvm++`` as your C
and C++ compilers, respectively.


In addition to the above environment variables the following can be optionally used:

 * ``LLVM_CC_NAME`` can be set if your clang compiler is not called ``clang`` but
   something like ``clang-3.7``. Similarly ``LLVM_CXX_NAME`` can be used to describe
   what the C++ compiler is called. Note that in these sorts of cases, the environment
   variable ``LLVM_COMPILER`` should still be set to ``clang`` not ``clang-3.7`` etc.
   We also pay attention to the environment variables ``LLVM_LINK_NAME`` and ``LLVM_AR_NAME`` in an
   analagous way,  since they too get adorned with suffixes in various Linux distributions.

 * ``LLVM_COMPILER_PATH`` can be set to the absolute path to the folder that
   contains the compiler and other LLVM tools such as ``llvm-link`` to be used.
   This prevents searching for the compiler in your PATH environment variable.
   This can be useful if you have different versions of clang on your system
   and you want to easily switch compilers without tinkering with your PATH
   variable.
   Example ``LLVM_COMPILER_PATH=/home/user/llvm_and_clang/Debug+Asserts/bin``.

 * ``WLLVM_CONFIGURE_ONLY`` can be set to anything. If it is set, ``wllvm``
   and ``wllvm++`` behave like a normal C or C++ compiler. They do not
   produce bitcode.  Setting ``WLLVM_CONFIGURE_ONLY`` may prevent
   configuration errors caused by the unexpected production of hidden
   bitcode files.


Documentation
-------------

More detailed documentation as well as some tutorials can be found
here:

https://github.com/SRI-CSL/whole-program-llvm
