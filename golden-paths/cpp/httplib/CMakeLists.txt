cmake_minimum_required(VERSION 3.20)
project(golden_cpp_httplib CXX)

# Golden path — C++ / cpp-httplib (B160). Single-header HTTP lib, fetched (not vendored) so the golden
# path stays tiny. Contract: /health /ready /metrics /hello. Two targets: the server + a doctest suite.
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

include(FetchContent)
FetchContent_Declare(httplib GIT_REPOSITORY https://github.com/yhirose/cpp-httplib.git GIT_TAG v0.18.3)
FetchContent_Declare(doctest GIT_REPOSITORY https://github.com/doctest/doctest.git GIT_TAG v2.4.11)
FetchContent_MakeAvailable(httplib doctest)
find_package(Threads REQUIRED)

# The server binary. Static libstdc++/libgcc so the runtime image needs only libc + pthread.
add_executable(golden-cpp-httplib src/main.cpp)
target_include_directories(golden-cpp-httplib PRIVATE src)
target_link_libraries(golden-cpp-httplib PRIVATE httplib::httplib Threads::Threads)
target_link_options(golden-cpp-httplib PRIVATE -static-libstdc++ -static-libgcc)

# The test binary (doctest). Contract tests + the deliberate test (in the "selfcheck" suite).
enable_testing()
add_executable(unit_tests test/main.cpp test/contract_test.cpp test/deliberate_test.cpp)
target_include_directories(unit_tests PRIVATE src)
target_link_libraries(unit_tests PRIVATE doctest::doctest)
add_test(NAME unit COMMAND unit_tests)
