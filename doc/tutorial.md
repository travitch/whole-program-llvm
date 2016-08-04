# Compiling Apache on Ubuntu


On a clean 14.04 machine I will build apache.

```
>pwd

/vagrant

>more /etc/lsb-release

DISTRIB_ID=Ubuntu
DISTRIB_RELEASE=14.04
DISTRIB_CODENAME=trusty
DISTRIB_DESCRIPTION="Ubuntu 14.04.2 LTS"
```


## Step 1.


Install `wllvm`.

```
>sudo apt-get update

>sudo apt-get install python-pip

>sudo pip install wllvm

```

## Step 2.

I am only going to build apache, not apr, so I first install the prerequisites.

```
>sudo apt-get install llvm-3.4 clang-3.4 libapr1-dev libaprutil1-dev

``` Note `wllvm` is agnostic with respect to llvm versions, when you
use clang, so feel free to install a more recent version if you
wish. However, if you are going to use dragonegg the llvm version is
tightly coupled to the gcc and plugin versions you are using.


## Step 3.

  Configure the wllvm tool to use clang and be relatively quiet:

```
>export LLVM_COMPILER=clang

>export WLLVM_OUTPUT=WARNING
```


## Step 4.

 Fetch apache, untar, configure, then build:

```
>wget https://archive.apache.org/dist/httpd/httpd-2.4.18.tar.gz

>tar xfz httpd-2.4.18.tar.gz

>cd httpd-2.4.18

>CC=wllvm ./configure

>make
```

## Step 5.

Extract the bitcode.

```
>extract-bc -l llvm-link-3.4 httpd

>ls -la httpd.bc
-rw-rw-r--  1 vagrant vagrant  860608 Aug  4 16:55 httpd.bc
```

The extra command line argument to `extract-bc` is because `apt`
installs `llvm-link` as `llvm-link-3.4` so we need to tell `extract-bc`
to use that one.