CC=clang

all:
	${CC} foo.c  -c
	${CC} bar.c  -c
	${CC} baz.c  -c
	${CC} main.c -c
	${CC} foo.o bar.o baz.o main.o -o main

obj: foo.c bar.c baz.c main.c
	${CC} foo.c  -c
	${CC} bar.c  -c
	${CC} baz.c  -c
	${CC} main.c -c

aux: obj
	echo "foo.o.bc" > foo.txt
	echo "bar.o.bc" > bar.txt
	echo "baz.o.bc" > baz.txt
	echo "main.o.bc" > main.txt

embed: aux
	ld -r foo.o -sectcreate __LLVM __llvm_bc foo.txt -o foo.xxx.o
	ld -r bar.o -sectcreate __LLVM __llvm_bc bar.txt -o bar.xxx.o
	ld -r baz.o -sectcreate __LLVM __llvm_bc baz.txt -o baz.xxx.o
	ld -r main.o -sectcreate __LLVM __llvm_bc main.txt -o main.xxx.o


archive: embed
	ar cr libfoo.a foo.xxx.o bar.xxx.o baz.xxx.o
	ranlib libfoo.a

link_embed: embed
	$(CC) foo.xxx.o bar.xxx.o baz.xxx.o main.xxx.o -o main.xxx

link_with_arch: archive
	$(CC) main.xxx.o libfoo.a -o main.arch

clean:
	rm -f *.o main .*.o.bc .*.o *.bc .*.bc a.out *.s *.i

