# RunPod Benchmark Suite

**Purpose:**  
Benchmark the most-used RunPod Docker images across common workloads (CPU, memory, I/O, network, TF inference) and recommend the best image per use case.

## Components

1. **orchestrator.py**  
   - Discovers images & workloads  
   - Runs them in parallel  
   - Scrapes Docker stats  
   - Pushes data to InfluxDB

2. **Workloads** (`workloads/`)  
   - `cpu_test.sh`, `memory_test.sh`, `io_test.sh`, `network_test.sh`, `tf_inference_test.py`

3. **Metrics Backend**  
   - Docker-Compose brings up InfluxDB & Grafana

4. **Dashboard**  
   - Import `grafana/dashboards/runpod_bench.json` into Grafana

## Quickstart

```bash
# Build & run metrics stack
docker-compose up -d

# Install Python deps
pip install -r requirements.txt

# Run benchmarks & push to InfluxDB
python orchestrator.py

# Grafana UI → import dashboard (http://localhost:3000)
```