// logic.cpp
#include <string>
#include <cstring>
#include <algorithm>

#ifdef _WIN32
#define EXPORT __declspec(dllexport)
#else
#define EXPORT
#endif

extern "C" {
    // Agregamos el límite estricto de memoria (max_len)
    EXPORT void format_url(const char* input_url, char* output_url, int max_len) {
        std::string text(input_url);
        
        text.erase(0, text.find_first_not_of(" \t\n\r"));
        text.erase(text.find_last_not_of(" \t\n\r") + 1);

        std::string final_url;

        if (text.empty()) {
            final_url = "https://www.google.com";
        } else if (text.rfind("http://", 0) == 0 || text.rfind("https://", 0) == 0 || text.rfind("about:", 0) == 0) {
            final_url = text;
        } else {
            bool has_space = (text.find(' ') != std::string::npos);
            bool has_dot = (text.find('.') != std::string::npos);

            if (has_dot && !has_space) {
                final_url = "https://" + text;
            } else {
                std::string query = "";
                for (char c : text) {
                    if (c == ' ') query += "+";
                    else query += c;
                }
                final_url = "https://www.google.com/search?q=" + query;
            }
        }

        // Copia segura respetando el tamaño del búfer de Python
        std::strncpy(output_url, final_url.c_str(), max_len - 1);
        output_url[max_len - 1] = '\0'; // Asegurar el terminador nulo
    }
}