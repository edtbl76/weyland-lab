# LLM Routing

Use-case **aliases → provider fallback chains**, served by **LiteLLM**. A client sends only the alias
(e.g. `wl-coding`); LiteLLM picks the **primary** and fails over down the chain on network / 5xx / 429 /
timeout — server-side and transparent. Left node = primary; each `→` is the next fallback. Colour = cost tier.
Hosted rungs egress **through Bifrost** (LiteLLM → Bifrost → provider) for per-VK cost/usage attribution; the
local **Ollama** lanes (`wl-rag` · `wl-reason` · `wl-judge`) stay direct to rogueone.

Every chain has a **free, always-on** rung so a call lands for $0 — usually the primary, and `wl-search` now carries a
free `wl-default` (groq) tail as its guaranteed lander (a non-web answer, but it always returns). The chat lanes keep
free rungs while escalating to funded providers before that tail; the media lane `wl-tts` grounds on its free
**primary** — self-hosted Kokoro. For the full interactive view see the
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
  wspd(["wl-speed"]):::alias --> wspd1["groq · gpt-oss-120b"]:::free --> wspd2["cerebras · gpt-oss-120b"]:::funded --> wspd3["gemini · 2.5-flash"]:::free
  wrsn(["wl-reason"]):::alias --> wrsn1["ollama · qwen3:30b-a3b (local)"]:::free --> wrsn2["deepseek · v4-pro"]:::funded --> wrsn3["groq · gpt-oss-120b"]:::free
  wbig(["wl-big-oss"]):::alias --> wbig1["openrouter · minimax-m3"]:::metered --> wbig2["groq · gpt-oss-120b"]:::free

  %% Code & agents
  wcod(["wl-coding"]):::alias --> wcod1["opencode-zen · kimi-k3"]:::funded --> wcod2["anthropic · claude-haiku-4.5"]:::funded --> wcod3["deepseek · v4-flash"]:::funded --> wcod4["groq · gpt-oss-120b"]:::free
  wagt(["wl-agentic"]):::alias --> wagt1["anthropic · claude-haiku-4.5"]:::funded --> wagt2["openai · gpt-4o-mini"]:::funded --> wagt3["cerebras · gpt-oss-120b"]:::funded --> wagt4["gemini · 2.5-flash"]:::free

  %% Retrieval, eval, search
  wrag(["wl-rag"]):::alias --> wrag1["ollama · gpt-oss:20b (local)"]:::free --> wrag2["groq · gpt-oss-120b"]:::free --> wrag3["gemini · 2.5-flash"]:::free
  wjdg(["wl-judge"]):::alias --> wjdg1["ollama · qwen2.5:7b (local)"]:::free --> wjdg2["groq · gpt-oss-120b"]:::free --> wjdg3["gemini · 2.5-flash"]:::free
  wsch(["wl-search"]):::alias --> wsch1["perplexity · sonar (web)"]:::funded --> wsch2["xai · grok-4.5 (web)"]:::funded --> wsch3["groq · gpt-oss-120b"]:::free

  %% Media — text-to-speech (audio_speech endpoint, not chat)
  wtts(["wl-tts"]):::alias --> wtts1["kokoro · kokoro"]:::free --> wtts2["elevenlabs · eleven_multilingual_v2"]:::funded
```
