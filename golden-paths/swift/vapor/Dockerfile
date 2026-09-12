# Golden path Swift / Vapor. Multi-stage: swift build → slim Swift runtime.
# buildkit → registry.weyland.lab/golden-swift-vapor.
FROM swift:6.0-jammy AS build
WORKDIR /build
# Resolve deps against the committed Package.resolved first (cache-friendly layer).
COPY Package.swift Package.resolved ./
RUN swift package resolve
COPY Sources ./Sources
# Tests/ dirs must exist for SwiftPM to validate the manifest, even when building only --product Run.
COPY Tests ./Tests
RUN swift build -c release --product Run \
    && install -m 0755 "$(swift build -c release --product Run --show-bin-path)/Run" /build/Run

# Runtime: swift:*-slim carries the Swift runtime shared libraries (Foundation/NIO/etc.) but not
# the compiler — so a dynamically linked Vapor binary runs. A plain ubuntu base would fail to load
# libswift* at start. curl is added for the ephemeral smoke.
FROM swift:6.0-jammy-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -u 10001 -m appuser
COPY --from=build /build/Run ./Run
COPY smoke.sh ./
USER 10001
EXPOSE 8080
CMD ["./Run"]
