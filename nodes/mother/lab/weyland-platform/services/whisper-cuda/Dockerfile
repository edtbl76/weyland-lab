# whisper-cuda — whisper.cpp v1.9.5 built for timberback's RTX 5070 Ti (Blackwell, compute capability 12.0), plus the
# OpenAI-compatible /v1/audio/transcriptions shim (shim.py). B134 plan step 2, 2026-11-14: replaces CPU-only CT 103.
#
# Why our own build: the upstream CUDA image (ghcr.io/ggml-org/whisper.cpp:main-cuda) is a rolling tag with no tag for
# v1.9.5, and it compiles only for architectures 75/80/86/90, so on this card it would JIT from PTX at startup.
# CUDA 12.8 is the first toolkit with Blackwell (sm_120) support; base images pinned by digest (pushed 2025-03-13).
#
# Hand-tagged, NOT in scripts/ci/images.tsv: registry.weyland.lab/whisper-cuda:<whisper.cpp version>. It changes only on
# a whisper.cpp or dependency bump (same reasoning as weyland-jupyter). Build and push: docs/runbooks/transcription-whisper.md.
ARG CUDA_DEVEL=nvidia/cuda:12.8.1-devel-ubuntu24.04@sha256:520292dbb4f755fd360766059e62956e9379485d9e073bbd2f6e3c20c270ed66
ARG CUDA_RUNTIME=nvidia/cuda:12.8.1-runtime-ubuntu24.04@sha256:ebef3c171eeef0298e4eb2e4be843105edf3b8b0ac45e0b43acee358e8046867

FROM ${CUDA_DEVEL} AS build
ARG WHISPER_VERSION=v1.9.5
ARG WHISPER_COMMIT=d1be6fde11ac6e0407606b4e42fe72d34add8037
RUN apt-get update \
 && apt-get install -y --no-install-recommends git cmake build-essential ca-certificates \
 && rm -rf /var/lib/apt/lists/*
# Clone the release tag and refuse to build if it no longer points at the commit we reviewed.
RUN git clone --depth 1 --branch "${WHISPER_VERSION}" https://github.com/ggml-org/whisper.cpp /src \
 && test "$(git -C /src rev-parse HEAD)" = "${WHISPER_COMMIT}"
WORKDIR /src
# Static libs so the runtime stage needs only the one binary; -j4 keeps nvcc inside mother's memory headroom.
RUN cmake -B build -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=120 -DCMAKE_BUILD_TYPE=Release \
      -DBUILD_SHARED_LIBS=OFF -DWHISPER_BUILD_TESTS=OFF \
 && cmake --build build -j4 --target whisper-server

FROM ${CUDA_RUNTIME}
RUN apt-get update \
 && apt-get install -y --no-install-recommends libgomp1 python3 python3-venv curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*
COPY --from=build /src/build/bin/whisper-server /usr/local/bin/whisper-server
# Fail the build if any shared library the binary needs is missing (libcuda.so.1 comes from the driver at runtime).
RUN out="$(ldd /usr/local/bin/whisper-server)" || { echo "ldd failed"; exit 1; }; \
    missing="$(printf '%s\n' "$out" | grep "not found" | grep -v libcuda.so || true)"; \
    if [ -n "$missing" ]; then echo "missing shared libraries:"; echo "$missing"; exit 1; fi
# The shim's dependencies, fully locked (requirements.in -> requirements.txt via `uv pip compile --exclude-newer`).
COPY requirements.txt /app/requirements.txt
RUN python3 -m venv /app/venv \
 && /app/venv/bin/pip install --no-cache-dir --no-deps -r /app/requirements.txt
COPY shim.py /app/shim.py
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin whisper
USER 10001
WORKDIR /app
# The pod runs two containers from this image: whisper-server (default) and the shim (command overridden).
ENTRYPOINT ["/usr/local/bin/whisper-server"]
