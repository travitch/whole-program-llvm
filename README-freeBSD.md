Steps to build bitcode version of FreeBSD 10.0 world and kernel
-----------------------------------------------

The following instructions have been tested with FreeBSD 10.0 amd64.

-- Prerequisites: --------------------------------------------------------------

1. FreeBSD

The ideal way to start is with a clean install of FreeBSD 10.0 with 
sources installed. The simplest way to do this is to install from the 
Release 10.0 ISO image and and on the "Distribution Select" screen 
select just the following:

  [*] ports   Ports tree
  [*] src     System source code

If you are on an existing system that has either an old version of the 
source tree or is missing source, you can follow the instructions in the 
FreeBSD Handbook Chapter 24 to get the relevant sources.

2. Necessary ports

Upgrade the ports collection (as 'root'):

   su -
   portsnap fetch
   portsnap extract
   cd /usr/ports/ports-mgmt/portupgrade
   make -DBATCH install clean
   portupgrade -a --batch

Install the following ports using the BSD port tree: 

  bash git subversion python27 sudo wget

(See the FreeBSD Handbook Chapter 5 for instructions.)
The quick way to do this is:

   su -
   cd /usr/ports
   cd shells/bash && make -DBATCH install clean && \
     cd ../../devel/git && make -DBATCH install clean && \
     cd ../../devel/subversion && make -DBATCH install clean && \
     cd ../../security/sudo && make -DBATCH install clean && \
     cd ../../ftp/wget && make -DBATCH install clean

(Python27 is installed as a prerequisite of Subversion.)

Below we assume the shell being used is bash, that is:

   chsh -s /usr/local/bin/bash

has been run. If you want to use another shell, replace bash-isms like 
'export' with the appropriate equivalent.

We suggest installing 'sudo' and setting up your account as a sudoer, to 
make installing programs easier. You can do this, or modify the commands 
that use 'sudo' below.

3. LLVM and Clang 3.3

Install LLVM and Clang version 3.3. (These instructions adapted from 
http://llvm.org/docs/GettingStarted.html) Decide where you want to 
install LLVM. If you have 'root' access, you can use the default 
'/usr/local', though any location is fine. You may then wish to add this 
to your shell startup (in '~/.profile' for bash):

  export LLVM_HOME=/usr/local/llvm-3.3

Get LLVM and Clang version 3.5:

  svn co http://llvm.org/svn/llvm-project/llvm/branches/release_33 llvm
  cd llvm/tools
  svn co http://llvm.org/svn/llvm-project/cfe/branches/release_33 clang
  cd ../projects
  svn co http://llvm.org/svn/llvm-project/compiler-rt/branches/release_33 compiler-rt
  cd ../..

Now finish the build and install:

  cd llvm
  mkdir build
  cd build
  ../configure --prefix=$LLVM_HOME --enable-assertions \
      --enable-targets=host-only --enable-optimized
  gmake 
  sudo gmake install

Note that the FreeBSD 10.0 base includes Clang 3.3 (but does not include 
the complete LLVM framework, in particular llvm-link is not included).

So to make life easier, so that extract-bc can find it do:

  sudo ln -s $LLVM_HOME/bin/llvm-link /usr/bin/llvm-link
  

1. Download SRI-modified version of WLLVM.

> cd ${HOME}
> git clone https://github.com/SRI-CSL/whole-program-llvm

2. Create the hooks for interposing on compiler calls.

> cd ${HOME}
> mkdir ${HOME}/wllvm.bin
> cd wllvm.bin
> ln -s ${HOME}/whole-program-llvm/wllvm cc
> ln -s ${HOME}/whole-program-llvm/wllvm++ c++
> ln -s ${HOME}/whole-program-llvm/wllvm clang
> ln -s ${HOME}/whole-program-llvm/wllvm++ clang++
this next one is a hack (make buildworld doesn't find python with /usr/bin/env without it)
> ln -s /usr/local/bin/python python

3. Insert the hooks into the build path.

> diff /usr/src/Makefile.inc1 Makefile.inc1.original 
180c180
< BPATH=	${HOME}/wllvm.bin:${WORLDTMP}/legacy/usr/sbin:${WORLDTMP}/legacy/usr/bin:${WORLDTMP}/legacy/usr/games:${WORLDTMP}/legacy/bin
---
> BPATH=	${WORLDTMP}/legacy/usr/sbin:${WORLDTMP}/legacy/usr/bin:${WORLDTMP}/legacy/usr/games:${WORLDTMP}/legacy/bin

4. If the build location doesn't exist, create it.

> mkdir ${HOME}/build.world

5. Configure the environment for the build.

> export MAKEOBJDIRPREFIX=${HOME}/build.world
> export LLVM_COMPILER=clang
> export LLVM_COMPILER_PATH=/usr/bin
> export WLLVM_OUTPUT=DEBUG

6. Start the build.

> cd /usr/src
> make buildworld

7. Once that succeeds build the kernel

> make buildkernel


8. extract the bitcode:


cd  ${MAKEOBJDIRPREFIX}/usr/src/sys/GENERIC

> ${HOME}/whole-program-llvm/extract-bc kernel

> nm kernel | wc
   53140  159418 2421852

> ${LLVM_HOME}/bin/llvm-nm kernel.bc | wc
   50664  101328 1910997

We are working on seeing if we can get these numbers to match.
But suspect their is some assembler causing this difference.


