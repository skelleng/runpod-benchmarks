#!/usr/bin/env bash
python3 - <<'EOF'
import time
start = time.time()
# busy-loop for ~2s
while time.time() - start < 2: pass
print("CPU test done")
EOF
