---
id: model-explainability
tags: [methodology, ai-ml, backend]
surfaces-at: [nfr-requirements, application-design]
related: [bias-and-fairness, responsible-ai, model-evaluation-metrics, feature-engineering, human-in-the-loop]
complexity: intermediate
---

# Model Explainability

## What It Is
Techniques for understanding why a machine learning model made a specific prediction — which features drove the output and by how much. Explainability is required for debugging model failures, building stakeholder trust, meeting regulatory requirements (GDPR right to explanation, financial services model risk management), and identifying bias. There is a spectrum from inherently interpretable models (linear regression, decision trees) to post-hoc explanation methods applied to black-box models (SHAP, LIME).

## When to Apply
- Regulated industries (financial services, healthcare, insurance) where model decisions must be auditable
- High-stakes decisions affecting individuals (credit, hiring, medical diagnosis)
- Debugging unexpectedly poor model performance — understanding what the model learned
- Building stakeholder confidence in model behavior before deployment
- Any model where "why" matters as much as "what"

## Key Concepts
- **Inherently Interpretable Models**: Linear regression, logistic regression, decision trees, rule-based models — the model structure itself is the explanation. Prefer these when performance is acceptable; interpretability is free
- **SHAP (SHapley Additive exPlanations)**: The leading post-hoc explanation method. Computes each feature's contribution to a specific prediction using Shapley values from game theory. Provides both local (per-prediction) and global (model-wide) explanations. Model-agnostic; exact for tree models (TreeSHAP is fast), approximate for neural networks
- **LIME (Local Interpretable Model-agnostic Explanations)**: Fits a simple interpretable model locally around a specific prediction. Faster than SHAP for some models; less theoretically grounded. Good for quick local explanations
- **Feature Importance**: Global measure of which features the model relies on most across all predictions. Built into tree-based models (XGBoost, LightGBM, Random Forest). Less informative than SHAP — doesn't show direction or per-prediction breakdown
- **Partial Dependence Plots (PDP)**: Show the marginal effect of one or two features on model predictions, averaged over all other features. Good for communicating model behavior to stakeholders
- **SHAP Summary and Dependence Plots**: SHAP beeswarm plots show global feature importance and direction; SHAP dependence plots show the relationship between a feature value and its SHAP impact
- **Attention Visualization**: For transformer-based models, attention weights show which input tokens influenced the output — limited interpretability value (attention ≠ attribution) but useful for debugging
- **Model Cards**: Standardized documentation of model behavior, intended use, performance across subgroups, and limitations. Google's format is widely adopted

## In Practice
Method uses SHAP (TreeSHAP for gradient boosted tree models, KernelSHAP for others) as the standard explainability method. SHAP summary plots are included in model review packages for stakeholder sign-off. Model cards are generated for all models deployed to production. For regulated industry clients, feature-level explanations are stored per prediction for audit purposes.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Model Explainability**: Prefer interpretable models when performance is sufficient — free explainability beats post-hoc explanations. When you need black-box models, use SHAP: it's theoretically grounded, works across model types, and produces both local (per-prediction) and global explanations. TreeSHAP is fast enough for production logging on tree models. Store per-prediction SHAP values for regulated use cases — retroactive explanation generation is unreliable. Generate model cards before production deployment — they force documentation of known limitations and subgroup performance. → `engineering-knowledge-repository/model-explainability.md`

## Related Entries
- [Bias and Fairness](bias-and-fairness.md) — explainability tools reveal where bias originates in model predictions
- [Responsible AI](responsible-ai.md) — explainability is a core pillar of responsible AI governance
- [Model Evaluation Metrics](model-evaluation-metrics.md) — explainability complements performance metrics with behavioral understanding
- [Feature Engineering](feature-engineering.md) — SHAP feature importance informs which engineered features the model actually uses
- [Human-in-the-Loop](human-in-the-loop.md) — explanations help human reviewers make informed override decisions
