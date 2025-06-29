# handler.py
import os
import json
import tempfile
import runpod

from orchestrator import run_benchmarks  # see note below

def handler(job):
    # ─── 1) Extract inputs ─────────────────────────────────────────────
    params = job.get("input", {})
    images      = params.get("images", [])
    iterations  = params.get("iterations",  3)
    max_workers = params.get("max_workers", 1)

    # ─── 2) Create a temp output dir ──────────────────────────────────
    outdir = tempfile.mkdtemp(prefix="bench-")

    # ─── 3) Run your benchmarks (refactored into a function) ──────────
    # You’ll need to pull the logic out of your CLI’s `main()`
    # into a function like run_benchmarks(images, iterations, max_workers, outdir)
    summary = run_benchmarks(images, iterations, max_workers, outdir)

    # ─── 4) Return the JSONable summary ───────────────────────────────
    return {"summary": summary}

# Start the Serverless worker
if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})
