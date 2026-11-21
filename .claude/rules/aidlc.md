<!--
  .claude/rules/aidlc.md — the AIDLC method @-import stub (NOT a copy).

  The AIDLC method (the layered practice files: org/team/project + phase rules)
  is authored ONCE at the workspace root under aidlc/spaces/default/memory/ —
  the single hand-editable source of truth, identical on every harness. This
  file is a REFERENCE, not a copy: it pulls that method into Claude's ambient
  context via @-imports so casual chat (outside an AIDLC stage) sees the
  standing practices. AIDLC's own stage resolver reads the same tree directly
  (it never needs this stub).

  Claude @-imports name an EXPLICIT file each (no glob support — verified
  against code.claude.com/docs memory.md), resolve relative paths from THIS
  file's location, and follow a nested chain up to four hops. From
  .claude/rules/ the workspace root is ../../, so the method tree is
  ../../aidlc/spaces/default/memory/. The @-lines below ship pointed at the
  always-present `default` space; this file stays committed (it carries this
  load-bearing wiring beyond the pointer), and `/aidlc space <name>` re-points
  these @-lines IN PLACE so the next turn's ambient context follows the active
  space. At `default` the re-point is a byte-identical no-op. (AIDLC's own stage
  resolver follows the active-space cursor directly and never needs this stub.)

  Edit the METHOD at aidlc/spaces/default/memory/*, never here.

  TRIMMED (B255, 2026-11-20, owner: "sure"): only team.md (the TDD posture) and
  project.md (the lab's own corrections) load into every session. org.md (framework
  defaults, ~4.3k tokens) and the four phases/*.md (~1.6k) were dropped from the
  ambient import: an /aidlc run still gets every method file, because the engine
  delivers them as rules_content in its load-steering directives, and nothing else
  needs them in casual chat. The re-point above rewrites whichever @-lines exist, so a
  shorter list is safe. To restore one, add its @-line back; the measurement is in
  docs/concepts/context-engineering.md.
-->

@../../aidlc/spaces/default/memory/team.md
@../../aidlc/spaces/default/memory/project.md
