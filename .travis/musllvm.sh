#!/bin/bash -x
# Make sure we exit if there is a failure
set -e


export PATH=/usr/lib/llvm-3.5/bin:${PATH}
export LLVM_COMPILER=clang
export WLLVM_OUTPUT=WARNING

wllvm-sanity-checker


git clone https://github.com/SRI-CSL/musllvm.git .
cd musllvm
WLLVM_CONFIGURE_ONLY=1  CC=wllvm ./configure --target=LLVM --build=LLVM
make
extract-bc --bitcode ./lib/libc.a

if [ -s "./lib/libc.a.bc" ]
then
    echo "libc.a.bc."
else
    exit 1
fi






