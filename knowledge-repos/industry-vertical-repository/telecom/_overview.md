---
id: telecom-overview
vertical: telecom
tags: [telecom, telco, 5g, bss, oss, network, overview]
surfaces-at: [requirements-analysis, application-design]
related: [strangler-fig]
---

# Telecom — Industry Overview

## What It Is
Telecommunications technology spans network infrastructure (5G, fiber, cable), network management software (OSS), business and operational support systems (BSS), and the digital services built on top of telecom networks. Clients include MNOs (Mobile Network Operators), MVNOs (Mobile Virtual Network Operators), cable MSOs, fiber providers, and enterprise connectivity providers.

## Why It Matters
Telecom is large-scale, complex, and running on aging stacks. The industry is in the middle of two simultaneous transformations: 5G network buildout (with its software-defined network architecture — NFV, SDN, cloud-native RAN) and BSS/OSS modernization (replacing decades-old systems with cloud-native, API-first platforms). Both create substantial software engineering demand. Scale is a defining constraint — billing and network management systems may handle hundreds of millions of subscribers.

## Key Concepts
- **OSS (Operations Support Systems)**: Software for managing the physical network — network inventory, configuration, fault management, performance management. Key functions: network topology, service provisioning, alarm management.
- **BSS (Business Support Systems)**: Software for customer-facing business operations — CRM, billing, order management, product catalog, revenue management. The front-to-back stack for a telecom operator.
- **Network Slicing**: 5G capability to create virtualized, logically isolated networks with different QoS characteristics on shared physical infrastructure. Enables enterprise private networks and dedicated IoT networks.
- **NFV (Network Functions Virtualization)**: Running network functions (firewalls, routers, session border controllers) as software on commodity hardware rather than specialized appliances. Core to 5G core and cloud-native RAN.
- **SDN (Software-Defined Networking)**: Separating the network control plane from the data plane, enabling programmable, centrally managed network infrastructure.
- **Charging and Billing**: Telecom billing is one of the most complex billing domains — multiple charging models (prepaid, postpaid, usage-based, event-based), rating engines, interconnect settlement, and regulatory taxation. Legacy billing systems (Amdocs, CSG, Ericsson) are deeply entrenched.
- **TM Forum Open APIs**: The industry-standard API framework for telecom BSS/OSS. Defines standard APIs for product catalog, order management, customer management, and more. ODA (Open Digital Architecture) is the TM Forum's architecture blueprint for cloud-native telecom.
- **MVNO (Mobile Virtual Network Operator)**: An operator that provides mobile services by leasing network capacity from an MNO rather than owning infrastructure. MVNO platforms need BSS/OSS without the network management layer.

## Common System Archetypes
- **Network Inventory / Topology Management**: Physical and logical network asset management
- **Service Assurance**: Fault detection, performance monitoring, and SLA management
- **Order Management (Service Fulfillment)**: End-to-end provisioning of network services for customers
- **Rating and Billing Platform**: Usage collection, rating, invoicing, and revenue management
- **Product Catalog**: Central definition of all products and services offered to customers

## Industry Insight
📡 **Industry Insight — Telecom**: You're working in telecom. BSS/OSS modernization programs almost always involve integrating with deeply entrenched legacy systems (Amdocs, Ericsson, NSN) before replacing them — strangler fig is the dominant migration pattern. Billing systems are among the most complex in any industry; rating engine requirements (usage events, pricing rules, taxation) require dedicated domain expertise and should not be approached as a generic billing problem. TM Forum Open APIs are the right integration vocabulary for BSS/OSS. → `industry-vertical-repository/telecom/_overview.md`

## Solutions Context
**Typical engagement patterns**: BSS/OSS modernization, cloud-native billing platform, MVNO platform build, network inventory management, 5G service orchestration, digital channel (self-service app/portal).

**Common scope anchors**: TM Forum Open API alignment, order management and fulfillment, rating and billing engine, product catalog, network inventory integration, legacy BSS integration and migration.

**Risk factors**: Legacy BSS integration complexity is the primary delivery risk in most telecom programs. Billing logic complexity is consistently underestimated. Network provisioning dependencies on OSS/network elements are frequently outside project team control.

## Related Entries
- [Strangler Fig](../../engineering-knowledge-repository/strangler-fig.md) — the dominant migration pattern for replacing legacy BSS/OSS systems incrementally
