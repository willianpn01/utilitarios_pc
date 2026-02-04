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
from PyQt6.QtCore import QObject, pyqtSignal


class SystemTrayManager(QObject):
    """Gerenciador do ícone na bandeja do sistema."""
    
    # Sinais
    show_window_requested = pyqtSignal()
    quit_requested = pyqtSignal()
    toggle_monitoring_requested = pyqtSignal()
    
    def __init__(self, parent=None, icon_path: str = ""):
        super().__init__(parent)
        
        self._tray_icon: Optional[QSystemTrayIcon] = None
        self._menu: Optional[QMenu] = None
        self._monitoring_active = False
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
        self._action_show = QAction("Mostrar Janela", self)
        self._action_show.triggered.connect(self.show_window_requested.emit)
        self._menu.addAction(self._action_show)
        
        self._menu.addSeparator()
        
        # Ação: Toggle monitoramento
        self._action_monitoring = QAction("▶ Iniciar Monitoramento", self)
        self._action_monitoring.triggered.connect(self.toggle_monitoring_requested.emit)
        self._menu.addAction(self._action_monitoring)
        
        self._menu.addSeparator()
        
        # Ação: Sair
        self._action_quit = QAction("Sair", self)
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
        """Atualiza status de monitoramento no menu e tooltip."""
        self._monitoring_active = active
        
        if self._action_monitoring:
            if active:
                self._action_monitoring.setText("⏹ Parar Monitoramento")
            else:
                self._action_monitoring.setText("▶ Iniciar Monitoramento")
        
        if self._tray_icon:
            status = "Ativo" if active else "Inativo"
            self._tray_icon.setToolTip(f"Utilitários PC - Monitoramento {status}")
    
    def show_notification(self, title: str, message: str, icon: QSystemTrayIcon.MessageIcon = QSystemTrayIcon.MessageIcon.Information):
        """Mostra uma notificação no sistema."""
        if self._tray_icon and self._tray_icon.isVisible():
            self._tray_icon.showMessage(title, message, icon, 3000)
    
    def is_available(self) -> bool:
        """Retorna se o system tray está disponível."""
        return self._tray_icon is not None
