#!/usr/bin/env python3
import argparse
import os
import subprocess
import json
import time
import concurrent.futures


def parse_args():
    parser = argparse.ArgumentParser(
        description="Orchestrate container-based GPU benchmarks for multiple images and workloads"
    )
    parser.add_argument(
        "--images", nargs='+', required=True,
        help="List of Docker images to test (e.g. python:3.10-slim ubuntu:22.04 alpine:3.14)"
    )
    parser.add_argument(
        "--iterations", type=int, default=3,
        help="Number of iterations per workload per image"
    )
    parser.add_argument(
        "--max-workers", type=int, default=1,
        help="Max parallel containers to run"
    )
    parser.add_argument(
        "--outdir", type=str, default="reports",
        help="Directory to write JSON reports"
    )
    return parser.parse_args()


def get_gpu_metrics():
    """
    Attempt to query NVIDIA GPUs for utilization, memory, power, temperature.
    Returns an empty list if nvidia-smi is unavailable or no GPUs are present.
    """
    cmd = [
        "nvidia-smi",
        "--query-gpu=index,name,utilization.gpu,utilization.memory,memory.used,memory.total,power.draw,temperature.gpu",
        "--format=csv,noheader,nounits"
    ]
    try:
        output = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode('utf-8').strip().splitlines()
    except (FileNotFoundError, subprocess.CalledProcessError):
        # nvidia-smi not found or no GPUs available
        return []

    metrics = []
    for line in output:
        idx, name, util_gpu, util_mem, mem_used, mem_total, power, temp = [x.strip() for x in line.split(',')]
        metrics.append({
            "index": int(idx),
            "name": name,
            "utilization_gpu": float(util_gpu),
            "utilization_memory": float(util_mem),
            "memory_used": float(mem_used),
            "memory_total": float(mem_total),
            "power_draw_watts": float(power),
            "temperature_c": float(temp),
        })
    return metrics


def run_container(image, workload, command, outdir, iteration):
    # Ensure image is available
    subprocess.run(["docker", "pull", image], check=True)

    # Record metrics before
    pre_metrics = get_gpu_metrics()
    start_ts = time.time()

    # Build docker run command
    docker_cmd = [
        "docker", "run", "--rm", "-v", f"{os.getcwd()}:/app", "-w", "/app"
    ]
    # Add GPU flag if available on host
    if pre_metrics:
        docker_cmd.extend(["--gpus", "all"]);
    docker_cmd.extend([image, "/bin/bash", "-c", command])

    # Run the workload inside a container
    subprocess.run(docker_cmd, check=True)
    duration = time.time() - start_ts

    # Record metrics after
    post_metrics = get_gpu_metrics()

    # Compose result
    result = {
        "image": image,
        "workload": workload,
        "iteration": iteration,
        "duration_seconds": duration,
        "pre_metrics": pre_metrics,
        "post_metrics": post_metrics
    }

    # Write to JSON
    safe_name = image.replace('/', '_').replace(':', '_')
    fname = f"{safe_name}__{workload}__iter{iteration}.json"
    with open(os.path.join(outdir, fname), 'w') as f:
        json.dump(result, f, indent=2)
    return result


def main():
    args = parse_args()
    os.makedirs(args.outdir, exist_ok=True)

    # Define sample GPU-intensive workloads
    workloads = {
        "gpu_stress": "python gpu_stress_test.py",
        "tf_inference": "python tf_inference_test.py",
        "llm_inference": "python llm_inference_test.py --model gpt2"
    }

    tasks = []
    for image in args.images:
        for workload, cmd in workloads.items():
            for i in range(1, args.iterations + 1):
                tasks.append((image, workload, cmd, i))

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.max_workers) as executor:
        future_to_task = {
            executor.submit(run_container, img, wl, cmd, args.outdir, itr): (img, wl, itr)
            for img, wl, cmd, itr in tasks
        }
        for future in concurrent.futures.as_completed(future_to_task):
            img, wl, itr = future_to_task[future]
            try:
                res = future.result()
                results.append(res)
                print(f"✓ {img} [{wl}] iter {itr}: {res['duration_seconds']:.2f}s")
            except subprocess.CalledProcessError as e:
                print(f"✗ {img} [{wl}] iter {itr} failed: {e}")

    # Write overall summary
    summary_path = os.path.join(args.outdir, "summary.json")
    with open(summary_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"Benchmark complete. Reports in '{args.outdir}'")


if __name__ == "__main__":
    main()
