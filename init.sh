#!/usr/bin/env bash

# install bubblewrap
sudo apt install bubblewrap
bwrap --version

# install build-essentials
sudo apt install build-essential
g++ --version

# compile tools
cd ./tools
make -j$(nproc)
