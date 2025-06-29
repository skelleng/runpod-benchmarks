#!/usr/bin/env bash
# simple HTTP download test
curl -s https://speed.hetzner.de/100MB.bin -o /tmp/net_test
echo "Network test done"
