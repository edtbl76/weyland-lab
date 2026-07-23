#!/usr/bin/env python3
"""B66 brain bake-off — FULL agent loop, apples-to-apples.

The real operator skill: reason -> call the LIVE tool -> read the JSON -> chain if needed -> answer grounded in the
result. Each brain uses its NATIVE protocol so the comparison is fair:
  - Haiku : text-JSON via `claude -p` (from $HOME, no dev-context skew).
  - local : native OpenAI tool-calling (the `tools` param + structured `tool_calls`) — how gpt-oss actually emits
            calls, and how a real agent framework (LangGraph) drives them.
READ-ONLY tools only (status / context_search / context_ask); act tools are excluded so nothing fires.

Usage (on rogueone):  python b66-brain-fullloop.py [local_model ...]      default locals: gpt-oss:20b
Env:  TOOLSERVER (default http://192.168.1.243:30080) · OLLAMA_BASE_URL · HAIKU_MODEL
NOTE: context_ask calls the tool-server's own LLM (~a minute each) — a full run takes several minutes.
"""
import json
import os
import subprocess
import sys
import time
import urllib.request

TOOLSERVER = os.environ.get("TOOLSERVER", "http://192.168.1.243:30080")
OLLAMA = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
HAIKU_MODEL = os.environ.get("HAIKU_MODEL", "haiku")
LOCAL_MODELS = sys.argv[1:] or ["gpt-oss:20b"]
HOME = os.path.expanduser("~")
MAX_STEPS = 4

# Haiku drives via a text-JSON protocol (it emits the call as JSON in `content`).
SYSTEM_TEXT = """You are the weyland homelab operator. You have these READ-ONLY tools:
- status        : full lab health (server + model + all four backends: pgvector, qdrant, weaviate, neo4j). args: none
- context_search: raw chunk retrieval from the knowledge base. args: {"query": str, "backend"?: str}
- context_ask   : RAG answer from the knowledge base (retrieve + generate). args: {"query": str, "backend"?: str}

Work step by step. To call a tool respond with ONLY {"tool":"<name>","args":{...}}. When you have enough to answer
the user, respond with ONLY {"final":"<your reply to the user>"}. Exactly ONE JSON object per turn — no prose, no markdown."""

# Local models use NATIVE tool-calling — the schemas below carry the tool descriptions; the system prompt is plain.
SYSTEM_STRUCT = ("You are the weyland homelab operator. Use the available READ-ONLY tools to satisfy the user's "
                 "request — call tools as needed, and chain them if the request has a condition — then give a final "
                 "natural-language answer grounded in the tool results.")
TOOLS_SCHEMA = [
    {"type": "function", "function": {"name": "status",
        "description": "Full lab health: server + embedding model + all four backends (pgvector, qdrant, weaviate, neo4j).",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "context_search",
        "description": "Raw chunk retrieval from the knowledge base (no generation).",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}, "backend": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "context_ask",
        "description": "RAG answer from the knowledge base (retrieve + generate an answer).",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}, "backend": {"type": "string"}}, "required": ["query"]}}},
]

TASKS = [
    "Is the lab healthy? Give me a one-line summary.",
    "What does our knowledge base say about the guardrail architecture? Summarize in two sentences.",
    "Check the cluster health, and if the pgvector backend is up, tell me in one line what the knowledge base says about the data mesh.",
]


def _get(url, timeout=30):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read())


def _post(url, body, timeout=300):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def exec_tool(tool, args):
    try:
        if tool == "status":
            return _get(f"{TOOLSERVER}/status")
        if tool == "context_search":
            b = args.get("backend", "pgvector")
            return _post(f"{TOOLSERVER}/context/search?backend={b}", {"query": args.get("query", ""), "limit": 3})
        if tool == "context_ask":
            return _post(f"{TOOLSERVER}/context/ask", {"query": args.get("query", ""), "backend": args.get("backend", "pgvector")})
        return {"error": f"tool '{tool}' is not available in this read-only test"}
    except Exception as e:
        return {"error": str(e)}


def parse(text):
    i = text.find("{")
    while i != -1:
        try:
            return json.JSONDecoder().raw_decode(text[i:])[0]
        except Exception:
            i = text.find("{", i + 1)
    return None


def loop_haiku(task):
    print(f"\n  TASK: {task}")
    convo = f"User request: {task}\n\nYour first tool call or final answer:"
    tools_called = []
    t0 = time.time()
    for step in range(MAX_STEPS):
        prompt = SYSTEM_TEXT + "\n\n" + convo
        try:
            out = subprocess.run(["claude", "-p", prompt, "--model", HAIKU_MODEL, "--output-format", "text"],
                                 capture_output=True, text=True, timeout=180, cwd=HOME)
            text = (out.stdout or out.stderr).strip()
        except Exception as e:
            print(f"    BRAIN ERROR: {e}"); return
        obj = parse(text)
        if obj and "final" in obj:
            print(f"    tools={tools_called} steps={step} ({time.time()-t0:.0f}s)")
            print(f"    FINAL: {obj['final']}"); return
        if obj and "tool" in obj:
            tool, args = obj["tool"], obj.get("args", {})
            tools_called.append(tool)
            snippet = json.dumps(exec_tool(tool, args))[:1200]
            print(f"    -> {tool}({args})  result[:110]={snippet[:110]}")
            convo += f"\n\n[you called {tool} with {args}; result]:\n{snippet}\n\nCall another tool or give your final answer:"
        else:
            print(f"    UNPARSED: {text[:160]}"); return
    print(f"    tools={tools_called} HIT MAX STEPS")


def loop_local(model, task):
    print(f"\n  TASK: {task}")
    messages = [{"role": "system", "content": SYSTEM_STRUCT}, {"role": "user", "content": task}]
    tools_called = []
    t0 = time.time()
    for step in range(MAX_STEPS):
        try:
            resp = _post(OLLAMA + "/chat/completions",
                         {"model": model, "stream": False, "messages": messages, "tools": TOOLS_SCHEMA})
        except Exception as e:
            print(f"    BRAIN ERROR: {e}"); return
        msg = resp["choices"][0]["message"]
        tcs = msg.get("tool_calls") or []
        if not tcs:
            final = (msg.get("content") or "").strip() or "(empty content)"
            print(f"    tools={tools_called} steps={step} ({time.time()-t0:.0f}s)")
            print(f"    FINAL: {final}"); return
        messages.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": tcs})
        for tc in tcs:
            name = tc["function"]["name"]
            try:
                args = json.loads(tc["function"].get("arguments") or "{}")
            except Exception:
                args = {}
            tools_called.append(name)
            snippet = json.dumps(exec_tool(name, args))[:1200]
            print(f"    -> {name}({args})  result[:110]={snippet[:110]}")
            messages.append({"role": "tool", "tool_call_id": tc.get("id", ""), "content": snippet})
    print(f"    tools={tools_called} HIT MAX STEPS")


if __name__ == "__main__":
    print(f"tool-server: {TOOLSERVER}")
    print(f"\n########## Haiku ({HAIKU_MODEL}) — text-JSON protocol ##########")
    for t in TASKS:
        loop_haiku(t)
    for m in LOCAL_MODELS:
        print(f"\n########## local: {m} — native tool-calling ##########")
        for t in TASKS:
            loop_local(m, t)
