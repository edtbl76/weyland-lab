---
id: bias-and-fairness
tags: [methodology, ai-ml, backend]
surfaces-at: [nfr-requirements, application-design]
related: [model-explainability, responsible-ai, model-evaluation-metrics, class-imbalance, data-augmentation, red-teaming-llms]
complexity: intermediate
---

# Bias and Fairness

## What It Is
The study and mitigation of systematic, unfair disparities in ML model predictions across demographic groups or protected characteristics (race, gender, age, disability status). ML models learn patterns from historical data — if that data reflects historical discrimination or underrepresentation, the model perpetuates and can amplify those disparities. Bias in production ML systems causes real harm: discriminatory loan decisions, biased hiring filters, unequal medical diagnosis quality. Fairness is both an ethical obligation and, increasingly, a legal requirement.

## When to Apply
- Any model making decisions that affect individuals (credit, hiring, housing, healthcare, criminal justice)
- Models trained on historical data that may reflect past discrimination
- Systems deployed across demographically diverse populations
- Regulated industries with anti-discrimination requirements (ECOA, Fair Housing Act, EEOC)
- LLMs used in high-stakes decision support

## Key Concepts
- **Sources of Bias**: Historical bias (discrimination in training data), representation bias (underrepresented groups have less training data), measurement bias (features measured differently across groups), aggregation bias (one model for groups with different underlying patterns)
- **Fairness Definitions** — these are mathematically incompatible; choose based on use case:
  - *Demographic Parity*: Equal positive prediction rates across groups — equal approval rates regardless of group
  - *Equalized Odds*: Equal true positive and false positive rates across groups — model is equally accurate for all groups
  - *Calibration*: Predicted probabilities reflect true rates equally across groups
  - *Individual Fairness*: Similar individuals receive similar predictions
- **Fairness-Accuracy Tradeoff**: Enforcing strict fairness constraints typically reduces overall accuracy — an explicit business and ethical tradeoff, not a technical problem with a perfect solution
- **Bias Detection**: Evaluate model metrics (accuracy, FPR, FNR, precision, recall) disaggregated by demographic subgroup. Look for disparate impact — outcome rates that differ significantly across groups. Fairlearn, Aequitas, IBM AI Fairness 360 are toolkits
- **Mitigation — Pre-processing**: Resampling or reweighting training data to balance representation across groups
- **Mitigation — In-processing**: Fairness constraints added to the training objective — penalize disparate predictions during training
- **Mitigation — Post-processing**: Adjust decision thresholds separately per group to equalize error rates after training
- **Disparate Impact Analysis**: The 4/5ths rule (80% rule) from US employment law — if a protected group's selection rate is less than 80% of the highest-selected group, disparate impact is indicated
- **LLM Bias**: LLMs exhibit social biases from pretraining data — stereotypical associations, differential quality of responses across languages and dialects. Red-team specifically for demographic bias

## In Practice
Method performs subgroup performance analysis as part of every model evaluation for client-facing systems. Fairlearn is used for fairness metric computation. Disparate impact analysis is documented in model cards. For regulated industry clients (financial services, HR tech), bias mitigation strategy is included in the NFR requirements stage.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Bias and Fairness**: Evaluate model performance disaggregated by demographic subgroup before deployment — overall accuracy hides disparate impacts. There is no universal fairness definition — demographic parity, equalized odds, and calibration are mathematically incompatible; choose explicitly based on the use case and regulatory context. Document the fairness-accuracy tradeoff — it's a business decision, not a technical one. For regulated industries, disparate impact analysis is a legal requirement, not a nice-to-have. Bias in LLMs requires adversarial probing across demographic scenarios, not just standard benchmarks. → `engineering-knowledge-repository/bias-and-fairness.md`

## Related Entries
- [Model Explainability](model-explainability.md) — SHAP and feature importance reveal which features drive biased predictions
- [Responsible AI](responsible-ai.md) — fairness is a core pillar of responsible AI governance
- [Model Evaluation Metrics](model-evaluation-metrics.md) — bias detection requires disaggregated evaluation metrics per subgroup
- [Class Imbalance](class-imbalance.md) — underrepresentation of demographic groups is a form of class imbalance
- [Data Augmentation](data-augmentation.md) — augmenting underrepresented groups is a pre-processing bias mitigation technique
- [Red-Teaming LLMs](red-teaming-llms.md) — red-teaming surfaces demographic bias in LLM outputs
