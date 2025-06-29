#!/usr/bin/env bash
# write & read a 50MB file
dd if=/dev/urandom of=/tmp/io_test bs=1M count=50 status=none
sync
dd if=/tmp/io_test of=/dev/null bs=1M status=none
echo "I/O test done"
