FROM python:3.10-slim

# Install the RunPod SDK (and any other deps you need)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your orchestrator and helper scripts
COPY orchestrator.py runpod_scripts/ /app/
COPY handler.py       /app/

WORKDIR /app

# Serverless containers entrypoint
CMD ["python", "handler.py"]
