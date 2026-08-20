---
id: component-architecture
tags: [pattern, frontend]
surfaces-at: [application-design, functional-design]
related: [state-management, micro-frontends, design-tokens, css-architecture, frontend-testing]
complexity: intermediate
---

# Component Architecture

## What It Is
The structural patterns for organizing, composing, and designing UI components in frameworks like React, Vue, and Angular. Good component architecture produces components that are reusable, testable, and have clear responsibilities. Poor architecture produces "god components" with hundreds of lines mixing data fetching, business logic, and rendering — making them hard to test, reuse, or change without side effects. Component architecture decisions affect the entire maintainability of the frontend codebase.

## When to Apply
- Starting a new frontend project or component library
- Refactoring components that have grown too complex
- Building a design system or shared component library
- Any component that will be reused across multiple pages or applications

## Key Concepts
- **Presentational vs. Container Components** (Smart/Dumb):
  - *Presentational (Dumb)*: Receive data and callbacks via props; render UI only. No data fetching, no side effects. Highly reusable; easy to test (pure rendering)
  - *Container (Smart)*: Fetch data, hold state, contain business logic. Pass data to presentational components. One container orchestrates multiple presentational components
  - In practice with hooks: The strict split is less relevant; hooks allow logic extraction from any component. The principle still applies — separate concerns
- **Component Composition**: Prefer composition over configuration. Instead of a `Button` component with 20 boolean props (`hasIcon`, `hasSpinner`, `isOutlined`), use compound components or render props that let consumers compose behavior:
  ```jsx
  <Button><Icon /> Submit</Button>  // composition
  vs.
  <Button hasIcon iconName="send" isLoading={false} />  // configuration hell
  ```
- **Compound Components**: Components that work together through shared context — `<Select>`, `<Select.Option>`, `<Select.Trigger>` share state implicitly. Common in design system components (Radix UI, Headless UI)
- **Single Responsibility**: Each component should do one thing. A `UserProfileCard` that fetches the user, formats the date, renders the avatar, and handles the follow action is doing four things. Split it
- **Component Granularity**:
  - Too coarse: One component for an entire page. Hard to test, hard to reuse
  - Too fine: Every text span is a component. Overhead without benefit
  - Rule of thumb: If you're copy-pasting JSX between components, extract it. If a component exceeds ~200 lines, consider splitting
- **Custom Hooks for Logic Extraction**: Extract stateful logic from components into custom hooks (`useFormValidation`, `useWindowSize`, `useDebounce`). Components become thinner; logic becomes testable in isolation
- **Colocation**: Keep related files together — `Button/Button.tsx`, `Button/Button.test.tsx`, `Button/Button.stories.tsx`, `Button/index.ts`. Makes components easy to find, move, and delete
- **Prop Interface Design**: Define explicit prop types. Use defaults for optional props. Avoid prop spreading (`<Component {...props} />`) beyond the immediate element — it obscures what a component accepts. Avoid boolean props that control fundamentally different visual states; use a `variant` prop instead
- **Design System Components**: Foundational components (Button, Input, Modal, Table) live in a shared design system. Application-specific components are built from design system primitives. This enforces consistency and reduces duplication

## In Practice
Method React projects follow a component directory structure with colocated tests and stories. Presentational components are stateless and receive all data via props. Custom hooks contain data fetching (via TanStack Query) and business logic. Design system components from the project's component library are used for all UI primitives — never bespoke button implementations. Components are documented and tested with Storybook and Vitest.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Component Architecture**: Extract logic into hooks before splitting components — a 300-line component with a 50-line render and 250 lines of hooks is well-structured; a 300-line render function is not. Prefer composition over prop proliferation — a component with 20 boolean props is a sign of missing abstraction. Colocate component files (test, stories, styles) for discoverability. Keep presentational components free of data fetching — they become trivially testable and trivially reusable. → `engineering-knowledge-repository/component-architecture.md`

## Related Entries
- [State Management](state-management.md) — component architecture decisions determine where state lives and how it flows
- [Micro-Frontends](micro-frontends.md) — component architecture scales to micro-frontend patterns for large teams
- [Design Tokens](design-tokens.md) — design tokens feed into component styling for consistent cross-component visual language
- [CSS Architecture](css-architecture.md) — component styling architecture is part of overall component design
- [Frontend Testing](frontend-testing.md) — well-structured components with clear props are far easier to unit and integration test
