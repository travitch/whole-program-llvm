#!/bin/bash -x
# Make sure we exit if there is a failure
set -e

export dragonegg_disable_version_check=true

export PATH=/usr/lib/llvm-3.3/bin:${PATH}
export LLVM_COMPILER=dragonegg
export LLVM_GCC_PREFIX=llvm-
export LLVM_DRAGONEGG_PLUGIN=/usr/lib/gcc/x86_64-linux-gnu/4.7/plugin/dragonegg.so

export WLLVM_OUTPUT=WARNING

wllvm-sanity-checker

wget https://archive.apache.org/dist/httpd/httpd-${APACHE_VER}.tar.gz


tar xfz httpd-${APACHE_VER}.tar.gz
mv httpd-${APACHE_VER} apache_dragonegg
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






