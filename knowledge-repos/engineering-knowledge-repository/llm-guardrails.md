---
id: llm-guardrails
tags: [pattern, ai-ml, security, backend]
surfaces-at: [application-design, nfr-requirements]
related: [prompt-injection-defense, llm-evaluation, defense-in-depth, prompt-engineering, red-teaming-llms]
complexity: intermediate
---

# LLM Guardrails

## What It Is
Validation and filtering layers applied to LLM inputs and outputs to enforce safety, accuracy, and behavioral constraints. Guardrails ensure the LLM stays within its intended operating envelope — blocking harmful inputs, validating output format, detecting hallucinations, filtering sensitive data leakage, and enforcing topic scope. They are a critical production-readiness requirement for any customer-facing LLM application.

## When to Apply
- Any production LLM application — especially customer-facing ones
- Applications in regulated industries where output compliance is required
- Agentic systems where unconstrained outputs could trigger real-world actions

## Key Concepts
- **Input Guardrails**: Validate and filter user input before it reaches the LLM. Block: hate speech, PII, off-topic queries (topic classifier), jailbreak attempts, competitor mentions (if policy requires). Route: classify intent and send to appropriate sub-system
- **Output Guardrails**: Validate LLM output before serving to the user. Check: JSON schema compliance, hallucination indicators, PII in output, policy violations, off-topic responses, competitor mentions, unsafe content
- **Schema Validation**: For structured output (JSON), validate against the expected schema before returning. Retry with the same prompt (1-2 times) if output fails schema validation before falling back to an error response
- **Factual Grounding Check**: In RAG systems, verify the response is grounded in the retrieved context — not making up facts. Prompt-based or model-based faithfulness scoring
- **PII Detection**: Scan both input and output for personally identifiable information — SSNs, credit cards, emails, phone numbers. Redact or block before logging and before serving
- **Topic Scope Enforcement**: Classify user queries — reject out-of-scope questions with a helpful redirect rather than attempting to answer. A customer service bot should not answer medical questions
- **Toxicity / Safety Filtering**: Classify output for harmful, offensive, or unsafe content before serving. OpenAI Moderation API, AWS Comprehend, Azure Content Safety provide pre-built classifiers
- **Retry with Repair**: When output fails a guardrail, attempt to repair by re-prompting with the failure mode as context: `"Your previous response was not valid JSON. Please respond only with valid JSON matching this schema: [schema]"`
- **Guardrails Libraries**: NVIDIA NeMo Guardrails (programmable, rails-as-code), Guardrails AI (schema validation + validators), LlamaGuard (Meta, open-source safety classification)
- **Latency Impact**: Each guardrail check adds latency. Parallel execution where possible; prioritize fast checks (schema validation) before slow checks (LLM-based faithfulness scoring)

## In Practice
Method LLM applications apply input topic classification, output schema validation, and PII scan as baseline guardrails on every response. Factual grounding checks are added for RAG applications where hallucination risk is high. Toxicity filtering is applied for all user-facing outputs. Guardrail failures are logged with the full input/output for review and model improvement.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — LLM Guardrails**: Never serve raw LLM output to users in production without validation. Minimum baseline: schema validation (is the output structured correctly?), PII scan (did the model leak sensitive data?), topic scope check (is the response on-topic?). Add faithfulness scoring in RAG to catch hallucinations. Retry with repair on schema failures before returning an error. Parallelize guardrail checks to minimize latency impact. Log all guardrail failures — they are ground truth for prompt improvement and red teaming. → `engineering-knowledge-repository/llm-guardrails.md`

## Related Entries
- [Prompt Injection Defense](prompt-injection-defense.md) — input guardrails catch injection attempts
- [LLM Evaluation](llm-evaluation.md) — guardrail metrics feed into evaluation pipelines
- [Defense in Depth](defense-in-depth.md) — guardrails are one layer of LLM application security
- [Prompt Engineering](prompt-engineering.md) — well-designed prompts reduce the need for output guardrails
- [Red-Teaming LLMs](red-teaming-llms.md) — red teaming identifies which guardrails are needed
