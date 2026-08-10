# main.py
import sys
import ctypes
import os
from PyQt6.QtWidgets import QApplication
from gui import AuroraLite

if __name__ == '__main__':
    # 1. Configurar red y hardware usando C (dns_core.dll)
    lib_ext = '.dll' if os.name == 'nt' else '.so'
    try:
        dns_lib = ctypes.CDLL(os.path.abspath(f'./dns_core{lib_ext}'))
        dns_lib.configurar_motor_chromium()
    except OSError:
        print(f"Error: No se encontró dns_core{lib_ext}.")
        sys.exit(1)
    
    # 2. Inicializar la app de PyQt
    app = QApplication(sys.argv)
    
    # 3. Lanzar la ventana principal
    browser = AuroraLite()
    browser.show()
    
    sys.exit(app.exec())