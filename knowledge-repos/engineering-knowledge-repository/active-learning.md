---
id: active-learning
tags: [pattern, ai-ml, backend]
surfaces-at: [application-design, functional-design]
related: [human-in-the-loop, data-augmentation, few-shot-learning, model-evaluation-metrics]
complexity: intermediate
---

# Active Learning

## What It Is
A machine learning paradigm where the model selects which unlabeled examples it wants humans to label next, rather than labeling data randomly. The model identifies the examples it is most uncertain about — or those most likely to improve model performance — and prioritizes them for annotation. Active learning achieves equivalent model performance with significantly fewer labeled examples than random sampling, reducing annotation cost and time.

## When to Apply
- Labeled data is expensive or slow to obtain (medical annotation, legal review, specialized expertise)
- Large pool of unlabeled data exists alongside a small labeled seed set
- Annotation budget is limited — maximize the value of each labeled example
- Iterative model improvement where each labeling round informs the next

## Key Concepts
- **Query Strategy — Uncertainty Sampling**: Select examples the model is most uncertain about. For classifiers: highest entropy over class probabilities, lowest margin between top-two classes, or lowest max-class probability. Simple and effective
- **Query Strategy — Query by Committee**: Train multiple models (a committee); select examples where the committee disagrees most. Reduces dependence on a single model's uncertainty estimate
- **Query Strategy — Expected Model Change**: Select examples that, if labeled, would cause the largest update to the model parameters. Computationally expensive; high quality
- **Query Strategy — Core-Set / Diversity Sampling**: Select examples that are most diverse (maximize coverage of the unlabeled data distribution). Ensures the labeled set is representative, not clustered around uncertain regions
- **Pool-Based Active Learning**: The most common setup — a fixed pool of unlabeled examples exists; the model queries from the pool. Each round: train on current labeled set → score unlabeled pool → query top-K → label → add to training set → repeat
- **Stream-Based Active Learning**: Examples arrive one at a time; the model decides whether to query the label for each. Used in online/streaming contexts
- **Cold Start**: Before any labels exist, active learning cannot compute uncertainty. Bootstrap with random sampling or a few-shot seed set
- **Human Fatigue and Query Budget**: Balance query efficiency with annotator experience — avoid presenting too many similar examples in one batch. Distribute queries across the data distribution

## In Practice
Method active learning pipelines use uncertainty sampling (entropy-based) as the default query strategy. Label Studio provides the annotation interface. Each labeling round produces K new labeled examples; the model is retrained and the cycle repeats. Cold start uses random selection for the first 100 examples.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Active Learning**: Don't label randomly — let the model tell you what to label. Uncertainty sampling (highest entropy predictions) is the practical default; it reliably outperforms random selection per annotation dollar. Start with a small random seed for cold start, then switch to active learning once the model has a baseline. Keep batches diverse — cluster-then-sample prevents annotators from seeing 100 near-identical examples. Log which examples were queried each round — the query history is informative for debugging model failures. → `engineering-knowledge-repository/active-learning.md`

## Related Entries
- [Human-in-the-Loop](human-in-the-loop.md) — active learning directs which examples the human-in-the-loop annotates
- [Data Augmentation](data-augmentation.md) — augmentation expands labeled data; active learning selects which data to label
- [Few-Shot Learning](few-shot-learning.md) — active learning improves few-shot bootstrapping by selecting maximally informative examples
- [Model Evaluation Metrics](model-evaluation-metrics.md) — model uncertainty estimates drive the active learning query strategy
