# Golden path Perl / Mojolicious. Multi-stage: perl:5.40 build (cpanm --installdeps into a
# self-contained local::lib) -> perl:5.40-slim run. buildkit -> registry.weyland.lab/golden-perl-mojolicious.
FROM perl:5.40 AS build
WORKDIR /app
COPY cpanfile ./
# Install runtime + test deps into /app/local (local::lib layout) so the runtime stage carries
# no build toolchain. Mojolicious is pure-Perl, so no compiler is exercised here.
RUN cpanm --local-lib=/app/local --installdeps --notest .
COPY . .

# Minimal non-root runtime: the interpreter + the vendored deps + curl/sh for the .smoke harness.
FROM perl:5.40-slim
WORKDIR /app
RUN apt-get update \
  && apt-get install -y --no-install-recommends curl ca-certificates \
  && rm -rf /var/lib/apt/lists/* \
  && useradd -u 10001 -m appuser
COPY --from=build /app /app
ENV PERL5LIB=/app/local/lib/perl5
ENV PATH=/app/local/bin:$PATH
USER 10001
EXPOSE 8080
CMD ["perl", "script/golden_perl_mojolicious"]
