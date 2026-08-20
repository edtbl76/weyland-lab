---
id: service-blueprinting
tags: [discovery, product, organizational]
surfaces-at: [requirements-analysis, validated-intent, application-design]
related: [customer-journey-mapping, event-storming, value-chain-analysis, contextual-inquiry, stakeholder-mapping]
complexity: intermediate
---

# Service Blueprinting

## What It Is
A service design tool that maps the full delivery of a service across four swim lanes: Customer Actions (what the customer does), Frontstage Actions (what employees or systems do that the customer can see), Backstage Actions (what employees or systems do behind the scenes), and Support Processes (the systems, tools, and infrastructure that enable the service). Originally developed by G. Lynn Shostack, service blueprints make visible the complete operating model behind a customer experience — not just what the customer sees, but everything required to deliver it. The "line of visibility" between frontstage and backstage is the key architectural boundary: it separates what customers experience from what enables that experience.

## When to Use
- Mapping the current state of a service before a transformation program
- Identifying operational pain points, gaps, and redundancies in service delivery
- Designing new service experiences that span multiple systems and organizational teams
- When technology investment decisions need to be grounded in operational reality
- Requirements analysis for systems that support customer-facing processes (CRM, case management, field service)

## Key Concepts
- **Customer Actions**: What the customer does at each step — touchpoints, decisions, channels. This is the top layer and the anchor for everything below. All other swim lanes exist to enable these actions
- **Frontstage Actions**: The visible service interactions — what agents, staff, or customer-facing systems do. Includes digital interfaces, emails, notifications, chat, and in-person interactions
- **Backstage Actions**: The invisible work that enables the frontstage — internal processes, manual tasks, escalation paths, quality checks. Often where inefficiency accumulates because it's not visible to customers
- **Support Processes**: Systems, databases, tools, and third-party services that support both frontstage and backstage. Technology investments typically land here — CRM updates, case management systems, ERP integrations
- **Line of Visibility**: The boundary between frontstage and backstage. Crossing this line — when backstage processes become visible to customers — is often unintentional and indicates process leakage
- **Line of Interaction**: The boundary between the customer and the service provider (frontstage). Touchpoints sit on or cross this line
- **Fail Points**: Moments in the blueprint where errors, delays, or breakdowns commonly occur. Blueprint facilitation specifically surfaces fail points — they are the primary input to process redesign
- **Blueprint vs. Journey Map**: Customer journey maps focus on the customer's emotional experience across a journey. Service blueprints focus on the full operational system required to deliver that experience. They are complementary: journey maps reveal customer pain; blueprints reveal operational cause

## Method Application
Method uses service blueprinting in transformation programs where the technology investment is inseparable from the operating model. A CRM implementation that ignores backstage processes will automate the wrong things. A customer portal that doesn't account for support process dependencies will create new fail points. The blueprint ensures technology design reflects operational reality, not just the happy path.

## Consulting Insight
🎯 **Consulting Tool — Service Blueprinting**: The backstage swim lane is where transformation programs find the most value — and the most resistance. Backstage processes are often undocumented, person-dependent, and invisible to leadership. When you blueprint a service and show the client what their backstage actually looks like — the manual reconciliations, the email chains, the spreadsheet workarounds — you change the conversation from "we need a new system" to "we need to redesign how this service is delivered." The technology investment follows from that, not the other way around. → `consulting-tools-repository/service-blueprinting.md`

## Related Entries
- [Customer Journey Mapping](customer-journey-mapping.md) — journey maps provide the customer experience layer; blueprints add the operational layer beneath it
- [Event Storming](event-storming.md) — event storming maps the system domain events that correspond to blueprint support processes
- [Value Chain Analysis](value-chain-analysis.md) — value chain identifies which primary activities the blueprint is capturing; support activities map to the support processes swim lane
- [Contextual Inquiry](contextual-inquiry.md) — field research provides the evidence for backstage and frontstage observations
- [Stakeholder Mapping](stakeholder-mapping.md) — backstage actors in the blueprint are often the same stakeholders who need to be engaged in the change program
