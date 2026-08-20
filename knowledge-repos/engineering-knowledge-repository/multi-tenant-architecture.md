---
id: multi-tenant-architecture
tags: [pattern, backend, infrastructure]
surfaces-at: [application-design, functional-design]
related: [database-sharding, rbac, data-privacy, database-normalization, cloud-native-design]
complexity: advanced
---

# Multi-Tenant Architecture

## What It Is
A software architecture where a single instance of an application serves multiple customers (tenants), with each tenant's data and configuration isolated from others. Multi-tenancy is the defining architectural pattern of SaaS — one deployment serves many customers at different subscription tiers, with strong guarantees that Tenant A cannot see Tenant B's data. The key design decisions are: what level of isolation do tenants require? (shared everything → dedicated everything), how is tenant context propagated through the system?, and how is the tenant data boundary enforced at each layer?

## When to Apply
- Building a SaaS product where the same application serves multiple paying customers
- When cost efficiency requires sharing infrastructure across customers rather than deploying per-customer
- When enterprise customers require data isolation guarantees but not necessarily dedicated infrastructure
- Migrating a single-tenant application to serve multiple independent organizations

## Key Concepts
- **Isolation Models**: The spectrum of multi-tenant isolation, from most shared to most isolated:
  - *Shared database, shared schema*: All tenants' data in the same tables, distinguished by a `tenant_id` column. Most cost-efficient; highest isolation risk if tenant scoping is missed
  - *Shared database, separate schemas*: Each tenant gets their own PostgreSQL schema (namespace) within the same database. Better isolation; schema migrations run per tenant
  - *Separate database per tenant*: Each tenant gets a dedicated database instance. Maximum data isolation; higher operational overhead; required for enterprise contracts with data residency requirements
  - *Separate deployment per tenant*: Full dedicated infrastructure per tenant. Maximum isolation; essentially single-tenant with automation. Suitable for highly regulated industries
- **Tenant Context Propagation**: Tenant identity must be established at the request boundary (JWT claim, subdomain, API key) and propagated through every layer — middleware, service calls, database queries. Losing tenant context mid-stack is the most common source of data leakage
- **Row-Level Security**: PostgreSQL and other databases support row-level security (RLS) policies that enforce tenant isolation at the database level, independent of application code. `CREATE POLICY tenant_isolation ON orders USING (tenant_id = current_setting('app.tenant_id'))`. This is the strongest isolation guarantee for shared-schema models
- **Tenant-Aware Data Access Layer**: All database queries must include tenant scoping. Use a repository pattern or ORM-level filter to ensure `tenant_id` is automatically applied — never rely on developers to remember to add `WHERE tenant_id = ?` to every query
- **Tenant Configuration**: Tenants need configurable behavior (feature flags per tenant, custom branding, tier-based feature access). Store tenant configuration in a central tenant registry; load at request time and cache
- **Noisy Neighbor Problem**: In shared infrastructure, one tenant's heavy workload can degrade performance for others. Mitigations: rate limiting per tenant, separate compute queues for high-tier tenants, database query timeouts
- **Tenant Onboarding and Offboarding**: Multi-tenant systems need automated tenant provisioning (create schema, seed configuration, set up billing) and offboarding (data export, schema teardown, billing cancellation). These are operational workflows, not afterthoughts

## In Practice
Method SaaS engagements default to shared database, separate schemas for small-to-medium customer counts (<500 tenants). Row-level security in PostgreSQL enforces isolation. Tenant context is extracted from JWT claims in API middleware and stored in request-scoped context. Database sessions receive `SET app.tenant_id = ?` before each query, activating RLS policies. Enterprise customers with data residency requirements receive separate database instances.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Multi-Tenant Architecture**: The most common multi-tenant security failure is tenant context loss — a code path that doesn't propagate tenant ID correctly and accidentally exposes another tenant's data. Database-level row-level security is the strongest defense because it can't be bypassed by application bugs. Choose your isolation model based on customer requirements, not theoretical security — shared schema with RLS is appropriate for most SaaS; separate databases are for enterprise contracts with explicit isolation SLAs. Automate tenant provisioning from day one; manual tenant setup doesn't scale past 10 customers. → `engineering-knowledge-repository/multi-tenant-architecture.md`

## Related Entries
- [Database Sharding](database-sharding.md) — sharding strategies may be used to distribute tenant data across database nodes
- [RBAC](rbac.md) — role-based access control within a tenant defines user permissions; tenant isolation defines data separation between tenants
- [Data Privacy](data-privacy.md) — multi-tenancy is a prerequisite for GDPR compliance in SaaS; data isolation and right-to-erasure must operate per tenant
- [Database Normalization](database-normalization.md) — tenant-aware schema design must balance normalization with tenant scoping requirements
- [Cloud-Native Design](cloud-native-design.md) — multi-tenant SaaS applications are typically cloud-native to leverage managed services at scale
