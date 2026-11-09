# IaC — OpenTofu Runbook — weyland

OpenTofu (OSS Terraform fork) owns the **non-k8s** IaC lane (B58 lane b) — the things Argo CD's GitOps can't
reconcile: **SaaS config** (Port, later GitHub/DNS) and **Proxmox** VMs/CTs. Runs from **rogueone** (the repo
box); state lives in **MinIO**. Pairs with Argo CD (the k8s lane — [runbooks/argocd.md](argocd.md)). NOT a
direct CI→CD wire; git is the seam.

---

## Layout & state
- Config: `nodes/mother/lab/weyland-platform/tofu/<lane>/` — one dir per lane (own backend key). Today: `port/`.
- **State backend = MinIO S3** (`s3.weyland.lab`, bucket `tofu-state`, key `<lane>/terraform.tfstate`).
  MinIO-isms in `main.tf`: `use_path_style = true`, `skip_credentials_validation/requesting_account_id/
  metadata_api_check/region_validation/s3_checksum = true` (the last one: MinIO rejects the newer AWS checksum
  trailers).
- **No secrets in git** — all via env, set before any `tofu` run:
  - `AWS_ACCESS_KEY_ID=admin  AWS_SECRET_ACCESS_KEY=weyland_dev_password`  (MinIO, for the state backend)
  - `PORT_CLIENT_ID=…  PORT_CLIENT_SECRET=…` (Port lane); `PROXMOX_VE_ENDPOINT/API_TOKEN` (Proxmox lane); `GITHUB_TOKEN` (GitHub lane)
- `.gitignore` ignores `.terraform/`, `*.tfstate*`, `*.tfvars`; the **lock file IS committed**.

## Port lane (done) — `tofu/port/`
**24 blueprints + 8 scorecards + 4 integrations + 1 action codified** (2026-10-13). CLI-imported, `tofu plan` a clean no-op,
state in MinIO. Blueprints: 8 webhook/category (`cost`, `ci_pipeline`, `glitchtip_issue`, `feature_flag`,
`code_quality`, `security_scan`, `code_hotspot`, `endpoint`) + 5 software-catalog (`domain`/`system`/`component`/
`resource`/`api`) + the 8 that B137 recovered from the UI (`service`, `workload`, `deployment`, `environment`,
`organization`, `backup`, `ai_session`, `ai_user`).

**Entities are NOT codified** — B60 decoupled them: **blueprints = schema (tofu, drift-checked); entities = data
(MCP + integrations, free to evolve)**. Codifying actively-edited entity data caused constant sync friction;
entities rebuild from the docs via MCP.

> **B60's `state rm` was never actually run, and that cost the lane its whole purpose (executed 2026-08-24, B137).**
> 64 `port_entity.component` resources sat in state for weeks with the decision to remove them already made. The
> effect was not cosmetic: **every** `tofu plan` reported `0 to add, 64 to change, 0 to destroy`, because other
> writers legitimately own that data and tofu could only ever read their work as drift to revert. A permanently
> dirty plan detects nothing — the signal is indistinguishable from the noise, exactly like a permanently-lit
> alert. `applications.tf` is now a comment-only file explaining why it declares nothing.
>
> Checked before removing rather than inferred from the diff: of the 64, `type`/`lifecycle`/`source` were populated
> on **0** and no component had a non-empty relation, but `datahub_application_url` was populated on **30**. An
> apply would have cleared those 30 links — a real hazard, and a bounded one. Both numbers came from the live API.
>
> To un-codify entities: `tofu state list | grep '^port_entity\.' | xargs -n1 tofu state rm` + delete the blocks.

**A clean plan is not coverage.** Plan compares the code to the resources **tofu knows about**, so a blueprint
created in Port's UI is invisible to it — which is how this org reached 51 live blueprints against 13 codified
with a clean plan throughout. `scripts/check-port-iac-coverage.sh` asks the inverse question and is what actually
guards the lane; see [port.md](port.md) § What is deliberately UI-managed.

**`k8s_workload.kind` carries Job/CronJob as of B145, and the enum extension was TESTED not assumed.** Port drops an out-of-enum property value SILENTLY, so the batch mappings originally wrote `null` rather than a value that would look accepted and write nothing. The enum lives on an integration-OWNED blueprint, so the fear was that the exporter would revert it. Experiment: extend the enum → restart the exporter (which runs `CREATE_DEFAULT_RESOURCES=true`) → re-read. **It survived.** Consistent with the blueprint's `updatedAt` sitting unchanged for 66 days across 3 pod restarts. Note the exporter does NOT rewrite unchanged entities when a mapping changes — a restart is what forces the full resync.

**Integrations (`port_integration`) — the two attributes that matter:** `version` is optional+**computed**, so
leave it unset. Port upgrades its hosted integrations on its own schedule (github-ocean 6.8.1 → 6.9.4 in two days
here) and pinning it makes the plan permanently dirty. `config` is the resource **mapping** — authored by a human,
safe to manage. `spec.appSpec.*` has no provider attribute and is not durable anyway: the Port-hosted integrations
re-register and push their own appSpec over server-side edits.

**Gotcha (only if you ever DO codify an entity):** generate-config-out emits the `provider = port-labs` phantom
AND read-only fields (`id`/`created_at`/`updated_at`/`updated_by`) → `sed`-strip BOTH before CLI import. Entity
import ID = `<blueprint>:<identifier>`. NOT codified: entities, dashboards, most pages.

## THE gotcha — port-labs provider + generated config = phantom `hashicorp/port-labs`
The provider's **source type (`port-labs`) ≠ its resource prefix (`port_`)**. Two failure modes fall out:
- **`tofu plan -generate-config-out` writes `provider = port-labs` into every generated resource** — a bare
  reference to a provider local name that `required_providers` doesn't map (it maps `port`). OpenTofu defaults
  the unmapped name to `registry.opentofu.org/hashicorp/port-labs` → **"provider … does not have a provider
  named …"** + "Inconsistent dependency lock file". One leftover generated file poisons every subsequent `init`.
- **`import` blocks for un-configured resources** resolve the provider by that same type name → same phantom.

**Fix / the working pattern:**
1. Write the **resource blocks** (a resource block anchors the provider via the `port_` prefix → `port`).
   Generated config is exact-from-Port — keep it, but **strip the `provider = port-labs` lines**:
   `sed -i -E '/^[[:space:]]*provider[[:space:]]*=[[:space:]]*port-labs[[:space:]]*$/d' blueprints.tf`
2. Use **CLI `tofu import port_blueprint.<id> <id>`**, NOT `import` blocks.
3. `tofu plan` → `No changes`.
- Also strip read-only fields if hand-cleaning generated config: `id`, `created_at/by`, `updated_at/by`.
- `required_providers` maps local name **`port`** → `port-labs/port-labs` (`~> 2.0`); `provider "port" {}` reads
  creds from env. EU org — default `base_url https://api.getport.io` works (routes by org token).

## Operate
- Add a resource: write the block (or generate + strip `provider`), `tofu import …`, `tofu plan` until no-op.
- Change config: edit the `.tf`, `tofu plan`, `tofu apply`. State round-trips through MinIO automatically.
- New lane: new `tofu/<lane>/` dir + its own `backend "s3"` key.
- **Format before you push — CI enforces it.** `scripts/check-tofu-fmt.sh` (the `repo-guards` step, 2026-09-24)
  runs `tofu fmt -check` on every `.tf` directory under `nodes/` (a new lane is picked up automatically). Exit 1 =
  a directory needs formatting; exit 2 = a file does not parse (or no tofu / no directories). Fix, then confirm the
  change is whitespace-only:
  ```
  [rogueone] cd /home/edwardmangini/IdeaProjects/weyland/nodes/mother/lab/weyland-platform/tofu/<lane> && tofu fmt && git diff -w --stat .
  ```
  Check the whole repo the way CI does: `bash /home/edwardmangini/IdeaProjects/weyland/scripts/check-tofu-fmt.sh`.

## Proxmox lane (done) — `tofu/proxmox/` — RECORD ONLY, never applied

> **How this lane is used (owner, 2026-11-08).** Guests are managed by hand on weyland (`pct` / `qm`). The code and
> state are a record of what exists, kept in step by hand when a guest is added or removed (edit the `.tf`, then
> `tofu import` or `tofu state rm`). Nothing applies this directory. The Port, GitHub and Keycloak lanes ARE
> applied routinely; this one is not. There is no stored tofu token: the `root@pam!tofu` token described below
> was used once for the import and not kept. The only stored Proxmox credential is the pve-exporter's read-only
> PVEAuditor token (`monitoring/pve-exporter-secret`, [observability.md](observability.md)). Because `tofu plan`
> only reads, that token is enough to check the record against Proxmox, but it is not kept in `.env`.
> Check the live guest set without any token: `pve_guest_info` in Prometheus (command below).
Guests were imported brownfield (CLI `tofu import <addr> <node>/<vmid>`, e.g. `weyland/103`). **Live on Proxmox as
of 2026-11-08: only VM mother (101, `proxmox_virtual_environment_vm`) and CT whisper (103,
`proxmox_virtual_environment_container`)** (checked through `pve_guest_info`). Hermes (CT 104) was destroyed
2026-07-23 and its resource is gone from the code. **Drift fixed by B239 (2026-11-08):** `openclaw.tf` (VM 100,
OpenClaw dropped) and `ollama.tf` (CT 102, Ollama moved to rogueone in B79) declared guests that no longer existed,
so a `tofu apply` would have tried to recreate them. Both files are deleted and both resources removed from state
(`tofu state rm`, owner, 2026-11-08: "Successfully removed 2 resource instance(s)"). The state now lists exactly
`proxmox_virtual_environment_vm.mother` and `proxmox_virtual_environment_container.whisper`, the two guests Proxmox
runs (`tofu state list` needs only the MinIO backend credentials in `scripts/.env`). The live set is checked with
`pve_guest_info` in Prometheus (`curl -s 'http://192.168.1.243:30909/api/v1/query' --data-urlencode 'query=pve_guest_info'`). Auth: API token — `PROXMOX_VE_API_TOKEN='root@pam!tofu=<uuid>'` (create in
Datacenter→Permissions→API Tokens, **Privilege Separation OFF**) + `PROXMOX_VE_ENDPOINT='https://weyland:8006/'`;
provider `insecure = true` (self-signed cert). No phantom here — bpg's source type (`proxmox`) == resource prefix.

**bpg gotchas — `-generate-config-out` emits write-invalid sentinels (fails plan, but still WRITES the file):**
- Empty/zero "unset" sentinels → **omit the line** (don't keep empty): `cpu.units = 0` (must be 1-500000),
  `initialization.entrypoint = ""` (CT), `cpu.architecture = ""`, `cpu.affinity = ""`, `memory.hugepages = ""` (VM).
- top-level **`mac_addresses`** is computed (the live NICs) → remove from config.
- **`timeout_*` are config-only** (client-side operation waits): CT timeouts import as null → pin to defaults
  (1800/60/300/1800) or they perpetually `+`-diff. `timeout_start` (CT) is deprecated, but pinning it beats the
  perpetual diff (cosmetic warning, kept on purpose). VM timeouts import already-set → no diff.
- **mother's raw passthrough disk** (`/dev/disk/by-id/…`, 4TB Seagate, `datastore_id/file_format = ""`) can't
  round-trip → omit disk blocks + `lifecycle { ignore_changes = [disk] }`; tofu adopts the VM, never touches storage.
- **`network_device` `enabled` is deprecated** (bpg/proxmox, seen 2026-11-08). The generated list-of-objects form
  (`network_device = [{ … }]`) requires every attribute, `enabled` included, so it always warns. Write the NIC in
  block form (`network_device { … }`) and omit `enabled` (default true). `mother.tf` was converted by B239: `tofu
  validate` is clean for it. A `tofu plan` against Proxmox (which needs a token, see above) has not been run on the
  new form.
- Pattern: generate (fails, writes `generated.tf`) → read it → fix sentinels into resource blocks → **CLI
  `tofu import`** (not `import` blocks) → `tofu plan` to no-op. Per-guest `.tf` files.

## GitHub lane (done) — `tofu/github/`
`integrations/github` provider (`~> 6.0`), auth via env `GITHUB_TOKEN` (PAT, `repo` scope), `owner = "edtbl76"`.
The **weyland-lab repo** codified (`repo.tf`) via CLI import — strip computed fields (`etag`, `fork`) + create-only
template fields (`gitignore_template`, `source_owner/repo`); leave `has_downloads` UNSET (deprecated by GitHub, reads false live — pinning it was a permanent plan diff, removed 2026-09-24). `ignore_vulnerability_alerts_during_read`
is deprecated (cosmetic warning, kept to avoid a perpetual diff). Webhooks can be added here later.

**Branch protection — stud.io (codified 2026-09-25, `stud_io_protection.tf`).** stud.io's `main` has two layers,
both imported (`-generate-config-out`, then cleaned): classic branch protection (PR required, 0 approvals) and the
`main` ruleset (same rule; repo admins may bypass). The required status check `ci/woodpecker/pr/main` was REMOVED:
since B57 put stud.io CI on weyland's LAN-only Woodpecker (2026-08-18), GitHub can't deliver PR webhooks to it, so no
PR could ever satisfy the check and every merge needed an admin bypass. Change protection here, never in the UI.

## Deliberately NOT codified (justified skips)
- **Port entities, dashboards, and most pages**: live **data**, not authored config. tofu would fight the writers
  that legitimately own it — which it did, for weeks, until B137 executed B60's `state rm` (above).
- **Port's system (`_`-prefixed) and integration-owned blueprints** — 30 of the 51 live. The rule is *codify what
  cannot recreate itself; document what does*: an Ocean integration creates its blueprints on install and revises
  them on upgrade, so tofu owning `githubRepository` would turn every integration upgrade into drift. Enumerated
  with per-group reasons in [port.md](port.md) § What is deliberately UI-managed, and enforced by
  `scripts/check-port-iac-coverage.sh` rather than left to prose.
  > **Superseded:** this bullet used to say scorecards were "Port-managed defaults … NOT authored config." That was
  > wrong. All 8 carry hand-written logic — 44 rules, including a 14-rule `service/delivery_performance` — and
  > losing the org would have lost every one of them. They are codified in `b137_scorecards.tf`.
- **DNS**: the lab's resolution is **CoreDNS** (a k8s ConfigMap, Argo's domain); no external zone to manage.
