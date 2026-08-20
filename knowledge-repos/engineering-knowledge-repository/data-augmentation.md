---
id: data-augmentation
tags: [pattern, ai-ml, data, backend]
surfaces-at: [application-design, functional-design]
related: [class-imbalance, feature-engineering, few-shot-learning, training-serving-skew]
complexity: intermediate
---

# Data Augmentation

## What It Is
Techniques for artificially expanding a training dataset by creating modified versions of existing examples — without collecting new labeled data. Augmentation increases dataset size, introduces diversity, and acts as a regularizer against overfitting. It is especially valuable when labeled data is scarce or expensive to collect. In computer vision, augmentation is near-universal. In NLP and tabular data, it is more selective.

## When to Apply
- Small training datasets where overfitting is a concern
- Class imbalance — augment minority class examples to balance the dataset
- Improving model robustness — models trained on augmented data generalize better to real-world variation

## Key Concepts

**Computer Vision Augmentation**:
- Geometric: random crop, flip, rotation, scaling, shear
- Color: brightness, contrast, saturation, hue jitter
- Noise: Gaussian noise, blur, JPEG compression artifacts
- Advanced: MixUp (blend two images and their labels), CutMix (paste a patch from one image into another), RandAugment (automated policy search for augmentation strategy)
- torchvision.transforms and Albumentations are the standard libraries

**NLP Augmentation**:
- *Synonym replacement*: Replace words with synonyms (EDA — Easy Data Augmentation)
- *Back-translation*: Translate to another language and back — produces semantically equivalent paraphrases
- *LLM paraphrase generation*: Use an LLM to generate diverse restatements of existing examples — highest quality NLP augmentation
- *Contextual word insertion/deletion*: Use a masked language model to insert or remove words naturally

**Tabular Data Augmentation**:
- SMOTE (Synthetic Minority Oversampling Technique): Generate synthetic minority class examples by interpolating between existing examples in feature space — primary technique for class imbalance in tabular data
- Gaussian noise injection: Add small random noise to continuous features
- CTGAN / TVAE: Deep generative models that produce realistic synthetic tabular data

**LLM-Based Synthetic Data Generation**:
- Use an LLM to generate additional labeled training examples from a small seed set
- Prompt the LLM: `"Generate 10 diverse examples of [task] similar to: [seed examples]"`
- Quality control: filter generated examples with a classifier or human review
- Increasingly used for NLP and LLM fine-tuning dataset expansion

**Augmentation Correctness**: Label-preserving augmentation is required — the augmented example must have the same correct label as the original. Geometric augmentations that change the spatial meaning of an image (e.g., flipping a "turn left" traffic sign) are label-destroying — must be applied carefully

## In Practice
Method computer vision pipelines use Albumentations with a standard augmentation policy (flip, crop, color jitter, Gaussian noise). NLP augmentation uses LLM-based paraphrase generation for high-quality data expansion. SMOTE is applied for class imbalance in tabular classification tasks. Augmented examples are flagged in the dataset — they can be excluded from evaluation sets.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Data Augmentation**: More data beats better algorithms — augmentation is how you get more data from less. Computer vision: random crop, flip, color jitter are the baseline; add MixUp/CutMix for modern architectures. NLP: LLM paraphrase generation produces the highest-quality augmented examples. Tabular class imbalance: SMOTE generates synthetic minority examples. Keep augmented examples out of validation and test sets — augmented training data is valid; augmented evaluation data is not. Verify augmentations are label-preserving — don't flip labels by accident. → `engineering-knowledge-repository/data-augmentation.md`

## Related Entries
- [Class Imbalance](class-imbalance.md) — augmentation is a primary technique for addressing class imbalance
- [Feature Engineering](feature-engineering.md) — augmentation and feature engineering are complementary dataset improvement strategies
- [Few-Shot Learning](few-shot-learning.md) — augmentation helps expand the small datasets used in few-shot learning
- [Training-Serving Skew](training-serving-skew.md) — augmentation that doesn't reflect production distribution can introduce skew
