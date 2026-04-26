import os
import sys
import faulthandler
import threading

# Ajusta o path para imports relativos quando executado diretamente
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ─── Captura de crashes GLOBAIS ──────────────────────────────────────────────
# Precisa ser o mais cedo possível, ANTES de qualquer import pesado, para
# garantir que mesmo crashes durante a inicialização sejam registrados.
# Build com --windows-console-mode=disable jogaria stderr para o vazio; sem
# isso, "app fechou sozinho" não deixa nenhum rastro.
def _install_global_crash_handlers() -> None:
    try:
        from app.core.logger import get_logger
        from app.core.app_paths import get_log_dir
    except Exception:
        # Se até o logger falha, ao menos imprime no stderr (que pode estar
        # redirecionado, mas é o melhor que dá para fazer aqui).
        import traceback
        traceback.print_exc()
        return

    crash_log = get_logger("crash")

    # 1) faulthandler: captura segfault/abort do C/Qt e despeja stack nativo
    #    em fault.log. Funciona mesmo quando o Python está corrompido.
    try:
        fault_path = os.path.join(get_log_dir(), "fault.log")
        # Mantém o handle aberto durante toda a vida do processo.
        fault_fp = open(fault_path, "a", encoding="utf-8", buffering=1)
        faulthandler.enable(file=fault_fp, all_threads=True)
    except Exception:
        crash_log.exception("Falha ao habilitar faulthandler")

    # 2) sys.excepthook: captura exceções Python não tratadas no thread principal.
    def _py_excepthook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        crash_log.error(
            "Exceção não tratada no thread principal",
            exc_info=(exc_type, exc_value, exc_tb),
        )
        # Encadeia o handler original (caso console esteja visível)
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = _py_excepthook

    # 3) threading.excepthook: captura exceções não tratadas em threads Python
    #    (QThread em PyQt geralmente protege a thread, mas worker.run() puro
    #    via threading.Thread, threading.Timer, etc. cai aqui).
    def _thread_excepthook(args):
        if issubclass(args.exc_type, SystemExit):
            return
        crash_log.error(
            "Exceção não tratada na thread '%s'",
            getattr(args.thread, "name", "?"),
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    threading.excepthook = _thread_excepthook

    crash_log.info("Crash handlers instalados (faulthandler + excepthook)")


_install_global_crash_handlers()
# ─────────────────────────────────────────────────────────────────────────────

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import Qt

from app.ui.custom_dialog import CustomDialog

from app.ui.main_window import MainWindow  # noqa: E402
from app.core.system_tray import SystemTrayManager  # noqa: E402
from app.core.app_paths import is_windows, get_lock_file_path

# Nome do Mutex (deve ser único, usado pelo instalador Inno Setup)
APP_MUTEX_NAME = "UtilitariosPCAppMutex"

# Referência global para o lock file (evitar GC fechar o fd)
_lock_file_handle = None


def acquire_instance_lock():
    """
    Adquire um lock de instância única, cross-platform:
    - Windows: Mutex via ctypes.windll.kernel32
    - Linux/macOS: fcntl.flock() em ~/.utilitarios/app.lock
    
    Retorna um handle/fd (truthy) em caso de sucesso, ou None se já existe instância.
    """
    global _lock_file_handle

    if is_windows():
        import ctypes
        kernel32 = ctypes.windll.kernel32
        mutex = kernel32.CreateMutexW(None, False, APP_MUTEX_NAME)
        last_error = kernel32.GetLastError()
        # ERROR_ALREADY_EXISTS = 183
        if last_error == 183:
            return None
        return mutex
    else:
        # Linux / macOS — usar fcntl.flock
        import fcntl
        lock_path = get_lock_file_path()
        try:
            _lock_file_handle = open(lock_path, 'w')
            fcntl.flock(_lock_file_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            # Escrever PID no arquivo de lock
            _lock_file_handle.write(str(os.getpid()))
            _lock_file_handle.flush()
            return _lock_file_handle
        except (IOError, OSError):
            # Já existe outra instância rodando
            if _lock_file_handle:
                _lock_file_handle.close()
                _lock_file_handle = None
            return None


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
    
    # Adquirir lock de instância única (cross-platform)
    lock = acquire_instance_lock()
    if lock is None:
        # Já existe uma instância rodando — mostrar aviso nativo do sistema
        if is_windows():
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                0,
                "O Utilitários PC já está em execução.\n\nVerifique o ícone na bandeja do sistema.",
                "Utilitários PC",
                0x40  # MB_ICONINFORMATION
            )
        else:
            # No Linux/macOS, imprimir no terminal (sem QApplication ainda)
            print("Utilitários PC já está em execução. Verifique o ícone na bandeja do sistema.")
        return 0
    
    app = QApplication(sys.argv)
    app.setApplicationName('Utilitários PC')
    app.setOrganizationName('Projeto Utilitarios')
    
    # Não fechar quando a janela é fechada (permite minimizar para bandeja)
    app.setQuitOnLastWindowClosed(False)

    # Inicializar Logger global
    from app.core.logger import get_logger
    log = get_logger("main")
    log.info("Iniciando Utilitários PC")

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
    app._tray = tray  # Expõe para acesso pelos widgets via QApplication.instance()._tray
    
    # Conectar sinais do tray
    tray.show_window_requested.connect(lambda: (window.showNormal(), window.activateWindow()))
    tray.quit_requested.connect(lambda: (tray.hide(), app.quit()))
    
    # Ação rápida: Limpar clipboard
    def clear_clipboard():
        app.clipboard().clear()
    tray.clear_clipboard_requested.connect(clear_clipboard)
    
    # Ação rápida: Pausar/retomar watchdog
    def toggle_watchdog_pause(minutes: int):
        organizer = window.stack.widget(MainWindow.PAGE_ORGANIZER)
        if hasattr(organizer, 'watcher_widget'):
            watcher = organizer.watcher_widget._watcher
            if minutes > 0:
                # Pausar
                watcher.stop()
            else:
                # Retomar (se tinha configurações)
                if organizer.watcher_widget._watcher.get_all_configs():
                    watcher.start()
                    tray.set_monitoring_status(True)
    tray.pause_watchdog_requested.connect(toggle_watchdog_pause)
    
    # Integrar toggle de monitoramento de pastas com o widget
    def toggle_monitoring():
        # Encontrar widget de monitoramento
        organizer = window.stack.widget(MainWindow.PAGE_ORGANIZER)
        if hasattr(organizer, 'watcher_widget'):
            watcher_widget = organizer.watcher_widget
            watcher_widget._toggle_monitoring()
            tray.set_monitoring_status(watcher_widget._watcher.is_running)
    
    tray.toggle_monitoring_requested.connect(toggle_monitoring)
    
    # Integrar toggle de monitoramento de clipboard com o widget
    def toggle_clipboard_monitoring():
        clipboard_widget = window.stack.widget(MainWindow.PAGE_CLIPBOARD)
        if hasattr(clipboard_widget, 'chk_monitor'):
            # Toggle o estado
            current_state = clipboard_widget.chk_monitor.isChecked()
            clipboard_widget.chk_monitor.setChecked(not current_state)
            tray.set_clipboard_monitoring_status(not current_state)
    
    tray.toggle_clipboard_monitoring_requested.connect(toggle_clipboard_monitoring)
    
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
        organizer = window.stack.widget(MainWindow.PAGE_ORGANIZER)
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
