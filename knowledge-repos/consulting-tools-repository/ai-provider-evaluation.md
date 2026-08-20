---
id: ai-provider-evaluation
tags: [technology-assessment, strategy, decision-framework, ai-ml]
surfaces-at: [validated-intent, requirements-analysis, application-design]
related: [build-buy-partner, tech-radar, technical-due-diligence, architecture-tradeoff-analysis, wardley-mapping]
complexity: intermediate
---

# AI Provider Evaluation

## What It Is
A structured framework for assessing and selecting AI model providers — including frontier model APIs (Anthropic, OpenAI, Google Gemini, Meta), cloud-native AI services (AWS Bedrock, Azure OpenAI, Google Vertex AI), and self-hosted open source models (Llama, Mistral). The framework moves AI provider selection beyond "which model scores highest on a benchmark" to a multi-dimensional assessment covering capability fit, cost structure, data governance, lock-in risk, latency profile, compliance requirements, and provider viability. Because the AI provider landscape is changing faster than almost any other technology category, evaluation must include architecture optionality — building so that the application can switch providers without a rewrite.

## When to Use
- Any engagement where the client application or product will consume AI model APIs in production
- When clients have a strong bias toward a specific provider (Azure for Microsoft shops, Bedrock for AWS shops) that needs to be stress-tested against requirements
- When a multi-model architecture is under consideration — different providers for different task types
- Regulated industries (healthcare, finance, government) where data residency, HIPAA, FedRAMP, or GDPR constraints affect provider eligibility
- Solutions scoping: AI provider choice affects build cost, ongoing cost structure, lock-in risk, and compliance posture — it must be made explicit, not assumed

## Key Concepts
- **Capability-Task Alignment**: Match model capabilities to the specific tasks in scope — reasoning, code generation, summarization, classification, multimodal, RAG. Benchmark on your actual prompts and data, not published benchmarks, which measure general capability rather than task-specific performance for your use case
- **Cost Structure Analysis**: Frontier model pricing varies dramatically by model tier, token volume, and input/output ratio. Estimate token consumption per request type and volume; model the monthly cost at P10, P50, and P90 usage levels. Hidden costs: context window size affects input cost; streaming vs. batch eligibility affects pricing tier; fine-tuning and storage add to base API cost
- **Data Governance and Residency**: Where does the prompt data go? Frontier API providers process data in their infrastructure — verify whether training opt-out is available, whether data is retained, and whether residency guarantees (EU-only, US-only) are contractually enforceable. For healthcare and finance, confirm BAA (Business Associate Agreement) or equivalent availability before evaluation proceeds
- **Lock-In Risk Assessment**: Every provider has proprietary features — structured output formats, tool call schemas, system prompt conventions, embedding dimensions. Using these creates migration friction. The Model Abstraction Layer pattern mitigates lock-in at the application layer; provider-neutral interfaces should be a design requirement from day one
- **Provider Viability and Roadmap**: The frontier AI market is consolidating rapidly. Assess: Is the provider financially stable? Is their model roadmap credible and consistent? Is there a clear successor path if the provider pivots or fails? Diversification across providers is a risk mitigation strategy, not just a performance optimization
- **Latency Profile**: API latency varies by provider, model tier, and region. Measure time-to-first-token (critical for streaming UX) and total response time for your actual payload sizes. Self-hosted models on client infrastructure may have higher setup cost but predictable, low latency and no data egress
- **Build/Buy/Partner Framing**: AI model selection is a specific application of the Build/Buy/Partner framework: Buy = frontier API subscription; Partner = cloud-native AI service (Bedrock, Azure OpenAI, Vertex AI); Build = self-hosted open source model. Each trades differently on cost, control, compliance, and capability — see Build vs. Buy vs. Partner entry

## Method Application
Applied at Validated Intent to establish the AI provider strategy before scope is set — because provider choice affects cost structure, compliance posture, and architecture optionality. Evaluated again at Application Design when the technical architecture is being set. Method strongly recommends implementing a Model Abstraction Layer regardless of which provider is chosen, so that provider evolution (new model versions, pricing changes, capability improvements) does not require application rewrites.

## Consulting Insight
🎯 **Consulting Tool — AI Provider Evaluation**: The most expensive AI architecture decision is the one you did not make deliberately — teams that pick a provider by default (because the developer had an API key) create lock-in debt that is hard to unwind. Evaluate against your actual requirements: the benchmark that matters is your task on your data at your volume, not the provider's marketing leaderboard. Always design with provider optionality — a Model Abstraction Layer costs a sprint to implement upfront and saves weeks of re-architecture when the model landscape shifts, which it will. For regulated industries, data governance is the threshold question — resolve it before evaluating capability. → `consulting-tools-repository/ai-provider-evaluation.md`

## Related Entries
- [Build vs. Buy vs. Partner](build-buy-partner.md) — AI provider selection is a specific application of this framework across the build/buy/partner decision space
- [Tech Radar](tech-radar.md) — radar ring placement for AI providers and model serving technologies informs provider shortlisting
- [Technical Due Diligence](technical-due-diligence.md) — due diligence on AI providers includes security, compliance, financial viability, and contractual assessment
- [Architecture Tradeoff Analysis](architecture-tradeoff-analysis.md) — provider selection involves architecture tradeoffs between cost, control, compliance, and capability
- [Wardley Mapping](wardley-mapping.md) — AI capabilities are evolving from custom-built toward commodity; Wardley mapping clarifies where a specific AI use case sits on that evolution axis and whether Build, Buy, or Partner is the right long-term posture
