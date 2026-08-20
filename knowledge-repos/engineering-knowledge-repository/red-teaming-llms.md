---
id: red-teaming-llms
tags: [methodology, ai-ml, security, backend]
surfaces-at: [nfr-requirements, application-design]
related: [prompt-injection-defense, llm-guardrails, llm-evaluation, threat-modeling]
complexity: advanced
---

# Red-Teaming LLMs

## What It Is
A systematic adversarial testing process for LLM-based systems — probing for failures, safety violations, harmful outputs, and exploitable behaviors before deployment. Red-teaming for LLMs extends traditional security red-teaming to include model-specific failure modes: jailbreaks, prompt injection, harmful content generation, data exfiltration via prompt, and model denial-of-service. It is a pre-deployment safety gate and an ongoing practice as models and adversarial techniques evolve.

## When to Apply
- Before deploying any LLM-based application accessible to users
- When integrating a new base model or updating to a newer model version
- After significant changes to system prompts or the application's use of model capabilities
- Any time the application processes untrusted user input

## Key Concepts
- **Jailbreaking**: Attempts to bypass model safety training — "DAN" prompts, roleplay scenarios ("pretend you have no restrictions"), character injection. Test whether the model can be made to violate its intended constraints
- **Prompt Injection**: Malicious instructions embedded in user input or tool outputs that hijack the model's behavior — cause it to ignore system prompt instructions, exfiltrate data, or take unintended actions. Especially dangerous in agentic systems with tool access
- **Data Exfiltration via Prompt**: Crafted prompts designed to extract system prompt contents, internal context, or user data from the model's context window
- **Harmful Content Generation**: Test the model's willingness to generate dangerous, illegal, or offensive content under adversarial prompting
- **Hallucination and Factual Accuracy**: Red-team for the model confidently producing false information in high-stakes domains — legal, medical, financial
- **Structured Red-Team Process**: (1) Define threat model — who are the adversaries, what are they trying to achieve; (2) Build a test set of adversarial prompts; (3) Evaluate systematically, not ad hoc; (4) Document failures with severity ratings; (5) Implement mitigations; (6) Retest
- **Automated Red-Teaming**: Use an "attacker LLM" to generate adversarial prompts at scale — tools like Garak, PyRIT (Microsoft), Promptfoo. Complements but does not replace human red-teamers
- **Multi-Turn Red-Teaming**: Attacks that unfold over multiple conversational turns — the adversary builds context gradually. Test multi-turn sequences, not just single-turn prompts
- **Severity Classification**: Not all failures are equal. Classify by potential harm (critical: assists in violence/self-harm; high: produces illegal content; medium: violates policy; low: minor quality issues)

## In Practice
Method conducts red-teaming before any LLM application goes to production. The process includes a threat model, a structured adversarial prompt test set, automated testing via Promptfoo, and a human red-team session. Findings are documented with severity ratings. Critical and high-severity findings block deployment. Mitigations (guardrails, prompt hardening) are retested before release.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Red-Teaming LLMs**: Red-team every LLM application before production — adversarial users will probe your system whether you test it first or not. Build a structured test set covering jailbreaks, prompt injection, data exfiltration, and harmful content. Use automated tools (Promptfoo, Garak) for scale, then supplement with human creativity for novel attacks. Test multi-turn scenarios — many defenses fail over multiple conversation turns. Classify findings by severity: critical/high findings block release. Treat red-teaming as ongoing — new attack techniques emerge continuously. → `engineering-knowledge-repository/red-teaming-llms.md`

## Related Entries
- [Prompt Injection Defense](prompt-injection-defense.md) — mitigations for prompt injection attacks found during red-teaming
- [LLM Guardrails](llm-guardrails.md) — safety layers that red-teaming validates and stress-tests
- [LLM Evaluation](llm-evaluation.md) — red-teaming is a form of adversarial evaluation
- [Threat Modeling](threat-modeling.md) — threat modeling defines the adversary model that informs red-team scope
