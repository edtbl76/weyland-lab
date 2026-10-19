# Demo — rogueone GPU driver drift: the hold and the check

On 2026-10-09 unattended-upgrades moved rogueone's userspace NVIDIA driver to 595.99.02 while the loaded kernel module
stayed 595.91.07 until the next reboot (2026-10-19). For nine days `nvidia-smi` failed with `Driver/library version
mismatch` and nothing alerted; Ollama kept the GPU only because it had run since boot with the old libraries loaded.
This demo shows the two halves of the fix (B226): the NVIDIA packages held back from unattended-upgrades, and an hourly
check of the loaded module against the installed driver that pushes to Uptime Kuma — including a forced drift that
reached the owner's Telegram. Runbook: [model-serving-ollama.md § NVIDIA driver](../runbooks/model-serving-ollama.md).

There is no UI deliverable beyond the Kuma monitor `gpu-driver-drift` — the CLI walkthrough is the demo.

## CLI walkthrough (RUN 2026-10-19 on rogueone, after the owner's reboot)

**1. The hold is installed and unattended-upgrades reads it:**

[rogueone]
```
sudo unattended-upgrade --dry-run --debug 2>&1 | grep -iE "blacklist" | head -5
```
Output (run): `Initial blacklist: nvidia- libnvidia- xserver-xorg-video-nvidia- linux-modules-nvidia-`.

**2. The check, today — module and driver agree after the reboot:**

[rogueone]
```
python3 /home/edwardmangini/IdeaProjects/weyland/scripts/gpu_driver_drift.py --no-push; echo "exit=$?"
```
Output (run): `gpu-driver-drift: OK — loaded module 595.99.02 == nvidia-driver-595-open 595.99.02`, `exit=0`.

**3. The check, on the nine days' state** — the module line from before the reboot, through the test seam:

[rogueone]
```
GPU_DRIFT_MODULE_FILE=<file holding the old /proc line> python3 /home/edwardmangini/IdeaProjects/weyland/scripts/gpu_driver_drift.py; echo "exit=$?"
```
Output (run): `DRIFT: loaded module 595.91.07 != installed nvidia-driver-595-open 595.99.02 — reboot to load the installed
driver (until then a restarted Ollama may lose the GPU)`, `exit=1`. It pushed `down`; **the owner received the Telegram
alert**; the next plain run pushed `up` (exit 0) and **the recovery message arrived too**.

**4. The timer runs it hourly:** `systemctl --user list-timers gpu-driver-drift.timer` showed the next run an hour out;
the first timer run logged the OK line above with `Result=success`. `kuma_push_check.py`: `OK — 6 push monitor(s) match`.

## What it does not need

The check reads `/proc/driver/nvidia/version` and runs `dpkg-query`: no root, no network beyond the Kuma push. dpkg
also lists driver names it knows but never installed (status `un`, empty version, e.g. `nvidia-driver-595`) — only
`ii` rows count, so those never read as a second driver.

Creates no data; the forced-drift file is a scratch file outside the repo.
