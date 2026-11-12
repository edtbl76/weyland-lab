# Trunk Flaky Tests runbook (B189, EMA-248)

Every CI pipeline uploads its test results to **Trunk Flaky Tests** (free plan, SaaS), which keeps each test's history,
detects flaky and broken tests, and files them as Linear issues in project **Weyland Auto-Filed** with label
`trunk-flaky`. Built 2026-11-06. Verdict and alternatives: `docs/concepts/test-visibility.md`.

| | |
|---|---|
| What runs | Woodpecker step `trunk-upload` (`.woodpecker.yml` § 5b), after every pipeline, green or red |
| Script | `scripts/ci/trunk-upload.sh <junit-root>` (tests: `scripts/tests/trunk-upload.bats`) |
| Uploader | `trunk-analytics-cli` **0.16.1**, downloaded each run from GitHub releases, sha256 `8c34f99a41d4b3151f711aca05d01478b2f707dd698d3980d2524646021af5f2` checked before it runs |
| Where results come from | `reports/junit/<source>/` in the shared workspace. Each `<source>` is one Trunk **variant** |
| Trunk org / collection | `weyland` / `bats` collection, id `ZuFEh5e5` (https://app.trunk.io/weyland/flaky-tests) |
| Key | Woodpecker secret **`trunk_org_token`** = Trunk's **legacy org token** (the "Legacy Keys" screen in Trunk's settings, beside the v2 API keys). The v2 API keys do not work: the CLI rejects them, and the v2 API has no upload endpoint. The same value is `TRUNK_ORG_TOKEN` in `scripts/.env` for local runs |
| Linear | Trunk's Linear connection, "Linear (TRUNK)", Configuration: team `emangini`, project **Weyland Auto-Filed**, assignee `ed`, priority **Low**, label **`trunk-flaky`**. Collections `bats`, `MyBodyGraph` and `grkit` (the last two set 2026-11-10) → Ticketing: auto-create for flaky and for broken tests, auto-close for healthy tests, reopen recent tickets (30 days) |
| Alert when it breaks | the `trunk-upload` step goes red (and so does the pipeline): see Troubleshooting |

## Sources (variants)

| Variant | Written by | How |
|---|---|---|
| `python` | `test-python` | `pytest --junitxml` per project (`run-lang-tests.sh`, `LANG_JUNIT_DIR`) |
| `shell` | `test-shell` | `bats --report-formatter junit`. **Not** `shell-tests`: it runs the same `scripts/tests` suite, and reporting both would count every bats result twice |
| `java` / `kotlin` / `scala` | `test-java` / `test-kotlin` / `test-scala` | the runner's own reports (Surefire, Gradle, sbt), copied out after the run whatever its exit |
| `php` | `test-php` | `phpunit --log-junit` |
| `swift` | `test-swift` | `swift test --parallel --xunit-output` (XCTest writes its report only with `--parallel`) |
| `go` | `test-go` | `gotestsum --junitfile -- <the same go test flags>` (phase 2b). gotestsum **v1.13.0** (owner-approved 2026-11-06) is downloaded per run as the release binary and checked against its published sha256 (`11ccddea…40e8ee`) before use. Without it on PATH the lane says so and runs plain `go test` |
| `rust` | `test-rust` | `cargo nextest run --config-file <generated>` (phase 2b). cargo-nextest **0.9.149** (owner-approved 2026-11-06), release binary checked against GitHub's sha256 (`32d1d8c0…290c770`), installed into the image's cargo bin (not the cache). The JUnit config is generated outside the project. **nextest runs no doctests**: the golden paths have none, but a crate that adds some must know its doctests leave the normal run |
| `dotnet` | `test-dotnet` | `dotnet test --test-adapter-path <logger dir> --logger "junit;LogFilePath=…"` (phase 2b). JunitXml.TestLogger **8.0.0** (owner-approved 2026-11-07): the nupkg is checked against its sha256 (`9ddfe96a…3da30b`; nuget.org's catalog SHA512 matched) and its DLLs extracted per run, so no `PackageReference` goes into the golden path. The golden path's test classes have no C# namespace, so cases appear as `UnknownNamespace.UnknownType` / `ContractTests.<Method>`: unique and stable, which is all Trunk's history needs |
| `r` | `test-r` | testthat `JunitReporter` beside the console reporter (phase 2b). It needs the `xml2` package: **1.6.0** (owner-approved 2026-11-07) from the dated Posit snapshot `p3m.dev/cran/__linux__/resolute/2026-10-20`, and the step fails unless exactly that version installed. The lane uses the reporter only when R confirms xml2 is present (wiring it in without xml2 broke the lane once). The self-check test shows as *skipped* in the normal run's report |
| `elixir` | `test-elixir` | `mix test --formatter ExUnit.CLIFormatter --formatter JUnitFormatter`, report copied from `_build/test/lib/<app>/test-junit-report.xml` (phase 2b). `junit_formatter` **3.4.0** (owner-approved 2026-11-07) is the one reporter that lives IN the golden paths, as `{:junit_formatter, "3.4.0", only: :test}` in each `mix.exs`: a Mix archive install of it writes nothing (tested twice). The images build with `mix deps.get --only prod`, so it never reaches one. A new elixir project needs the same line, or the lane prints `NO JUNIT REPORT` |
| `clojure` | `test-clojure` | `lein test2junit`, reports copied from `test2junit/xml/` (phase 2b). `test2junit` **1.4.4** (owner-approved 2026-11-07; last released 2022, stable) comes from the lein **user** profile the step writes, so `project.clj` stays clean. Checked before adopting: it honours `:test-selectors` (the `^:selfcheck` test stays out), exits 1 on a failing test, and Trunk's parser counts its reports. It also leaves `test2junit/` and an Ant `build.xml` in each project (gitignored) |
| `ruby` | `test-ruby` | minitest-reporters' `JUnitReporter`, via `scripts/ci/ruby_junit_setup.rb` loaded by `RUBYOPT` (phase 2b). `minitest-reporters` **1.8.0** (owner-approved 2026-11-07; version in `RUBY_JUNIT_REPORTERS_VERSION`) is added through a CI-only Gemfile beside the report that `eval_gemfile`s the project's own and starts from a copy of its committed lock, so no locked gem moves and the golden paths' Gemfiles are untouched. The setup file loads `bundler/setup` first: without it the reporter picked the machine's newest minitest and broke the next project (found 2026-11-07) |
| `dart` / `flutter` | `test-dart` / `test-flutter` | `<runner> test --file-reporter json:<f>` (console kept), converted by `tojunit --base <project>/` (phase 2b). `junitreport` **2.0.2** (owner-approved 2026-11-07; last released 2022) is activated globally per run (`dart pub global activate`), outside the projects. The self-check suite shows as *skipped*. The exit code is the test run's, never the converter's |
| `julia` / `haskell` / `ada` / `c` / `swift-tokamak` / `perl` | their `test-*` steps | **lane-level** (phase 3): no per-test reporter (perl: not worth its Moose stack), so `run-lang-tests.sh` writes ONE test case per project from the run's exit code, a failure carrying the last 30 output lines (XML-escaped). Trunk sees each project pass, fail and flake, not individual tests. The console output is kept (`tee`), and the status is the runner's (`PIPESTATUS[0]`) |
| `react-native` | `test-react-native` | jest-expo is jest: the same `jest-junit` 17.0.0 as `test-node` (owner-approved for this step 2026-11-07), installed into `/tmp/jest-junit` and passed by path. Found last: it has its own step, so it sat in no phase until the CI map showed it untagged |
| `lua` | `test-lua` | `busted -o junit -Xoutput` (phase 2a) |
| `cpp` | `test-cpp` | doctest `--reporters=junit --out` (phase 2a) |
| `erlang` | `test-erlang` | eunit's surefire report, enabled through a generated `REBAR_CONFIG` copy so the golden path's `rebar.config` stays clean (phase 2a) |
| `node` | `test-node` (all four node lanes) | vitest `--reporter=junit`, `node --test --test-reporter=junit` (phase 2a). The four node lanes discover the same projects, so they share ONE variant with files named by project path: four runs overwrite one file instead of counting four times. **Jest projects (phase 2b):** `jest-junit` **17.0.0** (owner-approved 2026-11-06) is installed per run into `/tmp/jest-junit`, outside the projects, and passed to jest by path (`JEST_JUNIT_REPORTER`), so the golden paths' `package.json`/lockfiles carry no CI plumbing. Unset, a jest project prints `junit: … no JUnit until B189 phase 2b` |
| `golden-path` | `golden-path-smoke` | `run-golden-path-jobs.sh` writes one test case per golden path: OK, BUILD FAILED, APPLY FAILED or SMOKE FAILED, with the log tail (`GOLDEN_PATH_JUNIT`) |

Every test lane reports (28 sources, #597). A lane whose reporter tool is missing at run time says so in its log
(`junit: <dir> — <tool> is not on PATH / not set`) and runs its tests as before; a lane whose runner ran but left no
report with a test case in a `<testsuite>` prints `NO JUNIT REPORT`. Self-check runs **never** report: their deliberate
failure would reach Trunk as a test that fails every build.

## How it decides an upload worked

The CLI's exit code is not the verdict (observed 2026-11-06): a landed upload exits **1** when tests failed, a refused one
exits 70, one run with no CA bundle exited 0 after an "unexpected error", and another hung. `trunk-upload.sh` counts an
upload only when the output has both `Upload: https://app.trunk.io/…` and `Test Report`, has no `Error Encountered`, the
exit is 0 or 1, and it finished within `TRUNK_UPLOAD_TIMEOUT` (300 s). Anything else is `UPLOAD FAILED: <variant>` and
the step exits 1. No reports at all is exit 2. The token is redacted from every line it prints.

## Install or restore (owner steps)

1. **Token.** In Trunk's settings, the "Legacy Keys" screen: the **legacy** org token. Copy it into `scripts/.env` as
   `TRUNK_ORG_TOKEN` (an editor, not a paste into chat).
2. **Woodpecker secret.** From `scripts/.env`, without printing the value:

   [rogueone]
   ```
   cd /home/edwardmangini/IdeaProjects/weyland && set -a && . scripts/.env && set +a && woodpecker-cli repo secret add --repository edtbl76/weyland-lab --name trunk_org_token --value "$TRUNK_ORG_TOKEN" --event cron --event manual --event push
   ```
   **No `--image` filter.** Woodpecker applies image filters to *plugins* only: a secret with one, requested by a normal
   commands step, makes the WHOLE pipeline refuse to start ("only allowed to be used by plugins … Image filters do not
   work for normal steps"; pipeline #588, 2026-11-06). Only `trunk-upload` requests the token, and the pipeline file is
   reviewed in git, as for every other secret here. To rotate it, use `repo secret update` with the same arguments.
3. **Trunk Linear connection and ticketing**: the values in the table above. Open **Create ticket** twice before filing
   by hand: the modal shows the saved defaults empty on its first open (a Trunk bug, reported 2026-11-06). EMA-334 was filed
   from an empty modal and landed with no project. `check-linear-sync.sh` catches that ("OPEN ISSUES WITH NO PROJECT").

## Test it

The exact CI step, run from rogueone in the same image (it downloads and checks the pinned CLI, then uploads every
`<variant>/` under `/home/edwardmangini/IdeaProjects/weyland/reports/junit/`; the repo is mounted read-only):

[rogueone]
```
cd /home/edwardmangini/IdeaProjects/weyland && set -a && . scripts/.env && set +a && docker run --rm -e TRUNK_API_TOKEN="$TRUNK_ORG_TOKEN" -e TRUNK_COLLECTION_ID=ZuFEh5e5 -e CI_COMMIT_SHA="$(git rev-parse HEAD)" -e CI_COMMIT_BRANCH=main -v /home/edwardmangini/IdeaProjects/weyland:/src:ro -w /src alpine:3.20 sh -c 'apk add --no-cache bash curl git >/dev/null && git config --global --add safe.directory /src && curl -sSfL -o /tmp/c.tgz https://github.com/trunk-io/analytics-cli/releases/download/0.16.1/trunk-analytics-cli-x86_64-unknown-linux.tar.gz && echo "8c34f99a41d4b3151f711aca05d01478b2f707dd698d3980d2524646021af5f2  /tmp/c.tgz" | sha256sum -c - && tar -xzf /tmp/c.tgz -C /usr/local/bin trunk-analytics-cli && bash scripts/ci/trunk-upload.sh reports/junit'
```
Expect `<variant>: uploaded` per source and `OK — N variant(s) uploaded`. Rehearsed this way on 2026-11-06 with the
`python` lane's 20 reports: 1,680 results, exit 0.

## Other repos (B238 2026-11-10; B245 2026-11-11)

**CI for every managed repo is the lab's Woodpecker, never GitHub Actions** (owner, 2026-11-11). Trunk needs CI runs
to report from, so a repo joins when it has a Woodpecker pipeline (`repos.yaml` lane `ci`, which the repo-coverage
guard checks against Woodpecker activation). A repo with no tests joins when it gets tests.

| Repo | CI | Trunk collection | Sources (variants) |
|---|---|---|---|
| **Algopedia** | Woodpecker repo 5, `kubernetes` | `bInb6P93` | `pytest` — collects the `unittest` suites under `python/tests` (692 tests; 7 quicksort tests red on `main` since before B245) |
| **ServiceTransformation** | Woodpecker repo 3, **`local`** (Testcontainers needs Docker) | `l7eE7ZjM` | `gradle` — every service's JUnit 5 results, Gradle run in `eclipse-temurin:17-jdk` with the host Docker socket (58 tests) |
| **emangini-tailwind-nextjs-contentlayer** (blog) | Woodpecker repo 4, `kubernetes`; pipeline on `main` | `SnnIoRn8` | `node-test` — `node --test scripts/*.test.mjs`, Node's built-in JUnit reporter (76 tests) |
| **stud.io** | Woodpecker repo 1, `local`; `main` workflow, push/manual on `main` only (the org secret is not given to pull requests) | `ddxR1SoJ` | roadie writes JUnit when `ROADIE_JUNIT=1` (set by the `unit-pbt` step): `jest` and `fast-check` (`jest-junit`), `pytest` and `hypothesis` (`--junitxml`), `go-test` (`gotestsum` in the `go_test` image) — ~2,470 tests. e2e (Playwright) not reported yet |
| **freejack** | Woodpecker repo 8, `local`, private | `u7IR4NZC` | `pytest` — `tools/tests` only (`vendor/` is third-party), 2,549 tests in three parallel steps at nice 10, ~25 min wall. **Don't run it while stud.io's `perf` runs:** both use rogueone's local agents, and stud.io #30's Lighthouse missed TBT (211 and 218 ms against 200) while freejack #2 ran; #31 alone was green |
| **MyBodyGraph** | Woodpecker repo 7, `local`, private (moved off GitHub Actions; `deploy.yml` stays a manual GitHub Actions job gated on the `ci/woodpecker/...` commit status) | `Tz9xc0cL` | `vitest` — `npm run check` in `node:22` (460 tests) |
| **grkit** | Woodpecker repo 6, `local` (moved off GitHub Actions; pull requests no longer get an automatic check) | `8jol5WOk` | `pytest` (38) and `bats` (6), written by `scripts/test.sh` |
| startme-curator | none | — | **never: a DONE project** (B132, done 2026-08-27; owner 2026-11-11). No CI, no Trunk. |
| OJayFloyd | none | — | not wired: no tests yet (2 files). Joins when it gets tests. |

How each repo uploads: a final `trunk-upload` step (`when: status: [success, failure]`, so a red test run still
reports) downloads the pinned `trunk-analytics-cli` 0.16.1 and **this repo's `scripts/ci/trunk-upload.sh` at a pinned
commit** (`45c0b1ca…`, sha256 `09f3887d…`), checks both against their sha256, and runs it on `reports/junit`. So the
fail-closed logic lives here, once. On a `local`-backend pipeline the downloads go under the workspace, not `/tmp`
(four agents share rogueone). The token is the **org-level** Woodpecker secret `trunk_org_token` (every `edtbl76`
repo inherits it; its recreate command is in [woodpecker.md](woodpecker.md) § SQLite state); the collection id is
plain text in each `.woodpecker.yml`. **Fail-closed, proven 2026-11-11:** the pinned uploader pointed at a
non-existent collection got "Error Encountered" from the CLI with exit **0**, and still exited 1
(`UPLOAD FAILED … 1 of 1 variant(s) did NOT reach Trunk`).

**Onboard a repo:** create its collection (below), add the two steps on the Algopedia pattern (test step writing
`reports/junit/<variant>/`, then `trunk-upload`), activate it (`woodpecker-cli repo add <GitHub repo id>`), flip
`lanes.ci`, add the row above and in `woodpecker.md`'s repo table, then run it once:

[rogueone]
```
set -a && . /home/edwardmangini/IdeaProjects/weyland/scripts/.env && set +a && woodpecker-cli pipeline create edtbl76/<repo> --branch main
```

Collections can be created through Trunk's v2 API with the v2 key (`TRUNK_UPLOAD_TOKEN` in `scripts/.env`):
`POST https://api.trunk.io/v2/test-collections` with `Authorization: Bearer <key>` and `{"name": …, "description": …}`;
`GET /v2/test-collections` lists them. **If `trunk-upload.sh` changes**, bump the pinned commit and sha256 in each
repo's `.woodpecker.yml`, or that repo keeps running the old version.

## Budget

**Checked 2026-11-10 (B238):** Settings → Billing shows the **Free** plan as "Free for repos with ≤ 5 committers",
**Committers 0**, and no span or result meter. So on the plan as Trunk shows it today, the limit is the number of human
committers, not test results, and adding the owner's other repos costs nothing against it. The span figures below are
from Trunk's pricing page as read for B189 (2026-11-06); keep them as the fallback if the plan page ever shows a meter.

Free plan (B189 reading): "1M test spans per committer per month, up to 5M". A span is one test result, and only non-bot committers count,
so for this lab about **1M a month across every repo**. The limit is soft: over it, Trunk shows an upgrade banner and keeps
accepting uploads. **Check Settings → Billing monthly.** Measured: a **full** weyland-lab run uploads about **3,200**
results (#597, 28 sources, 2026-11-07), and a lean run nearly as many (python + shell + java, about 3,000: python and
shell dominate both). At about 200 pipelines a month that is ~600k, most of the ~1M before any other repo joins. Check the Billing page after a week of real
traffic before adding repos (phase 4); the levers if it runs hot are fewer full runs, or reporting `shell` (the biggest
source after python) only on full runs.

**Projection with every managed repo reporting (B245, 2026-11-11).** Results per run × estimated runs a month; the run
counts are estimates (other repos run only when started by hand), to be replaced with real numbers from Settings →
Billing after a week:

| Repo | Results per run | Runs a month (est.) | Results a month |
|---|---|---|---|
| weyland-lab | ~3,200 | ~200 | ~640k |
| stud.io | ~2,470 | ~30 | ~74k |
| freejack | 2,549 | ~15 | ~38k |
| MyBodyGraph | 460 | ~60 | ~28k |
| Algopedia | 692 | ~20 | ~14k |
| blog, ServiceTransformation, grkit | 76 / 58 / 44 | ~20 each | ~4k |
| **Total** | | | **~800k** |

Under the ~1M span reading, and the plan page today meters committers, not results. If it ever runs hot: weyland's
levers above first, then upload freejack (the next-largest per run) only from runs started for it.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `UPLOAD FAILED: <variant> — the CLI did not confirm the upload (exit 70)` with `Unathorized access` | the token is wrong, revoked, or a v2 key. Redo steps 1–2 with the **legacy** org token |
| `UPLOAD FAILED … timed out after 300s` | Trunk or the network stalled (the same hang appears with no CA bundle). Re-run the pipeline; if it repeats, run the Test-it command above to see the CLI's own output |
| `trunk-upload.sh: no JUnit reports under reports/junit` (exit 2) | no lane wrote a report: the pipeline failed before any test ran, or `LANG_JUNIT_DIR` / `GOLDEN_PATH_JUNIT` was removed from the steps |
| The whole pipeline is `error` before any step, "secret trunk_org_token is only allowed to be used by plugins" | the secret has an image filter. Remove and re-add it without `--image` (step 2) |
| `sha256sum: WARNING: 1 computed checksum did NOT match` | the release asset changed. Don't bypass: check Trunk's release notes, then bump `TRUNK_CLI_VERSION` and `TRUNK_CLI_SHA256` together |
| A lane prints `NO JUNIT REPORT: the <lang> run in <dir> left none` | the runner ran but wrote no report with a test case (Trunk will not see that project). Check that runner's report flag or path in `run-lang-tests.sh` |
| A Trunk issue in Linear with no project | it was filed from the empty first-open modal; move it to Weyland Auto-Filed with `trunk-flaky` |

## Clean-up record

The trial left synthetic runs in collection `ZuFEh5e5`: variant `b189-probe` (two probe tests, one failed once) and the
simulated flake on `alert-rules.bats` "promtool is available …" (EMA-334, which auto-close should close once the test stays
healthy). They are labelled and harmless, so they were left in place. The Linear side was cleaned: EMA-335 (the config
test) is Canceled with a comment, and EMA-334 was moved into Weyland Auto-Filed by hand.
