---
id: inventory-management
vertical: retail
tags: [retail, inventory, availability, reservation, omnichannel, oversell, atp]
surfaces-at: [application-design, functional-design]
related: [retail-overview, order-management, customer-data-platform, eventual-consistency]
---

# Inventory Management

## What It Is
Retail inventory management is the set of systems and processes that track the quantity, location, and availability of merchandise — from supplier through warehouse through store through customer. In omnichannel retail, it extends to real-time availability calculation across all fulfillment nodes (DCs, stores, dropship vendors) and the reservation and allocation logic that prevents the same unit from being sold twice across channels.

## Why It Matters in Retail
Inventory is retail's primary asset. Oversell (committing inventory that doesn't exist) creates cancelled orders, customer disappointment, and margin-destroying expedite costs. Undersell (not offering available inventory for sale due to poor visibility) is lost revenue. In omnichannel retail, the same physical inventory serves multiple demand channels simultaneously — getting availability right across all of them, in real time, is one of the hardest distributed systems problems in retail technology.

## Key Concepts
- **ATP (Available to Promise)**: The quantity of a SKU that can be safely committed to a new order at a given location. ATP = On Hand − Safety Stock − Already Reserved. Accurate ATP is the foundation of inventory availability.
- **On-Hand vs Available**: On-hand is the physical count. Available (ATP) is what can be sold — on-hand minus safety stock, open reservations, and in-flight transfers. These are not the same number and must not be treated as such.
- **Safety Stock**: A buffer quantity held back from availability to protect against inventory record inaccuracies, in-transit losses, and fulfillment failures. Safety stock settings are a tunable business parameter, not a technical constant.
- **Inventory Reservation**: A soft hold placed on units when an order is created, before the order is confirmed to pick. Reservations prevent oversell by reducing available inventory atomically at order creation. The design of the reservation mechanism (optimistic vs pessimistic, reservation lifetime) is a core architectural decision.
- **Optimistic vs Pessimistic Reservation**:
  - **Pessimistic**: Inventory is locked at the moment an item is added to cart. Prevents oversell aggressively but may hold inventory against incomplete checkouts, reducing availability.
  - **Optimistic**: Inventory is reserved only at order confirmation. Higher availability, but races at high concurrency can cause oversell.
  - **Hybrid**: Reserve at order confirmation with a short-lived cart hold at add-to-cart. Most common in practice.
- **Inventory Record Accuracy (IRA)**: The percentage of inventory records that match physical counts. Store inventory IRA is typically 65–85% — significantly lower than DC inventory. This must be factored into availability calculations (safety stock buffers for stores) rather than assumed to be 100%.
- **Omnichannel Inventory Pooling**: Sharing inventory visibility and availability across all demand channels (ecommerce, store POS, B2B, marketplace) from a single inventory pool. Requires a real-time, channel-agnostic availability service.
- **Inventory Segmentation / Buffers**: Rules that restrict certain inventory from certain channels — e.g., reserve 20 units per store for in-store shoppers even when online demand is high. Prevents the online channel from depleting store inventory and creating dead-stock situations on the floor.
- **Real-Time vs Near-Real-Time Availability**: True real-time inventory (every transaction reflected in <1 second) is expensive and architecturally complex. Near-real-time (seconds to minutes lag, tuned safety stock) is sufficient for most retail scenarios and far more practical. Define the actual requirement, not an aspirational one.

## Common Patterns / Gotchas
- **Store inventory data is less accurate than you think.** Shrinkage, misplaced items, receive discrepancies, and infrequent cycle counts mean store on-hand counts are approximate. Any system serving store inventory to online channels must account for this with conservative buffers, not by trusting the record.
- **Reservation races at high concurrency.** During peak traffic (flash sales, Black Friday), hundreds of simultaneous orders may attempt to reserve the last few units of a popular SKU. Reservation logic must be atomic — optimistic concurrency with idempotent retry or database-level row locking. Race conditions lead to oversell.
- **Inventory sync across systems is eventually consistent.** OMS, WMS, ERP, and ecommerce platform each maintain inventory records. Keeping them synchronized is an ongoing data consistency challenge. Design for eventual consistency and reconciliation, not perfect real-time sync.
- **Marketplace channels complicate pooling.** Selling on Amazon, Walmart.com, or eBay in addition to owned channels means external parties are committing inventory. Marketplace SLA penalties for cancelling confirmed orders create strong incentives to buffer marketplace channels conservatively.
- **Returns create inventory complexity.** Returned units are not immediately resellable — they may require inspection, reprocessing, or liquidation. Returned inventory entering the available pool prematurely causes quality incidents.

## Industry Insight
🛒 **Industry Insight — Inventory Management**: You're designing a retail inventory system. Store inventory record accuracy is 65–85% in most retailers — do not model store availability against raw on-hand counts; build safety stock buffers per node to absorb inaccuracy. Reservation races at peak concurrency are a distributed systems problem, not a business logic problem — choose your reservation strategy (optimistic vs pessimistic) deliberately and design for atomic reservation under concurrent load. Define the actual latency requirement for availability updates; near-real-time with tuned buffers is almost always sufficient and far simpler than true real-time. → `industry-vertical-repository/retail/inventory-management.md`

## Solutions Context
**Typical engagement patterns**: Inventory platform modernization, omnichannel availability service, ATP calculation engine, store inventory accuracy program, real-time inventory visibility, DC/store inventory sync.

**Common scope anchors**: ATP calculation model, reservation mechanism design, omnichannel inventory pooling, safety stock configuration, inventory sync architecture (OMS/WMS/ERP), returns inventory workflow.

**Risk factors**: Store inventory accuracy assumptions are frequently optimistic — validate with the client's actual IRA data before designing availability logic. Reservation design under peak concurrency requires load testing at realistic traffic levels. Marketplace channel inventory sync creates external dependencies with SLA penalties.

## Related Entries
- [Retail Overview](_overview.md)
- [Order Management](order-management.md)
- [Eventual Consistency](../../engineering-knowledge-repository/eventual-consistency.md) — cross-system inventory sync (OMS, WMS, ERP, ecommerce) is eventually consistent; design reconciliation workflows accordingly
