.DEFAULT_GOAL := all

rlimit_wrapper: rlimit_wrapper.cpp
	g++ $< -o $@ -std=c++20 -O2

CHECKERS_SRC = $(wildcard checkers/*.cpp)
CHECKERS_EXE = $(patsubst %.cpp, %, $(CHECKERS_SRC))

$(CHECKERS_EXE): %: %.cpp
	g++ $< -o $@ -std=c++20 -O2 -I .

# Precompile testlib.h for various standards
CXX_STANDARDS := c++11 c++14 c++17 c++20 c++23
GCH_DIR := testlib.h.gch
GCH_FILES := $(foreach std,$(CXX_STANDARDS),$(GCH_DIR)/$(std).gch)

gch: $(GCH_FILES)

$(GCH_DIR)/%.gch: testlib.h | $(GCH_DIR)
	g++ -x c++-header $< -o $@ -std=$*

$(GCH_DIR):
	mkdir -p $@

all: $(CHECKERS_EXE) rlimit_wrapper gch
