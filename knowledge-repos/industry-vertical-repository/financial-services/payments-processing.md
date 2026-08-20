---
id: payments-processing
vertical: financial-services
tags: [financial-services, payments, ach, rtp, card, iso20022, idempotency]
surfaces-at: [application-design, functional-design]
related: [financial-services-overview, idempotency]
---

# Payments Processing

## What It Is
Payments processing is the orchestration of money movement between parties across one or more payment rails. A payment system receives a payment instruction, routes it to the appropriate rail, manages state through clearing and settlement, and reconciles the result. The complexity lies not in moving money but in handling the failure modes, regulatory requirements, and rail-specific behavior correctly.

## Why It Matters in Financial Services
Payments are the core revenue and operational function of most financial services engagements. Errors are consequential — a double-charge, a missed settlement, or a fraud loss is immediately visible and financially material. The irrevocability of certain rails (RTP, FedNow, wire) means that failure handling and fraud prevention must be designed before go-live, not added later.

## Key Concepts
- **Payment Rail**: The infrastructure over which money moves. Common US rails: ACH (batch, 1–2 days), RTP/FedNow (real-time, irrevocable), card networks (Visa/Mastercard, near-real-time authorization), SWIFT (international wire).
- **Authorization**: Approval that a payment can proceed. For cards, this is real-time. For ACH, there is no authorization step — the payment either settles or returns.
- **Clearing**: Confirmation and reconciliation of payment details between sender and receiver financial institutions.
- **Settlement**: The actual transfer of funds between institutions. Separate from clearing. Timing varies by rail (ACH settles in batches; RTP settles immediately).
- **Return / Reversal / Chargeback**: The mechanisms for correcting erroneous payments. ACH returns can occur days after initiation. Card chargebacks can occur months later. RTP and wire are generally irrevocable.
- **ISO 20022**: The modern financial messaging standard. SWIFT is migrating to it; RTP and FedNow are built on it. New payment systems should default to ISO 20022.
- **Idempotency**: The property that submitting the same payment instruction multiple times produces the same result (one payment, not N). Critical for retry logic.

## Common Patterns / Gotchas
- **Idempotency is not optional.** Network failures and retries are guaranteed to happen. Every payment endpoint must accept an idempotency key and return the same result for duplicate requests. This must be designed in, not bolted on.
- **Model payment state explicitly.** States: initiated → submitted → clearing → settled / failed / returned. Attempting to infer state from transaction records leads to inconsistency under failure conditions.
- **Distinguish between the payment instruction and the ledger entry.** The instruction (what was requested) and the ledger entry (what actually settled) are not the same thing and must be tracked separately.
- **Each rail has its own failure modes.** ACH returns arrive 2–5 days after submission. Card chargebacks arrive weeks or months later. RTP failures are synchronous. Design the reconciliation and exception handling workflow for each rail independently.
- **Settlement timing creates float.** The gap between clearing and settlement has cash flow and accounting implications. Make sure finance stakeholders are involved in settlement timing decisions.
- **Fraud prevention must be in scope before go-live on irrevocable rails.** There is no "add fraud detection later" for RTP or wire. Design it as a first-class concern.

## Industry Insight
💳 **Industry Insight — Payments Processing**: You're designing a payments system. Model payment lifecycle as an explicit state machine and implement idempotency at every payment submission endpoint before anything else — these two decisions prevent the most common and expensive production incidents in payments. Each payment rail has distinct failure modes and settlement timing; design exception handling per rail, not as a single generic flow. → `industry-vertical-repository/financial-services/payments-processing.md`

## Solutions Context
**Typical engagement patterns**: Payments platform builds or modernizations, multi-rail orchestration layers, embedded payments for non-bank fintechs, ACH or RTP integration for existing platforms, payment reconciliation and exception management.

**Common scope anchors**: Rail selection and integration (ACH, RTP, FedNow, card), payment state machine, idempotency layer, ledger design, reconciliation workflow, fraud prevention, PCI-DSS scoping (if card payments in scope).

**Risk factors**: Sponsor bank or payment processor relationships introduce external timelines and API constraints outside client control. PCI scope expands significantly if card data flows through the platform. Fraud/risk model design requires domain expertise and real transaction data — frequently underscoped.

**Estimation notes**: Each payment rail integration should be scoped separately. Reconciliation and exception handling is often 30–40% of total payments platform work. Fraud prevention (rules engine, ML scoring, case management) is a significant standalone workstream if not using a third-party vendor.

## Related Entries
- [Financial Services Overview](_overview.md) — regulatory landscape and common integration points
- [Idempotency](../../engineering-knowledge-repository/idempotency.md) — every payment submission endpoint must implement idempotency; network failures and retries are guaranteed to occur
