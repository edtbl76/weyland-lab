#!/usr/bin/env python3
import os
import threading
import httpx
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

DAGSTER_URL = os.environ.get("DAGSTER_GRAPHQL_URL", "http://192.168.1.243:30088/graphql")
WATCH_PATH = os.environ.get("WEYLAND_WATCH_PATH",
    "/home/edwardmangini/Documents/ObsidianVault/Projects/weyland/weyland.md")
DEBOUNCE_SECONDS = int(os.environ.get("WEYLAND_DEBOUNCE_SECONDS", "30"))

LAUNCH_RUN_MUTATION = """
mutation LaunchRun {
  launchRun(executionParams: {
    selector: {
      repositoryLocationName: "weyland_pipeline",
      repositoryName: "__repository__",
      jobName: "weyland_ingestion_job"
    }
    runConfigData: {}
  }) {
    __typename
    ... on LaunchRunSuccess { run { runId } }
    ... on PythonError { message }
  }
}
"""


class WeylandWatchHandler(FileSystemEventHandler):
    def __init__(self):
        self._timer: threading.Timer | None = None
        self._lock = threading.Lock()

    def on_modified(self, event):
        if event.src_path != WATCH_PATH:
            return
        self._schedule_trigger()

    def on_created(self, event):
        if event.src_path != WATCH_PATH:
            return
        self._schedule_trigger()

    def _schedule_trigger(self):
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(DEBOUNCE_SECONDS, self._trigger)
            self._timer.start()

    def _trigger(self):
        print(f"[weyland-watcher] Change detected — triggering Dagster run")
        try:
            response = httpx.post(
                DAGSTER_URL,
                json={"query": LAUNCH_RUN_MUTATION},
                timeout=10,
            )
            data = response.json()
            result = data.get("data", {}).get("launchRun", {})
            if result.get("__typename") == "LaunchRunSuccess":
                print(f"[weyland-watcher] Run launched: {result['run']['runId']}")
            else:
                print(f"[weyland-watcher] Launch failed: {result}")
        except Exception as e:
            print(f"[weyland-watcher] Error triggering run: {e}")


if __name__ == "__main__":
    watch_dir = os.path.dirname(WATCH_PATH)
    print(f"[weyland-watcher] Watching {WATCH_PATH} (debounce {DEBOUNCE_SECONDS}s)")

    handler = WeylandWatchHandler()
    observer = Observer()
    observer.schedule(handler, path=watch_dir, recursive=False)
    observer.start()

    try:
        observer.join()
    except KeyboardInterrupt:
        observer.stop()
        observer.join()
