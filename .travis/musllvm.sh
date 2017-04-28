#!/bin/bash -x
# Make sure we exit if there is a failure
set -e


export PATH=/usr/lib/llvm-3.5/bin:${PATH}
export LLVM_COMPILER=clang
export WLLVM_OUTPUT=WARNING

wllvm-sanity-checker

#setup the store so we test that feature as well
export WLLVM_BC_STORE=/tmp/bc
mkdir -p /tmp/bc

git clone https://github.com/SRI-CSL/musllvm.git musllvm
cd musllvm
WLLVM_CONFIGURE_ONLY=1  CC=wllvm ./configure --target=LLVM --build=LLVM
make
extract-bc --bitcode ./lib/libc.a

if [ -s "./lib/libc.a.bc" ]
then
    echo "libc.a.bc exists."
else
    exit 1
fi

#now lets makes sure the store has the bitcode too.
mv ./lib/libc.a .
make clean
extract-bc --bitcode ./libc.a

if [ -s "./libc.a.bc" ]
then
    echo "libc.a.bc exists."
else
    exit 1
fi
