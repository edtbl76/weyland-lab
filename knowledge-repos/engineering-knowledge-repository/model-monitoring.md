---
id: model-monitoring
tags: [methodology, ai-ml, observability, backend]
surfaces-at: [nfr-requirements, infrastructure-design]
related: [mlops, data-drift, concept-drift, service-level-objectives, metrics-and-alerting, continuous-training, model-registry]
complexity: intermediate
---

# Model Monitoring

## What It Is
The continuous tracking of a deployed ML model's health in production — measuring whether it continues to make accurate, well-calibrated predictions on real-world data over time. Unlike software, ML models degrade silently — the code hasn't changed, but the world has. Model monitoring catches this degradation before it impacts business outcomes, and triggers retraining when needed.

## When to Apply
- Every production ML model — monitoring is a production readiness requirement
- Especially for models where the input distribution is expected to change (user behavior, language, seasonal patterns)

## Key Concepts
- **The Three Monitoring Layers**:
  1. *Infrastructure monitoring*: Latency, throughput, error rate, resource utilization — standard service health metrics
  2. *Data monitoring*: Input feature distributions — are the features being sent to the model consistent with what it was trained on?
  3. *Model performance monitoring*: Prediction quality — are predictions still accurate?

- **Data Drift Detection**: Comparing the statistical distribution of features in the current inference window against the training distribution. Detects when the model is operating outside its training domain. See Data Drift entry

- **Prediction Distribution Monitoring**: Track the distribution of model outputs (predicted labels, confidence scores). Sudden shifts in prediction distribution indicate something has changed — input data, upstream systems, or actual concept shift

- **Ground Truth Labels**: The gold standard for monitoring model quality — comparing predictions against actual outcomes. Often delayed (labels arrive hours/days/weeks after prediction) and incomplete. When available, compute accuracy, precision, recall, AUC-ROC on sampled production data

- **Proxy Metrics**: Business metrics that correlate with model quality — CTR, conversion rate, user feedback. Used when direct ground truth is unavailable. A drop in CTR on a ranking model signals degradation

- **Statistical Tests**: Kolmogorov-Smirnov test, Population Stability Index (PSI), Jensen-Shannon divergence — quantify distribution shift with p-values. PSI > 0.2 is a conventional threshold for significant drift

- **Monitoring Cadence**: High-frequency metrics (latency, error rate) in real time. Feature distribution checks daily or hourly. Ground truth labels as they arrive (often with lag)

- **Alerting Strategy**: Alert on statistically significant drift (PSI threshold, KS p-value), prediction distribution anomalies, and ground truth metric degradation below SLO. Avoid alert fatigue — PSI thresholds should be validated empirically

- **Evidently AI**: Open-source ML monitoring library — data drift reports, model performance reports, test suites. Integrates with Grafana

- **Arize, Fiddler, WhyLabs**: Managed ML monitoring platforms — richer than open-source options; SaaS cost

## In Practice
Method production ML systems use Evidently AI for drift reports and Prometheus/Grafana for infrastructure metrics. Prediction distribution is monitored daily. Ground truth labels are ingested as they arrive and used for retrospective accuracy calculations. PSI > 0.2 on any feature triggers a drift alert. Consecutive drift alerts trigger the CT pipeline.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Model Monitoring**: Models degrade silently — monitor proactively. Track three layers: infrastructure (latency, errors), data (feature drift), and model performance (prediction quality against ground truth). Use PSI or KS test for drift detection — PSI > 0.2 is a threshold worth investigating. Monitor prediction distribution — sudden shifts signal problems before ground truth arrives. Tie drift alerts to retraining triggers. Use Evidently AI for open-source monitoring; Arize or WhyLabs for managed. Monitoring without action is useless — alert thresholds must connect to the CT pipeline. → `engineering-knowledge-repository/model-monitoring.md`

## Related Entries
- [MLOps](mlops.md) — model monitoring is a core MLOps discipline
- [Data Drift](data-drift.md) — the statistical detection of input feature distribution changes
- [Concept Drift](concept-drift.md) — the change in the relationship between inputs and target labels
- [Service Level Objectives](service-level-objectives.md) — model performance SLOs define when monitoring alerts should fire
- [Metrics and Alerting](metrics-and-alerting.md) — model monitoring metrics feed the standard alerting infrastructure
- [Continuous Training](continuous-training.md) — monitoring triggers CT when degradation is detected
- [Model Registry](model-registry.md) — rollback to a previous registry version when monitoring detects degradation
