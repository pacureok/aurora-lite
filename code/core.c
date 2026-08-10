// core.c
#include <stdio.h>

// Compilar como librería compartida (.dll en Windows o .so en Linux)
#ifdef _WIN32
#define EXPORT __declspec(dllexport)
#else
#define EXPORT
#endif

EXPORT const char* get_browser_name() {
    return "Aurora-Lite";
}

EXPORT const char* get_initial_url() {
    return "https://www.google.com";
}
