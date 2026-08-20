---
id: interpreter
tags: [pattern, backend]
surfaces-at: [functional-design, code-generation]
related: [composite, visitor, strategy-pattern]
complexity: advanced
---

# Interpreter Pattern

## What It Is
A behavioral pattern that defines a grammar for a simple language and provides an interpreter to deal with that grammar. Each grammar rule is represented as a class; the interpreter builds an abstract syntax tree (AST) from the input and evaluates it. Primarily used for domain-specific languages (DSLs), expression evaluation, and query parsing.

## When to Apply
- Implementing a simple language or grammar whose sentences can be represented as an AST
- When recurring problems can be expressed as sentences in a simple language (filtering rules, expression evaluation, configuration DSLs)
- SQL-like query languages, math expression evaluators, rule engines, regex-like pattern matchers, command interpreters
- When the grammar is simple and performance is not a primary concern

## When Not to Apply
- Complex grammars — the pattern produces large class hierarchies (one class per grammar rule); use a parser generator (ANTLR, PEG.js) instead
- Performance-critical expression evaluation — interpreted AST traversal is slower than compiled alternatives
- When an off-the-shelf DSL (Groovy, Lua, JEXL) satisfies the need — implement from scratch only when embeddability or full control is required

## Key Concepts
- **Abstract Expression**: The interface with an `interpret(context)` method
- **Terminal Expression**: Implements interpretation for the base elements of the grammar (literals, variables)
- **Non-Terminal Expression**: Implements interpretation for grammar rules that combine other expressions (operators, conditionals)
- **Context**: Stores global information used during interpretation (variable values, state)
- **Abstract Syntax Tree (AST)**: The tree of expression objects representing a parsed sentence — interpretation is a tree traversal
- **Composite Relationship**: Interpreter is a specialized application of Composite — non-terminal expressions are composites of sub-expressions

## In Practice
Interpreter is less frequently used than other GoF patterns in enterprise software, but it's the foundation of expression engines and rule systems. In Method engagements, the pattern appears in business rule engines (evaluate discount eligibility rules), filter expression parsers (search query DSLs), and configuration DSLs where simple logic must be user-configurable. For anything beyond simple grammars, use ANTLR or a parser combinator library instead.

## Engineering Knowledge
💡 **Engineering Knowledge — Interpreter Pattern**: Building a small DSL, expression evaluator, or rule engine? Interpreter maps grammar rules to classes and evaluates an AST. Good for simple languages (filter rules, math expressions, config DSLs). For anything complex, use ANTLR or a parser combinator library — the class-per-rule approach becomes unwieldy fast. Interpreter is structurally a Composite: non-terminal expressions compose terminal ones. → `engineering-knowledge-repository/design-patterns/interpreter.md`

## Related Entries
- [Composite Pattern](composite.md) — Interpreter is a specialized Composite — AST nodes are composites of sub-expressions
- [Visitor Pattern](visitor.md) — Visitor is the natural partner for applying operations (evaluation, printing) to an Interpreter's AST
