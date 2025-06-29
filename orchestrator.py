#!/usr/bin/env python3
import os
import time
import docker
from influxdb_client import InfluxDBClient, Point, WritePrecision
from concurrent.futures import ThreadPoolExecutor, as_completed

# CONFIGURATION
INFLUX_URL    = os.getenv("INFLUX_URL",   "http://localhost:8086")
INFLUX_TOKEN  = os.getenv("INFLUX_TOKEN", "admin:adminpass")
INFLUX_ORG    = os.getenv("INFLUX_ORG",   "runpod")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET","runpod_bench")
WORKLOADS_DIR = os.getenv("WORKLOADS_DIR","./workloads")
IMAGES        = os.getenv("IMAGES",       "python:3.10-slim,runpod/pytorch:latest").split(",")
MAX_WORKERS   = int(os.getenv("MAX_WORKERS", 0)) or None

# Initialize clients
docker_client = docker.from_env()
influx_client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
write_api = influx_client.write_api(write_options=WritePrecision.S)

def run_workload(image, script_path, iterations=3, timeout=120):
    docker_client.images.pull(image)
    script_name = os.path.basename(script_path)
    metrics = []

    for i in range(1, iterations + 1):
        print(f"[{image}][{script_name}] Iteration {i}/{iterations}")
        container = docker_client.containers.run(
            image,
            command=["/bin/bash", "-c", f"./{script_name}"],
            volumes={os.path.abspath(WORKLOADS_DIR): {'bind': '/workloads', 'mode': 'ro'}},
            working_dir="/workloads",
            detach=True
        )

        start = time.time()
        stats = container.stats(stream=False, decode=True)
        exit_info = container.wait(timeout=timeout)
        end = time.time()

        # CPU calculation
        cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - stats["precpu_stats"]["cpu_usage"]["total_usage"]
        sys_delta = stats["cpu_stats"]["system_cpu_usage"] - stats["precpu_stats"]["system_cpu_usage"]
        cpu_count = len(stats["cpu_stats"]["cpu_usage"]["percpu_usage"])
        cpu_percent = (cpu_delta / sys_delta) * cpu_count * 100 if sys_delta else 0.0

        # Memory usage
        mem_usage = stats["memory_stats"]["usage"]
        mem_limit = stats["memory_stats"]["limit"]
        mem_percent = (mem_usage / mem_limit) * 100 if mem_limit else 0.0

        container.remove(force=True)

        metrics.append({
            "image": image,
            "workload": script_name,
            "iteration": i,
            "runtime_s": end - start,
            "cpu_percent": cpu_percent,
            "mem_usage_bytes": mem_usage,
            "mem_percent": mem_percent,
            "status": exit_info.get("StatusCode"),
            "timestamp": int(time.time() * 1e9)
        })
    return metrics

def push_to_influx(points):
    for p in points:
        pt = Point("runpod_bench")             .tag("image", p["image"])             .tag("workload", p["workload"])             .field("runtime_s", p["runtime_s"])             .field("cpu_percent", p["cpu_percent"])             .field("mem_usage_bytes", p["mem_usage_bytes"])             .field("mem_percent", p["mem_percent"])             .time(p["timestamp"], WritePrecision.NS)
        write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=pt)

if __name__ == "__main__":
    # discover workloads
    scripts = [
        os.path.join(WORKLOADS_DIR, s) for s in os.listdir(WORKLOADS_DIR)
        if os.path.isfile(os.path.join(WORKLOADS_DIR, s))
    ]

    all_metrics = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(run_workload, img, script) for img in IMAGES for script in scripts]
        for future in as_completed(futures):
            try:
                all_metrics.extend(future.result())
            except Exception as e:
                print(f"Error: {e}")

    print(f"Pushing {len(all_metrics)} metrics to InfluxDB...")
    push_to_influx(all_metrics)
    print("Finished.")
