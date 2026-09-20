# B165 — Kindle extraction: batch decrypt + export + upload (run in the VM, AFTER Kindle-for-PC is signed in and
# has synced your library). The "script the rest" half of "log in once, script the rest". See docs/runbooks/kindle-rag.md.
#
#   # book #1 gate — prove ONE book end to end first (open the resulting .txt; must be real readable text):
#   powershell -ExecutionPolicy Bypass -File kindle-extract.ps1 -Only "A Philosophy of Software Design" -DryRun
#   # then the whole library:
#   powershell -ExecutionPolicy Bypass -File kindle-extract.ps1 -MinioAlias weyland -Bucket kindle-corpus
#
# How it works: DeDRM is a Calibre file-type plugin that strips DRM ON IMPORT, so `calibredb add` of the Kindle
# content folder decrypts each book into a temp Calibre library; we then export EPUB + TXT and mc-mirror to MinIO.
# The temp library + export dir are throwaway (the VM itself is discarded after the batch).
param(
  [string]$MinioAlias = "weyland",
  [string]$Bucket     = "kindle-corpus",
  [string]$Only       = "",          # substring of a title/ASIN — restrict to ONE book (the gate) or a subset
  [switch]$DryRun                     # decrypt + export locally, skip the MinIO upload
)
$ErrorActionPreference = 'Stop'
function Say($m) { Write-Host "== $m" -ForegroundColor Cyan }

# Resolve Calibre CLIs (installer usually adds Calibre2 to PATH).
foreach ($exe in 'calibredb.exe','ebook-convert.exe') {
  if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) {
    $g = "$env:ProgramFiles\Calibre2"; if (Test-Path "$g\$exe") { $env:Path += ";$g" }
    else { throw "$exe not found — add Calibre's install dir to PATH and re-run." }
  }
}

# Find the Kindle content folder. Path moved across app versions — check the known roots, newest layout first.
$candidates = @(
  "$env:USERPROFILE\Documents\My Kindle Content",
  "$env:LOCALAPPDATA\Amazon\Kindle\Cache",
  "$env:LOCALAPPDATA\Amazon\Kindle\Content",
  "$env:APPDATA\Amazon\Kindle\Content"
)
$content = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $content) { throw "no Kindle content folder found (looked in: $($candidates -join '; ')). Is Kindle-for-PC signed in and synced?" }
Say "Kindle content: $content"

# Gather the encrypted book files. -Only narrows to the gate book / a subset by filename substring.
$books = Get-ChildItem -Path $content -Recurse -Include *.azw,*.azw3,*.kfx,*.kfx-zip,*.prc,*.mobi -File
if ($Only) { $books = $books | Where-Object { $_.Name -like "*$Only*" -or $_.DirectoryName -like "*$Only*" } }
if (-not $books) { throw "no book files matched (Only='$Only'). Downloaded books appear here only AFTER Kindle-for-PC syncs them." }
Say "$($books.Count) book file(s) to process$( if($Only){" (filtered by '$Only')"} )"

# Temp Calibre library + export dir (throwaway).
$lib = Join-Path $env:TEMP "kindle-lib"; $out = Join-Path $env:TEMP "kindle-out"
Remove-Item -Recurse -Force $lib,$out -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $lib,$out | Out-Null

# Import → DeDRM strips on import. One at a time so a single bad book doesn't abort the batch.
$ok = 0; $fail = @()
foreach ($b in $books) {
  try { calibredb.exe add --with-library "$lib" "$($b.FullName)" 2>&1 | Out-Null; $ok++ }
  catch { $fail += $b.Name; Write-Warning "import failed (likely still DRM'd — see the gate): $($b.Name)" }
}
Say "$ok imported$( if($fail){", $($fail.Count) failed: $($fail -join ', ')"} )"
if ($ok -eq 0) { throw "nothing imported — every book failed. Sign into Kindle-for-PC, install KFX Input, and re-run the book #1 gate before batching." }

# Export EPUB + TXT for every imported book (TXT is what the RAG chunker consumes; EPUB keeps structure).
Say "exporting EPUB + TXT to $out"
calibredb.exe export --with-library "$lib" --all --to-dir "$out" --single-dir --formats epub,txt --template "{title}_{author_sort}" 2>&1 | Out-Null
$exported = Get-ChildItem -Path $out -Include *.epub,*.txt -Recurse -File
Say "$($exported.Count) exported file(s)"
if ($DryRun) { Say "DryRun — skipping upload. Inspect $out (open a .txt: it must be REAL readable text, not garbage)."; return }

# Upload to MinIO. Alias must be configured once: mc alias set <MinioAlias> <endpoint> <key> <secret> (from scripts/.env).
$mc = (Get-Command mc.exe -ErrorAction SilentlyContinue).Source; if (-not $mc) { $mc = "$env:ProgramFiles\minio-client\mc.exe" }
if (-not (Test-Path $mc)) { throw "mc.exe not found — run kindle-vm-setup.ps1, or add it to PATH." }
& $mc mb --ignore-existing "$MinioAlias/$Bucket" | Out-Null
& $mc mirror --overwrite "$out" "$MinioAlias/$Bucket"
Say "uploaded to $MinioAlias/$Bucket — the dagster kindle assets ingest from there. VM can now be torn down."
