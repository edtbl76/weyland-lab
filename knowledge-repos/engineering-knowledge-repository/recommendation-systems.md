---
id: recommendation-systems
tags: [pattern, ai-ml, backend]
surfaces-at: [application-design, functional-design]
related: [embeddings, vector-databases, feature-stores, model-serving, offline-vs-online-evaluation, a-b-testing]
complexity: advanced
---

# Recommendation Systems

## What It Is
ML systems that predict which items a user is most likely to engage with or find valuable — products, content, connections, ads. Recommendation systems are one of the highest-value ML applications in industry: they drive engagement, revenue, and retention at scale for e-commerce, streaming, social, and content platforms. They are also architecturally complex — combining retrieval (finding candidates from millions of items) with ranking (scoring and ordering candidates for a specific user).

## When to Apply
- Personalized product or content recommendations
- Search result ranking and personalization
- "Related items," "people you may know," "next watch" features
- Any use case where matching users to items at scale is the core problem

## Key Concepts
- **Collaborative Filtering**: Recommend items based on the behavior of similar users ("users like you also liked..."). Matrix factorization (ALS, SVD) decomposes user-item interaction matrices into latent vectors. Effective but requires interaction history — cold start problem for new users/items
- **Content-Based Filtering**: Recommend items similar to ones the user has liked, based on item features. Less susceptible to cold start; limited by feature quality and diversity
- **Two-Tower Architecture**: The dominant production architecture. Two separate neural networks — one encodes the user, one encodes the item — into a shared embedding space. Similarity (dot product or cosine) between user and item embeddings drives retrieval. Train offline; serve via approximate nearest neighbor (ANN) search
- **Retrieval + Ranking Pipeline**: Recommendations are produced in two stages:
  1. *Retrieval (Candidate Generation)*: Fast, approximate — retrieve hundreds of candidates from millions of items using ANN search on embeddings (Faiss, Pinecone, Weaviate)
  2. *Ranking*: Slower, precise — score the candidates with a more complex model that incorporates rich features (user context, item metadata, interaction history). Output the top-K ranked items
- **Implicit vs. Explicit Feedback**: Explicit (ratings, likes) is rare and biased. Implicit (clicks, views, purchases, dwell time) is abundant but noisy. Most production systems train on implicit feedback
- **Cold Start Problem**: New users and new items have no interaction history. Mitigations: content-based fallback for new items, onboarding questionnaires for new users, popularity-based recommendations
- **Position Bias**: Items shown higher in the ranking receive more clicks regardless of quality. Correct for position bias in training data or use counterfactual learning to avoid learning a "show at top → gets clicked" pattern
- **Evaluation**: Offline metrics (NDCG, MRR, hit rate at K) are standard but imperfectly predict online impact. A/B test business metrics (CTR, conversion, engagement) — the offline-online gap is significant in recsys
- **Diversity and Serendipity**: Purely relevance-optimized systems produce filter bubbles and repetitive recommendations. Add diversity constraints — re-rank to increase category spread

## In Practice
Method recommendation systems use the two-tower retrieval + learning-to-rank pipeline. User and item embeddings are stored in Pinecone for ANN retrieval. The ranking model uses LightGBM with rich feature sets from the feature store. Offline evaluation uses NDCG@10; online evaluation uses A/B tests on CTR and conversion. Cold start is handled with content-based fallback and popularity-based defaults.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Recommendation Systems**: Use the two-tower retrieval + ranking pipeline — retrieval filters millions of items to hundreds fast; ranking applies a rich model to those hundreds. Train embeddings offline, serve via ANN (Faiss, Pinecone). Implicit feedback (clicks, purchases) is your primary training signal — correct for position bias or your model learns ranking artifacts. Offline metrics (NDCG) are necessary but not sufficient — always A/B test. Add diversity constraints post-ranking to prevent filter bubbles. The cold start problem never fully goes away; design an explicit fallback strategy for new users and items. → `engineering-knowledge-repository/recommendation-systems.md`

## Related Entries
- [Embeddings](embeddings.md) — two-tower models produce user and item embeddings
- [Vector Databases](vector-databases.md) — ANN search on embeddings is the retrieval mechanism
- [Feature Stores](feature-stores.md) — ranking models require rich features served at low latency from a feature store
- [Model Serving](model-serving.md) — recommendation serving has strict latency requirements (< 100ms)
- [Offline vs. Online Evaluation](offline-vs-online-evaluation.md) — the offline-online gap is particularly large in recommendation systems
- [A/B Testing](a-b-testing.md) — A/B tests on engagement metrics are the ground truth for recommendation quality
