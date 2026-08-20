---
id: kano-model
tags: [product, discovery]
surfaces-at: [requirements-analysis, validated-intent]
related: [moscow-prioritization, rice-scoring, north-star-metric, jobs-to-be-done-research, value-proposition-canvas]
complexity: intermediate
---

# Kano Model

## What It Is
A product development framework developed by Noriaki Kano that categorizes product features by their relationship to customer satisfaction. Unlike prioritization frameworks that rank features by importance, the Kano Model classifies features into five types based on how customer satisfaction changes with increasing feature quality: Basic Needs (must-have), Performance Needs (more is better), Excitement Needs (delighters), Indifferent, and Reverse. The key insight is that not all features contribute equally to satisfaction — some prevent dissatisfaction but don't create satisfaction, while others have outsized positive impact when present but are unnoticed when absent. Over time, Excitement features decay into Basic Needs as the market matures.

## When to Use
- Product roadmap prioritization when the team is debating feature investment
- Distinguishing hygiene features (table stakes) from differentiating features
- When a client is investing equally in all requirements without understanding their satisfaction impact
- Evaluating competitive positioning: what do competitors have that is now a Basic Need vs. what would be a differentiator
- Guiding build/buy decisions: Basic Needs are candidates for commercial solutions; Excitement Needs may warrant custom development

## Key Concepts
- **Basic Needs (Must-Be)**: Expected features — their absence causes severe dissatisfaction, but their presence doesn't increase satisfaction. Users don't mention them until they're missing. Examples: a login function, data security, basic search. These should be funded and done — not invested in for differentiation
- **Performance Needs (One-Dimensional)**: Linear relationship with satisfaction — more is better, less is worse. Examples: page load speed, report generation time, battery life. These are worth optimizing because the improvement is directly proportional to satisfaction
- **Excitement Needs (Attractive/Delighters)**: Unexpected features that create disproportionate satisfaction when present and cause no dissatisfaction when absent. Examples: proactive insights, personalized recommendations, one-click workflows. These are the source of competitive differentiation — but they decay
- **Indifferent**: Features that neither increase nor decrease satisfaction regardless of their presence. Often features built because an engineer thought they were cool or a stakeholder requested them without real user demand
- **Reverse**: Features that actually decrease satisfaction when present — often due to complexity added to support one user type that burdens others
- **Feature Decay**: Excitement features eventually become Performance and then Basic Needs as competitors copy them and user expectations normalize. Today's delighter is tomorrow's table stakes
- **Kano Survey**: The Kano Model is validated through paired survey questions — functional ("How do you feel if this feature is present?") and dysfunctional ("How do you feel if this feature is absent?") — to classify each feature

## Method Application
Used during requirements analysis and roadmap planning to categorize client requirements by satisfaction type. Prevents over-investment in Basic Needs (commodity features that should be bought or built to minimum) and under-investment in Excitement Needs (the differentiating features that justify the program). Particularly useful when a client's requirements list is flat — all items weighted equally — and needs prioritization logic.

## Consulting Insight
🎯 **Consulting Tool — Kano Model**: The most common misapplication of investment in product programs is over-engineering Basic Needs. Clients spend months perfecting authentication, audit logging, or data export — features users expect to exist but don't value. The Kano Model reframes the question: don't optimize for Basic Needs beyond the minimum acceptable threshold; instead, invest that capacity in Excitement Needs where marginal investment produces disproportionate satisfaction. Ask: "What would users be surprised and delighted by?" — that's where roadmap differentiation lives. → `consulting-tools-repository/kano-model.md`

## Related Entries
- [MoSCoW Prioritization](moscow-prioritization.md) — complementary prioritization; MoSCoW classifies by delivery necessity, Kano by satisfaction type
- [RICE Scoring](rice-scoring.md) — quantitative prioritization; Kano classification should inform RICE impact estimates
- [North Star Metric](north-star-metric.md) — Excitement and Performance features should connect to the North Star; Basic Needs often don't
- [Jobs to Be Done Research](jobs-to-be-done-research.md) — JTBD research surfaces which jobs create Excitement vs. Basic Need features
- [Value Proposition Canvas](value-proposition-canvas.md) — Gains and Pains map to Excitement and Basic Need categories
