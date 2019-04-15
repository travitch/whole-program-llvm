#iam: please leave this Makefile; it is useful for debugging when things break.

all: one archive

zero:
	${CXX} hello.cc -o hello

zero_e:
	${CXX} hello.cc -emit-llvm -c
	${CXX} hello.bc -o hello


e:
	${CC} -emit-llvm  foo.c  -c
	${CC} -emit-llvm  bar.c  -c
	${CC} -emit-llvm  baz.c -c
	${CC} -emit-llvm  main.c -c
	${CC} foo.bc bar.bc baz.bc main.bc -o main


one:
	${CC} foo.c bar.c baz.c main.c -o main

two:
	${CC} foo.c bar.c baz.c main.c -c
	${CC} foo.o bar.o baz.o main.o -o main

two_e:
	${CC} -emit-llvm  foo.c bar.c baz.c main.c -c
	${CC} foo.bc bar.bc baz.bc main.bc -o main

mix:
	${CC} foo.c bar.c -c
	${CC} foo.o bar.o baz.c main.c -o main

mix_e:
	${CC} -emit-llvm foo.c bar.c -c
	${CC} foo.bc bar.bc baz.c main.c -o main


objects:
	${CC} foo.c -c
	${CC} bar.c -c
	${CC} baz.c -c
	${CC} main.c -c

many: objects
	${CC} foo.o bar.o baz.o main.o -o main

archive: objects
	ar cr libfoo.a foo.o bar.o baz.o
	ranlib libfoo.a

dylib: objects
	${CC} -dynamiclib foo.o bar.o baz.o -o libfoo.dylib

deadstrip: objects
	${CC} -dynamiclib -Wl,-dead_strip foo.o bar.o baz.o -o libfoo.dylib

link_with_archive:: archive
	$(CC) main.o libfoo.a -o main.arch

clean:
	rm -f *.o main main.arch .*.o.bc .*.o *.bc .*.bc a.out *.s *.i hello *.a *.bca *.dylib *.manifest *.ll

mystery:
	otool -X -s __WLLVM __llvm_bc main > main.otool
	xxd -r main.otool
	xxd -r main.otool main.xxd
