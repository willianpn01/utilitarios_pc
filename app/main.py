import os
import sys
import ctypes
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import Qt

# Ajusta o path para imports relativos quando executado diretamente
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.ui.main_window import MainWindow  # noqa: E402
from app.core.system_tray import SystemTrayManager  # noqa: E402

# Nome do Mutex (deve ser único, usado pelo instalador Inno Setup)
APP_MUTEX_NAME = "UtilitariosPCAppMutex"


def create_mutex():
    """
    Cria um Mutex do Windows para:
    1. Prevenir múltiplas instâncias do app
    2. Permitir que o instalador detecte se o app está rodando
    """
    if sys.platform != 'win32':
        return None
    
    kernel32 = ctypes.windll.kernel32
    mutex = kernel32.CreateMutexW(None, False, APP_MUTEX_NAME)
    last_error = kernel32.GetLastError()
    
    # ERROR_ALREADY_EXISTS = 183
    if last_error == 183:
        # Já existe outra instância rodando
        return None
    
    return mutex


def get_resource_path(relative_path: str) -> str:
    """
    Retorna o caminho absoluto para um recurso, funcionando tanto em
    desenvolvimento quanto quando compilado com Nuitka/PyInstaller.
    """
    # Quando compilado com Nuitka --onefile, os arquivos ficam em um diretório temporário
    # Quando compilado com --standalone, ficam junto ao executável
    
    # Tentar vários caminhos possíveis
    possible_paths = [
        # Desenvolvimento: relativo ao PROJECT_ROOT
        os.path.join(PROJECT_ROOT, relative_path),
        # Nuitka standalone/onefile: relativo ao executável
        os.path.join(os.path.dirname(sys.executable), relative_path),
        # Nuitka onefile: dentro do diretório temporário
        os.path.join(getattr(sys, '_MEIPASS', CURRENT_DIR), relative_path),
        # Relativo ao CURRENT_DIR
        os.path.join(CURRENT_DIR, relative_path),
        # Subindo um nível do executável
        os.path.join(os.path.dirname(os.path.dirname(sys.executable)), relative_path),
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return path
    
    # Retorna o primeiro caminho como fallback
    return possible_paths[0]


def load_qss(app: QApplication) -> None:
    """Carrega o arquivo de estilos QSS."""
    qss_path = get_resource_path(os.path.join('app', 'assets', 'styles', 'theme.qss'))
    
    try:
        with open(qss_path, 'r', encoding='utf-8') as f:
            app.setStyleSheet(f.read())
            print(f"[INFO] QSS carregado de: {qss_path}")
    except FileNotFoundError:
        print(f"[WARN] Arquivo QSS não encontrado: {qss_path}")
        # Tentar caminho alternativo sem 'app' prefix
        alt_path = get_resource_path(os.path.join('assets', 'styles', 'theme.qss'))
        try:
            with open(alt_path, 'r', encoding='utf-8') as f:
                app.setStyleSheet(f.read())
                print(f"[INFO] QSS carregado de caminho alternativo: {alt_path}")
        except FileNotFoundError:
            print(f"[WARN] QSS alternativo também não encontrado: {alt_path}")


def main() -> int:
    # Verificar argumentos
    start_minimized = '--minimized' in sys.argv
    
    # Criar Mutex para detecção pelo instalador e prevenção de múltiplas instâncias
    mutex = create_mutex()
    if mutex is None and sys.platform == 'win32':
        # Já existe uma instância rodando
        # Mostrar mensagem simples (sem QApplication ainda)
        ctypes.windll.user32.MessageBoxW(
            0,
            "O Utilitários PC já está em execução.\n\nVerifique o ícone na bandeja do sistema.",
            "Utilitários PC",
            0x40  # MB_ICONINFORMATION
        )
        return 0
    
    app = QApplication(sys.argv)
    app.setApplicationName('Utilitários PC')
    app.setOrganizationName('Projeto Utilitarios')
    
    # Não fechar quando a janela é fechada (permite minimizar para bandeja)
    app.setQuitOnLastWindowClosed(False)

    load_qss(app)

    # Configurar ícone (tentar vários caminhos)
    icon_path = get_resource_path(os.path.join('app', 'icone.ico'))
    if not os.path.exists(icon_path):
        icon_path = get_resource_path('icone.ico')
    if not os.path.exists(icon_path):
        icon_path = get_resource_path(os.path.join('app', 'assets', 'icons', 'app.png'))
    
    app_icon = QIcon(icon_path) if os.path.exists(icon_path) else QIcon()
    app.setWindowIcon(app_icon)

    # Criar janela principal
    window = MainWindow()
    window.setWindowIcon(app_icon)
    
    # Criar system tray
    tray = SystemTrayManager(parent=app, icon_path=icon_path)
    
    # Conectar sinais do tray
    tray.show_window_requested.connect(lambda: (window.showNormal(), window.activateWindow()))
    tray.quit_requested.connect(lambda: (tray.hide(), app.quit()))
    
    # Integrar toggle de monitoramento com o widget
    def toggle_monitoring():
        # Encontrar widget de monitoramento
        organizer = window.stack.widget(3)  # Organizador é o índice 3
        if hasattr(organizer, 'watcher_widget'):
            watcher_widget = organizer.watcher_widget
            watcher_widget._toggle_monitoring()
            tray.set_monitoring_status(watcher_widget._watcher.is_running)
    
    tray.toggle_monitoring_requested.connect(toggle_monitoring)
    
    # Conectar sinal de arquivo organizado para notificação
    def on_file_organized_notification(event):
        if event.success and tray.is_available():
            basename = os.path.basename(event.source)
            tray.show_notification(
                "Arquivo Organizado",
                f"{basename} → {event.category}/"
            )
    
    # Conectar quando o widget for acessado
    def connect_watcher_signals():
        organizer = window.stack.widget(3)
        if hasattr(organizer, 'watcher_widget'):
            organizer.watcher_widget.file_organized.connect(on_file_organized_notification)
            # Atualizar status do tray quando monitoramento mudar
            watcher = organizer.watcher_widget._watcher
            original_start = watcher.start
            original_stop = watcher.stop
            
            def wrapped_start():
                original_start()
                tray.set_monitoring_status(True)
            
            def wrapped_stop():
                original_stop()
                tray.set_monitoring_status(False)
            
            watcher.start = wrapped_start
            watcher.stop = wrapped_stop
    
    # Conectar após inicialização
    from PyQt6.QtCore import QTimer, QSettings
    from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox
    QTimer.singleShot(100, connect_watcher_signals)
    
    # Diálogo de confirmação ao fechar
    def show_close_dialog() -> str:
        """Mostra diálogo perguntando o que fazer ao fechar. Retorna 'minimize', 'quit' ou 'cancel'."""
        dialog = QDialog(window)
        dialog.setWindowTitle("Fechar Utilitários PC")
        dialog.setMinimumWidth(400)
        
        layout = QVBoxLayout(dialog)
        
        # Mensagem
        msg = QLabel("O que você deseja fazer?")
        msg.setStyleSheet("font-size: 14px; margin-bottom: 10px;")
        layout.addWidget(msg)
        
        # Checkbox para lembrar
        remember_check = QCheckBox("Lembrar minha decisão")
        remember_check.setToolTip("Você pode mudar isso depois nas configurações")
        layout.addWidget(remember_check)
        
        layout.addSpacing(15)
        
        # Botões
        btn_layout = QHBoxLayout()
        
        btn_minimize = QPushButton("📥 Minimizar para Bandeja")
        btn_minimize.setToolTip("Continua rodando em segundo plano")
        
        btn_quit = QPushButton("❌ Sair do Aplicativo")
        btn_quit.setToolTip("Fecha completamente o aplicativo")
        
        btn_cancel = QPushButton("Cancelar")
        
        btn_layout.addWidget(btn_minimize)
        btn_layout.addWidget(btn_quit)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        
        layout.addLayout(btn_layout)
        
        result = {'action': 'cancel'}
        
        def on_minimize():
            result['action'] = 'minimize'
            if remember_check.isChecked():
                QSettings().setValue('app/close_action', 'minimize')
            dialog.accept()
        
        def on_quit():
            result['action'] = 'quit'
            if remember_check.isChecked():
                QSettings().setValue('app/close_action', 'quit')
            dialog.accept()
        
        def on_cancel():
            result['action'] = 'cancel'
            dialog.reject()
        
        btn_minimize.clicked.connect(on_minimize)
        btn_quit.clicked.connect(on_quit)
        btn_cancel.clicked.connect(on_cancel)
        
        dialog.exec()
        return result['action']
    
    # Sobrescrever closeEvent com diálogo de opções
    original_close_event = window.closeEvent
    def custom_close_event(event):
        if not tray.is_available():
            original_close_event(event)
            return
        
        # Verificar se há preferência salva
        settings = QSettings()
        saved_action = settings.value('app/close_action', '')
        
        if saved_action == 'minimize':
            event.ignore()
            window.hide()
            tray.show_notification(
                "Utilitários PC",
                "Minimizado para a bandeja do sistema."
            )
        elif saved_action == 'quit':
            tray.hide()
            app.quit()
        else:
            # Mostrar diálogo perguntando
            action = show_close_dialog()
            
            if action == 'minimize':
                event.ignore()
                window.hide()
                tray.show_notification(
                    "Utilitários PC",
                    "Minimizado para a bandeja do sistema."
                )
            elif action == 'quit':
                tray.hide()
                app.quit()
            else:  # cancel
                event.ignore()
    
    window.closeEvent = custom_close_event
    
    # Mostrar tray
    tray.show()
    
    # Mostrar janela (ou não, se iniciar minimizado)
    if not start_minimized:
        window.show()
    else:
        tray.show_notification(
            "Utilitários PC",
            "Iniciado na bandeja do sistema. Clique no ícone para abrir."
        )

    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())
