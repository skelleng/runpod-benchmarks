diff --git a/README.md b/README.md
index abcdef0..1234567 100644
--- a/README.md
+++ b/README.md
@@ -1,6 +1,12 @@
 # RunPod Benchmark Suite
[![Runpod](https://api.runpod.io/badge/skelleng/runpod-benchmarks)](https://console.runpod.io/hub/skelleng/runpod-benchmarks)
-**Purpose:**  
-Benchmark the most-used RunPod Docker images across common workloads (CPU, memory, I/O, network, TF inference) and recommend the best image per use case.
+**Purpose:**  
+1. Spin up a set of Docker images against a suite of workloads  
+2. Collect CPU, memory, and runtime stats  
+3. **Generate** a lightweight HTML report (and JSON)  
+4. **Optionally** push metrics to InfluxDB / Grafana

+**Quick report view:**  
+After running, open `report.html` in your browser for a summary table.

 ## Components

@@ -13,7 +19,7 @@ 4. **Dashboard**  

 ## Quickstart

-```bash
+```bash
 # Build & run metrics stack (optional)
 docker-compose up -d

@@ -21,14 +27,18 @@ docker-compose up -d

 # Run benchmarks, push to InfluxDB, and generate HTML report
 python orchestrator.py
+
+# View the HTML report (opens in your default browser)
+python -m http.server 8000
+# then point your browser at http://localhost:8000/report.html
