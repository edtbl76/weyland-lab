---
id: machine-onboarding
title: The machine onboarding
category: Operations
description: Bring a new host into the machine inventory and the Port catalog by running the onboarding checklist, step by step, each with its pass/fail gate.
terminal_condition: machine_inventory.py verify <host> prints "verify <host> OK" (exit 0), or a step tagged [operator] or [decision] is reached (stop and hand the owner that exact step).
source: docs/runbooks/machine-inventory.md (Onboarding a new machine (B169))
---

## Prompt

Onboard host {{host}} (SSH user {{user}}) into the machine inventory.

Follow `docs/runbooks/machine-inventory.md` § "Onboarding a new machine" in order, steps 0 to 4. Each step has a
gate; a step whose gate is not met stops the process. Never assume a pass.

1. Step 0, preflight: the host is a hostname, not an IP; SSH key auth works with BatchMode; the Port credentials
   file exists. A failed check is not a pass.
2. Step 1 is [operator]: if SSH key auth failed, stop and hand the owner `ssh-copy-id {{user}}@{{host}}`, then re-run
   preflight when they say it is done.
3. Step 2: collect and merge. Read the `sources:` line and the new/unreviewed counts.
4. Step 3 is [decision]: pre-triage the obvious platform runtimes as keep, then hand the owner only the genuine
   per-app calls.
5. Step 4: emit, then verify. Emit's own success is not proof; only verify is.

Stop when the terminal condition holds. Report each step's gate result.
