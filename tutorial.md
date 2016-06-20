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


## Step 0.

Checkout the wllvm repository

```
>git clone https://github.com/SRI-CSL/whole-program-llvm.git
```

## Step 1.

Set up the environment 

```
>export WLLVM_HOME=/vagrant/whole-program-llvm

>export PATH=${WLLVM_HOME}:${PATH}

>which wllvm

/vagrant/whole-program-llvm/wllvm
```

## Step 2.

I am only going to build apache, not apr, so I first install the prerequisites.

```
>sudo apt-get update

>sudo apt-get install llvm-3.4 clang-3.4 libapr1-dev libaprutil1-dev

```

## Step 3.

  Configure the wllvm tool to use clang and be relatively quiet:

```
>export LLVM_COMPILER=clang

>export WLLVM_OUTPUT=WARNING
```

## Step 4.

 Fetch apache, untar, configure, then build:

```
>wget http://apache.mirrors.pair.com//httpd/httpd-2.4.12.tar.gz

>tar xfz httpd-2.4.12.tar.gz

>cd httpd-2.4.12

>CC=wllvm ./configure

>make
```

## Step 5.

Extract the bitcode.

```
>extract-bc -l llvm-link-3.4 httpd

>ls -la httpd.bc
-rw-r--r-- 1 vagrant vagrant 829960 Jun  1  2015 httpd.bc
```

The extra command line argument to `extract-bc` is because `apt`
installs `llvm-link` as `llvm-link-3.4` so we need to tell `extract-bc`
to use that one.