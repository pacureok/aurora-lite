// logic.cpp
#include <string>
#include <cstring>

#ifdef _WIN32
#define EXPORT __declspec(dllexport)
#else
#define EXPORT
#endif

extern "C" {
    // Función que verifica si la URL tiene http:// o https://
    // Si no lo tiene, se lo agrega.
    EXPORT void format_url(const char* input_url, char* output_url) {
        std::string url(input_url);
        
        if (url.find("http://") != 0 && url.find("https://") != 0) {
            url = "https://" + url;
        }
        
        // Copiar el resultado al buffer de salida
        std::strcpy(output_url, url.c_str());
    }
}