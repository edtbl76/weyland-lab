# Kindle library → RAG — extraction feasibility spike (B165)

> B165's **Stage-1 extraction spike** (2026-09-15). B165 wants the owner's personal Kindle library as a
> knowledge-management RAG corpus (chunk → bge-base embed → Qdrant/Weaviate → KM query surface — all existing
> infra, [[b113-finance-filings-rag]] / [[b74-retrieval-precision]] / [[vector-store-hydration-b1]]). The build
> is ~90% reuse; the **only** real risk is extraction — getting readable text out of DRM-wrapped Kindle books.
> **Personal use, LAN-only, $0 — the owner's own purchased books.** This doc is the spike's verdict: which of the
> three extraction routes are viable *for this account/hardware*, proven against the real device, not assumed.

## TL;DR

**Feasible, but extraction is genuinely the hard part — the cheap routes are dead, the working route needs a
Windows VM.** Proven on the real hardware:

| Route | Verdict | Evidence |
|-------|---------|----------|
| **(a) Full text — on-device / serial de-DRM** | **DEAD END** | The book copies off the device fine, but its KFX is a **DRMION container without an on-device DRM voucher** — the decryption key lives in the Kindle *app*, not the device serial. Newest $0 tools (Calibre 7.6 + DeDRM 10.0.5 + KFX Input 2.34.2) confirm it cannot be decrypted from the copied file. |
| **(a) Full text — Kindle-for-PC key route** | **VIABLE, effortful** | DeDRM's own fallback tries to pull the key from a Kindle-for-PC install (under wine it failed only because none is set up). A **Windows VM + Kindle-for-PC** holds the voucher DeDRM needs. This is the reliable 2026 route. |
| **(b) Highlights / notes** | **VIABLE, partial + manual** | `read.amazon.com/notebook` — no bulk export, manual copy-paste per book, per-publisher clipping caps. `My Clippings.txt` (the clean bulk pull) is **not populated** on this device. |
| **(c) Personal docs** | Trivial if any exist | Sideloaded/Send-to-Kindle files are unprotected; device `documents/` root held none. |

## What the spike actually did (live, on rogueone)

1. **Hardware reality-check.** The owner's "Kindle" turned out to be two devices. A **Fire tablet** (`Amazon_Fire_G001MG…`)
   — dead end: Kindle content lives in Android app-private storage, not exposed over MTP. And a **Kindle Paperwhite
   Signature Edition** (`…GN43H805430402NE`, an e-ink reader, Lab126) — the real candidate. Both connect over **MTP**
   (not USB mass-storage), mounting under gvfs.
2. **On-device inventory.** The Paperwhite's MTP tree exposed `Internal Storage/documents/` but — before a real book
   was downloaded — held only preloaded Oxford dictionaries and **no `My Clippings.txt`** (that file isn't maintained
   for Amazon-delivered content on current firmware; highlights sync to the cloud instead).
3. **Registered the device + downloaded one book.** The Paperwhite had been the late owner's mother's; factory-reset,
   re-registered to the owner's account, one book downloaded (`A Philosophy of Software Design, 2nd Edition_B09B8LFKQL`).
   It **did** land MTP-visible at `documents/Downloads/Items01/…kfx` (310 KB) — so on-device books ARE reachable here,
   correcting an earlier assumption that current firmware hides them.
4. **Strip test.** Copied the `.kfx` to rogueone; installed **Calibre 7.6** + **DeDRM plugin** (v10.0.3, then the
   Satsuoni fork build v10.0.5) + **KFX Input** (2.34.2); seeded the device serial. Convert → **"This book has DRM."**
5. **Read the real reason** (DeDRM debug, not the popup):
   ```
   DeDRM v10.0.5: Failed to decrypt with error:
     The .kfx-zip archive contains an encrypted DRMION file without a DRM voucher
   ```
   DeDRM then tried its Kindle-for-PC-under-wine key fallback and failed (`wine C:\Python27\python.exe does not exist`)
   — i.e. the tool itself points at the Kindle-app key as the working path.

## Why the on-device route is structurally dead (not a tooling gap)

Modern KFX wraps the book as a **DRMION** whose content key is sealed in a **voucher** that is delivered to and held
by the Kindle *app/account*, not written into the copy sitting on the e-ink device. The eInk-serial de-DRM method
(which worked for older AZW/KFX) has the locked container but no voucher, so **no version of DeDRM can open the
copied-off file** — confirmed against the newest $0 toolchain. This matches the 2026 landscape: the reliable route is
Kindle-for-PC on Windows, where the app produces/holds the voucher.

## Routes forward (for the B165 *build*, gated behind this spike)

- **Full text (a):** a **Windows VM** (Proxmox + vTPM — the owner can build one) running **Kindle-for-PC**, downloading
  books through the app so the voucher/key is derivable, then DeDRM strips them. Effort: build VM, install + version-pin
  Kindle-for-PC, wire DeDRM to the app key. Yield: the books the app will deliver — richest for pre-April-2025 titles.
  A cheaper thing to check *first*: whether the account still offers **"Download & transfer via USB"** on Manage Your
  Content and Devices (Amazon removed it for many accounts in Feb 2025) — if present it may deliver a serial-strippable
  copy and sidestep the VM.
- **Highlights (b):** `read.amazon.com/notebook` (manual/capped) or a Readwise-style sync — the reliable-but-partial floor.
- **Corpus honesty:** realistically **highlights + whatever the VM route recovers**, not "all the text effortlessly."

## $0 / legality lens

The owner's own purchased books, personal LAN-only KM use, no redistribution — format-shifting owned content.
Highlights (b) and personal docs (c) involve no DRM circumvention at all and are the guaranteed-clean floor.

## Toolchain installed on rogueone (this spike)

`calibre` 7.6.0 (apt) + Calibre plugins **DeDRM** (10.0.5, Satsuoni fork) and **KFX Input** (2.34.2, via Calibre's
plugin index). `wine` was already present. Captured in the machine-inventory SoT (`calibre` → `system`); Calibre
plugins are app-internal, not OS packages, so they are not in the collector's scope — noted here instead. See
[[b129-machine-inventory-catalog]] and **B170** (the follow-on that makes host-install → Port catalog a tracked step).

Relates **B165** (this spike's parent), **B113/B74/B96** (RAG + retrieval + eval infra the build reuses), **B1**
(vector stores).
