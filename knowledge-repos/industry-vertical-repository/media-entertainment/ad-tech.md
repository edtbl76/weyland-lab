---
id: ad-tech
vertical: media-entertainment
tags: [media, advertising, avod, fast, ssai, programmatic, monetization]
surfaces-at: [application-design, functional-design]
related: [media-entertainment-overview, streaming-platform, content-supply-chain]
---

# Ad Tech & Streaming Monetization

## What It Is
Ad tech in media covers the systems that enable advertising-supported content monetization — the ad decision infrastructure, ad insertion technology, audience targeting, and measurement systems that power AVOD (Advertising-based Video on Demand), FAST (Free Ad-Supported Streaming TV), and hybrid SVOD/AVOD tiers. As subscription growth has slowed, ad-supported streaming has become the primary growth lever for major streaming platforms and the foundation of FAST channel networks.

## Why It Matters in Media & Entertainment
Ad-supported streaming is now a major revenue model — Netflix, Disney+, Peacock, Paramount+, and Hulu all offer ad tiers. FAST channels (Pluto TV, Tubi, Peacock Free) generate significant revenue from entirely ad-funded content. The technology that delivers, targets, and measures ads directly determines CPMs and fill rates — the two levers that determine ad revenue. Poor ad tech (buffering during ad breaks, duplicate ads, targeting failures) directly reduces advertiser spend and viewer retention.

## Key Concepts
- **AVOD (Advertising Video on Demand)**: An on-demand streaming model where content is free to the viewer, funded by advertising. Examples: Tubi, Pluto TV, Peacock Free, ad-supported Netflix/Disney+ tiers.
- **FAST (Free Ad-Supported Streaming TV)**: Linear-style streaming channels with scheduled programming and ad breaks — the streaming equivalent of broadcast TV. Requires a channel schedule management system in addition to ad insertion.
- **Ad Pod**: A group of ads played in sequence during an ad break. Pod length, ad count, and competitive separation rules (no two ads from the same advertiser in a pod) are defined by the publisher and enforced by the ad server.
- **SSAI (Server-Side Ad Insertion)**: Stitching ads into the video stream server-side so ads are delivered as part of the content stream. Enables delivery across all devices without client-side ad blockers, maintains stream continuity, and simplifies measurement. The standard approach for streaming ad insertion.
- **CSAI (Client-Side Ad Insertion)**: The legacy approach where the player fetches and inserts ads client-side. Vulnerable to ad blocking, causes buffering at ad boundaries on some devices. Being replaced by SSAI for most streaming use cases.
- **Ad Decision Server (ADS) / Ad Server**: The system that receives an ad request (with targeting parameters) and returns ad creative. Publishers may use their own ad server or a third-party (Google Ad Manager, FreeWheel). The ADS evaluates available inventory against demand and selects the optimal ad.
- **VAST (Video Ad Serving Template)**: The IAB standard XML format for ad responses from an ad server — contains the ad media URL, tracking pixels, and metadata. VMAP (Video Multiple Ad Playlist) extends VAST to define ad break structure for long-form content.
- **Programmatic Advertising**: Automated buying and selling of ad inventory through real-time bidding (RTB) — the publisher's ad server calls a Supply Side Platform (SSP), which auctions the impression to Demand Side Platforms (DSPs) representing advertisers. The auction happens in ~100ms.
- **DAI (Dynamic Ad Insertion)**: The capability to insert different ads for different viewers watching the same content — enabling personalized, targeted advertising. Requires the SSAI system to support viewer-level ad decisioning.
- **Audience Segmentation / Targeting**: Using first-party data (viewing history, registration data) and third-party data to target ads to specific audience segments. Privacy regulation (GDPR, COPPA, deprecation of third-party cookies) is reshaping targeting approaches.

## Common Patterns / Gotchas
- **SSAI latency at ad break boundaries determines viewer experience.** The time from content end to first ad frame must be imperceptible. SSAI systems that take 2+ seconds to stitch ads create visible buffering that degrades experience and is measured by advertisers.
- **Ad fill rate depends on demand integration breadth.** An ad server with one demand source will have poor fill rates on unsold inventory. Programmatic integration (SSP connections, header bidding) maximizes fill. Low fill rates mean blank ad breaks — content without revenue.
- **Measurement and verification are advertiser requirements.** Advertisers require third-party verification of impressions and completion rates (IAB, MRC standards). Integrate with measurement partners (Nielsen, Comscore, DoubleVerify) from the start — retrofitting measurement is painful.
- **COPPA compliance is critical for family content.** Content targeted at children under 13 is subject to COPPA — behavioral targeting is prohibited, and only contextual advertising is permitted. Family content platforms must enforce strict ad category restrictions and cannot use standard behavioral targeting.
- **Competitive separation is legally and contractually required.** Advertisers pay premiums for separation from competitor ads. Ad servers must enforce competitive separation rules reliably. Failures are contract violations.
- **FAST channel scheduling adds supply chain complexity.** FAST requires a channel schedule (EPG — Electronic Program Guide) in addition to content. Schedule management, ad break placement in scheduled content, and EPG distribution to aggregators are additional operational requirements beyond VOD.

## Industry Insight
🎬 **Industry Insight — Ad Tech**: You're building ad-supported streaming. SSAI latency at ad break boundaries is a viewer experience metric as much as a technical one — design for imperceptible transitions and measure it explicitly. Ad fill rate depends on demand integration breadth; plan programmatic SSP integration as a first-class capability, not a follow-on. COPPA compliance for family content requires strict ad category enforcement and prohibits behavioral targeting — design audience segmentation with content rating as a filter from the start. → `industry-vertical-repository/media-entertainment/ad-tech.md`

## Solutions Context
**Typical engagement patterns**: AVOD/FAST platform launch, SSAI infrastructure, ad server integration, programmatic demand integration, DAI and audience targeting, measurement and verification, FAST channel management.

**Common scope anchors**: SSAI pipeline, VAST/VMAP ad server integration, programmatic SSP integration, DAI audience targeting, ad pod management and competitive separation, measurement partner integration, FAST EPG management.

**Risk factors**: SSAI latency under load requires dedicated performance testing. Programmatic demand integration involves multiple SSP and DSP partners with varying API quality. COPPA compliance scope must be determined early — it fundamentally constrains targeting architecture for family content.

## Related Entries
- [Media & Entertainment Overview](_overview.md)
- [Streaming Platform](streaming-platform.md)
- [Content Supply Chain](content-supply-chain.md)
