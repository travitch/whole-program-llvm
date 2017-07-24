
all:
	@echo ''
	@echo 'Here are the targets:'
	@echo ''
	@echo 'To develop          :    "make develop"'
	@echo 'To install          :    "make install"'
	@echo 'To publish          :    "make publish"'

	@echo 'To check clang      :    "make check_clang"'
	@echo ''
	@echo 'e.g. on linux: LLVM_COMPILER_PATH=/usr/lib/llvm-3.5/bin/ make check_clang'
	@echo ''
	@echo 'To check dragonegg  :    "make check_dragonegg"'
	@echo ''
	@echo 'e.g. on linux: PATH=/usr/lib/llvm-3.3/bin:... make check_dragonegg'
	@echo ''
	@echo 'To pylint           :  "make lint"'
	@echo ''



#local editable install for developing
develop:
	pip install -e .


dist: clean
	python setup.py bdist_wheel

# If you need to push this project again,
# INCREASE the version number in wllvm/version.py,
# otherwise the server will give you an error.

publish: dist
	python setup.py sdist upload

install:
	pip install

check_clang:
	cd test; python -m unittest -v test_base_driver test_clang_driver

check_dragonegg:
	cd test; python -m unittest -v test_base_driver test_dragonegg_driver

clean:
	rm -f  wllvm/*.pyc wllvm/*~


PYLINT = $(shell which pylint)

lint:
ifeq ($(PYLINT),)
	$(error lint target requires pylint)
endif
#	@ $(PYLINT) -E wllvm/*.py
# for detecting more than just errors:
	@ $(PYLINT) --rcfile=.pylintrc wllvm/*.py
