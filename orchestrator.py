#!/usr/bin/env python3
import os
import time
import json
import statistics
import docker
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from concurrent.futures import ThreadPoolExecutor, as_completed

# ───── CONFIGURATION ──────────────────────────────────────────────────────────
INFLUX_URL    = os.getenv("INFLUX_URL",   "http://localhost:8086")
INFLUX_TOKEN  = os.getenv("INFLUX_TOKEN", "admin:adminpass")
INFLUX_ORG    = os.getenv("INFLUX_ORG",   "runpod")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET","runpod_bench")

WORKLOADS_DIR = os.getenv("WORKLOADS_DIR","./workloads")
IMAGES        = os.getenv("IMAGES", "python:3.10-slim").split(",")
MAX_WORKERS   = int(os.getenv("MAX_WORKERS", "0")) or None
# ──────────────────────────────────────────────────────────────────────────────

docker_client = docker.from_env()
influx_client = InfluxDBClient(
    url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG
)
write_api = influx_client.write_api(write_options=SYNCHRONOUS)

def run_workload(image, script_path, iterations=3, timeout=120):
    try:
        docker_client.images.pull(image)
    except Exception as e:
        print(f"⚠️ Skipping {image}: could not pull – {e}")
        return []

    script_name = os.path.basename(script_path)
    metrics = []

    for i in range(1, iterations + 1):
        container = None
        try:
            print(f"[{image}][{script_name}] Iteration {i}/{iterations}")
            container = docker_client.containers.run(
                image,
                command=["/bin/bash", "-c", f"./{script_name}"],
                volumes={os.path.abspath(WORKLOADS_DIR): {'bind':'/workloads','mode':'ro'}},
                working_dir="/workloads",
                detach=True,
            )

            t0 = time.time()
            stats = container.stats(stream=False)
            exit_info = container.wait(timeout=timeout)
            t1 = time.time()

            # CPU delta
            cpu_total     = stats.get("cpu_stats", {}) \
                                  .get("cpu_usage", {}) \
                                  .get("total_usage", 0)
            precpu_total  = stats.get("precpu_stats", {}) \
                                  .get("cpu_usage", {}) \
                                  .get("total_usage", 0)
            cpu_delta     = cpu_total - precpu_total

            # System CPU delta
            sys_total     = stats.get("cpu_stats", {}) \
                                  .get("system_cpu_usage", 0)
            precpu_sys    = stats.get("precpu_stats", {}) \
                                  .get("system_cpu_usage", 0)
            sys_delta     = sys_total - precpu_sys

            percpu       = stats.get("cpu_stats", {}) \
                                 .get("cpu_usage", {}) \
                                 .get("percpu_usage") or []
            cpu_count    = len(percpu)
            cpu_percent  = (cpu_delta/sys_delta)*cpu_count*100 if sys_delta else 0.0

            # Memory
            mem_usage    = stats.get("memory_stats", {}) \
                                 .get("usage", 0)
            mem_limit    = stats.get("memory_stats", {}) \
                                 .get("limit", 0)
            mem_percent  = (mem_usage/mem_limit)*100 if mem_limit else 0.0

            metrics.append({
                "image": image,
                "workload": script_name,
                "iteration": i,
                "runtime_s": t1 - t0,
                "cpu_percent": cpu_percent,
                "mem_percent": mem_percent,
                "mem_usage_bytes": mem_usage,
                "status": exit_info.get("StatusCode"),
                "timestamp": int(time.time()*1e9),
            })

        except Exception as e:
            print(f"❌ Error in {image}/{script_name} iter {i}: {e}")
        finally:
            if container:
                try: container.remove(force=True)
                except: pass

    return metrics

def push_to_influx(points):
    for p in points:
        pt = (
            Point("runpod_bench")
            .tag("image", p["image"])
            .tag("workload", p["workload"])
            .field("runtime_s", p["runtime_s"])
            .field("cpu_percent", p["cpu_percent"])
            .field("mem_percent", p["mem_percent"])
            .field("mem_usage_bytes", p["mem_usage_bytes"])
            .time(p["timestamp"])
        )
        write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=pt)

def generate_html_report(metrics, filename="report.html"):
    # Group metrics by (image, workload)
    summary = {}
    for m in metrics:
        key = (m["image"], m["workload"])
        summary.setdefault(key, {"runtime": [], "cpu": [], "mem": []})
        summary[key]["runtime"].append(m["runtime_s"])
        summary[key]["cpu"].append(m["cpu_percent"])
        summary[key]["mem"].append(m["mem_percent"])

    rows = []
    for (img, wl), data in summary.items():
        avg_rt  = statistics.mean(data["runtime"])
        avg_cpu = statistics.mean(data["cpu"])
        avg_mem = statistics.mean(data["mem"])
        rows.append((img, wl, avg_rt, avg_cpu, avg_mem))
    # Sort for readability
    rows.sort(key=lambda r: (r[0], r[1]))

    # Build HTML
    html = [
        "<!DOCTYPE html>",
        "<html><head><meta charset='utf-8'><title>RunPod Bench Report</title></head><body>",
        "<h1>RunPod Benchmark Summary</h1>",
        "<table border='1' cellpadding='5' cellspacing='0'>",
        "<tr><th>Image</th><th>Workload</th><th>Avg Runtime (s)</th><th>Avg CPU (%)</th><th>Avg Mem (%)</th></tr>",
    ]
    for img, wl, rt, cpu, mem in rows:
        html.append(f"<tr><td>{img}</td><td>{wl}</td>"
                    f"<td>{rt:.3f}</td><td>{cpu:.1f}</td><td>{mem:.1f}</td></tr>")
    html += ["</table></body></html>"]

    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(html))
    print(f"📄 Report written to {filename}")

if __name__ == "__main__":
    # discover scripts
    scripts = [
        os.path.join(WORKLOADS_DIR, f)
        for f in os.listdir(WORKLOADS_DIR)
        if os.path.isfile(os.path.join(WORKLOADS_DIR, f))
    ]

    all_metrics = []
    # benchmark in parallel
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as exe:
        futures = [
            exe.submit(run_workload, img, scr)
            for img in IMAGES for scr in scripts
        ]
        for fut in as_completed(futures):
            try:
                all_metrics.extend(fut.result())
            except Exception as e:
                print(f"❌ Error collecting results: {e}")

    # push to InfluxDB (optional)
    if INFLUX_BUCKET:
        print(f"Pushing {len(all_metrics)} metrics to InfluxDB…")
        push_to_influx(all_metrics)

    # dump raw data & generate HTML
    with open("metrics.json", "w", encoding="utf-8") as jf:
        json.dump(all_metrics, jf, indent=2)
    print("🔢 metrics.json written.")

    generate_html_report(all_metrics)
