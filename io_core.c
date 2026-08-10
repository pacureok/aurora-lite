// io_core.c
#include <stdio.h>
#include <stdlib.h>

#ifdef _WIN32
#define EXPORT __declspec(dllexport)
#else
#define EXPORT
#endif

EXPORT int reservar_espacio(const char* ruta_archivo, long long tamano_total) {
    FILE* archivo = fopen(ruta_archivo, "wb");
    if (!archivo) return 0;
    
    if (tamano_total > 0) {
        _fseeki64(archivo, tamano_total - 1, SEEK_SET); 
        fputc('\0', archivo);
    }
    
    fclose(archivo);
    return 1;
}

// Recibe la posición en 64 bits (long long)
EXPORT int escribir_fragmento_rapido(const char* ruta_archivo, const char* datos, int longitud, long long posicion) {
    FILE* archivo = fopen(ruta_archivo, "rb+");
    
    if (!archivo) {
        // Fallback seguro: si rb+ falla porque no existe, lo creamos primero
        archivo = fopen(ruta_archivo, "wb");
        if (!archivo) return 0;
        fclose(archivo);
        archivo = fopen(ruta_archivo, "rb+");
        if (!archivo) return 0;
    }
    
    // Saltamos exactamente a la posición indicada por Python
    _fseeki64(archivo, posicion, SEEK_SET);
    size_t escritos = fwrite(datos, 1, longitud, archivo);
    fclose(archivo);
    
    return (escritos == (size_t)longitud) ? 1 : 0;
}