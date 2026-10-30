---
name: l-llm-deploy-guide
description: >-
  Use as PLSI Engineer when PLSI asks to deploy Longevity-LLM (L-LLM), choose local GGUF vs Docker vLLM vs remote GPU vs
  Hugging Face endpoint, set up SSH access to a GPU host, or connect `plsi oracle l-llm` to a running L-LLM.
---

# L-LLM deploy guide

Follow persona.md norms and `shared/team`. Owner: **PLSI Engineer**. Reply only in handoffs to PLSI; never message the user.

Pick a Longevity-LLM deployment path from the user's machine and preferences, then walk that one path to a working OpenAI-compatible endpoint and PLSI config. Do not dump every recipe at once.
Every question for the user goes in ONE `question` handoff per step; PLSI shows it and returns the `answer`.

## When to use

- PLSI forwards the user's pick of "L-LLM" in the optional-capabilities card.
- PLSI forwards a request to deploy, move or reconnect Longevity-LLM.

## Steps

### 1. Profile before recommending

On the machine the user is working on (ask which host in a `question` handoff if unclear), summarize in plain language, without walls of raw output:

1. OS and architecture (`uname -a`; Windows `systeminfo`).
2. Docker present; on Linux/macOS whether the NVIDIA Container Toolkit works (`docker run --rm --gpus all <cuda-image> nvidia-smi`).
3. Local GPU name and free/total VRAM (`nvidia-smi`). No NVIDIA GPU means no local full-precision vLLM.
4. Free disk on the filesystem that holds images and weights (follow Docker root / containerd symlinks): about 55 GB for vLLM plus weights, about 10 GB for GGUF.
5. SSH client and key files (`~/.ssh/id_ed25519`, `~/.ssh/id_rsa`): list paths only, never print key material.
6. Hugging Face: whether a connector is authenticated (`hf auth whoami`). Remote servers still need a user-minted token.
7. An L-LLM already running: probe `http://127.0.0.1:8000/health` and `http://127.0.0.1:1234/v1/models`.

If the user named a remote GPU host, after they approve SSH (through PLSI) also check: login with the given user/key, remote `nvidia-smi`, Docker, disk, and whether port 8000 is free.

### 2. Decide with a question

Send one `question` handoff; offer only feasible options (hide "This machine: Docker vLLM" without a GPU of at least 24 GB):

| Option | When to offer |
|---|---|
| Already running: just connect | `/health` or `/v1/models` succeeds, or the user gives a URL |
| Local GGUF (LM Studio / llama.cpp) | consumer laptop, no big GPU, quality trade-off acceptable |
| This machine: Docker vLLM | local NVIDIA GPU with at least 24 GB VRAM, and Docker |
| Remote GPU over SSH (+ tunnel) | the user has or will give `user@host` and a key; preferred for shared H100/A100 |
| Hugging Face Inference Endpoint | managed hosting wanted; HF org/quota; paying per hour is acceptable |
| Not sure: recommend for me | always |

"Recommend for me" order: running endpoint, then remote SSH GPU with at least 24 GB, then local GPU with at least 24 GB plus Docker, else local GGUF; HF Endpoint only if the user wants managed cloud or has no SSH GPU. State the recommendation in one sentence in the `question` and proceed on the `answer`. The same `question` carries the recommended path's defaults (port, model name) for the user to confirm and, when a remote host was named, asks for SSH approval, so step 3 asks only for what is still missing.

### 3. Collect only what the chosen path needs

- **Connect existing:** base URL ending in `/v1`, optional API key, model name if not `longevity-llm`.
- **Local GGUF:** willingness to install LM Studio or llama.cpp; port (default 1234).
- **Docker vLLM (local or remote):** weights directory, GPU index, host port; remote: `user@host`, SSH key path, bind the API to `127.0.0.1` only (default yes).
- **HF Endpoint:** endpoint URL once created; `HF_TOKEN` with read scope (write only if uploading).

Secrets go in the Grok secret store or the workspace `.env`, never in chat or a handoff. If one reaches you, store it
and say in your `result` that the user should rotate it.

### 4. Walk the chosen path

Lead with the next concrete command and verify before moving on.

**A) Connect existing.** `curl <base>/models` (or `/health`), then configure PLSI (step 5).

**B) Local GGUF.** Install LM Studio or llama.cpp; load a `longevity-llm` Q4_K_M GGUF (for example `mradermacher/longevity-llm-GGUF`); start the OpenAI-compatible server (usually `http://127.0.0.1:1234/v1`); set `PLSI_LLLM_MODE=local`.

**C) Docker vLLM** on the GPU host:

1. Prerequisites: NVIDIA driver, Docker, NVIDIA Container Toolkit, about 55 GB free on the real Docker/weights filesystem.
2. Weights: `hf download insilicomedicine/longevity-llm --local-dir /srv/longevity-llm` (use `hf`, not the deprecated `huggingface-cli`; a venv or pipx on PEP 668 distros). Gated repo: `hf auth login` with a read token.
3. `docker pull fgalkin/longevity-llm-vllm:0.1`
4. Run. Set `--gpu-memory-utilization` from free VRAM as `(free_GiB - 2) / total_GiB`; do not use `--rm` on the first run:

   ```bash
   docker run -d --name lllm --gpus '"device=0"' -p 127.0.0.1:8000:8000 \
     --entrypoint python3 \
     -v "/srv/longevity-llm:/repository:ro" \
     -e VLLM_LOGGING_LEVEL=INFO \
     -e VLLM_WORKER_MULTIPROC_METHOD=spawn \
     fgalkin/longevity-llm-vllm:0.1 \
     -m vllm.entrypoints.openai.api_server \
       --model /repository \
       --served-model-name longevity-llm \
       --trust-remote-code --dtype bfloat16 \
       --max-model-len 28000 --max-num-seqs 64 \
       --gpu-memory-utilization 0.92 --enforce-eager \
       --no-enable-log-requests --host 0.0.0.0 --port 8000
   ```

   VRAM sizing: 80-141 GB as above; 40-48 GB `--max-model-len 16000 --max-num-seqs 16`; 24 GB `--max-model-len 8000 --max-num-seqs 4 --gpu-memory-utilization 0.95`.

5. Wait for `/health` 200 (about 90 s cold). Exit code 126 means `--entrypoint python3` is missing.

From the laptop when the host is remote (keep it running while PLSI calls the model; on Windows use OpenSSH or WSL):

```bash
ssh -N -L 8000:127.0.0.1:8000 user@gpu-host
```

Then `PLSI_LLLM_MODE=server`. Prefer the tunnel plus a `127.0.0.1` bind on the host over exposing port 8000.

**D) Hugging Face Inference Endpoint.**

1. Token from https://huggingface.co/settings/tokens (read for private weights or endpoint; write only to upload).
2. Create the endpoint: custom container `fgalkin/longevity-llm-vllm:0.1`, port 8000, health route `/health`, a pinned repo tag (not `main`), `HUGGING_FACE_HUB_TOKEN` as a Secret env var.
3. Container command: `python3 -m vllm.entrypoints.openai.api_server --model /repository --served-model-name longevity-llm --trust-remote-code --dtype bfloat16 --max-model-len 28000 --max-num-seqs 64 --gpu-memory-utilization 0.92 --enforce-eager --no-enable-log-requests --host 0.0.0.0 --port 8000`
4. Set `PLSI_LLLM_BASE_URL=https://<endpoint>/v1` and `HF_TOKEN` (or `PLSI_LLLM_API_KEY`). Expect scale-to-zero cold starts of several minutes.

### 5. Configure and smoke-test PLSI

Set these in the workspace `.env` (see `.env.example`) or the Grok secret store:

| Variable | Value |
|---|---|
| `PLSI_LLLM_MODE` | `local` (http://127.0.0.1:1234/v1) or `server` (http://127.0.0.1:8000/v1) |
| `PLSI_LLLM_BASE_URL` | any other endpoint, ending in `/v1`; overrides the mode |
| `PLSI_LLLM_MODEL` | served model name, default `longevity-llm` |
| `PLSI_LLLM_API_KEY` / `HF_TOKEN` | bearer key if the endpoint needs one; `HF_TOKEN` is sent only to `https://*.huggingface.cloud` or `*.hf.space`, any other endpoint needs `PLSI_LLLM_API_KEY` |
| `PLSI_LLLM_ENABLE_THINKING` | `1` for open-ended questions (thinking on, longer answers) |

```bash
plsi keys status
echo '{"prompt": "List the hallmarks of aging, one line each."}' | plsi oracle l-llm --file -
```

PLSI sends temperature 0, top_p 0.8, top_k 20, repetition_penalty 1.1, max_tokens 700 (2200 with thinking, via `chat_template_kwargs.enable_thinking`) and strips everything up to `</think>`.

### 6. Finish

Send one `result` to PLSI: path, base URL (no secrets), how to reopen the tunnel, and the smoke test that succeeded; one `questions` item "Remember host and mode?" (Yes / No). Never leave a background SSH tunnel or container without saying in the `result` how to stop it (`kill` the `ssh` job, `docker stop lllm`).

## Rules

- Never commit or print tokens, SSH private keys or endpoint passwords.
- An HF connector login is not a portable `hf_...` token; GPU hosts and endpoints need a user-minted token.
- Verified image `fgalkin/longevity-llm-vllm:0.1` has `ENTRYPOINT bash`: `docker run` needs `--entrypoint python3`.
- Client model id `longevity-llm` must match `--served-model-name`. Weights `insilicomedicine/longevity-llm` (about 18 GB; GGUF about 5.6 GB).
- L-LLM answers are `model_derived`; cite them as `{"kind": "model", "id": "longevity_llm"}`.
