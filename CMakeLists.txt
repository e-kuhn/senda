cmake_minimum_required(VERSION 3.28)

set(LLVM_PREFIX "/opt/homebrew/opt/llvm")

project(senda
    VERSION 0.1.0
    DESCRIPTION "Automotive DSL built on the Rupa language"
    LANGUAGES CXX C)

set(CMAKE_CXX_STANDARD 26)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Use Homebrew LLVM's libc++ (required for C++ module support)
execute_process(COMMAND xcrun --show-sdk-path OUTPUT_VARIABLE MACOS_SDK_PATH OUTPUT_STRIP_TRAILING_WHITESPACE)
add_compile_options(-nostdinc++ -isystem ${LLVM_PREFIX}/include/c++/v1 -isysroot ${MACOS_SDK_PATH})
add_link_options(-nostdlib++ -L${LLVM_PREFIX}/lib/c++ -Wl,-rpath,${LLVM_PREFIX}/lib/c++ -lc++)

# Warning flags for senda targets
function(senda_target_settings target)
    target_compile_options(${target} PRIVATE -Wall -Wextra -Werror)
endfunction()

#-------------------------------------------------------------------------------
# Dependencies
#-------------------------------------------------------------------------------

include(FetchContent)
set(CMAKE_POLICY_DEFAULT_CMP0135 NEW)

# expat (SAX XML parser for ARXML compiler — replaces pugixml)
FetchContent_Declare(
    expat
    SYSTEM
    GIT_REPOSITORY https://github.com/libexpat/libexpat.git
    GIT_TAG R_2_6_4
    SOURCE_SUBDIR expat
    EXCLUDE_FROM_ALL
)
set(EXPAT_BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(EXPAT_BUILD_TOOLS OFF CACHE BOOL "" FORCE)
set(EXPAT_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
set(EXPAT_BUILD_DOCS OFF CACHE BOOL "" FORCE)
set(EXPAT_SHARED_LIBS OFF CACHE BOOL "" FORCE)
FetchContent_MakeAvailable(expat)

# Google Test
FetchContent_Declare(
    googletest
    SYSTEM
    GIT_REPOSITORY https://github.com/google/googletest
    GIT_TAG v1.16.0
    EXCLUDE_FROM_ALL
)
FetchContent_MakeAvailable(googletest)

#-------------------------------------------------------------------------------
# Rupa (submodule — provides rupa.lexer, rupa.parser, rupa.fir, rupa.domain,
#        rupa.compiler, rupa.driver, rupa.sema, kore)
#-------------------------------------------------------------------------------

add_subdirectory(external/rupa)

#-------------------------------------------------------------------------------
# Senda Libraries
#-------------------------------------------------------------------------------

add_subdirectory(src/domains)
add_subdirectory(src/compiler-arxml)
add_subdirectory(src/emitter-arxml)

#-------------------------------------------------------------------------------
# Senda CLI
#-------------------------------------------------------------------------------

add_executable(senda src/main.cpp)
target_link_libraries(senda PRIVATE
    rupa.driver
    rupa.sema
    rupa.compiler
    senda.compiler.arxml
    senda.domains
)
senda_target_settings(senda)

#-------------------------------------------------------------------------------
# Testing
#-------------------------------------------------------------------------------

enable_testing()
add_subdirectory(test/compiler-arxml)
add_subdirectory(test/emitter-arxml)
add_subdirectory(test/integration)
