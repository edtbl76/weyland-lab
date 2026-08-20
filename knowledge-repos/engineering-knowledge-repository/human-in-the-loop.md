---
id: human-in-the-loop
tags: [pattern, ai-ml, backend]
surfaces-at: [application-design, functional-design]
related: [llm-evaluation, llm-guardrails, model-monitoring, active-learning, data-augmentation]
complexity: intermediate
---

# Human-in-the-Loop

## What It Is
A system design pattern where human judgment is incorporated into an AI/ML workflow — either to provide labels for training data, review and correct model outputs before they take effect, or handle cases the model is uncertain about. Human-in-the-loop (HITL) is critical for high-stakes decisions, building training data, managing model uncertainty, and maintaining human accountability in automated systems.

## When to Apply
- High-stakes decisions where model errors have significant consequences (medical, legal, financial)
- Building or improving training data — human labelers provide ground truth
- Model confidence is low — route uncertain predictions to humans
- Regulatory requirements mandate human review before automated action
- Detecting and correcting model failures in production

## Key Concepts
- **Active Learning**: The model identifies which unlabeled examples it is most uncertain about; a human labels those examples first. More efficient than random labeling — the same annotation budget yields higher model improvement
- **Human Review Queue**: Route low-confidence predictions to a human review queue. The human's decision becomes the ground truth. Balances automation throughput with quality
- **Annotation Pipelines**: Infrastructure for collecting, routing, and recording human labels — Label Studio, Scale AI, AWS SageMaker Ground Truth, Labelbox. Annotation quality control (inter-annotator agreement, gold standard examples) is as important as quantity
- **Feedback Loops**: Human corrections on model outputs feed back into the training pipeline — the model improves from its own mistakes. Requires careful design to avoid feedback loop biases
- **Confidence Thresholds**: Automate high-confidence predictions; escalate low-confidence ones. Threshold is a tunable tradeoff between automation rate and accuracy. Monitor the threshold's effectiveness over time — distribution shift changes what "low confidence" means
- **Human-on-the-Loop**: A weaker form — the model acts autonomously but a human monitors for anomalies and can intervene. Appropriate when latency requirements prevent human-in-the-loop but oversight is still needed
- **Labeler Agreement and Quality**: Multiple labelers per example + inter-annotator agreement (Cohen's Kappa, Krippendorff's Alpha) quantifies label quality. Disagreement often reveals ambiguous cases that the model will also find hard
- **Escalation Design**: Clear criteria for what gets escalated, SLAs for human response time, fallback behavior when human review is unavailable

## In Practice
Method HITL implementations route predictions below a confidence threshold to a human review queue backed by Label Studio. Active learning is used for new labeling campaigns — select the top-K uncertain examples per labeling batch. Human corrections are captured in the training data pipeline and included in the next training run. Inter-annotator agreement is reported for every labeling project.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Human-in-the-Loop**: Don't automate fully when the cost of errors is high — build a confidence threshold and a human escalation path. Use active learning for labeling: let the model tell you which examples to label next rather than labeling randomly. Capture human corrections back into the training pipeline — the model should learn from the cases it got wrong. Track inter-annotator agreement to quantify label quality. Human-on-the-loop (monitor rather than approve) is appropriate when latency prevents full HITL but oversight is still required. → `engineering-knowledge-repository/human-in-the-loop.md`

## Related Entries
- [LLM Evaluation](llm-evaluation.md) — human evaluation is the gold standard for LLM output quality
- [LLM Guardrails](llm-guardrails.md) — guardrails can escalate borderline cases to human review
- [Model Monitoring](model-monitoring.md) — monitoring surfaces model failures that trigger human review
- [Active Learning](active-learning.md) — active learning optimizes which examples humans label next
- [Data Augmentation](data-augmentation.md) — human labels provide the ground truth that augmented data extends
