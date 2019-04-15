# Compiling Apache on Ubuntu


On a clean 16.04 server machine I will build apache.  Desktop instructions should be no different.

```
>more /etc/lsb-release

DISTRIB_ID=Ubuntu
DISTRIB_RELEASE=16.04
DISTRIB_CODENAME=xenial
DISTRIB_DESCRIPTION="Ubuntu 16.04 LTS"
```


## Step 1.

Install wllvm

```
>sudo apt-get update

>sudo install python-pip

>sudo pip install wllvm
```

## Step 2.

I am only going to build apache, not apr, so I first install the prerequisites.

```
>sudo apt-get install llvm clang libapr1-dev libaprutil1-dev libpcre3-dev make

```

At this point, you could check your clang version with `which clang` and `ls -l /usr/bin/clang`.
It should be at least clang-3.8.

## Step 3.

  Configure the wllvm tool to use clang and be relatively quiet:

```
>export LLVM_COMPILER=clang

>export WLLVM_OUTPUT=WARNING
```

## Step 4.

 Fetch apache, untar, configure, then build:

```

>wget https://archive.apache.org/dist/httpd/httpd-2.4.23.tar.gz

>tar xfz httpd-2.4.23.tar.gz

>cd httpd-2.4.23

>CC=wllvm ./configure

>make
```

## Step 5.

Extract the bitcode.

```
>extract-bc httpd

>ls -la httpd.bc
-rw-r--r-- 1 vagrant vagrant 1119584 Aug  4 20:02 httpd.bc
```

## Step 6.

Turn the bitcode into a second executable binary. (optional -- just for fun and sanity checking)

```
llc -filetype=obj httpd.bc
clang httpd.o  -Wl,--export-dynamic -lpthread -lapr-1 -laprutil-1 -lpcre -o httpd_from_bc
```
See [here](http://tldp.org/HOWTO/Program-Library-HOWTO/shared-libraries.html) for an explanation of the
```
-Wl,--export-dynamic
```
incantation.
