"""
System Tray - Ícone na bandeja do sistema com menu de contexto.

Permite minimizar para bandeja e controlar monitoramento.
"""
from __future__ import annotations

import os
import sys
from typing import Optional, Callable

from PyQt6.QtWidgets import QSystemTrayIcon, QMenu, QApplication
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtCore import QObject, pyqtSignal, QTimer

from app.core.logger import is_debug_mode, set_debug_mode


class SystemTrayManager(QObject):
    """Gerenciador do ícone na bandeja do sistema."""
    
    # Sinais
    show_window_requested = pyqtSignal()
    quit_requested = pyqtSignal()
    toggle_monitoring_requested = pyqtSignal()  # Watchdog de pastas
    toggle_clipboard_monitoring_requested = pyqtSignal()  # Histórico de clipboard
    clear_clipboard_requested = pyqtSignal()
    pause_watchdog_requested = pyqtSignal(int)  # minutos
    
    def __init__(self, parent=None, icon_path: str = ""):
        super().__init__(parent)
        
        self._tray_icon: Optional[QSystemTrayIcon] = None
        self._menu: Optional[QMenu] = None
        self._monitoring_active = False
        self._clipboard_monitoring_active = False
        self._watchdog_paused = False
        self._pause_timer: Optional[QTimer] = None
        self._icon_path = icon_path
        
        self._init_tray()
    
    def _init_tray(self):
        """Inicializa o ícone na bandeja."""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        
        self._tray_icon = QSystemTrayIcon(self)
        
        # Definir ícone
        if self._icon_path and os.path.exists(self._icon_path):
            self._tray_icon.setIcon(QIcon(self._icon_path))
        else:
            # Usar ícone padrão do app se disponível
            app = QApplication.instance()
            if app:
                self._tray_icon.setIcon(app.windowIcon())
        
        self._tray_icon.setToolTip("Utilitários PC - Monitoramento Inativo")
        
        # Criar menu
        self._menu = QMenu()
        
        # Ação: Mostrar janela
        self._action_show = QAction("📺 Mostrar Janela", self)
        self._action_show.triggered.connect(self.show_window_requested.emit)
        self._menu.addAction(self._action_show)
        
        self._menu.addSeparator()
        
        # === Ações Rápidas ===
        self._menu.addSection("⚡ Ações Rápidas")
        
        # Limpar área de transferência
        self._action_clear_clipboard = QAction("🧹 Limpar Clipboard", self)
        self._action_clear_clipboard.triggered.connect(self._on_clear_clipboard)
        self._menu.addAction(self._action_clear_clipboard)
        
        # Pausar watchdog
        self._action_pause = QAction("⏸ Pausar Watchdog (1h)", self)
        self._action_pause.triggered.connect(lambda: self._on_pause_watchdog(60))
        self._menu.addAction(self._action_pause)
        
        self._menu.addSeparator()

        # Debug Mode (Logs)
        self._action_debug = QAction("📝 Modo Debug (Logs)", self)
        self._action_debug.setCheckable(True)
        self._action_debug.setChecked(is_debug_mode())
        self._action_debug.toggled.connect(self._on_toggle_debug)
        self._menu.addAction(self._action_debug)
        
        self._menu.addSeparator()
        
        # === Monitoramento ===
        self._menu.addSection("📁 Monitoramento")
        
        # Watchdog (pastas)
        self._action_monitoring = QAction("▶ Watchdog de Pastas", self)
        self._action_monitoring.triggered.connect(self.toggle_monitoring_requested.emit)
        self._menu.addAction(self._action_monitoring)
        
        # Clipboard
        self._action_clipboard_monitoring = QAction("▶ Histórico de Clipboard", self)
        self._action_clipboard_monitoring.triggered.connect(self.toggle_clipboard_monitoring_requested.emit)
        self._menu.addAction(self._action_clipboard_monitoring)
        
        self._menu.addSeparator()
        
        # Ação: Sair
        self._action_quit = QAction("❌ Sair", self)
        self._action_quit.triggered.connect(self.quit_requested.emit)
        self._menu.addAction(self._action_quit)
        
        self._tray_icon.setContextMenu(self._menu)
        
        # Clique duplo abre a janela
        self._tray_icon.activated.connect(self._on_tray_activated)
    
    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason):
        """Callback quando o ícone é ativado."""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_window_requested.emit()
    
    def show(self):
        """Mostra o ícone na bandeja."""
        if self._tray_icon:
            self._tray_icon.show()
    
    def hide(self):
        """Esconde o ícone da bandeja."""
        if self._tray_icon:
            self._tray_icon.hide()
    
    def set_monitoring_status(self, active: bool):
        """Atualiza status de monitoramento de pastas no menu e tooltip."""
        self._monitoring_active = active
        
        if self._action_monitoring:
            if active:
                self._action_monitoring.setText("⏹ Parar Watchdog de Pastas")
            else:
                self._action_monitoring.setText("▶ Watchdog de Pastas")
        
        self._update_tooltip()
    
    def set_clipboard_monitoring_status(self, active: bool):
        """Atualiza status de monitoramento de clipboard no menu."""
        self._clipboard_monitoring_active = active
        
        if self._action_clipboard_monitoring:
            if active:
                self._action_clipboard_monitoring.setText("⏹ Parar Histórico de Clipboard")
            else:
                self._action_clipboard_monitoring.setText("▶ Histórico de Clipboard")
        
        self._update_tooltip()
    
    def _update_tooltip(self):
        """Atualiza tooltip com status de todos os monitoramentos."""
        if not self._tray_icon:
            return
        
        status_parts = []
        if self._monitoring_active:
            status_parts.append("📁 Pastas")
        if self._clipboard_monitoring_active:
            status_parts.append("📋 Clipboard")
        
        if status_parts:
            status = f"Monitorando: {', '.join(status_parts)}"
        else:
            status = "Monitoramento Inativo"
        
        self._tray_icon.setToolTip(f"Utilitários PC - {status}")
    
    def show_notification(self, title: str, message: str, icon: QSystemTrayIcon.MessageIcon = QSystemTrayIcon.MessageIcon.Information):
        """Mostra uma notificação no sistema."""
        if self._tray_icon and self._tray_icon.isVisible():
            self._tray_icon.showMessage(title, message, icon, 3000)
    
    def is_available(self) -> bool:
        """Retorna se o system tray está disponível."""
        return self._tray_icon is not None
    
    def _on_clear_clipboard(self):
        """Limpa a área de transferência."""
        self.clear_clipboard_requested.emit()
        self.show_notification(
            "Clipboard Limpo",
            "A área de transferência foi limpa."
        )
    
    def _on_pause_watchdog(self, minutes: int):
        """Pausa o watchdog por X minutos."""
        if self._watchdog_paused:
            # Retomar
            self._resume_watchdog()
            return
        
        self._watchdog_paused = True
        self.pause_watchdog_requested.emit(minutes)
        
        # Atualizar menu
        self._action_pause.setText(f"▶ Retomar Watchdog ({minutes}min restantes)")
        
        # Timer para retomar automaticamente
        if not self._pause_timer:
            self._pause_timer = QTimer(self)
            self._pause_timer.setSingleShot(True)
            self._pause_timer.timeout.connect(self._resume_watchdog)
        
        self._pause_timer.start(minutes * 60 * 1000)  # Converter para ms
        
        self.show_notification(
            "Watchdog Pausado",
            f"O monitoramento será retomado em {minutes} minutos."
        )
    
    def _resume_watchdog(self):
        """Retoma o watchdog após a pausa."""
        self._watchdog_paused = False
        self._action_pause.setText("⏸ Pausar Watchdog (1h)")
        
        if self._pause_timer:
            self._pause_timer.stop()
        
        # Emitir sinal com 0 para indicar retomada
        self.pause_watchdog_requested.emit(0)
        
        self.show_notification(
            "Watchdog Retomado",
            "O monitoramento foi retomado."
        )
    
    def is_watchdog_paused(self) -> bool:
        """Retorna se o watchdog está pausado."""
        return self._watchdog_paused

    def _on_toggle_debug(self, is_checked: bool) -> None:
        """Ativa ou desativa os logs do modo debug."""
        set_debug_mode(is_checked)
        self.show_notification("Modo Debug", f"Logs detalhados {'ativados' if is_checked else 'desativados'}.")


def notify_tray(title: str, message: str) -> None:
    """
    Envia notificação via system tray de forma segura.
    Não faz nada se o tray não estiver disponível ou não for inicializado.
    """
    app = QApplication.instance()
    # Verifica de forma segura se o tray existe
    tray = getattr(app, '_tray', None) if app else None
    
    # Se existe um SystemTrayManager, chama o método para exibir a notificação
    if tray is not None and hasattr(tray, 'show_notification'):
        tray.show_notification(title, message)

