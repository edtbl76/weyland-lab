---
id: clustering
tags: [pattern, ai-ml, backend]
surfaces-at: [application-design, functional-design]
related: [dimensionality-reduction, embeddings, feature-engineering, anomaly-detection]
complexity: intermediate
---

# Clustering

## What It Is
Unsupervised learning techniques for grouping data points into clusters based on similarity — without predefined labels. Clustering discovers structure in data: customer segments, document topics, behavioral groups, product categories. It is exploratory and descriptive — the algorithm finds natural groupings, but a human must interpret and validate what those groups mean. Clustering is widely used in customer analytics, content organization, anomaly detection, and as a preprocessing step for other models.

## When to Apply
- Customer segmentation — identify distinct behavioral or demographic groups
- Document and content clustering — topic discovery, content organization
- Preprocessing — cluster-based features or reducing a large label set
- Anomaly detection — points that don't fit any cluster are anomalies
- Exploratory analysis — understanding the natural structure of a dataset

## Key Concepts
- **K-Means**: Partition data into K clusters by minimizing within-cluster variance. Fast, scalable, simple. Requires specifying K; assumes spherical clusters of similar size; sensitive to outliers. The practical default for large tabular datasets
- **Choosing K**: Elbow method (plot inertia vs. K, find the elbow); silhouette score (measures how well-separated clusters are — higher is better). Use both — elbow for efficiency intuition, silhouette for quality
- **DBSCAN (Density-Based Spatial Clustering of Applications with Noise)**: Clusters based on density — groups points with many nearby neighbors; marks low-density points as noise/outliers. Finds arbitrarily shaped clusters; doesn't require specifying K; identifies outliers natively. Sensitive to `eps` and `min_samples` hyperparameters
- **Hierarchical Clustering**: Builds a tree of nested clusters (dendrogram). Agglomerative (bottom-up): start with each point as its own cluster, merge closest pairs iteratively. Provides the full cluster hierarchy — cut at any level to get K clusters. Computationally expensive for large datasets
- **Gaussian Mixture Models (GMM)**: Probabilistic extension of K-Means — assumes data is generated from a mixture of Gaussian distributions. Provides soft cluster assignments (probability of belonging to each cluster). More flexible than K-Means for non-spherical clusters
- **Clustering on Embeddings**: Cluster in the semantic embedding space rather than raw feature space — produces more meaningful clusters for text, images, and behavioral data. Standard pattern: encode with a pretrained model → reduce dimensions (UMAP) → cluster (K-Means or HDBSCAN)
- **HDBSCAN**: Hierarchical DBSCAN — more robust than DBSCAN; handles varying cluster densities; only one key hyperparameter (`min_cluster_size`). Preferred over DBSCAN in practice
- **Cluster Validation**: No ground truth labels — evaluate with silhouette score, Davies-Bouldin index, or domain expert review. Business validation (do the segments make sense?) is as important as statistical metrics

## In Practice
Method uses K-Means for customer segmentation on tabular data and HDBSCAN for clustering text embeddings (document grouping, semantic topic discovery). Dimensionality reduction (UMAP) precedes clustering on high-dimensional embedding spaces. Cluster quality is evaluated with silhouette scores and domain expert review of representative samples from each cluster.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Clustering**: K-Means is the fast default for tabular data — use the elbow method and silhouette score to select K. For text and embeddings, HDBSCAN on UMAP-reduced embeddings produces more semantically meaningful clusters than K-Means. DBSCAN and HDBSCAN are preferable when cluster shapes are non-spherical or when you need outlier detection as a side effect. Always validate clusters with domain experts — algorithmic metrics tell you clusters are tight; only humans can tell you they're meaningful. Cluster labels are a starting point, not ground truth; iterate with business stakeholders. → `engineering-knowledge-repository/clustering.md`

## Related Entries
- [Dimensionality Reduction](dimensionality-reduction.md) — dimensionality reduction improves cluster quality in high-dimensional spaces
- [Embeddings](embeddings.md) — clustering on semantic embeddings produces meaningful content and behavioral groupings
- [Feature Engineering](feature-engineering.md) — feature quality directly determines clustering meaningfulness
- [Anomaly Detection](anomaly-detection.md) — DBSCAN/HDBSCAN identify outliers (anomalies) as a natural byproduct of clustering
