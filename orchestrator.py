#!/usr/bin/env python3
import argparse, os, json, subprocess, time, textwrap
from concurrent.futures import ThreadPoolExecutor, as_completed

def get_gpu_metrics():
    cmd = [
        "nvidia-smi",
        "--query-gpu=index,utilization.gpu,utilization.memory,"
        "memory.used,memory.total,power.draw,temperature.gpu",
        "--format=csv,noheader,nounits"
    ]
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL)
        lines = out.decode().strip().splitlines()
        metrics = []
        for line in lines:
            idx, util, mem_util, used, total, power, temp = [x.strip() for x in line.split(',')]
            metrics.append({
                "index": int(idx),
                "utilization_gpu_pct": int(util),
                "utilization_mem_pct": int(mem_util),
                "memory_used_mib": int(used),
                "memory_total_mib": int(total),
                "power_draw_w": float(power),
                "temperature_c": int(temp),
            })
        return metrics
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []

def run_workload(image, workload, iteration, outdir, cwd):
    # 1) ensure image
    subprocess.run(["docker", "pull", image], check=True, stdout=subprocess.DEVNULL)

    # 2) snapshot GPU before
    pre = get_gpu_metrics()

    # 3) build & run
    docker_cmd = [
        "docker", "run", "--rm", "--gpus", "all",
        "-v", f"{cwd}:/app", "-w", "/app",
        image, "sh", "-c", workload["cmd"]
    ]
    start = time.time()
    try:
        subprocess.run(docker_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        success = True
    except subprocess.CalledProcessError as e:
        success = False
        print(f"⚠️  [{image}][{workload['name']}] iter {iteration} failed:", e)
    duration = time.time() - start

    # 4) snapshot GPU after
    post = get_gpu_metrics()

    # 5) write report
    result = {
        "image": image,
        "workload": workload["name"],
        "iteration": iteration,
        "duration_s": duration,
        "success": success,
        "gpu_pre": pre,
        "gpu_post": post
    }
    safe = image.replace("/", "_").replace(":", "_")
    rpt = os.path.join(outdir, f"{safe}_{workload['name']}_iter{iteration}.json")
    with open(rpt, "w") as f:
        json.dump(result, f, indent=2)
    return result

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--images", nargs="+", required=True)
    parser.add_argument("--iterations", type=int, default=3)
    parser.add_argument("--max-workers", type=int, default=4)
    parser.add_argument("--outdir", required=True)
    args = parser.parse_args()

    cwd = os.getcwd()
    os.makedirs(args.outdir, exist_ok=True)

    # --- generate helper scripts in ./runpod_scripts/ ---
    scripts_dir = os.path.join(cwd, "runpod_scripts")
    os.makedirs(scripts_dir, exist_ok=True)

    matrix_py = textwrap.dedent("""\
        import torch
        a = torch.randn((4096, 4096), device='cuda')
        b = torch.randn((4096, 4096), device='cuda')
        for _ in range(10):
            torch.mm(a, b)
    """)
    with open(os.path.join(scripts_dir, "matrix_stress.py"), "w") as f:
        f.write(matrix_py)

    gpt2_py = textwrap.dedent("""\
        from transformers import GPT2LMHeadModel, GPT2Tokenizer
        import torch
        tok = GPT2Tokenizer.from_pretrained('gpt2')
        model = GPT2LMHeadModel.from_pretrained('gpt2').cuda()
        inputs = tok('Hello world', return_tensors='pt').to('cuda')
        with torch.no_grad():
            model.generate(**inputs, max_length=50)
    """)
    with open(os.path.join(scripts_dir, "gpt2_inference.py"), "w") as f:
        f.write(gpt2_py)

    # --- define workloads as simple one‐liners ---
    workloads = [
        {
            "name": "gpu_matrix_stress",
            "cmd": "pip install --no-cache-dir torch torchvision && python3 runpod_scripts/matrix_stress.py"
        },
        {
            "name": "tf_inference",
            "cmd": "pip install --no-cache-dir tensorflow && python3 tf_inference_test.py"
        },
        {
            "name": "gpt2_inference",
            "cmd": "pip install --no-cache-dir transformers torch && python3 runpod_scripts/gpt2_inference.py"
        }
    ]

    # --- run them in parallel ---
    all_results = []
    with ThreadPoolExecutor(max_workers=args.max_workers) as exe:
        futures = []
        for img in args.images:
            for wl in workloads:
                for i in range(1, args.iterations+1):
                    futures.append(
                        exe.submit(run_workload, img, wl, i, args.outdir, cwd)
                    )
        for f in as_completed(futures):
            all_results.append(f.result())

    # --- summary.json ---
    with open(os.path.join(args.outdir, "summary.json"), "w") as f:
        json.dump(all_results, f, indent=2)

if __name__ == "__main__":
    main()
