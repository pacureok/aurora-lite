# gestor_descargas.py
import ctypes
import os
import requests
import threading

# Cargar la librería de C ultrarrápida
lib_ext = '.dll' if os.name == 'nt' else '.so'
try:
    io_lib = ctypes.CDLL(os.path.abspath(f'./io_core{lib_ext}'))
    io_lib.escribir_fragmento_rapido.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int, ctypes.c_int]
    io_lib.escribir_fragmento_rapido.restype = ctypes.c_int
except OSError:
    print(f"Error: No se encontró io_core{lib_ext}")

class DescargaResiliente(threading.Thread):
    def __init__(self, url, ruta_destino, callback_progreso=None):
        super().__init__()
        self.url = url
        self.ruta_destino = ruta_destino
        self.callback_progreso = callback_progreso
        self.detenido = False

    def run(self):
        # 1. Comprobar si el archivo ya existe para reanudarlo
        bytes_descargados = 0
        modo_anexar = 0 # 0 para nuevo, 1 para anexar

        if os.path.exists(self.ruta_destino):
            bytes_descargados = os.path.getsize(self.ruta_destino)
            modo_anexar = 1

        # 2. Configurar cabeceras para reanudar donde se quedó
        cabeceras = {'Range': f'bytes={bytes_descargados}-'}
        
        try:
            # stream=True y un timeout corto evitan que se quede colgado si se va el internet
            respuesta = requests.get(self.url, headers=cabeceras, stream=True, timeout=10)
            
            # Si el servidor no soporta reanudación (rango), empezamos de cero
            if respuesta.status_code not in [200, 206]:
                print("Error de conexión o archivo no encontrado.")
                return
                
            if respuesta.status_code == 200 and bytes_descargados > 0:
                print("El servidor no soporta reanudación. Reiniciando descarga...")
                bytes_descargados = 0
                modo_anexar = 0

            # Tamaño total para el porcentaje
            tamano_total = int(respuesta.headers.get('content-length', 0)) + bytes_descargados

            # 3. Bucle de descarga por fragmentos (Chunks)
            # 64KB por fragmento es un buen equilibrio para discos duros e internet inestable
            for fragmento in respuesta.iter_content(chunk_size=65536):
                if self.detenido:
                    break
                
                if fragmento:
                    # Enviar el fragmento a C para escribirlo en disco
                    ruta_c = self.ruta_destino.encode('utf-8')
                    exito = io_lib.escribir_fragmento_rapido(ruta_c, fragmento, len(fragmento), modo_anexar)
                    
                    if not exito:
                        print("Error crítico al escribir en disco.")
                        break
                        
                    # Después del primer fragmento, siempre anexamos
                    modo_anexar = 1 
                    bytes_descargados += len(fragmento)
                    
                    # Reportar progreso
                    if tamano_total > 0 and self.callback_progreso:
                        porcentaje = int((bytes_descargados / tamano_total) * 100)
                        self.callback_progreso(porcentaje, bytes_descargados, tamano_total)

        except requests.exceptions.RequestException as e:
            # Si el internet se corta, simplemente se detiene. 
            # La próxima vez que llames a este script, detectará el archivo y continuará.
            print(f"Descarga interrumpida por red inestable (se puede reanudar luego): {e}")

    def detener(self):
        self.detenido = True