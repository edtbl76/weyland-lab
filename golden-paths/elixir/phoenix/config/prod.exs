import Config

# LAN-only $0 canary — served over plain HTTP, so the generated `force_ssl` (which redirects http→https
# and would 301 the smoke's curl) is deliberately removed. A real internet-facing service re-enables
# force_ssl + HSTS here. Runtime production config (port, secret_key_base) lives in config/runtime.exs.
config :logger, level: :info
