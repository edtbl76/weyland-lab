# weyland-watcher

inotify-based file watcher that triggers a Dagster ingestion run when `weyland.md` changes.

## Install on rogueone

```bash
# 1. Install dependencies
pip3 install --user watchdog httpx

# 2. Copy watcher script
mkdir -p ~/.local/lib/weyland-watcher
cp watcher.py ~/.local/lib/weyland-watcher/

# 3. Create env file
mkdir -p ~/.config/weyland-watcher
cat > ~/.config/weyland-watcher/env << 'EOF'
DAGSTER_GRAPHQL_URL=http://192.168.1.243:30088/graphql
WEYLAND_WATCH_PATH=/home/edwardmangini/Documents/ObsidianVault/Projects/weyland/weyland.md
WEYLAND_DEBOUNCE_SECONDS=30
EOF

# 4. Install and enable systemd user service
mkdir -p ~/.config/systemd/user
cp weyland-watcher.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now weyland-watcher

# 5. Check status
systemctl --user status weyland-watcher
journalctl --user -u weyland-watcher -f
```

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `DAGSTER_GRAPHQL_URL` | `http://192.168.1.243:30088/graphql` | Dagster webserver GraphQL endpoint |
| `WEYLAND_WATCH_PATH` | Obsidian vault path | Absolute path to weyland.md |
| `WEYLAND_DEBOUNCE_SECONDS` | `30` | Seconds to wait after last write before triggering |

## Behaviour

- Watches the directory containing `weyland.md` for `modified` and `created` events
- Trailing-edge debounce: resets the timer on each event; fires once after `DEBOUNCE_SECONDS` of quiet
- On trigger: POSTs `launchRun` GraphQL mutation to Dagster webserver
- systemd `Restart=on-failure` with 10s back-off ensures automatic recovery
- The Dagster 15-minute schedule provides pipeline coverage if the watcher is down
