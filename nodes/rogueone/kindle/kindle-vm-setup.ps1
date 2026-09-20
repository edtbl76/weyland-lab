# B165 - Kindle extraction VM: first-boot setup, run UNATTENDED by kindle-bootstrap.cmd (from autounattend.xml).
# Installs the toolchain, wires MinIO creds, registers the auto-extract watcher, and opens Kindle-for-PC - so the
# ONLY human step is signing into Amazon. Logs to C:\kindle\setup.log. See docs/runbooks/kindle-rag.md.
# UNTESTED by the author (no Windows here) - the first provisioning run is the proving ground; read the log if it stalls.
$ErrorActionPreference = 'Continue'   # a single failed step must not abort the whole unattended setup
# Print to the console AND append to the log — live visible progress, never a blank screen (a quiet console reads
# as hung). The bootstrap does NOT redirect this to a log-only for the same reason.
function Say($m) { $l = "== " + (Get-Date -Format HH:mm:ss) + " " + $m; Write-Host $l; try { Add-Content C:\kindle\setup.log $l } catch {} }

# 1) Kindle-for-PC + Calibre via winget (retry - winget's sources may not be ready the instant we log in).
foreach ($id in 'Amazon.Kindle','calibre.calibre') {
  for ($i=0; $i -lt 5; $i++) {
    Say "installing $id (try $($i+1))"
    winget install --exact --id $id --accept-source-agreements --accept-package-agreements --silent 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) { break }
    Start-Sleep 20
  }
}

# Resolve Calibre's CLIs for this session (installer adds Calibre2 to PATH on next login, not this one).
$cal = "$env:ProgramFiles\Calibre2"; if (Test-Path "$cal\calibredb.exe") { $env:Path += ";$cal" }

# 2) DeDRM plugin - latest release of the maintained fork -> calibre-customize.
Say "installing DeDRM plugin"
try {
  $rel = Invoke-RestMethod "https://api.github.com/repos/noDRM/DeDRM_tools/releases/latest" -Headers @{'User-Agent'='weyland'}
  $asset = $rel.assets | Where-Object { $_.name -like 'DeDRM_tools*.zip' } | Select-Object -First 1
  $zip = "$env:TEMP\dedrm.zip"; Invoke-WebRequest $asset.browser_download_url -OutFile $zip
  Expand-Archive $zip "$env:TEMP\dedrm" -Force
  $p = Get-ChildItem "$env:TEMP\dedrm" -Recurse -Filter DeDRM_plugin.zip | Select-Object -First 1
  & "$cal\calibre-customize.exe" --add-plugin $p.FullName
  Say "DeDRM installed ($($rel.tag_name))"
} catch { Say "WARN DeDRM auto-install failed: $_  (manual: calibre-customize -a DeDRM_plugin.zip from github.com/noDRM/DeDRM_tools)" }

# 3) KFX Input plugin - scripted via Calibre's bundled Python fetching the plugin INDEX (no GUI click). Best-effort:
#    if the index schema shifts, the log says to do the ONE GUI step (Preferences>Plugins>Get new plugins>KFX Input).
Say "installing KFX Input plugin (via calibre plugin index)"
$fetch = @'
import bz2, json, os, sys, tempfile, urllib.request
raw = urllib.request.urlopen("https://code.calibre-ebook.com/plugins/plugins.json.bz2", timeout=90).read()
idx = json.loads(bz2.decompress(raw))
entry = idx.get("KFX Input") or next((v for k,v in idx.items() if k.lower()=="kfx input"), None)
url = entry and (entry.get("file") or entry.get("url"))
if not url: sys.exit("KFX Input not resolvable in index")
dst = os.path.join(tempfile.gettempdir(), "KFXInput.zip"); urllib.request.urlretrieve(url, dst); print(dst)
'@
try {
  $kfxZip = (& "$cal\calibre-debug.exe" -c $fetch | Select-Object -Last 1).Trim()
  if ($kfxZip -and (Test-Path $kfxZip)) { & "$cal\calibre-customize.exe" --add-plugin $kfxZip; Say "KFX Input installed" }
  else { Say "WARN KFX Input not resolved - do the ONE GUI step: Calibre>Preferences>Plugins>Get new plugins>KFX Input" }
} catch { Say "WARN KFX Input auto-install failed: $_ - GUI fallback: Calibre>Preferences>Plugins>Get new plugins>KFX Input" }

# 4) MinIO client + alias (creds injected on the config CD -> C:\kindle\kindle-minio.env).
Say "installing mc + configuring the MinIO alias"
$mc = "$env:ProgramFiles\minio-client\mc.exe"; New-Item -ItemType Directory -Force (Split-Path $mc) | Out-Null
Invoke-WebRequest "https://dl.min.io/client/mc/release/windows-amd64/mc.exe" -OutFile $mc
$envf = "C:\kindle\kindle-minio.env"
if (Test-Path $envf) {
  $kv = @{}; Get-Content $envf | ForEach-Object { if ($_ -match '^(\w+)=(.*)$') { $kv[$matches[1]] = $matches[2] } }
  & $mc alias set weyland $kv['MINIO_ENDPOINT'] $kv['MINIO_ACCESS_KEY'] $kv['MINIO_SECRET_KEY'] | Out-Null
  Say "mc alias 'weyland' -> $($kv['MINIO_ENDPOINT']) (bucket $($kv['MINIO_BUCKET']))"
} else { Say "WARN C:\kindle\kindle-minio.env missing - extract can't upload; set the alias by hand." }

# 5) Register the auto-extract watcher as a scheduled task at logon (survives reboots -> on-demand re-runs are
#    zero-touch: start the VM, Kindle re-syncs, this fires again). It waits for the library to finish downloading,
#    then runs the extract ONCE per sync.
Say "registering the auto-extract watcher (logon scheduled task)"
$action  = New-ScheduledTaskAction  -Execute "powershell.exe" -Argument "-ExecutionPolicy Bypass -File C:\kindle\kindle-autorun.ps1"
$trigger = New-ScheduledTaskTrigger -AtLogOn
Register-ScheduledTask -TaskName "KindleAutoExtract" -Action $action -Trigger $trigger -RunLevel Highest -Force -User "kindle" | Out-Null

# 6) Launch Kindle-for-PC + start the watcher now. YOUR ONE STEP: sign into Amazon in the window that opens.
Say "launching Kindle-for-PC - SIGN IN when it opens; extraction is automatic after the library syncs"
$k = Get-ChildItem "$env:LOCALAPPDATA\Amazon\Kindle","$env:ProgramFiles*\Amazon\Kindle" -Filter Kindle.exe -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
if ($k) { Start-Process $k.FullName }
Start-ScheduledTask -TaskName "KindleAutoExtract"
Say "setup complete."
