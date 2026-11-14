# Don't adopt Linear's coding Agent or its self-hosted variants (Cyrus)

## Status

accepted

Date: 2026-09-25

## Context and Problem Statement

Linear offers an Agent that turns a delegated issue into a coding session and a PR. Self-hosted variants such as Cyrus run Claude Code on your own machine.

## Decision Drivers

* $0.
* Self-hosted, with no new ingress into the LAN.
* No duplicate of the local Claude Code workflow the lab already runs.

## Considered Options

* Don't adopt; invest in portable skills instead
* Linear's cloud Agent
* Cyrus (self-hosted, BYOK)

## Decision Outcome

Chosen option: Don't adopt either, because the cloud Agent is paid and runs off the LAN, and Cyrus fixes cost and location but still duplicates the local workflow and would need Linear's webhooks to reach into the LAN.

### Consequences

* Good, because skills stay portable: git is their source of truth and Bifrost serves them.
* Bad, because issue-to-PR delegation from inside Linear is not available.

## More Information

Verdict table: [linear-evaluation.md](../concepts/linear-evaluation.md) (Agent + Skills row). The unattended path is Emdash (B179, [software-factory.md](../runbooks/software-factory.md)).
