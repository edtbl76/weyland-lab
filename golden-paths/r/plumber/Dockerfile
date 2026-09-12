# Golden path R / plumber. Multi-stage: rocker/r-ver:4 (install packages) -> rocker/r-ver:4 run.
# buildkit -> registry.weyland.lab/golden-r-plumber.
# rocker/r-ver serves version-pinned binary packages from the Posit Package Manager, so
# install.packages pulls precompiled binaries (no per-dep source compile). The runtime stage
# shares the exact base, so every system .so the copied library links against is already present;
# it adds only curl (for the .smoke harness) and a non-root user, and drops the apt caches.
FROM rocker/r-ver:4 AS build
RUN Rscript -e 'install.packages(c("plumber", "jsonlite", "testthat"))' \
  && Rscript -e 'stopifnot(all(c("plumber","jsonlite","testthat") %in% rownames(installed.packages())))'

FROM rocker/r-ver:4
WORKDIR /app
RUN apt-get update \
  && apt-get install -y --no-install-recommends curl ca-certificates \
  && rm -rf /var/lib/apt/lists/* \
  && useradd -u 10001 -m appuser
COPY --from=build /usr/local/lib/R/site-library /usr/local/lib/R/site-library
COPY payloads.R plumber.R entrypoint.R smoke.sh ./
USER 10001
EXPOSE 8080
CMD ["Rscript", "entrypoint.R"]
