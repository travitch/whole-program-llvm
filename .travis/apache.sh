#!/bin/bash -x
# Make sure we exit if there is a failure
set -e


export PATH=/usr/lib/llvm-3.4/bin:${WLLVM_HOME}:${PATH}
export LLVM_COMPILER='clang'
export WLLVM_OUTPUT=WARNING

wget http://apache.mirrors.pair.com//httpd/httpd-2.4.12.tar.gz
tar xfz httpd-2.4.12.tar.gz
cd httpd-2.4.12
CC=wllvm ./configure
make
extract-bc httpd


if [ -s "httpd.bc" ]
then
    echo "httpd.bc built."
else
    exit 1
fi






