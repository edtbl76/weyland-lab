#!/usr/bin/env bash
# Shared fixture resolution for the per-language lanes (run-lang-tests.sh, run-lang-scan.sh,
# coverage-ratchet.sh).
#
# B153 FIXTURE-SWITCH: each lane's fixture+probe is now the language's GOLDEN PATH, not a throwaway
# hello app. The golden path is one artifact that is both the blessed service template AND the
# build-infra canary — so the B88 tests/lang/<lang> hello fixtures are retired. `shell` has no golden
# path (it is a lane, not a service language), so it keeps its hello fixture.
#
# The WEYLAND_LANG_FIXTURE_DIR override is PRESERVED and still means `<dir>/<lang>`: the bats guards
# inject a temp fixture tree that way, and that seam is how those tests stay hermetic. Only the
# DEFAULT (no override) changed — from tests/lang/<lang> to the golden path.
resolve_fixture() {
  local lang="$1" repo="$2"
  if [ -n "${WEYLAND_LANG_FIXTURE_DIR:-}" ]; then
    printf '%s/%s\n' "$WEYLAND_LANG_FIXTURE_DIR" "$lang"
    return 0
  fi
  case "$lang" in
    python)     printf '%s/golden-paths/python/fastapi\n'       "$repo" ;;
    java)       printf '%s/golden-paths/java/spring-boot\n'     "$repo" ;;
    go)         printf '%s/golden-paths/go/nethttp\n'           "$repo" ;;
    rust)       printf '%s/golden-paths/rust/axum\n'            "$repo" ;;
    dotnet)     printf '%s/golden-paths/dotnet/aspnet\n'        "$repo" ;;
    kotlin)     printf '%s/golden-paths/kotlin/ktor\n'          "$repo" ;;
    scala)      printf '%s/golden-paths/scala/http4s\n'         "$repo" ;;
    php)        printf '%s/golden-paths/php/slim\n'             "$repo" ;;
    ruby)       printf '%s/golden-paths/ruby/rails\n'           "$repo" ;;
    elixir)     printf '%s/golden-paths/elixir/phoenix\n'       "$repo" ;;
    clojure)    printf '%s/golden-paths/clojure/compojure\n'    "$repo" ;;
    cpp)        printf '%s/golden-paths/cpp/httplib\n'          "$repo" ;;
    c)          printf '%s/golden-paths/c/libmicrohttpd\n'      "$repo" ;;
    erlang)     printf '%s/golden-paths/erlang/cowboy\n'        "$repo" ;;
    julia)      printf '%s/golden-paths/julia/oxygen\n'         "$repo" ;;
    lua)        printf '%s/golden-paths/lua/openresty\n'        "$repo" ;;
    swift)      printf '%s/golden-paths/swift/vapor\n'          "$repo" ;;
    dart)       printf '%s/golden-paths/dart/shelf\n'           "$repo" ;;
    r)          printf '%s/golden-paths/r/plumber\n'            "$repo" ;;
    perl)       printf '%s/golden-paths/perl/mojolicious\n'     "$repo" ;;
    haskell)    printf '%s/golden-paths/haskell/scotty\n'       "$repo" ;;
    ada)        printf '%s/golden-paths/ada/aws\n'              "$repo" ;;
    javascript) printf '%s/golden-paths/node/express\n'         "$repo" ;;
    typescript) printf '%s/golden-paths/node/nestjs\n'          "$repo" ;;
    react)      printf '%s/golden-paths/frontend/vite-react\n'  "$repo" ;;
    nextjs)     printf '%s/golden-paths/frontend/nextjs\n'      "$repo" ;;
    react-native) printf '%s/golden-paths/mobile/react-native\n' "$repo" ;;  # B164 mobile CLIENT
    flutter)    printf '%s/golden-paths/mobile/flutter\n'       "$repo" ;;    # B164 mobile CLIENT
    shell)      printf '%s/tests/lang/shell\n'                  "$repo" ;;
    *)          return 1 ;;
  esac
}
