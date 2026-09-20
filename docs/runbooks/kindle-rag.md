# Runbook — Kindle library → KM RAG (B165)

Ingest the owner's **own purchased** Kindle library as a knowledge-management RAG corpus. Personal use, LAN-only,
$0. Two halves with a deliberate split of labour:

- **Extraction (this runbook, § "The Windows VM"):** DRM-stripped EPUB/TXT out of Kindle. Runs in a **throwaway
  Windows VM on rogueone** because the working route needs Kindle-for-PC (Windows), your Amazon login, and the
  Calibre GUI. **"Log in once, script the rest":** you build the VM, log into Kindle-for-PC once and let it sync,
  then a script does the batch decrypt + upload. Grounded in the extraction spike
  ([concepts/kindle-rag-eval.md](../concepts/kindle-rag-eval.md)) — read it; it proves why the cheap on-device
  route is a dead end and this VM route is the reliable one.
- **Ingestion + query (the cluster half):** extracted files land in MinIO `kindle-corpus`; the weyland-dagster
  pipeline chunks → bge-base embeds → writes a `kindle` Qdrant/Weaviate collection; query via the operator/MCP,
  graded against a golden set. All existing infra — see the demo.

## Step 0 — the cheaper pre-check (may skip the whole VM)

Before building anything, check **Manage Your Content and Devices → Preferences → whether "Download & transfer
via USB" is offered** for your account. Amazon removed it for many accounts in Feb 2025; **if it's still there** it
delivers an older AZW that the on-device/serial de-DRM path may strip directly (no VM). If it's gone (the common
2026 case), continue to the VM.

## The Windows VM — fully automated ("log in once, script the rest")

The whole VM is provisioned unattended by one script; **your only action is signing into Kindle-for-PC.** The VM
**persists** (stopped between uses), so later runs for new books are zero-touch — Kindle stays signed in.

### One-time prerequisites (first run only — setup, not extraction work)

1. VM tooling on rogueone: `sudo apt install -y virtinst genisoimage libvirt-daemon-system` (rogueone already has
   `virsh`/`qemu`/`swtpm`).
2. The free **Windows 11 Enterprise Evaluation** ISO (Microsoft gates it behind a browser) — download from
   <https://www.microsoft.com/en-us/evalcenter/download-windows-11-enterprise> and save to `~/kindle-vm/Win11_Eval.iso`
   (or point `KINDLE_WIN_ISO` at it). 90-day eval, no license — the VM is throwaway.
3. MinIO S3 creds in `scripts/.env`: `KINDLE_MINIO_ACCESS_KEY` / `KINDLE_MINIO_SECRET_KEY` (an S3 key that can write
   the `kindle-corpus` bucket; endpoint defaults to the LAN NodePort `http://192.168.1.243:30990`).

### Provision + extract (the whole flow)

```
bash nodes/rogueone/kindle/provision-kindle-vm.sh
```

That builds the config ISO (autounattend + the scripts + injected MinIO creds) and creates the VM. Then, unattended:
Windows installs with no clicks → `kindle-vm-setup.ps1` self-installs **Kindle-for-PC + Calibre + DeDRM + KFX Input**
(KFX Input is fetched from Calibre's plugin index, not the GUI) **+ `mc`** and wires the MinIO alias → it registers
the **auto-extract watcher** (`kindle-autorun.ps1`) and opens Kindle-for-PC.

**Your one step:** in the Kindle-for-PC window that opens, **sign into Amazon** (2FA — the one thing that can't be
scripted). Watch the desktop with `virt-viewer --connect qemu:///session kindle-extract`. After you sign in, the
library syncs, the watcher detects the download finished, and `kindle-extract.ps1` runs on its own — `calibredb add`
imports each book (**DeDRM strips DRM on import**, Calibre's documented batch path), exports EPUB + TXT, and
`mc mirror`s them to MinIO `kindle-corpus/`. The cluster's dagster `kindle` assets ingest from there.

### On-demand later (new books) — zero-touch

```
bash nodes/rogueone/kindle/provision-kindle-vm.sh --rerun
```

Starts the persisted VM; Kindle-for-PC is still signed in, so it re-syncs and the watcher re-extracts — **no login,
no clicks.** (Only if the 90-day eval lapses do you re-provision, which re-logs-in once.)

### The book #1 gate — prove ONE decrypt before trusting the batch

The spike confirmed the **route** but not the full decrypt on **your** account, and the Windows automation is
untested by the author. So on the **first** run, before syncing the whole shelf: keep just one book in the library
(or run `kindle-extract.ps1 -Only "<title>" -DryRun` from the VM) and confirm the exported `.txt` is **real readable
text**. If instead the log shows `This book has DRM` / `encrypted DRMION file without a DRM voucher`, **stop** — the
app isn't signed in, KFX Input didn't install (check `C:\kindle\setup.log` — do the one GUI step it names), or the
Kindle-for-PC version doesn't hold the voucher. A failed decrypt on book #1 is a cheap lesson; a failed batch is not.

### Logs (if the automation stalls — it's untested here)

Inside the VM: `C:\kindle\setup.log` (toolchain install) and `C:\kindle\autorun.log` (sync-wait + extract). The
first provisioning run is the proving ground — read these if anything hangs.

### Shut down / teardown

By default the VM **persists stopped** so new-book re-runs are zero-touch — just `virsh shutdown kindle-extract`
when the extract finishes (`--rerun` starts it again later; Kindle stays signed in). **Delete it permanently** only
when you're truly done (or the 90-day eval lapses): `virsh destroy kindle-extract && virsh undefine kindle-extract
--remove-all-storage --nvram` — then re-provision from scratch (one fresh login) if you need it again.

## The cluster half (ingestion + query)

Once files are in MinIO `kindle-corpus`, the weyland-dagster `datasets_kindle_*` assets land → chunk (the
section-aware chunker, books have real chapters) → bge-base embed → write the **`kindle`** collection to
Qdrant/Weaviate with per-book payload (title/author/ASIN) for filtered retrieval, and emit the dataset + lineage to
DataHub. Deploy is the standard dagster image tag flow (new registry tag + bump `user-code`). Query via the operator
or the read-only MCP; retrieval is graded against a `kindle` golden set through the existing eval matrix. See
[demos/kindle-rag.md](../demos/kindle-rag.md) and [diagrams/flow-kindle-rag.md](../diagrams/flow-kindle-rag.md).

## Legality / scope

Your own purchased books, personal LAN-only KM use, no redistribution — format-shifting owned content. The
collector only sees OS packages, so Calibre's plugins are app-internal (noted in the spike doc, out of the
machine-inventory scope by design — [[b129-machine-inventory-catalog]]).
