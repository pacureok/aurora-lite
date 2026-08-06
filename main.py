# main.py
import sys
from PyQt6.QtWidgets import QApplication
from DNS import configurar_motor_chromium
from gui import AuroraLite

if __name__ == '__main__':
    # 1. Aplicar aceleración por hardware y DNS 1.1.1.1 antes de iniciar la app
    configurar_motor_chromium()
    
    # 2. Iniciar la aplicación
    app = QApplication(sys.argv)
    
    # 3. Mostrar la ventana principal
    window = AuroraLite()
    window.show()
    
    sys.exit(app.exec())