# ── Stage 1: build the frontend ───────────────────────────────────────
FROM node:22-slim AS web

WORKDIR /build
COPY web/package.json web/package-lock.json ./
RUN npm ci

COPY web/ ./
# A static export: no API URL is baked in, so the bundle calls whatever origin
# serves it. See web/lib/api.ts.
RUN npm run build


# ── Stage 2: the application ──────────────────────────────────────────
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    # Keep the model cache inside the image rather than a home directory the
    # host may mount over.
    HF_HOME=/app/.cache/huggingface

WORKDIR /app

# CPU-only torch. The default wheel drags in ~2 GB of CUDA libraries that are
# dead weight on a CPU host, so it is installed from PyTorch's CPU index first
# and pinned there before anything else can pull the GPU build.
RUN pip install --no-cache-dir \
      --index-url https://download.pytorch.org/whl/cpu \
      torch

COPY requirements.txt ./
# Gradio is a local-development fallback UI; the container serves Next.js.
RUN grep -v '^gradio' requirements.txt > requirements.docker.txt \
    && pip install --no-cache-dir -r requirements.docker.txt

COPY *.py ./
COPY healthcare_dataset.csv ./

# Clean the data, build SQLite and FAISS, and pull the embedding model down
# now. Doing it at build time means a cold start is just a process launch
# rather than a multi-minute data build plus a 90 MB download.
RUN python cli.py --setup && python -c "from vectorstore import load_vectorstore; load_vectorstore()"

COPY --from=web /build/out ./web/out

EXPOSE 7860
ENV PORT=7860 API_HOST=0.0.0.0

# Not `python server.py`: uvicorn is invoked directly so the process that
# receives SIGTERM is the server itself, and the platform's stop signal is
# handled rather than swallowed by a parent.
CMD ["sh", "-c", "uvicorn server:app --host 0.0.0.0 --port ${PORT:-7860}"]
