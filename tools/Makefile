.DEFAULT_GOAL := all

rlimit_wrapper: rlimit_wrapper.cpp
	g++ $< -o $@ -std=c++20 -O2

CHECKERS_SRC = $(wildcard checkers/*.cpp)
CHECKERS_EXE = $(patsubst %.cpp, %, $(CHECKERS_SRC))

$(CHECKERS_EXE): %: %.cpp
	g++ $< -o $@ -std=c++20 -O2 -I .

all: $(CHECKERS_EXE) rlimit_wrapper
