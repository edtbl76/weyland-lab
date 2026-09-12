# Golden path Julia / Oxygen.jl. Multi-stage: julia build (instantiate + precompile the pinned Manifest)
# -> julia runtime (non-root, curl for the smoke). buildkit -> registry.weyland.lab/golden-julia-oxygen.
FROM julia:1.11 AS build
ENV JULIA_DEPOT_PATH=/depot
WORKDIR /app
# Pinned deps first so the precompile layer caches across source-only edits.
COPY Project.toml Manifest.toml ./
COPY src ./src
# Instantiate the committed Manifest (exact versions) and precompile into the depot.
RUN julia --project=. -e 'using Pkg; Pkg.instantiate(); Pkg.precompile()'

FROM julia:1.11
ENV JULIA_DEPOT_PATH=/depot
WORKDIR /app
# Non-root runtime user + curl for the ephemeral smoke.
RUN useradd -m -u 10001 appuser \
    && apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*
# Precompiled depot from the build stage (same /depot + /app paths -> cache stays valid, no recompile).
COPY --from=build --chown=10001:10001 /depot /depot
COPY --chown=10001:10001 Project.toml Manifest.toml main.jl ./
COPY --chown=10001:10001 src ./src
COPY --chown=10001:10001 smoke.sh ./
USER 10001
EXPOSE 8080
CMD ["julia", "--project=.", "main.jl"]
