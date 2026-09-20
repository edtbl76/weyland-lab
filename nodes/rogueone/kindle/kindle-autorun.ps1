# B165 - auto-extract watcher (registered by kindle-vm-setup.ps1 as a logon scheduled task). Waits for
# Kindle-for-PC to finish downloading the library, then runs kindle-extract.ps1 ONCE. This is what makes the
# flow "just your login": after you sign in, the library syncs and this fires on its own -> MinIO. On a later
# VM restart (new books) it fires again at logon and re-extracts. Logs to C:\kindle\autorun.log.
$ErrorActionPreference = 'Continue'
function Say($m) { $line = "== " + (Get-Date -Format HH:mm:ss) + " " + $m; Write-Host $line; Add-Content C:\kindle\autorun.log $line }

$roots = @(
  "$env:USERPROFILE\Documents\My Kindle Content",
  "$env:LOCALAPPDATA\Amazon\Kindle\Cache",
  "$env:LOCALAPPDATA\Amazon\Kindle\Content"
)
$exts = @('*.azw','*.azw3','*.kfx','*.kfx-zip','*.prc','*.mobi')

# Wait for the library to APPEAR and STABILISE (download finished): poll total book count+size; when unchanged
# for 3 consecutive 30s polls AND >=1 book, sync is done. Cap the wait so it never hangs forever.
Say "waiting for Kindle-for-PC to sign in + finish syncing the library (sign in now if you haven't)"
$stable = 0; $last = ""; $maxPolls = 240   # up to ~2h for a big library
for ($i=0; $i -lt $maxPolls; $i++) {
  $dir = $roots | Where-Object { Test-Path $_ } | Select-Object -First 1
  if ($dir) {
    $files = Get-ChildItem $dir -Recurse -Include $exts -File -ErrorAction SilentlyContinue
    $sig = "{0}:{1}" -f $files.Count, (($files | Measure-Object Length -Sum).Sum)
    if ($files.Count -ge 1 -and $sig -eq $last) { $stable++ } else { $stable = 0 }
    $last = $sig
    if ($stable -ge 3) { Say "library stable ($($files.Count) book files) - extracting"; break }
    Say "syncing... ($($files.Count) book files so far)"
  } else { Say "no Kindle content folder yet (waiting for sign-in + first download)" }
  Start-Sleep 30
}
if ($stable -lt 3) { Say "gave up waiting (still syncing or not signed in). Re-run manually: powershell -File C:\kindle\kindle-extract.ps1"; exit 1 }

# Read the target bucket from the injected creds env (default kindle-corpus); alias 'weyland' was set at setup.
$bucket = "kindle-corpus"
if (Test-Path C:\kindle\kindle-minio.env) {
  $b = (Get-Content C:\kindle\kindle-minio.env | Where-Object { $_ -match '^MINIO_BUCKET=' }) -replace '^MINIO_BUCKET=',''
  if ($b) { $bucket = $b.Trim() }
}
Say "running kindle-extract.ps1 -> MinIO $bucket"
& powershell -ExecutionPolicy Bypass -File C:\kindle\kindle-extract.ps1 -MinioAlias weyland -Bucket $bucket 2>&1 |
  ForEach-Object { Add-Content C:\kindle\autorun.log $_ ; Write-Host $_ }
Say "auto-extract finished - the dagster kindle assets can now ingest from MinIO $bucket. Safe to shut the VM down."
