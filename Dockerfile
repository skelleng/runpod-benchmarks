FROM python:3.10-slim

RUN apt-get update \
 && apt-get install -y docker.io curl gcc \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY orchestrator.py .
COPY workloads/ ./workloads/

CMD ["python", "orchestrator.py"]