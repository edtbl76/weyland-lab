#!/usr/bin/env bash
# Parse-check every ```mermaid block in the given markdown files/dirs.
#
# WHY THIS EXISTS: on 2026-08-21 five mermaid diagrams shipped into
# aidlc/spaces/default/codekb/weyland/architecture.md with a `;` inside Note text.
# Mermaid treats `;` as a STATEMENT SEPARATOR, so each Note terminated early and the
# remainder parsed as garbage -- "Parse error on line 19 ... got 'INVALID'". The diagram
# rendered as a red error block in the IDE preview. Nothing caught it because nothing
# parsed the diagrams before they landed.
#
# WHY NOT mermaid-cli: `@mermaid-js/mermaid-cli` depends on puppeteer, which downloads
# and runs headless Chromium. On rogueone `kernel.apparmor_restrict_unprivileged_userns=1`
# blocks Chromium's sandbox (the same wall that breaks IntelliJ's JCEF markdown preview),
# and this box has an open whole-machine instability whose dominant crash signature
# involves Chromium memory churn. So we parse with mermaid's own parser under jsdom --
# same catch, no browser, no sandbox, nothing to crash.
#
# PREREQ: the parser lives in its own resolution root OUTSIDE this repo, because the repo
# has no package.json anywhere and should not gain one just for a doc check. ESM ignores
# NODE_PATH, so a global `npm i -g` is NOT enough -- bare `import "mermaid"` will not
# resolve from it. Set up once with:
#   mkdir -p ~/.local/lib/weyland-mermaid-check
#   cd ~/.local/lib/weyland-mermaid-check
#   printf '{"name":"weyland-mermaid-check","private":true,"type":"module"}\n' > package.json
#   npm install mermaid jsdom
#
# Usage:
#   scripts/check-mermaid.sh                 # checks docs/
#   scripts/check-mermaid.sh path/to/file.md path/to/dir ...
#
# Exit 0 = every block parsed. Exit 1 = at least one block failed (prints file, block
# number, the parser's message, and the offending source).
set -euo pipefail

here="$(cd "$(dirname "$0")/.." && pwd)"
targets=("$@")
if [ ${#targets[@]} -eq 0 ]; then
  targets=("$here/docs")
fi

command -v node >/dev/null 2>&1 || { echo "❌ node not found on PATH" >&2; exit 1; }

PARSER_ROOT="${MERMAID_CHECK_ROOT:-$HOME/.local/lib/weyland-mermaid-check}"
[ -d "$PARSER_ROOT/node_modules/mermaid" ] && [ -d "$PARSER_ROOT/node_modules/jsdom" ] || {
  echo "❌ mermaid parser root not set up at $PARSER_ROOT" >&2
  echo "   See the PREREQ block at the top of this script (one-time npm install)." >&2
  exit 1; }

# Collect the markdown files to scan.
files=()
for t in "${targets[@]}"; do
  # Absolute paths throughout: the node step runs with cwd=$PARSER_ROOT, so a
  # repo-relative path would resolve against the wrong directory.
  if [ -d "$t" ]; then
    while IFS= read -r f; do files+=("$(realpath "$f")"); done < <(find "$t" -type f -name '*.md' | sort)
  elif [ -f "$t" ]; then
    files+=("$(realpath "$t")")
  else
    echo "⚠ skipping (not found): $t" >&2
  fi
done

[ ${#files[@]} -gt 0 ] || { echo "→ no markdown files found under: ${targets[*]}"; exit 0; }

echo "→ parse-checking mermaid blocks in ${#files[@]} markdown file(s)"

# Run from the parser root so bare ESM specifiers resolve there; every file path passed
# through is already absolute or repo-relative-resolved above, so cwd does not matter to
# the reads. `--input-type=module` + `-e` takes its resolution base from cwd.
( cd "$PARSER_ROOT" && node --input-type=module -e '
import { readFileSync } from "node:fs";
import { JSDOM } from "jsdom";

// mermaid needs a DOM at import time; jsdom supplies one without a browser.
const dom = new JSDOM("<!doctype html><html><body></body></html>");
globalThis.window = dom.window;
globalThis.document = dom.window.document;
// Node 22+ ships a getter-only `navigator` global, so a plain assignment throws
// ("Cannot set property navigator of #<Object> which has only a getter").
// defineProperty replaces it; if even that is locked down, the jsdom one is optional.
try {
  Object.defineProperty(globalThis, "navigator", {
    value: dom.window.navigator, configurable: true, writable: true,
  });
} catch { /* keep the built-in navigator */ }

const mermaid = (await import("mermaid")).default;
mermaid.initialize({ startOnLoad: false, securityLevel: "loose" });

const files = process.argv.slice(1);
let blocks = 0, failures = 0;

for (const file of files) {
  const lines = readFileSync(file, "utf8").split("\n");
  let inBlock = false, start = 0, buf = [], n = 0;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (!inBlock && /^\s*```mermaid\s*$/.test(line)) {
      inBlock = true; start = i + 2; buf = []; n++;
      continue;
    }
    if (inBlock && /^\s*```\s*$/.test(line)) {
      inBlock = false; blocks++;
      const src = buf.join("\n");
      try {
        await mermaid.parse(src);
      } catch (e) {
        failures++;
        const msg = (e && e.message ? e.message : String(e)).split("\n").slice(0, 6).join("\n    ");
        console.error(`\n❌ ${file}  (mermaid block #${n}, starts line ${start})`);
        console.error(`    ${msg}`);
        // Reprint the block with absolute line numbers so the message maps to the file.
        buf.forEach((l, k) => console.error(`    ${String(start + k).padStart(5)} | ${l}`));
      }
      continue;
    }
    if (inBlock) buf.push(line);
  }
  if (inBlock) {
    failures++;
    console.error(`\n❌ ${file}  (mermaid block #${n} starting line ${start} is never closed)`);
  }
}

if (failures) {
  console.error(`\n❌ ${failures} of ${blocks} mermaid block(s) failed to parse`);
  process.exit(1);
}
console.log(`✓ all ${blocks} mermaid block(s) parsed`);
' "${files[@]}" )
