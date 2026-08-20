---
id: accessibility
tags: [pattern, frontend, methodology]
surfaces-at: [application-design, functional-design]
related: [css-architecture, frontend-testing, design-tokens, component-architecture]
complexity: intermediate
---

# Accessibility

## What It Is
The practice of designing and building web applications that are usable by people with disabilities — visual, motor, auditory, cognitive. Accessibility (a11y) is both an ethical obligation and a legal requirement in many jurisdictions (ADA in the US, EN 301 549 in the EU). The Web Content Accessibility Guidelines (WCAG) define the international standard. Practically, accessibility also improves usability for everyone: keyboard navigation, clear labels, and logical structure benefit all users, not just those with disabilities. For consulting firms building client products, accessibility compliance is often a contractual or legal requirement.

## When to Apply
- Every user-facing web application (accessibility is not optional)
- Government, healthcare, financial services, and education applications (often legally mandated)
- Consumer-facing products with broad audiences
- Applications with enterprise clients who have internal accessibility policies

## Key Concepts
- **WCAG Levels**:
  - *A*: Minimum — must meet to avoid excluding users entirely
  - *AA*: Standard target — required by most legal standards (ADA, EN 301 549). The default target for production applications
  - *AAA*: Enhanced — aspirational; not required for full conformance
- **Core Principles (POUR)**:
  - *Perceivable*: All information is presentable in ways users can perceive (alt text, captions, sufficient color contrast)
  - *Operable*: All UI is operable via keyboard; no content requires mouse interaction; no time limits without control
  - *Understandable*: Predictable behavior, clear labels, error messages explain what went wrong and how to fix it
  - *Robust*: Works with assistive technologies (screen readers, switch access, voice control)
- **Semantic HTML**: The foundation of accessibility. Use elements for their purpose: `<button>` for buttons (not `<div onClick>`), `<a>` for navigation, `<h1>`–`<h6>` for headings in logical order, `<nav>`, `<main>`, `<aside>` as landmarks. Screen readers use semantic structure for navigation
- **ARIA (Accessible Rich Internet Applications)**: Attributes that describe roles, states, and properties to assistive technologies when native HTML semantics are insufficient. Rule: never use ARIA when native HTML can do the job. Common uses: `aria-label`, `aria-describedby`, `aria-expanded`, `role="dialog"`
- **Keyboard Navigation**:
  - All interactive elements must be focusable and operable via keyboard
  - Focus order must follow the visual reading order (check with Tab key)
  - Focus must be visible — don't suppress focus outlines (`outline: none`) without an alternative focus indicator
  - Modals must trap focus within the modal while open; restore focus to the trigger on close
- **Color Contrast**: Text on background must meet contrast ratios — 4.5:1 for normal text, 3:1 for large text (AA). Check with browser DevTools, Figma plugins, or automated tools. Don't rely on color alone to convey information (use icons or labels too)
- **Images**: Informational images need `alt` text describing their content. Decorative images use `alt=""` (empty) so screen readers skip them. Never use `alt="image"` — it provides no information
- **Forms**: Every input needs a visible label associated via `for`/`id` or wrapping `<label>`. Error messages must describe what went wrong and how to fix it. Required fields must be indicated. Don't rely on placeholder text as a label — it disappears on focus
- **Testing Tools**:
  - *Automated*: axe-core (integrates with Testing Library, Playwright), Lighthouse accessibility audit, ESLint jsx-a11y plugin
  - *Manual*: Keyboard navigation test, screen reader test (NVDA + Firefox, VoiceOver + Safari, JAWS + Chrome)
  - Automated tools catch ~30-40% of accessibility issues; manual testing is required for full coverage
- **Headless UI Libraries**: Radix UI, Headless UI, Ark UI provide unstyled, accessible component primitives (dialogs, dropdowns, comboboxes) with keyboard interaction and ARIA already implemented correctly. Building accessible dialogs and comboboxes from scratch is complex — use these

## In Practice
Method applications target WCAG 2.1 AA compliance. ESLint jsx-a11y plugin runs in CI. axe-core runs in Playwright E2E tests. Radix UI provides accessible primitives for complex components (modals, dropdowns, tooltips). Color contrast is checked in design review before implementation. Keyboard navigation is tested manually on all critical user flows before release.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Accessibility**: Semantic HTML does 80% of the accessibility work for free — use `<button>` not `<div onClick>`, use heading hierarchy correctly, and use landmark elements. Automated tools (axe-core) catch only ~30-40% of issues; test with a keyboard and a screen reader before considering a flow accessible. For complex interactive components (modals, comboboxes, date pickers), use Radix UI or Headless UI — building accessible keyboard interaction patterns correctly from scratch is weeks of work. ARIA is not a substitute for bad HTML; the first rule of ARIA is "don't use ARIA if native HTML can do the job." → `engineering-knowledge-repository/accessibility.md`

## Related Entries
- [CSS Architecture](css-architecture.md) — CSS choices affect focus indicators, color contrast, and visual accessibility
- [Frontend Testing](frontend-testing.md) — axe-core integration in Testing Library and Playwright enables automated accessibility testing
- [Design Tokens](design-tokens.md) — color contrast ratios and accessible color palettes are defined in the design token system
- [Component Architecture](component-architecture.md) — accessible component design begins with semantic HTML and ARIA in the component definition
