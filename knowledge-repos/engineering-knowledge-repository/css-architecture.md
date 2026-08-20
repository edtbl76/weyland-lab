---
id: css-architecture
tags: [pattern, frontend]
surfaces-at: [application-design, functional-design]
related: [component-architecture, design-tokens, accessibility, frontend-build-tooling]
complexity: intermediate
---

# CSS Architecture

## What It Is
The methodology for organizing, writing, and maintaining CSS at scale — ensuring styles are predictable, scoped, maintainable, and consistent. CSS has no inherent encapsulation: a class defined anywhere can affect elements anywhere. Without intentional architecture, CSS devolves into specificity wars, global namespace pollution, and styles that can't be safely changed. Modern approaches (Tailwind, CSS Modules, CSS-in-JS) each solve the scoping problem differently, with different tradeoffs around developer experience, runtime performance, and design consistency.

## When to Apply
- Every frontend project with more than trivial styling
- When establishing a new project (architecture choice affects all future CSS)
- When an existing codebase has CSS specificity issues or style conflicts
- When building a component library or design system

## Key Concepts
- **Tailwind CSS**: Utility-first CSS framework. Compose styles from predefined utility classes (`flex`, `gap-4`, `text-sm`, `rounded-lg`) directly in JSX/HTML. No custom CSS written; styles extracted to a minimal CSS bundle via PurgeCSS. Growing rapidly; dominant in new React projects
  - Pros: No context switching, no class naming, no specificity issues, design tokens built in
  - Cons: Verbose markup, requires learning utility vocabulary, harder to extract reusable style patterns
  - Use with design tokens (custom Tailwind config) for consistent spacing and color
- **CSS Modules**: CSS files where class names are locally scoped by default via a hash transformation. `styles.button` in `Button.module.css` becomes `.Button_button__abc123` in the output. No global namespace collision; styles colocated with components
  - Pros: Local scoping, standard CSS, works with any framework
  - Cons: Dynamic styling is verbose; no design token integration out of the box
- **CSS-in-JS** (styled-components, Emotion): Write CSS as JavaScript template literals; styles are scoped to components; supports dynamic styles based on props. Runtime cost for style generation; large bundle size. Less favored in new projects since Tailwind emerged. Still viable for design-system-heavy, theme-switching use cases
- **Vanilla Extract**: CSS-in-JS with zero runtime — styles are extracted to static CSS at build time. TypeScript-native. Excellent for design systems requiring type-safe design tokens. More complex setup
- **BEM (Block Element Modifier)**: A naming convention for global CSS (`block__element--modifier`). Reduces conflicts without tooling; verbose; replaced by scoped CSS in component-based frameworks. Still common in server-rendered non-component applications
- **Design Tokens Integration**: Colors, spacing, typography, and shadows should come from design tokens, not hardcoded values. In Tailwind: custom `tailwind.config.js` with brand tokens. In CSS Modules/vanilla CSS: CSS custom properties (CSS variables). This is what connects developer implementation to the design system
- **Global vs. Component Styles**:
  - Global: CSS reset/normalize, base typography, CSS custom properties (design tokens). Keep minimal
  - Component: All component-specific styles scoped to the component. Never bleed globally
- **Dark Mode**: Implement via CSS custom properties switched with a `data-theme` attribute, or Tailwind's `dark:` prefix. Avoid duplicating all styles for dark mode — use token substitution

## In Practice
Method new projects use Tailwind CSS with a custom configuration file defining the client's brand tokens (colors, spacing scale, typography). CSS Modules are used for complex, stateful component styles that would be verbose in Tailwind. Global styles are limited to CSS reset, base font, and CSS custom property definitions. All color and spacing values come from the design token system rather than hardcoded values.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — CSS Architecture**: Choose one scoping strategy and commit to it — mixing global CSS, CSS Modules, and styled-components in the same project creates a maintenance nightmare. Tailwind is the pragmatic choice for most new React projects: no class naming decisions, no specificity issues, and the utility constraints promote design consistency. Whatever approach you choose, connect styles to design tokens (Tailwind config or CSS custom properties) — hardcoded hex values and magic spacing numbers are technical debt from day one. → `engineering-knowledge-repository/css-architecture.md`

## Related Entries
- [Component Architecture](component-architecture.md) — CSS scoping strategy is part of component design; colocation of styles with components is the goal
- [Design Tokens](design-tokens.md) — CSS architecture should always reference design tokens for colors, spacing, and typography
- [Accessibility](accessibility.md) — CSS choices affect focus indicators, color contrast, and screen reader behavior
- [Frontend Build Tooling](frontend-build-tooling.md) — bundlers process CSS modules, extract Tailwind utilities, and handle style optimization
