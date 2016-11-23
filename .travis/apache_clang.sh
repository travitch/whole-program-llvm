#!/bin/bash -x
# Make sure we exit if there is a failure
set -e


export PATH=/usr/lib/llvm-3.5/bin:${PATH}
export LLVM_COMPILER=clang
export WLLVM_OUTPUT=WARNING

wllvm-sanity-checker

wget https://archive.apache.org/dist/httpd/httpd-${APACHE_VER}.tar.gz

tar xfz httpd-${APACHE_VER}.tar.gz
mv httpd-${APACHE_VER} apache_clang

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






