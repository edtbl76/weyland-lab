---
id: design-tokens
tags: [pattern, frontend, methodology]
surfaces-at: [application-design, functional-design]
related: [css-architecture, component-architecture, accessibility, micro-frontends]
complexity: foundational
---

# Design Tokens

## What It Is
Named, stored design decisions — colors, spacing, typography, border radii, shadows, motion durations — expressed as platform-agnostic key-value pairs that serve as the single source of truth between design and engineering. Instead of `color: #0057FF` scattered across CSS files or Figma frames, the value lives once as `color-brand-primary: #0057FF` and is referenced by name everywhere. Design tokens make design decisions explicit, consistent, and changeable: updating a token propagates the change across all components, all platforms, and all themes simultaneously.

## When to Apply
- Any application with a design system or brand standards
- Projects where design and engineering must stay in sync on visual values
- Multi-platform products (web + mobile) sharing the same brand
- Applications requiring theming or dark mode support
- Consulting engagements where client brand guidelines must be implemented consistently

## Key Concepts
- **Token Categories**:
  - *Color*: Brand palette, semantic colors (success, warning, error, info), surface colors, text colors
  - *Typography*: Font families, font sizes, line heights, font weights, letter spacing
  - *Spacing*: A consistent scale (4, 8, 12, 16, 24, 32, 48, 64px) for margin, padding, and gaps
  - *Border*: Border radii, border widths
  - *Shadow*: Elevation levels (shadow-sm, shadow-md, shadow-lg)
  - *Motion*: Duration (fast, normal, slow) and easing curves for animations
- **Semantic vs. Primitive Tokens**:
  - *Primitive*: Raw values — `blue-500: #0057FF`
  - *Semantic*: Named by usage — `color-action-primary: {blue-500}`. Semantic tokens reference primitive tokens. This indirection enables theming: swap `color-action-primary` to `green-600` for a white-label client without changing component code
- **Token Formats**:
  - *CSS Custom Properties*: `--color-brand-primary: #0057FF`. The universal delivery format for web
  - *Tailwind config*: Token values mapped to Tailwind theme keys in `tailwind.config.js`
  - *JSON/YAML*: Source of truth format, transformed to CSS/JS/Swift/Kotlin for different platforms
- **W3C Design Tokens Format**: An emerging standard for a common JSON token format. Supported by Style Dictionary, Theo, and Figma Token Studio
- **Style Dictionary**: Amazon's open-source tool for transforming design tokens from a JSON source format into any output format (CSS variables, SCSS, JavaScript objects, iOS Swift, Android XML). The standard for multi-platform token pipelines
- **Figma to Code**: Token Studio for Figma stores tokens in Figma and syncs to a GitHub repository in JSON format. Design changes push token updates via PR. Engineering reviews and merges the PR — no manual copy-paste of color values
- **Theming**: Multiple token sets (light/dark, brand-A/brand-B) that switch by applying a different CSS custom property scope. Dark mode: swap surface and text tokens at the `[data-theme="dark"]` level. White-label: swap brand tokens per client
- **Naming Conventions**: Names should describe purpose, not value. `--color-text-muted` is better than `--color-gray-400` — the value can change; the purpose stays the same

## In Practice
Method maintains design tokens in JSON (W3C format) in the project repository. Style Dictionary transforms tokens to CSS custom properties, Tailwind config, and Figma Token Studio format. Figma designs reference the same token names as CSS. Dark mode and white-label theming use semantic token overrides. Spacing and typography tokens enforce a consistent visual rhythm across all components.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Design Tokens**: Don't hardcode color values, font sizes, or spacing values directly in CSS or components — they are design decisions that belong in tokens. The key insight is semantic tokens: name tokens by purpose (`color-text-primary`) not by value (`color-gray-900`) so that theme changes require updating one place, not hundreds. Use Style Dictionary to transform a single JSON token source into CSS variables, Tailwind config, and mobile outputs simultaneously. Connect Figma to your token repo via Token Studio — design changes become PRs, not Slack messages. → `engineering-knowledge-repository/design-tokens.md`

## Related Entries
- [CSS Architecture](css-architecture.md) — design tokens are delivered via CSS custom properties and integrated into CSS architecture approaches
- [Component Architecture](component-architecture.md) — components reference design tokens for consistent visual language
- [Accessibility](accessibility.md) — color contrast ratios and accessible color palettes are enforced at the token level
- [Micro-Frontends](micro-frontends.md) — design tokens provide the shared visual contract across independently deployed micro-frontends
