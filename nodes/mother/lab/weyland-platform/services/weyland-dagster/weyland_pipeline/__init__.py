# B51 — error tracking → GlitchTip (Sentry SDK). Inits when the user-code loads the code location; the default
# logging integration captures Dagster's error-level run-failure logs. Empty DSN = no-op (dev-safe).
import os

import sentry_sdk
from sentry_sdk.integrations.modules import ModulesIntegration

sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN", ""),
    environment=os.getenv("SENTRY_ENVIRONMENT", "weyland"),
    traces_sample_rate=0.0,
    send_default_pii=False,
    # Dagster's huge dep tree bloats the SDK `modules` (installed-packages) list past GlitchTip's event-size
    # limit → GlitchTip 200s the ingest then silently DROPS the event. Disable just that integration; keep
    # logging/excepthook (which capture the actual Dagster run failures).
    disabled_integrations=[ModulesIntegration()],
)

from weyland_pipeline.definitions import defs
