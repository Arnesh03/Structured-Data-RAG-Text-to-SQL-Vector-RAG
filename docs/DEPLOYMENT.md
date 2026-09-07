# Deployment

The whole project ships as **one container behind one URL**: FastAPI serves the
API and the Next.js static export from the same process. No CORS, no second
service to keep alive, no `NEXT_PUBLIC_API_URL` to configure.

> **Status:** the single-process serving path is verified locally. The
> `Dockerfile` itself has **not** been built or run — treat the first build as
> something to watch rather than trust.

---

## How it fits together

Every component in `web/` is client-side and fetches from the API at runtime,
so there is no server rendering to give up. `next build` with
`output: "export"` produces a folder of plain files, and
[`server.py`](../server.py) mounts it at `/` — after the `/api` routes, so it
cannot shadow them.

```
GET /api/*   ->  FastAPI
GET /*       ->  web/out/  (the exported frontend)
```

When `web/out` is absent, `/` returns a small JSON stub instead, so the API is
still usable on its own.

---

## The one real footgun

`web/.env.local` sets `NEXT_PUBLIC_API_URL=http://127.0.0.1:8010` for local
development. Next.js inlines that at **build time**, so an export built with
that file present is hardcoded to your laptop and fails with
`ERR_CONNECTION_REFUSED` anywhere else.

The Docker build is immune — `web/.env.local` is in `.dockerignore`. **If you
build the export by hand, remove or empty that file first.**

```bash
mv web/.env.local web/.env.local.bak   # keep it for dev
npm run build --prefix web
mv web/.env.local.bak web/.env.local
```

Confirm nothing was baked in:

```bash
grep -r "127.0.0.1:8010" web/out/_next/static/chunks/ && echo "BAKED IN" || echo "clean"
```

---

## Sizing

This decides where it can run.

| | |
|---|---|
| Python dependencies | ~1.2 GB installed, **torch alone is 554 MB** |
| Why | `sentence-transformers` needs torch for the local embedding model |

The `Dockerfile` installs **CPU-only torch** from PyTorch's own index first.
The default wheel pulls roughly 2 GB of CUDA libraries that are dead weight on
a CPU host, so this is not an optimisation — it is the difference between a
buildable image and a broken one.

**512 MB free tiers (Render free, Fly's default VM) will not fit this.** Either
host somewhere with more memory, or swap the embedding model for an
ONNX-based one such as `fastembed` to drop torch entirely.

The image also runs `cli.py --setup` and preloads the embedding model at
**build** time, so a cold start is a process launch rather than a multi-minute
data build plus a 90 MB download.

---

## Hugging Face Spaces (free)

The only free tier that comfortably fits torch: 16 GB RAM, 50 GB disk.

1. Create a free account at [huggingface.co](https://huggingface.co).
2. **New Space** → SDK **Docker** → blank template.
3. In the Space's `README.md`, set `app_port`:

   ```yaml
   ---
   title: Healthcare Structured Data RAG
   emoji: 🏥
   colorFrom: blue
   colorTo: purple
   sdk: docker
   app_port: 7860
   ---
   ```

4. Add your LLM key under **Settings → Variables and secrets** as a *secret*
   named `GROQ_API_KEY` (never commit it).
5. Push:

   ```bash
   git remote add space https://huggingface.co/spaces/<user>/<space>
   git push space main
   ```

Free CPU Spaces sleep after ~48 h idle and cold-start in a minute or two.

---

## Anywhere else

The `Dockerfile` is portable — nothing in it is Hugging Face specific.

| Platform | Notes |
|---|---|
| Render | Web Service → Docker. Free tier's 512 MB will OOM; the paid tier works. |
| Railway | Detects the Dockerfile. Injects `PORT`, which the app honours. |
| Fly.io | `fly launch --dockerfile`. Raise the VM memory from the 256 MB default. |
| Any VPS | `docker build -t hcrag . && docker run -p 7860:7860 -e GROQ_API_KEY=... hcrag` |

[`config.py`](../config.py) reads `PORT` before its own `API_PORT`, so
platforms that assign a port at runtime work without changes.

---

## Required configuration

| Variable | Required | Notes |
|---|---|---|
| `GROQ_API_KEY` | yes | Or `DEEPSEEK_API_KEY` / `OPENAI_API_KEY` with `LLM_PROVIDER` set |
| `LLM_PROVIDER` | no | `groq` (default), `deepseek`, `openai` |
| `PORT` | no | Injected by most hosts; defaults to 7860 in the image |

Set the key as a **secret**, not a build argument — build arguments are visible
in image layers.

---

## Verifying a deployment

```bash
curl -s https://<your-host>/api/health
```

`"has_api_key": true` means it can answer questions;
`"database_ready"` and `"vectorstore_ready"` confirm the baked-in data
survived the build. Then open the root URL and ask something.
