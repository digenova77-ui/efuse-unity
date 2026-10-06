FROM python:3.12-slim

# DCLM — Deterministic Compute Logic Machine
# The computer. Not the company.

WORKDIR /dclm

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    nodejs \
    && rm -rf /var/lib/apt/lists/*

# Python deps (stdlib only for core; add as needed)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt || true

# DCLM source
COPY dclm/ ./dclm/
COPY core-rings/ ./core-rings/
COPY keys/ ./keys/

# Non-root
RUN useradd -m dclm && chown -R dclm:dclm /dclm
USER dclm

EXPOSE 8080

CMD ["python3", "-m", "dclm.compute"]
