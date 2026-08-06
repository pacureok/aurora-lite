# gui.py
import sys
import ctypes
import os
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
from PyQt6.QtCore import QUrl, QStandardPaths, Qt

lib_ext = '.dll' if os.name == 'nt' else '.so'
try:
    core_lib = ctypes.CDLL(os.path.abspath(f'./core{lib_ext}'))
    logic_lib = ctypes.CDLL(os.path.abspath(f'./logic{lib_ext}'))
    core_lib.get_browser_name.restype = ctypes.c_char_p
    core_lib.get_initial_url.restype = ctypes.c_char_p
except OSError:
    print(f"Error: No se encontraron las librerías de C/C++ (core{lib_ext} / logic{lib_ext}).")
    sys.exit(1)

class VentanaDescargas(QDialog):
    """Ventana independiente para gestionar y visualizar las descargas activas y completadas"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Gestor de Descargas - Aurora-Lite")
        self.resize(600, 300)
        
        layout = QVBoxLayout(self)
        
        self.tabla = QTableWidget()
        self.tabla.setColumnCount(4)
        self.tabla.setHorizontalHeaderLabels(["Archivo", "Estado", "Progreso", "Ruta / Acción"])
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.tabla)

    def agregar_descarga(self, download: QWebEngineDownloadRequest):
        fila = self.tabla.rowCount()
        self.tabla.insertRow(fila)
        
        nombre_archivo = os.path.basename(download.downloadFileName())
        self.tabla.setItem(fila, 0, QTableWidgetItem(nombre_archivo))
        self.tabla.setItem(fila, 1, QTableWidgetItem("Iniciando..."))
        self.tabla.setItem(fila, 2, QTableWidgetItem("0%"))
        self.tabla.setItem(fila, 3, QTableWidgetItem(download.downloadDirectory()))

        # Conectar eventos de la descarga
        download.downloadProgress.bytesReceived.connect.bind(lambda r, t: None) # Evitar errores de tipos
        
        def actualizar_progreso(recibidos, total):
            if total > 0:
                porcentaje = int((recibidos / total) * 100)
                self.tabla.setItem(fila, 2, QTableWidgetItem(f"{porcentaje}%"))
                self.tabla.setItem(fila, 1, QTableWidgetItem("Descargando..."))

        def estado_cambiado():
            estado = download.state()
            if estado == QWebEngineDownloadRequest.DownloadState.DownloadCompleted:
                self.tabla.setItem(fila, 1, QTableWidgetItem("Completado ✅"))
                self.tabla.setItem(fila, 2, QTableWidgetItem("100%"))
            elif estado == QWebEngineDownloadRequest.DownloadState.DownloadCancelled:
                self.tabla.setItem(fila, 1, QTableWidgetItem("Cancelado ❌"))
            elif estado == QWebEngineDownloadRequest.DownloadState.DownloadInterrupted:
                self.tabla.setItem(fila, 1, QTableWidgetItem("Interrumpido ⚠️"))

        download.downloadProgress.connect(actualizar_progreso)
        download.stateChanged.connect(estado_cambiado)
        download.accept()


class AuroraLite(QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.browser_name = core_lib.get_browser_name().decode('utf-8')
        self.initial_url = core_lib.get_initial_url().decode('utf-8')
        
        self.setWindowTitle(self.browser_name)
        self.resize(1024, 768)
        
        # Configuración del Perfil
        self.perfil = QWebEngineProfile.defaultProfile()
        ruta_datos = os.path.join(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation), "AuroraLite")
        self.perfil.setPersistentStoragePath(ruta_datos)
        self.perfil.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)
        
        # Ventana de descargas en segundo plano
        self.ventana_descargas = VentanaDescargas(self)
        self.perfil.downloadRequested.connect(self.ventana_descargas.agregar_descarga)

        # Almacenes locales para marcadores e historial
        self.marcadores = []
        self.historial = []
        
        self.init_ui()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # --- BARRA DE HERRAMIENTAS ---
        top_layout = QHBoxLayout()
        
        # Botones de Navegación
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
        
        # Nueva pestaña
        self.btn_nueva_pestana = QPushButton("+")
        self.btn_nueva_pestana.setFixedWidth(30)
        self.btn_nueva_pestana.clicked.connect(lambda: self.crear_pestana(self.initial_url))
        top_layout.addWidget(self.btn_nueva_pestana)
        
        # Barra de URL
        self.url_bar = QLineEdit()
        self.url_bar.setFixedHeight(30)
        self.url_bar.returnPressed.connect(self.navegar_url)
        top_layout.addWidget(self.url_bar)

        # Botón para Marcar / Favorito (⭐)
        self.btn_marcador = QPushButton("⭐")
        self.btn_marcador.setFixedWidth(30)
        self.btn_marcador.setToolTip("Añadir a Marcadores")
        self.btn_marcador.clicked.connect(self.agregar_marcador)
        top_layout.addWidget(self.btn_marcador)

        # Menú Desplegable de Utilidades (Historial, Descargas, Config)
        self.btn_menu = QPushButton("☰")
        self.btn_menu.setFixedWidth(30)
        self.crear_menu_desplegable()
        top_layout.addWidget(self.btn_menu)
        
        layout.addLayout(top_layout)
        
        # Sistema de pestañas
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.cerrar_pestana)
        self.tabs.currentChanged.connect(self.actualizar_barra_url_por_pestana)
        self.tabs.setStyleSheet("QTabBar::tab { padding: 5px 15px; }")
        layout.addWidget(self.tabs)
        
        self.crear_pestana(self.initial_url)

    def crear_menu_desplegable(self):
        menu = QMenu(self)
        
        accion_descargas = menu.addAction("📥 Descargas")
        accion_descargas.triggered.connect(self.ventana_descargas.show)
        
        accion_historial = menu.addAction("🕒 Historial")
        accion_historial.triggered.connect(self.mostrar_historial)
        
        accion_marcadores = menu.addAction("📌 Ver Marcadores")
        accion_marcadores.triggered.connect(self.mostrar_marcadores)
        
        menu.addSeparator()
        
        accion_config = menu.addAction("⚙ Configuración")
        accion_config.triggered.connect(self.abrir_configuracion)
        
        self.btn_menu.setMenu(menu)

    def crear_pestana(self, url_str):
        navegador = QWebEngineView()
        pagina = QWebEnginePage(self.perfil, navegador)
        
        pagina.featurePermissionRequested.connect(self.manejar_permisos)
        
        navegador.setPage(pagina)
        navegador.urlChanged.connect(lambda qurl, nav=navegador: self.actualizar_url_si_activa(qurl, nav))
        navegador.titleChanged.connect(lambda titulo, nav=navegador: self.actualizar_titulo_pestana(titulo, nav))
        
        navegador.setUrl(QUrl(url_str))
        indice = self.tabs.addTab(navegador, "Cargando...")
        self.tabs.setCurrentIndex(indice)

    def agregar_marcador(self):
        url_actual = self.url_bar.text()
        if url_actual and url_actual not in self.marcadores:
            self.marcadores.append(url_actual)
            QMessageBox.information(self, "Marcadores", "Página añadida a favoritos exitosamente.")

    def mostrar_marcadores(self):
        dialogo = QDialog(self)
        dialogo.setWindowTitle("Mis Marcadores")
        dialogo.resize(400, 300)
        layout = QVBoxLayout(dialogo)
        
        tabla = QTableWidget()
        tabla.setColumnCount(1)
        tabla.setHorizontalHeaderLabels(["Sitios Guardados"])
        tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        tabla.setRowCount(len(self.marcadores))
        for i, url in enumerate(self.marcadores):
            tabla.setItem(i, 0, QTableWidgetItem(url))
            
        layout.addWidget(tabla)
        dialogo.exec()

    def mostrar_historial(self):
        dialogo = QDialog(self)
        dialogo.setWindowTitle("Historial de Navegación")
        dialogo.resize(400, 300)
        layout = QVBoxLayout(dialogo)
        
        tabla = QTableWidget()
        tabla.setColumnCount(1)
        tabla.setHorizontalHeaderLabels(["Páginas Visitadas"])
        tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        tabla.setRowCount(len(self.historial))
        for i, url in enumerate(self.historial):
            tabla.setItem(i, 0, QTableWidgetItem(url))
            
        layout.addWidget(tabla)
        dialogo.exec()

    def manejar_permisos(self, url, feature):
        nombres_permisos = {
            QWebEnginePage.Feature.Geolocation: "Ubicación",
            QWebEnginePage.Feature.MediaAudioCapture: "Micrófono",
            QWebEnginePage.Feature.MediaVideoCapture: "Cámara",
            QWebEnginePage.Feature.MediaAudioVideoCapture: "Cámara y Micrófono",
            QWebEnginePage.Feature.Notifications: "Notificaciones"
        }
        nombre = nombres_permisos.get(feature, "un permiso desconocido")
        
        respuesta = QMessageBox.question(
            self, "Solicitud de Permiso",
            f"El sitio {url.host()} solicita acceso a: {nombre}.\n¿Deseas permitirlo?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if respuesta == QMessageBox.StandardButton.Yes:
            self.sender().setFeaturePermission(url, feature, QWebEnginePage.PermissionPolicy.PermissionGrantedByUser)
        else:
            self.sender().setFeaturePermission(url, feature, QWebEnginePage.PermissionPolicy.PermissionDeniedByUser)

    def abrir_configuracion(self):
        dialogo = QDialog(self)
        dialogo.setWindowTitle("Configuración de Aurora-Lite")
        dialogo.resize(300, 150)
        
        layout = QFormLayout(dialogo)
        ajustes = self.perfil.settings()
        
        chk_js = QCheckBox("Habilitar JavaScript")
        chk_js.setChecked(ajustes.testAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled))
        chk_js.toggled.connect(lambda checked: ajustes.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, checked))
        
        chk_img = QCheckBox("Cargar imágenes automáticamente")
        chk_img.setChecked(ajustes.testAttribute(QWebEngineSettings.WebAttribute.AutoLoadImages))
        chk_img.toggled.connect(lambda checked: ajustes.setAttribute(QWebEngineSettings.WebAttribute.AutoLoadImages, checked))
        
        btn_limpiar = QPushButton("Limpiar Caché y Cookies")
        btn_limpiar.clicked.connect(lambda: (self.perfil.clearAllVisitedLinks(), self.perfil.cookieStore().deleteAllCookies(), QMessageBox.information(dialogo, "Éxito", "Datos limpiados.")))
        
        layout.addRow(chk_js)
        layout.addRow(chk_img)
        layout.addRow(btn_limpiar)
        
        dialogo.exec()

    def cerrar_pestana(self, index):
        if self.tabs.count() > 1:
            self.tabs.removeTab(index)
        else:
            self.close()

    def navegar_url(self):
        raw_url = self.url_bar.text().strip()
        input_url = ctypes.c_char_p(raw_url.encode('utf-8'))
        output_url = ctypes.create_string_buffer(512)
        logic_lib.format_url(input_url, output_url)
        final_url = output_url.value.decode('utf-8')
        
        if final_url not in self.historial:
            self.historial.append(final_url)
            
        if self.tabs.currentWidget():
            self.tabs.currentWidget().setUrl(QUrl(final_url))

    def actualizar_url_si_activa(self, qurl, navegador):
        if self.tabs.currentWidget() == navegador:
            url_str = qurl.toString()
            self.url_bar.setText(url_str)
            if url_str and url_str not in self.historial and not url_str.startswith("about:"):
                self.historial.append(url_str)

    def actualizar_barra_url_por_pestana(self, index):
        if self.tabs.widget(index):
            self.url_bar.setText(self.tabs.widget(index).url().toString())

    def actualizar_titulo_pestana(self, titulo, navegador):
        titulo_corto = titulo[:20] + "..." if len(titulo) > 20 else titulo
        indice = self.tabs.indexOf(navegador)
        if indice != -1:
            self.tabs.setTabText(indice, titulo_corto)