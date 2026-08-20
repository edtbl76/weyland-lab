---
id: dimensionality-reduction
tags: [pattern, ai-ml, backend]
surfaces-at: [functional-design, application-design]
related: [feature-engineering, embeddings, clustering, model-evaluation-metrics]
complexity: intermediate
---

# Dimensionality Reduction

## What It Is
Techniques for reducing the number of features in a dataset while preserving the most important structure. High-dimensional data causes the curse of dimensionality — distance metrics become meaningless, models overfit, and computation grows exponentially. Dimensionality reduction addresses this by projecting data into a lower-dimensional space that retains maximum information. It is used for preprocessing before modeling, visualization of high-dimensional data, compression of embeddings, and exploratory data analysis.

## When to Apply
- High-dimensional feature sets where many features are correlated or redundant
- Visualizing high-dimensional data (embeddings, clusters) in 2D or 3D
- Compressing dense embeddings for efficient similarity search
- Preprocessing before clustering or anomaly detection
- When model performance degrades due to the curse of dimensionality

## Key Concepts
- **PCA (Principal Component Analysis)**: Linear dimensionality reduction. Finds orthogonal axes (principal components) that capture maximum variance. Deterministic, fast, interpretable components. The standard first choice for linear dimensionality reduction. Limitation: captures only linear structure
- **t-SNE (t-Distributed Stochastic Neighbor Embedding)**: Non-linear; preserves local neighborhood structure — similar points in high-D space remain close in 2D. Excellent for visualization. Computationally expensive; not used for preprocessing (non-deterministic, no transform for new data)
- **UMAP (Uniform Manifold Approximation and Projection)**: Non-linear; faster than t-SNE; preserves both local and some global structure. Better for preprocessing than t-SNE because it supports transforming new data points. Increasingly preferred over t-SNE for embedding visualization
- **Autoencoders**: Neural network encoder-decoder architecture. The bottleneck layer is the compressed representation. Captures non-linear structure. Used for image and text compression, anomaly detection (reconstruction error)
- **Truncated SVD / LSA**: Linear dimensionality reduction for sparse matrices (TF-IDF text features). Does not center the data — compatible with sparse representations where PCA is not
- **Variance Explained**: For PCA, plot the cumulative explained variance ratio vs. number of components. Choose the number of components that capture 90-95% of variance
- **Curse of Dimensionality**: In high dimensions, all points become equidistant — nearest-neighbor search, distance-based clustering, and many ML algorithms fail. Dimensionality reduction is the primary mitigation
- **Fit on Train, Transform on Test**: Like all preprocessing, dimensionality reduction transformers (PCA, UMAP) must be fit on training data only, then applied to test data. Prevents leakage

## In Practice
Method uses PCA for preprocessing high-dimensional tabular features before classical ML models. UMAP is used for visualizing embedding spaces (customer segments, semantic clusters). Autoencoders are used for learned compression of image features. All reducers are fit on training data and wrapped in scikit-learn Pipelines.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Dimensionality Reduction**: Use PCA first — it's fast, interpretable, and handles linear redundancy well. For visualization, UMAP produces better-structured 2D projections than t-SNE and is faster. For sparse text features, use Truncated SVD (LSA), not PCA. Always fit the reducer on training data and transform test data separately — PCA is a preprocessing step subject to the same leakage rules as scaling and encoding. Target 90-95% explained variance for PCA component selection rather than picking an arbitrary number. → `engineering-knowledge-repository/dimensionality-reduction.md`

## Related Entries
- [Feature Engineering](feature-engineering.md) — dimensionality reduction is a feature transformation technique applied after initial feature engineering
- [Embeddings](embeddings.md) — dimensionality reduction (UMAP, PCA) is used to compress and visualize high-dimensional embeddings
- [Clustering](clustering.md) — dimensionality reduction is commonly applied before clustering to improve distance metric quality
- [Model Evaluation Metrics](model-evaluation-metrics.md) — explained variance ratio is the evaluation metric for PCA component selection
