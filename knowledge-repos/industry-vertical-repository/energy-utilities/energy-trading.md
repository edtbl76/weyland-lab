---
id: energy-trading
vertical: energy-utilities
tags: [energy, trading, etrm, risk, settlement, iso, rto, commodities]
surfaces-at: [application-design, functional-design]
related: [energy-utilities-overview, grid-management, renewable-integration]
---

# Energy Trading & Risk Management

## What It Is
Energy trading and risk management (ETRM) encompasses the systems that support the buying, selling, and hedging of energy commodities — electricity, natural gas, oil, and emissions credits — across physical and financial markets. Participants include utilities, IPPs, energy retailers, trading firms, and large industrial consumers. The domain sits at the intersection of commodity trading (fast-moving, quantitative) and physical grid operations (constrained, regulated).

## Why It Matters in Energy & Utilities
Energy is simultaneously a physical commodity (electrons and molecules that must balance in real time) and a financial instrument (futures, swaps, options traded on exchanges and OTC). The software that manages this must bridge both worlds: ISO market operations with millisecond clearing, long-dated financial contracts with complex pricing structures, and real-time position and risk exposure across both. Errors are immediately financial — a missed hedge, an incorrect position, or a failed settlement submission can mean material losses.

## Key Concepts
- **ETRM System**: The system of record for all energy trades — physical and financial. Manages deal capture, scheduling, risk, settlements, and reporting. Major platforms: Allegro, Brady, Openlink/ION, Triple Point. Often old, deeply customized, and expensive to replace.
- **Physical vs Financial Trading**: Physical trades involve the actual delivery of energy at a location and time. Financial trades are hedges or speculative positions — no physical delivery. Most portfolios contain both.
- **Position**: The net exposure of a portfolio to a commodity price at a given location, time period, and delivery type. Real-time position management is core ETRM functionality.
- **Mark-to-Market (MtM)**: The current market value of open positions. MtM P&L is tracked daily and drives risk reporting and margin calls.
- **ISO/RTO Market Integration**: In deregulated markets, generators and load-serving entities submit bids and schedules to the ISO (CAISO, PJM, MISO, ERCOT, etc.). Integration with ISO OASIS/market systems for bid submission, schedule confirmation, and settlement is mandatory for wholesale market participants.
- **Settlement**: The reconciliation and financial clearing of physical deliveries and market transactions. Energy settlement involves comparing metered quantities against scheduled quantities and calculating imbalance charges.
- **VaR (Value at Risk)**: Standard risk metric quantifying the maximum expected loss at a given confidence level over a time horizon. Reported to management and often required by counterparties and credit providers.
- **Counterparty Credit Risk**: The risk that a trading counterparty defaults before settling. ETRM systems track credit exposure by counterparty and enforce credit limits.
- **Forward Curve**: The market's expectation of future commodity prices at different delivery points and time periods. Drives MtM valuation and hedging strategy.

## Common Patterns / Gotchas
- **ETRM data models are extremely complex.** A single energy trade may have hundreds of attributes — delivery points, pricing formulas, transportation paths, transmission rights, counterparty details. Data migration from legacy ETRM systems is one of the hardest problems in the industry.
- **ISO integration is slow and brittle.** Each ISO has proprietary APIs, file formats (XML, CSV, FTP drops), and timing windows. CAISO OASIS, PJM eMKT, ERCOT MIS — each requires separate integration work. ISOs do not prioritize API modernization.
- **Settlement reconciliation is never clean.** Differences between scheduled quantities and metered actuals (imbalances) must be investigated and disputed where appropriate. Automated imbalance detection and dispute workflow is essential.
- **Real-time and day-ahead are different systems with different requirements.** Day-ahead market operations (bidding, scheduling) are batch-oriented. Real-time balancing is latency-sensitive. These workloads should be architecturally separated.
- **Regulatory reporting is extensive.** FERC EQR (Electric Quarterly Report), CFTC reporting for financial derivatives, state PUC requirements — compliance reporting is a significant ongoing obligation.
- **Forward curve management is a specialty.** Accurate forward curves require market data feeds (ICE, Bloomberg, Platts), curve building logic, and version management. This is typically a dedicated quantitative function.

## Industry Insight
⚡ **Industry Insight — Energy Trading**: You're working on energy trading systems. Treat ISO market integration as a discrete, high-uncertainty workstream — each ISO has proprietary APIs, unique timing constraints, and limited support for third-party integrations. Settlement reconciliation is never fully automated; design an exception management workflow from the start, not as a follow-on. ETRM data models are substantially more complex than standard financial systems — validate data model requirements with trading desk users before designing. → `industry-vertical-repository/energy-utilities/energy-trading.md`

## Solutions Context
**Typical engagement patterns**: ETRM implementation or modernization, ISO market integration, settlement automation, risk reporting and analytics, trading data platform.

**Common scope anchors**: ISO/RTO integration (bid submission, schedule management, settlement), position and P&L reporting, forward curve management, deal capture workflow, settlement reconciliation and exception management, regulatory reporting.

**Risk factors**: ISO integration timelines are driven by ISO support availability, not the project team. ETRM data migration from legacy systems (Openlink, Triple Point) is consistently the highest-risk workstream. Quantitative pricing logic (option valuation, complex deal structures) requires specialized expertise not found in standard engineering teams.

## Related Entries
- [Energy & Utilities Overview](_overview.md)
- [Grid Management](grid-management.md)
