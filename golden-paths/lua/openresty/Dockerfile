# Golden path Lua / OpenResty. Single-stage on the official OpenResty alpine image (nginx + LuaJIT).
# buildkit → registry.weyland.lab/golden-lua-openresty. Runs non-root: the whole process is `appuser`,
# port 8080 (> 1024) binds unprivileged, and every writable path (pid, temp, logs) is /tmp or stdout/stderr.
FROM openresty/openresty:alpine

RUN apk add --no-cache curl \
    && adduser -D -u 10001 appuser

WORKDIR /app
COPY nginx.conf /app/nginx.conf
COPY lua/ /app/lua/
COPY smoke.sh /app/smoke.sh
# nginx opens the prefix-default error log (/app/logs/error.log) during early init, before the config's
# `error_log /dev/stderr` takes over — create it so startup is alert-free (runtime logs still go to stderr).
RUN mkdir -p /app/logs && chown -R 10001:10001 /app

USER 10001
EXPOSE 8080

# `-p /app` sets the prefix; the config points pid + temp at /tmp and logs at stdout/stderr, so nothing
# under the read-only prefix is written. `daemon off;` keeps PID 1 in the foreground for the container.
CMD ["openresty", "-p", "/app", "-c", "/app/nginx.conf", "-g", "daemon off;"]
