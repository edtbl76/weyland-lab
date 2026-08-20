---
id: snapshot-testing
tags: [methodology, testing]
surfaces-at: [code-generation]
related: [end-to-end-testing, test-doubles, shift-left-testing]
complexity: foundational
---

# Snapshot Testing

## What It Is
A testing technique that captures the rendered output of a component or function as a serialized "snapshot" file and compares future test runs against it. If the output changes, the test fails — requiring an explicit update to the snapshot. Popularized by Jest for React component testing. Useful for preventing unintentional UI regressions but prone to over-acceptance if teams reflexively update snapshots without review.

## When to Apply
- React/Vue/Angular component output that changes infrequently and where visual regressions are undesirable
- Serialized data structures where exact format matters (API response shape, configuration objects)
- Auto-generated code or documentation that should not change unexpectedly

## When Not to Apply
- Dynamic content with timestamps, IDs, or random values — snapshots will always fail without masking
- Components under active development — snapshot failures become noise and teams start ignoring them
- As a replacement for meaningful behavioral assertions — snapshots test structure, not behavior

## Key Concepts
- **Snapshot File**: A `.snap` file committed to version control containing the serialized expected output. Acts as a specification at a point in time
- **Jest Snapshot Testing**: `expect(component).toMatchSnapshot()` — Jest creates or compares the `.snap` file automatically
- **Snapshot Update**: When output intentionally changes, `jest --updateSnapshot` refreshes the file. Teams must review what changed before updating — mindless updates eliminate the test's value
- **Inline Snapshots**: `toMatchInlineSnapshot()` — embeds the snapshot directly in the test file. Better for small outputs; avoids proliferating `.snap` files
- **Visual Regression Testing**: Pixel-level screenshot comparison — Chromatic, Percy, Playwright visual comparisons. A higher-fidelity form of snapshot testing for visual UI
- **Serializer Customization**: Jest allows custom serializers — control how components or objects are serialized to make snapshots more readable and less brittle

## In Practice
Method uses snapshot tests sparingly — for stable UI components and serialized data structures. The primary risk is snapshot approval becoming a rubber-stamp. Team discipline is required: review snapshot diffs carefully in code review. For visual regression at the pixel level, Chromatic is used in Storybook-based component library workflows.

## Engineering Knowledge
💡 **Engineering Knowledge — Snapshot Testing**: Snapshots capture "what was" and alert you when it changes. Useful for stable components and serialized structures. The failure mode: teams blindly run `--updateSnapshot` without reviewing changes, turning the test into a formality. Always review snapshot diffs in code review. Avoid snapshots for frequently changing components — they generate noise and get ignored. For true visual regression, use Chromatic or Playwright screenshot comparisons over Jest snapshots. → `engineering-knowledge-repository/testing/snapshot-testing.md`

## Related Entries
- [End-to-End Testing](end-to-end-testing.md) — E2E visual tests provide higher-fidelity regression detection
- [Test Doubles](test-doubles.md) — clean component isolation makes snapshots more stable
- [Shift-Left Testing](shift-left-testing.md) — snapshot tests live in the unit/component layer of the test pyramid
