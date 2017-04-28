#!/bin/bash -x
# Make sure we exit if there is a failure
set -e


export PATH=/usr/lib/llvm-3.5/bin:${PATH}
export LLVM_COMPILER=clang
export WLLVM_OUTPUT=WARNING

wllvm-sanity-checker

#setup the store so we test that feature as well
export WLLVM_BC_STORE=/tmp/bc
mkdir /tmp/bc

cd ./test/test_files
make clean
CC=wllvm make one
mv main ../..
make clean
cd ../..
extract-bc main

if [ -s "main.bc" ]
then
    echo "main.bc exists."
else
    exit 1
fi
