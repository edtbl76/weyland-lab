---
id: capability-maturity-model
tags: [organizational, technology-assessment]
surfaces-at: [validated-intent, requirements-analysis]
related: [mckinsey-7s, tech-radar, technical-due-diligence, organizational-design, adkar]
complexity: intermediate
---

# Capability Maturity Model (CMM / CMMI)

## What It Is
A framework that describes the progression of an organization's capabilities across five maturity levels — from chaotic and ad hoc (Level 1) to optimizing and continuously improving (Level 5). Originally developed by the Software Engineering Institute (SEI) at Carnegie Mellon for software development process maturity (the original CMM), and later expanded to CMMI (Capability Maturity Model Integration) covering development, services, and acquisition. In consulting practice, the maturity model concept is applied broadly: any capability domain — data management, DevOps, security, product management, agile delivery — can be assessed against a maturity scale to establish a baseline and define a target state.

## When to Use
- Establishing a baseline of organizational or technical capability before a transformation program
- When a client asks "where are we and where do we need to be?" for a specific capability domain
- Justifying investment: demonstrating the gap between current and required maturity
- Scoping transformation programs: each maturity level defines a set of practices to implement
- Technical due diligence: assessing engineering capability maturity of an acquisition target

## Key Concepts
- **The Five Maturity Levels**:
  - *Level 1 — Initial*: Processes are unpredictable, poorly controlled, and reactive. Success depends on individual heroics. No consistent process
  - *Level 2 — Managed*: Basic project management in place. Processes are planned and monitored at the project level, but not consistent across projects
  - *Level 3 — Defined*: Processes are documented, standardized, and consistent across the organization. Standards are derived from best practices
  - *Level 4 — Quantitatively Managed*: Process performance is measured and controlled using statistical methods. Predictable quality and performance
  - *Level 5 — Optimizing*: Focus on continuous improvement. Innovative practices are piloted and scaled. Processes adapt to changing environments
- **Process Areas**: CMMI defines process areas (e.g., Configuration Management, Requirements Management, Risk Management) with specific practices at each maturity level. Each process area can be assessed independently
- **Capability vs. Maturity**: CMMI distinguishes capability levels (how well a specific process performs) from maturity levels (the overall process maturity of the organization). An organization can have high capability in some areas and low in others
- **Custom Maturity Models**: CMMI is formal and certification-oriented. In consulting practice, custom maturity models are built for specific domains — data maturity (ad hoc → managed → standardized → optimizing), DevOps maturity, AI maturity — using the five-level structure as a template
- **Target Maturity**: The goal is not always Level 5. For many organizations, Level 3 (defined, standardized processes) is the appropriate target — fully managed quality may not be worth the investment. The target should reflect strategic requirements
- **Assessment Methods**: CMMI assessments range from formal SCAMPI appraisals (certification-grade) to lightweight self-assessments against a custom rubric. In consulting contexts, a one-day maturity workshop with key stakeholders typically produces a defensible current-state assessment

## Method Application
Method uses capability maturity assessments as a structured baseline tool at the start of transformation programs. When a client asks "how does our current state compare to best practice," a maturity model provides the answer with specific dimensions rather than vague ratings. The maturity assessment output is used to scope the transformation: what practices must be implemented to reach the target maturity level?

## Consulting Insight
🎯 **Consulting Tool — Capability Maturity Model**: The most useful part of a maturity assessment is not the overall score — it's the practice-level gap analysis. An organization can be Level 2 on average but Level 4 on Configuration Management and Level 1 on Requirements Management. The practice-level view identifies where investment will produce the most maturity movement. Score the dimensions individually, not in aggregate, and the transformation roadmap writes itself. → `consulting-tools-repository/capability-maturity-model.md`

## Related Entries
- [McKinsey 7-S](mckinsey-7s.md) — capability maturity assesses the Skills and Systems elements of the 7-S model in depth
- [Tech Radar](tech-radar.md) — radar ring placement reflects technology adoption maturity; complements CMM process maturity assessment
- [Technical Due Diligence](technical-due-diligence.md) — operational maturity is a due diligence dimension; CMM framework provides the assessment structure
- [Organizational Design](organizational-design.md) — higher maturity levels require organizational structures that support defined, managed processes
- [ADKAR](adkar.md) — moving from lower to higher maturity levels requires individual behavior change; ADKAR structures the adoption journey
