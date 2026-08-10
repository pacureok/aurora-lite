// dns_core.c
#include <stdlib.h>
#include <stdio.h>

#ifdef _WIN32
#define EXPORT __declspec(dllexport)
#else
#define EXPORT
#endif

EXPORT void configurar_motor_chromium() {
    const char* flags = "--enable-gpu --enable-gpu-rasterization --ignore-gpu-blocklist "
                        "--enable-oop-rasterization "
                        "--dns-over-https-templates=\"https://cloudflare-dns.com/dns-query\" "
                        "--enable-features=dns-over-https,NetworkPrediction "
                        "--prerender-from-omnibox "
                        "--enable-webaudio --enable-accelerated-video-decode "
                        "--autoplay-policy=no-user-gesture-required "
                        "--disable-blink-features=AutomationControlled --disable-infobars";
    
    #ifdef _WIN32
        // _putenv_s hace una copia segura en memoria gestionada por el SO
        _putenv_s("QTWEBENGINE_CHROMIUM_FLAGS", flags);
    #else
        setenv("QTWEBENGINE_CHROMIUM_FLAGS", flags, 1);
    #endif
}