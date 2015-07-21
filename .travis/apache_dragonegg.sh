#!/bin/bash -x
# Make sure we exit if there is a failure
set -e

export dragonegg_disable_version_check=true

export PATH=/usr/lib/llvm-3.0/bin:${WLLVM_HOME}:${PATH}
export LLVM_COMPILER=dragonegg
export LLVM_GCC_PREFIX=llvm-
export LLVM_DRAGONEGG_PLUGIN=/usr/lib/gcc/x86_64-linux-gnu/4.6/plugin/dragonegg.so

export WLLVM_OUTPUT=WARNING

wget http://www.csl.sri.com/~iam/httpd-2.4.12.tar.gz
tar xfz httpd-2.4.12.tar.gz
mv httpd-2.4.12 apache_dragonegg
cd apache_dragonegg
CC=wllvm ./configure
make
extract-bc httpd


if [ -s "httpd.bc" ]
then
    echo "httpd.bc built."
else
    exit 1
fi






