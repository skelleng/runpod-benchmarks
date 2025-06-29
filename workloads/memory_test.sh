#!/usr/bin/env bash
python3 - <<'EOF'
# allocate ~200MB, hold for 2s, then exit
a = bytearray(200 * 1024 * 1024)
import time; time.sleep(2)
print("Memory test done")
EOF
