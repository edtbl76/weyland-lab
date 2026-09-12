# Golden path Ada / AWS (Ada Web Server). Multi-stage: Alire (alr) builds AWS via gnat_native ->
# slim runtime with the binary + its shared libs. buildkit -> registry.weyland.lab/golden-ada-aws.
#
# TWO shared-lib families the AOT binary needs at runtime, and neither is a plain system lib:
#   * libgnat-14.so / libgnarl-14.so  -> the GNAT runtime, which lives INSIDE the Alire toolchain
#     (not in any apt package), so they are copied out of the build stage explicitly.
#   * libssl.so.3 / libcrypto.so.3    -> AWS links OpenSSL 3; curl pulls it into the runtime.
# The runtime base is ubuntu:24.04 to match the build base's glibc (2.39) and its OpenSSL 3.0 — a
# newer/older runtime is the glibc/openssl-skew trap the C golden path documents.
FROM ubuntu:24.04 AS build
ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /app

# The Ada compiler + builder come from Alire as binary crates (no apt gnat), which is what makes
# AWS 25.x's gnatcoll/libgpr chain resolve against a matched GNAT 14.2.1. The rest are what AWS's
# build shells out to, and are pre-installed here because a `rm apt-lists` build stage denies Alire
# its own apt fallback:
#   * build-essential  - the toolchain gcc compiles+links a C helper (xoscons / aws-os_lib-tmplt.c);
#                        needs C headers + crt*.o + make.
#   * libssl-dev       - AWS declares `openssl` as a system dep and links `-lssl -lcrypto`; the dev
#                        package carries the libssl.so/libcrypto.so link names (SOCKET=openssl).
#   * git / curl       - Alire clones its crate index over git and downloads the toolchain over curl.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      wget curl ca-certificates unzip git build-essential libssl-dev \
 && rm -rf /var/lib/apt/lists/*
RUN wget -q https://github.com/alire-project/alire/releases/download/v2.1.1/alr-2.1.1-bin-x86_64-linux.zip \
 && unzip -q alr-2.1.1-bin-x86_64-linux.zip -d /tmp/alr \
 && install -m755 /tmp/alr/bin/alr /usr/local/bin/alr \
 && rm -rf /tmp/alr alr-2.1.1-bin-x86_64-linux.zip

# The pin that builds AWS cleanly: gnat_native 14.2.1 + gprbuild 26.x, both Alire binary crates.
RUN alr -n settings --global --set toolchain.assistant false \
 && alr -n --force toolchain --select gnat_native=14.2.1 gprbuild=26.0.1

COPY alire.toml golden_ada_aws.gpr ./
COPY src src
COPY test test
RUN alr -n build --release

# Pull the GNAT runtime shared objects out of the toolchain so the runtime stage is self-contained.
RUN mkdir -p /gnatlib \
 && cp "$(find / -name libgnat-14.so 2>/dev/null | head -1)" /gnatlib/ \
 && cp "$(find / -name libgnarl-14.so 2>/dev/null | head -1)" /gnatlib/ \
 && test -f /gnatlib/libgnat-14.so && test -f /gnatlib/libgnarl-14.so

# ---- runtime ----
FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /app
# curl for the .smoke harness; it also drags in libssl3/libcrypto3 (OpenSSL 3) that AWS needs.
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates libssl3 \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin appuser
COPY --from=build /gnatlib/ /usr/local/lib/
RUN ldconfig
COPY --from=build /app/bin/server ./server
COPY smoke.sh ./
USER 10001
EXPOSE 8080
CMD ["./server"]
