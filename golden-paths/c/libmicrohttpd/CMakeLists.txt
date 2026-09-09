cmake_minimum_required(VERSION 3.20)
project(golden_c_libmicrohttpd C)

# Golden path — C / libmicrohttpd (B160). GNU libmicrohttpd (a system dep) serves the contract;
# the payload builders are factored out so they are unit-testable. Contract: /health /ready /metrics /hello.
set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)

find_package(PkgConfig REQUIRED)
pkg_check_modules(MHD REQUIRED libmicrohttpd)

add_executable(golden-c-libmicrohttpd src/main.c src/handlers.c)
target_include_directories(golden-c-libmicrohttpd PRIVATE src ${MHD_INCLUDE_DIRS})
target_link_libraries(golden-c-libmicrohttpd PRIVATE ${MHD_LIBRARIES})

# The test binary asserts on the payload builders (no HTTP layer). A `--selfcheck` arg triggers the
# deliberate failure; without that branch, --selfcheck falls through to the passing checks (exit 0) so
# the lane self-check reports LANE BROKEN — fail-closed on a rename.
enable_testing()
add_executable(unit_tests test/handlers_test.c src/handlers.c)
target_include_directories(unit_tests PRIVATE src)
add_test(NAME unit COMMAND unit_tests)
