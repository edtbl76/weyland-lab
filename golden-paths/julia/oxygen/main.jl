# Container entrypoint — boots the Oxygen.jl golden-path server on :8080 (blocking).
# Run with: julia --project=. main.jl
using OxygenGolden

OxygenGolden.start()
