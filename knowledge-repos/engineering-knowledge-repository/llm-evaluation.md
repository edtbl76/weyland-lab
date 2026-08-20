---
id: llm-evaluation
tags: [methodology, ai-ml, testing, backend]
surfaces-at: [application-design, nfr-requirements, code-generation]
related: [model-evaluation-metrics, offline-vs-online-evaluation, human-in-the-loop, llm-observability, retrieval-augmented-generation, llm-guardrails]
complexity: intermediate
---

# LLM Evaluation

## What It Is
The systematic assessment of LLM application quality — measuring whether the system produces accurate, relevant, safe, and useful outputs across a representative range of inputs. LLM evaluation is harder than traditional software testing: outputs are not deterministic, "correct" is often subjective, and the space of possible inputs is unbounded. A robust evaluation pipeline is a prerequisite for shipping LLM features with confidence and for detecting regressions as models or prompts change.

## When to Apply
- Before launching any LLM feature — establish a baseline evaluation before the first deployment
- After every prompt change — prompts are code; changes require regression testing
- When switching model versions or providers
- On a continuous basis in production to detect quality drift

## Key Concepts
- **Evaluation Dataset (Golden Set)**: A curated set of input/expected-output pairs representing the application's use cases. The foundation of offline evaluation. Start with 50-100 examples; grow to 500+ for production confidence. Must cover edge cases, adversarial inputs, and failure modes
- **LLM-as-Judge**: Using a more capable LLM (e.g., GPT-4o, Claude Opus) to evaluate the outputs of the application LLM. Scores outputs on dimensions like correctness, relevance, helpfulness, and groundedness. Scales better than human eval; introduces its own biases
- **RAG-Specific Metrics** (RAGAS framework):
  - *Faithfulness*: Does the answer match the retrieved context? (hallucination detection)
  - *Answer Relevance*: Does the answer address the question?
  - *Context Precision*: Are the retrieved chunks relevant?
  - *Context Recall*: Were all relevant documents retrieved?
- **Human Evaluation**: Ground truth for subjective quality — crowdsourced or expert annotators rate responses. Expensive and slow; use for calibrating automated evaluators
- **A/B Evaluation**: Presenting two responses (from different prompts or models) to human raters and asking which is better. Produces preference data for ranking systems
- **Regression Testing**: Run the golden set on every prompt or model change. Flag any response where quality score drops below baseline. Part of the CI pipeline for LLM applications
- **Latency and Cost as Eval Dimensions**: Quality alone is insufficient — measure tokens used, latency, and cost per query as evaluation metrics alongside output quality
- **Evals Frameworks**: LangSmith (prompt versioning + eval), Braintrust, RAGAS (RAG evaluation), DeepEval, PromptFoo

## In Practice
Method LLM applications maintain a golden evaluation dataset in the repository. LLM-as-judge scoring runs automatically on every prompt change in CI. RAGAS is used for RAG application evaluation. Human evaluation is used quarterly and for major capability changes. Evaluation results are tracked over time — a dashboard shows quality trends across model and prompt versions.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — LLM Evaluation**: You cannot ship LLM features safely without an eval pipeline. Build a golden dataset of 50-100 input/output pairs before launch — it's the test suite for your prompts. Run LLM-as-judge scoring on every prompt change in CI. For RAG, use RAGAS to measure faithfulness, answer relevance, and context precision separately. Human evaluation calibrates your automated evaluators. Track quality over time — prompts degrade as models update. Evaluation is the feedback loop that makes LLM development disciplined rather than vibes-driven. → `engineering-knowledge-repository/llm-evaluation.md`

## Related Entries
- [Model Evaluation Metrics](model-evaluation-metrics.md) — traditional ML metrics that apply to classifiers within LLM pipelines
- [Offline vs. Online Evaluation](offline-vs-online-evaluation.md) — golden set evals are offline; production monitoring is online
- [Human-in-the-Loop](human-in-the-loop.md) — human eval calibrates and grounds automated LLM-as-judge scoring
- [LLM Observability](llm-observability.md) — production quality signals feed back into the evaluation dataset
- [Retrieval-Augmented Generation](retrieval-augmented-generation.md) — RAG evaluation requires measuring retrieval quality separately
- [LLM Guardrails](llm-guardrails.md) — guardrail failure rates are an evaluation metric
