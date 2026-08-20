---
id: memento
tags: [pattern, backend]
surfaces-at: [functional-design, code-generation]
related: [command-pattern, prototype, event-sourcing]
complexity: intermediate
---

# Memento Pattern

## What It Is
A behavioral pattern that captures and externalizes an object's internal state so that the object can be restored to this state later — without violating encapsulation. The originator creates a memento snapshot of its state; a caretaker stores and retrieves mementos; the originator restores itself from a memento when needed.

## When to Apply
- Implementing undo/redo functionality (text editors, drawing applications, form wizards)
- State snapshots before a risky operation — roll back if the operation fails
- Saving and restoring application state (game save points, document autosave)
- When an object's internal state must be saved externally but without exposing private implementation details

## When Not to Apply
- When the state is large — copying the full state for every snapshot is memory-intensive (consider incremental snapshotting or Event Sourcing instead)
- When the originator's state changes frequently — snapshot overhead accumulates
- Simple state that can be represented as a plain value object without the pattern's ceremony

## Key Concepts
- **Originator**: The object whose state is being saved — creates a Memento containing a snapshot of its current state and can restore itself from a Memento
- **Memento**: Stores the internal state of the Originator — opaque to all objects except the Originator (encapsulation preserved)
- **Caretaker**: Holds mementos but never examines or modifies them — manages the undo stack
- **Encapsulation Preservation**: The Memento exposes state only to the Originator — the Caretaker holds it as an opaque object
- **Event Sourcing vs. Memento**: Event Sourcing is Memento at architectural scale — the event log is an append-only sequence of state snapshots

## In Practice
Memento is the classic undo/redo pattern. In modern frameworks, state management libraries (Redux, Vuex) implement a form of Memento — every state transition produces an immutable snapshot, and time-travel debugging replays or restores previous states. In domain models, Memento appears in workflow engines (save the state before executing a step; roll back if it fails) and form wizards (back/next navigation with state preservation).

## Engineering Knowledge
💡 **Engineering Knowledge — Memento Pattern**: Want undo/redo? Memento captures an object's state as a snapshot without breaking encapsulation — only the object itself knows how to interpret its memento. The caretaker holds the stack of snapshots but can't peek inside. Redux's immutable state snapshots and time-travel debugging are Memento at the framework level. For large objects, consider incremental snapshots or Event Sourcing instead of full copies. → `engineering-knowledge-repository/design-patterns/memento.md`

## Related Entries
- [Command Pattern](command-pattern.md) — Commands + Mementos together implement undo: Command executes, Memento captures state for reversal
- [Event Sourcing](../data/event-sourcing.md) — Event Sourcing is Memento at architectural scale — the event log is the persistent snapshot history
- [Prototype Pattern](prototype.md) — Prototype clones objects; Memento captures state for later restoration
