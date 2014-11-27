
zero:
	${CXX} hello.cc -o hello

one:
	${CC} foo.c bar.c baz.c main.c -o main

two:
	${CC} foo.c bar.c baz.c main.c -c
	${CC} foo.o bar.o baz.o main.o -o main

mix:
	${CC} foo.c bar.c -c
	${CC} foo.o bar.o baz.c main.c -o main

objects:
	${CC} foo.c  -c
	${CC} bar.c  -c
	${CC} baz.c  -c
	${CC} main.c -c

many: objects
	${CC} foo.o bar.o baz.o main.o -o main

archive: objects
	ar cr libfoo.a foo.o bar.o baz.o
	ranlib libfoo.a


link_with_archive:: archive
	$(CC) main.o libfoo.a -o main.arch


clean:
	rm -f *.o main .*.o.bc .*.o *.bc .*.bc a.out *.s *.i hello *.a



mystery:
	otool -X -s __LLVM __llvm_bc main > main.otool
	xxd -r  main.otool
	xxd -r  main.otool main.xxd


