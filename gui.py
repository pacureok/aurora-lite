# gui.py
import sys
import ctypes
import os
import re
import requests
from PyQt6.QtWidgets import (
    QMainWindow, QVBoxLayout, QLabel, QLineEdit, 
    QPushButton, QHBoxLayout, QTabWidget, QWidget,
    QMessageBox, QDialog, QFormLayout, QCheckBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QMenu
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import (
    QWebEngineProfile, QWebEnginePage, QWebEngineSettings,
    QWebEngineDownloadRequest
)
from PyQt6.QtCore import QUrl, QStandardPaths, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut

# --- 1. SINCRONIZACIÓN ESTRICTA DE TIPOS C/PYTHON ---
lib_ext = '.dll' if os.name == 'nt' else '.so'
try:
    core_lib = ctypes.CDLL(os.path.abspath(f'./core{lib_ext}'))
    logic_lib = ctypes.CDLL(os.path.abspath(f'./logic{lib_ext}'))
    io_lib = ctypes.CDLL(os.path.abspath(f'./io_core{lib_ext}'))
    
    core_lib.get_browser_name.restype = ctypes.c_char_p
    core_lib.get_initial_url.restype = ctypes.c_char_p
    
    # format_url: string input, string output, int buffer_size
    logic_lib.format_url.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
    
    # reservar_espacio: string ruta, long long tamano
    io_lib.reservar_espacio.argtypes = [ctypes.c_char_p, ctypes.c_longlong]
    io_lib.reservar_espacio.restype = ctypes.c_int
    
    # escribir_fragmento: string ruta, bytes datos, int longitud, long long posicion
    io_lib.escribir_fragmento_rapido.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int, ctypes.c_longlong]
    io_lib.escribir_fragmento_rapido.restype = ctypes.c_int
except OSError:
    print(f"Error: Faltan librerías compiladas (.dll/.so) en el directorio raíz.")
    sys.exit(1)


class DescargaResiliente(QThread):
    progreso = pyqtSignal(int, int)
    estado = pyqtSignal(int, str)

    def __init__(self, url, ruta_destino, id_fila, user_agent):
        super().__init__()
        self.url = url
        self.ruta_destino = ruta_destino
        self.id_fila = id_fila
        self.user_agent = user_agent
        self.detenido = False

    def run(self):
        bytes_descargados = 0

        if os.path.exists(self.ruta_destino):
            bytes_descargados = os.path.getsize(self.ruta_destino)

        cabeceras = {
            'Range': f'bytes={bytes_descargados}-',
            'User-Agent': self.user_agent
        }
        
        try:
            respuesta = requests.get(self.url, headers=cabeceras, stream=True, timeout=15)
            
            if respuesta.status_code not in [200, 206]:
                self.estado.emit(self.id_fila, "Error de Servidor ❌")
                return
                
            if respuesta.status_code == 200 and bytes_descargados > 0:
                bytes_descargados = 0

            tamano_total = int(respuesta.headers.get('content-length', 0)) + bytes_descargados
            ruta_c = self.ruta_destino.encode('utf-8')

            # --- 2. ANTICIPACIÓN DE DISCO ---
            # Si empezamos desde cero, reservamos todo el espacio de golpe
            if bytes_descargados == 0 and tamano_total > 0:
                io_lib.reservar_espacio(ruta_c, tamano_total)

            for fragmento in respuesta.iter_content(chunk_size=65536):
                if self.detenido:
                    self.estado.emit(self.id_fila, "Pausado ⏸️")
                    break
                
                if fragmento:
                    # Pasamos la variable bytes_descargados que actúa como posicion (long long)
                    exito = io_lib.escribir_fragmento_rapido(ruta_c, fragmento, len(fragmento), bytes_descargados)
                    
                    if not exito:
                        self.estado.emit(self.id_fila, "Error Disco ❌")
                        break
                        
                    bytes_descargados += len(fragmento)
                    
                    if tamano_total > 0:
                        porcentaje = int((bytes_descargados / tamano_total) * 100)
                        self.progreso.emit(self.id_fila, porcentaje)
                        self.estado.emit(self.id_fila, "Descargando...")

            if bytes_descargados >= tamano_total and tamano_total > 0:
                self.estado.emit(self.id_fila, "Completado ✅")
                self.progreso.emit(self.id_fila, 100)

        except requests.exceptions.RequestException:
            self.estado.emit(self.id_fila, "Red Interrumpida ⚠️")


class VentanaDescargas(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Gestor de Descargas C/C++ - Aurora-Lite")
        self.resize(650, 300)
        layout = QVBoxLayout(self)
        
        self.tabla = QTableWidget()
        self.tabla.setColumnCount(4)
        self.tabla.setHorizontalHeaderLabels(["Archivo", "Estado", "Progreso", "Ruta"])
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.tabla)
        
        self.hilos_activos = []

    def agregar_descarga(self, download: QWebEngineDownloadRequest):
        url_str = download.url().toString()
        nombre_archivo = os.path.basename(download.downloadFileName())
        directorio = download.downloadDirectory()
        ruta_completa = os.path.join(directorio, nombre_archivo)
        
        fila = self.tabla.rowCount()
        self.tabla.insertRow(fila)
        self.tabla.setItem(fila, 0, QTableWidgetItem(nombre_archivo))
        self.tabla.setItem(fila, 1, QTableWidgetItem("Iniciando..."))
        self.tabla.setItem(fila, 2, QTableWidgetItem("0%"))
        self.tabla.setItem(fila, 3, QTableWidgetItem(directorio))

        if url_str.startswith("blob:") or url_str.startswith("data:"):
            self._descarga_nativa(download, fila)
        else:
            download.cancel()
            hilo = DescargaResiliente(url_str, ruta_completa, fila, self.parent().agente_usuario)
            hilo.progreso.connect(lambda p, f=fila: self.actualizar_progreso_hilo(f, p))
            hilo.estado.connect(lambda st, f=fila: self.actualizar_estado_hilo(f, st))
            self.hilos_activos.append(hilo)
            hilo.start()

    def actualizar_progreso_hilo(self, fila, porcentaje):
        self.tabla.setItem(fila, 2, QTableWidgetItem(f"{porcentaje}%"))

    def actualizar_estado_hilo(self, fila, estado_str):
        self.tabla.setItem(fila, 1, QTableWidgetItem(estado_str))

    def _descarga_nativa(self, download, fila):
        def actualizar_progreso():
            recibidos = download.receivedBytes()
            total = download.totalBytes()
            if total > 0:
                p = int((recibidos / total) * 100)
                self.tabla.setItem(fila, 2, QTableWidgetItem(f"{p}%"))
                self.tabla.setItem(fila, 1, QTableWidgetItem("Descargando (Nativo)..."))
            else:
                self.tabla.setItem(fila, 1, QTableWidgetItem(f"Descargando ({recibidos} bytes)..."))

        download.receivedBytesChanged.connect(actualizar_progreso)
        download.totalBytesChanged.connect(actualizar_progreso)
        download.stateChanged.connect(lambda: self._actualizar_tabla_estado_nativa(fila, download))
        download.accept()

    def _actualizar_tabla_estado_nativa(self, fila, download):
        estado = download.state()
        if estado == QWebEngineDownloadRequest.DownloadState.DownloadCompleted:
            self.tabla.setItem(fila, 1, QTableWidgetItem("Completado ✅"))
            self.tabla.setItem(fila, 2, QTableWidgetItem("100%"))
        elif estado == QWebEngineDownloadRequest.DownloadState.DownloadCancelled:
            self.tabla.setItem(fila, 1, QTableWidgetItem("Cancelado ❌"))


class AuroraLite(QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.browser_name = core_lib.get_browser_name().decode('utf-8')
        self.initial_url = core_lib.get_initial_url().decode('utf-8')
        
        self.setWindowTitle(self.browser_name)
        self.resize(1100, 750)
        
        ruta_usuario_local = os.path.abspath("./user data")
        self.perfil_normal = QWebEngineProfile("AuroraProfile", self)
        self.perfil_normal.setPersistentStoragePath(ruta_usuario_local)
        self.perfil_normal.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)
        
        ajustes = self.perfil_normal.settings()
        ajustes.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
        ajustes.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        ajustes.setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled, True)
        ajustes.setAttribute(QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture, False)
        ajustes.setAttribute(QWebEngineSettings.WebAttribute.FullScreenSupportEnabled, True)
        
        try:
            ajustes.setAttribute(QWebEngineSettings.WebAttribute.WidevineEnabled, True)
        except AttributeError:
            pass
        
        ua_original = self.perfil_normal.httpUserAgent()
        ua_limpio = re.sub(r'QtWebEngine/[\d\.]+', '', ua_original).strip()
        self.perfil_normal.setHttpUserAgent(ua_limpio)
        self.agente_usuario = ua_limpio
        
        self.ventana_descargas = VentanaDescargas(self)
        self.perfil_normal.downloadRequested.connect(self.ventana_descargas.agregar_descarga)

        self.marcadores = []
        self.historial = []
        
        self.init_ui()
        self.configurar_atajos()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(4, 4, 4, 4)
        
        top_layout = QHBoxLayout()
        
        self.btn_atras = QPushButton("◀")
        self.btn_atras.setFixedWidth(30)
        self.btn_atras.clicked.connect(lambda: self.tabs.currentWidget().back() if self.tabs.currentWidget() else None)
        top_layout.addWidget(self.btn_atras)

        self.btn_adelante = QPushButton("▶")
        self.btn_adelante.setFixedWidth(30)
        self.btn_adelante.clicked.connect(lambda: self.tabs.currentWidget().forward() if self.tabs.currentWidget() else None)
        top_layout.addWidget(self.btn_adelante)

        self.btn_recargar = QPushButton("↻")
        self.btn_recargar.setFixedWidth(30)
        self.btn_recargar.clicked.connect(lambda: self.tabs.currentWidget().reload() if self.tabs.currentWidget() else None)
        top_layout.addWidget(self.btn_recargar)
        
        self.btn_nueva_pestana = QPushButton("+")
        self.btn_nueva_pestana.setFixedWidth(30)
        self.btn_nueva_pestana.setToolTip("Nueva Pestaña (Ctrl+T)")
        self.btn_nueva_pestana.clicked.connect(lambda: self.crear_pestana(self.initial_url))
        top_layout.addWidget(self.btn_nueva_pestana)
        
        self.url_bar = QLineEdit()
        self.url_bar.setFixedHeight(30)
        self.url_bar.returnPressed.connect(self.navegar_url)
        top_layout.addWidget(self.url_bar)

        self.btn_marcador = QPushButton("⭐")
        self.btn_marcador.setFixedWidth(30)
        self.btn_marcador.clicked.connect(self.agregar_marcador)
        top_layout.addWidget(self.btn_marcador)

        self.btn_menu = QPushButton("☰")
        self.btn_menu.setFixedWidth(30)
        self.crear_menu_desplegable()
        top_layout.addWidget(self.btn_menu)
        
        layout.addLayout(top_layout)
        
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.cerrar_pestana)
        self.tabs.currentChanged.connect(self.actualizar_barra_url_por_pestana)
        self.tabs.setStyleSheet("QTabBar::tab { padding: 6px 16px; font-weight: bold; }")
        layout.addWidget(self.tabs)
        
        self.crear_pestana(self.initial_url)

    def configurar_atajos(self):
        QShortcut(QKeySequence("Ctrl+T"), self).activated.connect(lambda: self.crear_pestana(self.initial_url))
        QShortcut(QKeySequence("Ctrl+W"), self).activated.connect(lambda: self.cerrar_pestana(self.tabs.currentIndex()))
        QShortcut(QKeySequence("F5"), self).activated.connect(lambda: self.tabs.currentWidget().reload() if self.tabs.currentWidget() else None)

    def crear_menu_desplegable(self):
        menu = QMenu(self)
        menu.addAction("📥 Descargas", self.ventana_descargas.show)
        menu.addAction("🕒 Historial", self.mostrar_historial)
        menu.addAction("📌 Marcadores", self.mostrar_marcadores)
        menu.addSeparator()
        menu.addAction("⚙ Configuración", self.abrir_configuracion)
        self.btn_menu.setMenu(menu)

    def crear_pestana(self, url_str):
        navegador = QWebEngineView()
        
        pagina = QWebEnginePage(self.perfil_normal, navegador)
        pagina.featurePermissionRequested.connect(self.manejar_permisos)
        navegador.setPage(pagina)
        
        navegador.urlChanged.connect(lambda qurl, nav=navegador: self.actualizar_url_si_activa(qurl, nav))
        navegador.titleChanged.connect(lambda titulo, nav=navegador: self.actualizar_titulo_pestana(titulo, nav))
        
        navegador.setUrl(QUrl(url_str))
        indice = self.tabs.addTab(navegador, "Cargando...")
        self.tabs.setCurrentIndex(indice)

    def navegar_url(self):
        raw_url = self.url_bar.text().strip()
        
        input_url = ctypes.c_char_p(raw_url.encode('utf-8'))
        # Usamos 1024 como tamaño de búfer explícito
        tamanio_buffer = 1024
        output_url = ctypes.create_string_buffer(tamanio_buffer)
        
        # --- 3. PREVENCIÓN DE DESBORDAMIENTO ---
        logic_lib.format_url(input_url, output_url, tamanio_buffer)
        final_url = output_url.value.decode('utf-8')
        
        if not final_url.startswith("about:") and final_url not in self.historial:
            self.historial.append(final_url)
            
        if self.tabs.currentWidget():
            self.tabs.currentWidget().setUrl(QUrl(final_url))

    def actualizar_url_si_activa(self, qurl, navegador):
        if self.tabs.currentWidget() == navegador:
            url_str = qurl.toString()
            self.url_bar.setText(url_str)
            if url_str and not url_str.startswith("about:") and url_str not in self.historial:
                self.historial.append(url_str)

    def actualizar_barra_url_por_pestana(self, index):
        if self.tabs.widget(index):
            self.url_bar.setText(self.tabs.widget(index).url().toString())

    def actualizar_titulo_pestana(self, titulo, navegador):
        titulo_corto = titulo[:22] + "..." if len(titulo) > 22 else titulo
        indice = self.tabs.indexOf(navegador)
        if indice != -1:
            self.tabs.setTabText(indice, titulo_corto)

    def cerrar_pestana(self, index):
        if self.tabs.count() > 1:
            widget = self.tabs.widget(index)
            self.tabs.removeTab(index)
            if widget:
                widget.deleteLater()
        else:
            self.close()

    def closeEvent(self, event):
        while self.tabs.count() > 0:
            widget = self.tabs.widget(0)
            self.tabs.removeTab(0)
            if widget:
                widget.deleteLater()
        event.accept()

    def agregar_marcador(self):
        url_actual = self.url_bar.text()
        if url_actual and url_actual not in self.marcadores:
            self.marcadores.append(url_actual)
            QMessageBox.information(self, "Marcadores", "¡Página agregada a favoritos!")

    def mostrar_marcadores(self):
        dialogo = QDialog(self)
        dialogo.setWindowTitle("Marcadores Guardados")
        dialogo.resize(450, 300)
        layout = QVBoxLayout(dialogo)
        tabla = QTableWidget(len(self.marcadores), 1)
        tabla.setHorizontalHeaderLabels(["URL del Marcador"])
        tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        for i, url in enumerate(self.marcadores):
            tabla.setItem(i, 0, QTableWidgetItem(url))
        layout.addWidget(tabla)
        dialogo.exec()

    def mostrar_historial(self):
        dialogo = QDialog(self)
        dialogo.setWindowTitle("Historial de Navegación")
        dialogo.resize(450, 300)
        layout = QVBoxLayout(dialogo)
        tabla = QTableWidget(len(self.historial), 1)
        tabla.setHorizontalHeaderLabels(["Sitios Visitados"])
        tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        for i, url in enumerate(self.historial):
            tabla.setItem(i, 0, QTableWidgetItem(url))
        layout.addWidget(tabla)
        dialogo.exec()

    def manejar_permisos(self, url, feature):
        nombres = {
            QWebEnginePage.Feature.Geolocation: "Ubicación",
            QWebEnginePage.Feature.MediaAudioCapture: "Micrófono",
            QWebEnginePage.Feature.MediaVideoCapture: "Cámara",
            QWebEnginePage.Feature.MediaAudioVideoCapture: "Cámara y Micrófono",
            QWebEnginePage.Feature.Notifications: "Notificaciones"
        }
        permiso_str = nombres.get(feature, "un recurso del sistema")
        resp = QMessageBox.question(self, "Permiso Solicitado", f"El sitio '{url.host()}' solicita acceso a: {permiso_str}.\n¿Deseas permitirlo?")
        
        pol = QWebEnginePage.PermissionPolicy.PermissionGrantedByUser if resp == QMessageBox.StandardButton.Yes else QWebEnginePage.PermissionPolicy.PermissionDeniedByUser
        self.sender().setFeaturePermission(url, feature, pol)

    def abrir_configuracion(self):
        dialogo = QDialog(self)
        dialogo.setWindowTitle("Configuración de Aurora-Lite")
        dialogo.resize(320, 180)
        layout = QFormLayout(dialogo)
        
        ajustes = self.perfil_normal.settings()
        
        chk_js = QCheckBox("Habilitar JavaScript")
        chk_js.setChecked(ajustes.testAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled))
        chk_js.toggled.connect(lambda v: ajustes.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, v))
        
        chk_img = QCheckBox("Cargar imágenes automáticamente")
        chk_img.setChecked(ajustes.testAttribute(QWebEngineSettings.WebAttribute.AutoLoadImages))
        chk_img.toggled.connect(lambda v: ajustes.setAttribute(QWebEngineSettings.WebAttribute.AutoLoadImages, v))
        
        btn_limpiar = QPushButton("Borrar Caché y Cookies")
        btn_limpiar.clicked.connect(lambda: (
            self.perfil_normal.clearAllVisitedLinks(), 
            self.perfil_normal.cookieStore().deleteAllCookies(), 
            QMessageBox.information(dialogo, "Limpieza", "Datos de navegación eliminados correctamente.")
        ))
        
        layout.addRow(chk_js)
        layout.addRow(chk_img)
        layout.addRow(btn_limpiar)
        dialogo.exec()
