# C4 Component — rogueone (external)

Level 3: components on the rogueone laptop. rogueone is an EXTERNAL system to weyland (separate physical machine on the same LAN). See [c4-context.md](c4-context.md) for system context.

```mermaid
C4Component
    title rogueone (.230) — Components (External System)

    Person_Ext(user, "Edward", "Primary dev workstation operator")
    System_Ext(anthropic, "Anthropic API", "Claude models")
    System_Ext(github, "GitHub", "weyland-lab repo — RAG source")
    Container_Ext(tool_server, "weyland-tool-server", "MCP /mcp :30080")
    Container_Ext(dagster, "Dagster (mother)", "git-pulls docs/+nodes/ from GitHub (B25b)")
    Container_Ext(ray_head, "Ray head (mother)", "ray.weyland.lab · GCS :6379 · dashboard/Jobs API :8265")
    Container_Ext(mlflow, "MLflow (mother)", "NodePort :30500 (metadata) + MinIO s3://mlflow (artifacts)")
    Container_Ext(registry, "Registry (mother)", "registry.weyland.lab — MinIO-backed OCI")

    Container_Boundary(rogueone_sys, "rogueone — laptop (.230) · RTX 5000 Ada 16GB · 128GB RAM") {

        Component(claude_code, "Claude Code", "CLI (claude)", "Primary dev assistant. MCP client: registered weyland system-view MCP (url: http://192.168.1.243:30080/mcp, transport: http). Validated 2026-06-14 — status tool returns live system state. Reasoning brain: Anthropic API (cloud). Project: /home/edwardmangini/IdeaProjects/weyland")

        Component(vllm, "vLLM", "Python / CUDA", "GPU LLM serving. On-demand (not always-on). OpenAI-compatible /v1 :8000. RTX 5000 Ada 16GB VRAM. Serves Qwen models. Too small for 30B@4bit; sweet spot <=13B for speed.")

        Component(ray_worker, "Ray edge worker", "systemd / ray", "Permanent NATIVE Ray worker (ray-worker.service) → mother Ray head GCS :6379. Runs the heavy training / HP-sweep compute. Not-always-up: drops from the cluster on sleep, systemd auto-rejoins on wake. Env exactly matches the head (py3.11.9 + ray[tune] + pyarrow/numpy/boto3 from head pip freeze). MinIO TLS via AWS_CA_BUNDLE (mkcert root).")

        Component(genre_trainer, "genre-trainer", "Docker Desktop / Python", "Remote model-training container (services/genre-trainer/), pulled from registry.weyland.lab. Reads lakeFS silver, trains genre_classifier, logs to MLflow (:30500) with the artifact DIRECT to MinIO. --tune = Ray Tune sweep; winner retrains+registers on the worker.")

        Component(rag_embed, "rag-embed", "systemd / FastAPI / CUDA", "B-RAG-STREAM warm embedding service (services/rag-embed/, rag-embed.service). bge-small-en-v1.5 (384-dim) resident on the RTX 5000 Ada; model + CUDA context load ONCE at startup so every request is warm (invariants I1, I6). GET /health + POST /embed (L2-normalized vectors). :8900. LAN-only. Sole client = the Dagster rag_stream_produce producer on mother.")

        Component(weyland_repo, "weyland git repo", "git / IdeaProjects", "/home/edwardmangini/IdeaProjects/weyland. Canonical source of truth for all infra, k8s manifests, services, and docs. Pushed to GitHub, where Dagster git-pulls docs/ + nodes/ for the RAG (B25b — done).")
    }

    Rel(user, claude_code, "primary dev interface")
    Rel(user, vllm, "on-demand GPU inference")
    Rel(claude_code, tool_server, "MCP /mcp (status, context_search, context_ask, list_models)")
    Rel(claude_code, anthropic, "LLM reasoning (cloud)")
    Rel(weyland_repo, github, "git push")
    Rel(dagster, github, "git-pull docs/ + nodes/ for RAG ingestion (B25b)")
    Rel(ray_worker, ray_head, "joins cluster (GCS :6379); runs trials")
    Rel(ray_head, ray_worker, "schedules trials onto (--num-cpus=0 coordinator)")
    Rel(genre_trainer, registry, "docker pull image")
    Rel(genre_trainer, mlflow, "log run/metrics :30500 + artifact direct to MinIO")
    Rel(ray_worker, mlflow, "log trials + register winner")
    Rel(dagster, rag_embed, "POST /embed :8900 (rag_stream_produce, warm GPU embed)")
```
