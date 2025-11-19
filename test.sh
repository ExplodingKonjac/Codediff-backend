bwrap \
    --ro-bind /usr /usr \
    --symlink usr/lib64 /lib64 \
    --symlink usr/lib /lib \
	--ro-bind test.cpp /test.cpp \
	--bind /tmp/tmptest /test \
    g++ test.cpp -o test
