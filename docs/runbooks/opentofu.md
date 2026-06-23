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
All **7 webhook/category blueprints** (`cost`, `ci_pipeline`, `glitchtip_issue`, `feature_flag`, `code_quality`,
`security_scan`, `endpoint`) PLUS the **B59 software catalog** — 5 blueprints (`domain`/`system`/`component`/
`resource`/`api`) + **26 entities** (`catalog.tf`), all CLI-imported, `tofu plan` clean no-op. State in MinIO,
live Port unchanged. **`port_entity` codify gotcha:** generate-config-out emits the `provider = port-labs` phantom
AND read-only fields (`id`/`created_at`/`updated_at`/`updated_by`) → `sed`-strip BOTH before CLI import, else a
perpetual "to change". Entity import ID = `<blueprint>:<identifier>`. NOT codified: dashboards, actions, scorecards.

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

## Proxmox lane (done) — `tofu/proxmox/`
All **5 guests imported** (brownfield CLI `tofu import <addr> <node>/<vmid>`, e.g. `weyland/102`): CTs ollama (102),
whisper (103), hermes (104) = `proxmox_virtual_environment_container`; VMs openclaw (100), mother (101) =
`proxmox_virtual_environment_vm`. Auth: API token — `PROXMOX_VE_API_TOKEN='root@pam!tofu=<uuid>'` (create in
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
- Pattern: generate (fails, writes `generated.tf`) → read it → fix sentinels into resource blocks → **CLI
  `tofu import`** (not `import` blocks) → `tofu plan` to no-op. Per-guest `.tf` files.

## GitHub lane (done) — `tofu/github/`
`integrations/github` provider (`~> 6.0`), auth via env `GITHUB_TOKEN` (PAT, `repo` scope), `owner = "edtbl76"`.
The **weyland-lab repo** codified (`repo.tf`) via CLI import — strip computed fields (`etag`, `fork`) + create-only
template fields (`gitignore_template`, `source_owner/repo`); pin `has_downloads`. `ignore_vulnerability_alerts_during_read`
is deprecated (cosmetic warning, kept to avoid a perpetual diff). Branch protection / webhooks can be added here later.

## Deliberately NOT codified (justified skips)
- **Rest of Port** (actions, scorecards, most dashboards, entities): **Port-managed defaults + integration-generated**
  (the `set_*_relations` automations, the DORA/quality scorecard templates) or live **data** (entities) — NOT authored
  config. tofu would fight Port's own lifecycle for zero benefit. Blueprints were the authored config (done).
- **DNS**: the lab's resolution is **CoreDNS** (a k8s ConfigMap, Argo's domain); no external zone to manage.
