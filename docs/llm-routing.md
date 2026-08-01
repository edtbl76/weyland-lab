# LLM Routing

Use-case **aliases → provider fallback chains**, served by **LiteLLM**. A client sends only the alias
(e.g. `wl-coding`); LiteLLM picks the **primary** and fails over down the chain on network / 5xx / 429 /
timeout — server-side and transparent. Left node = primary; each `→` is the next fallback. Colour = cost tier.

Every chain ends on a **free, always-on** rung so a call always lands. For the full interactive view see the
**[LLM Routing Map](llm-routing-map.html)** (internal). This diagram is copy-paste-able — grab the fenced block below.

**Legend** — <span style="color:#5fa37e">■ free</span> ($0 self-hosted / free tier) ·
<span style="color:#5f93c4">■ funded</span> (prepaid credits) ·
<span style="color:#cf7a92">■ metered</span> (pay-per-token, budget-capped) · `(local)` = rogueone GPU · `(web)` = web search.

```mermaid
flowchart LR
  classDef alias fill:#d9a44126,stroke:#d9a441,color:#d9a441,font-weight:bold;
  classDef free fill:#5fa37e22,stroke:#5fa37e,color:#cfe3d8;
  classDef funded fill:#5f93c422,stroke:#5f93c4,color:#d3e2f0;
  classDef metered fill:#cf7a9222,stroke:#cf7a92,color:#f0d5dd;

  %% Chat & reasoning
  wldef(["wl-default"]):::alias --> wldef1["groq · gpt-oss-120b"]:::free --> wldef2["gemini · 2.5-flash"]:::free --> wldef3["anthropic · claude-haiku-4.5"]:::funded
  wspd(["wl-speed"]):::alias --> wspd1["groq · gpt-oss-120b"]:::free --> wspd2["cerebras · gpt-oss-120b"]:::free --> wspd3["gemini · 2.5-flash"]:::free
  wrsn(["wl-reason"]):::alias --> wrsn1["ollama · qwen3:30b (local)"]:::free --> wrsn2["deepseek · reasoner"]:::metered --> wrsn3["groq · gpt-oss-120b"]:::free
  wbig(["wl-big-oss"]):::alias --> wbig1["openrouter · minimax-m3"]:::free --> wbig2["groq · gpt-oss-120b"]:::free

  %% Code & agents
  wcod(["wl-coding"]):::alias --> wcod1["opencode-zen · kimi-k3"]:::free --> wcod2["anthropic · claude-haiku-4.5"]:::funded --> wcod3["deepseek · chat"]:::metered --> wcod4["groq · gpt-oss-120b"]:::free
  wagt(["wl-agentic"]):::alias --> wagt1["anthropic · claude-haiku-4.5"]:::funded --> wagt2["openai · gpt-4o-mini"]:::metered --> wagt3["cerebras · gpt-oss-120b"]:::free --> wagt4["gemini · 2.5-flash"]:::free

  %% Retrieval, eval, search
  wrag(["wl-rag"]):::alias --> wrag1["ollama · gpt-oss:20b (local)"]:::free --> wrag2["groq · gpt-oss-120b"]:::free --> wrag3["gemini · 2.5-flash"]:::free
  wjdg(["wl-judge"]):::alias --> wjdg1["ollama · qwen2.5:7b (local)"]:::free --> wjdg2["groq · gpt-oss-120b"]:::free --> wjdg3["gemini · 2.5-flash"]:::free
  wsch(["wl-search"]):::alias --> wsch1["perplexity · sonar (web)"]:::funded --> wsch2["xai · grok-3"]:::metered
```
