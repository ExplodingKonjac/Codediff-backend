#!/usr/bin/env bash

# install bubblewrap
sudo apt install bubblewrap
bwrap --version

# install build-essentials
sudo apt install build-essential
g++ --version

# compile rlimit_wrapper
cd ./tools
g++ rlimit_wrapper.cpp -o rlimit_wrapper -O2
