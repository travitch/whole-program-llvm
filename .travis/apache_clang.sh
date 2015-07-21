#!/bin/bash -x
# Make sure we exit if there is a failure
set -e


export PATH=/usr/lib/llvm-3.4/bin:${WLLVM_HOME}:${PATH}
export LLVM_COMPILER=clang
export WLLVM_OUTPUT=WARNING

wget http://www.csl.sri.com/~iam/httpd-2.4.12.tar.gz
tar xfz httpd-2.4.12.tar.gz
mv httpd-2.4.12 apache_clang
cd apache_clang
CC=wllvm ./configure
make
extract-bc httpd


if [ -s "httpd.bc" ]
then
    echo "httpd.bc built."
else
    exit 1
fi






