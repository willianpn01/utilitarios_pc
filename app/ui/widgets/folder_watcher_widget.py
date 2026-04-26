"""
Folder Watcher Widget - UI para monitoramento automático de pastas.

Widget que permite configurar e gerenciar o monitoramento de pastas
para organização automática de arquivos.
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFileDialog, QTableWidget, QTableWidgetItem, QHeaderView,
    QTextEdit, QCheckBox, QGroupBox, QSplitter,
    QAbstractItemView, QDialog, QDialogButtonBox, QFormLayout
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor

from app.core.folder_watcher import FolderWatcher, WatchEvent
from app.core.watcher_config import (
    WatchConfig, load_settings, save_settings, get_default_rules_text,
    add_watch_config, remove_watch_config, update_watch_config, WatcherSettings
)
from app.core.auto_organizer import default_mapping
from app.core.autostart import is_autostart_enabled, set_autostart, is_windows
from app.core.logger import get_logger
from app.ui.custom_dialog import CustomDialog

# Nome distinto para não colidir com o método de instância self._log() (UI).
_logger = get_logger("watcher.ui")


class AddWatchDialog(QDialog):
    """Diálogo para adicionar uma nova pasta ao monitoramento."""
    
    def __init__(self, parent=None, existing_path: str = "", existing_rules: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Adicionar Pasta ao Monitoramento")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        
        layout = QVBoxLayout(self)
        
        # Pasta
        path_layout = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("Caminho da pasta a monitorar...")
        self.path_edit.setText(existing_path)
        btn_browse = QPushButton("Escolher...")
        btn_browse.clicked.connect(self._browse_folder)
        path_layout.addWidget(QLabel("Pasta:"))
        path_layout.addWidget(self.path_edit, 1)
        path_layout.addWidget(btn_browse)
        
        # Regras
        rules_group = QGroupBox("Regras de Organização")
        rules_layout = QVBoxLayout(rules_group)
        
        rules_header = QHBoxLayout()
        rules_header.addWidget(QLabel("Defina categoria: extensões (uma por linha)"))
        rules_header.addStretch()
        btn_defaults = QPushButton("Restaurar Padrões")
        btn_defaults.clicked.connect(self._fill_defaults)
        rules_header.addWidget(btn_defaults)
        rules_layout.addLayout(rules_header)
        
        self.rules_text = QTextEdit()
        self.rules_text.setPlaceholderText(
            "Exemplo:\nImagens: .jpg, .png, .gif\nDocumentos: .pdf, .docx"
        )
        if existing_rules:
            self.rules_text.setPlainText(existing_rules)
        else:
            self._fill_defaults()
        rules_layout.addWidget(self.rules_text)
        
        # Botões
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        
        layout.addLayout(path_layout)
        layout.addWidget(rules_group, 1)
        layout.addWidget(buttons)
    
    def _browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Selecionar pasta")
        if folder:
            self.path_edit.setText(folder)
    
    def _fill_defaults(self):
        self.rules_text.setPlainText(get_default_rules_text())
    
    def _validate_and_accept(self):
        path = self.path_edit.text().strip()
        if not path:
            CustomDialog.warning(self, "Aviso", "Selecione uma pasta.")
            return
        if not os.path.isdir(path):
            CustomDialog.warning(self, "Aviso", "A pasta selecionada não existe.")
            return
        rules = self.rules_text.toPlainText().strip()
        if not rules:
            CustomDialog.warning(self, "Aviso", "Defina pelo menos uma regra.")
            return
        self.accept()
    
    def get_config(self) -> WatchConfig:
        return WatchConfig(
            path=self.path_edit.text().strip(),
            rules_text=self.rules_text.toPlainText().strip(),
            enabled=True
        )


class FolderWatcherWidget(QWidget):
    """Widget para gerenciar monitoramento de pastas."""
    
    # Sinal emitido quando um arquivo é organizado
    file_organized = pyqtSignal(object)  # WatchEvent
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._watcher = FolderWatcher()
        self._watcher.set_callbacks(
            on_file_organized=self._on_file_organized,
            on_status_changed=self._on_status_changed
        )
        self._init_ui()
        self._load_watches()
    
    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)
        
        # Header com controle master
        header = QHBoxLayout()
        
        title = QLabel("Monitoramento de Pastas")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()
        
        self.status_label = QLabel("⚫ Inativo")
        self.status_label.setStyleSheet("font-weight: bold;")
        header.addWidget(self.status_label)
        
        self.btn_toggle = QPushButton("▶ Iniciar Monitoramento")
        self.btn_toggle.setMinimumWidth(180)
        self.btn_toggle.clicked.connect(self._toggle_monitoring)
        header.addWidget(self.btn_toggle)
        
        root.addLayout(header)
        
        # Splitter para tabela e log
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Grupo de pastas monitoradas
        watches_group = QGroupBox("Pastas Monitoradas")
        watches_layout = QVBoxLayout(watches_group)
        
        # Tabela de pastas
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Pasta", "Categorias", "Status", "Ações"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        watches_layout.addWidget(self.table)
        
        # Botões de ação
        actions = QHBoxLayout()
        self.btn_add = QPushButton("➕ Adicionar Pasta")
        self.btn_add.clicked.connect(self._add_watch)
        self.btn_edit = QPushButton("✏️ Editar")
        self.btn_edit.clicked.connect(self._edit_watch)
        self.btn_remove = QPushButton("🗑️ Remover")
        self.btn_remove.clicked.connect(self._remove_watch)
        actions.addWidget(self.btn_add)
        actions.addWidget(self.btn_edit)
        actions.addWidget(self.btn_remove)
        actions.addStretch()
        watches_layout.addLayout(actions)
        
        splitter.addWidget(watches_group)
        
        # Log de atividades
        log_group = QGroupBox("Log de Atividades")
        log_layout = QVBoxLayout(log_group)
        
        log_header = QHBoxLayout()
        self.stats_label = QLabel("Arquivos organizados: 0")
        log_header.addWidget(self.stats_label)
        log_header.addStretch()
        btn_clear_log = QPushButton("Limpar Log")
        btn_clear_log.clicked.connect(self._clear_log)
        log_header.addWidget(btn_clear_log)
        log_layout.addLayout(log_header)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        self.log_text.setPlaceholderText(
            "O log de atividades aparecerá aqui quando arquivos forem organizados automaticamente..."
        )
        log_layout.addWidget(self.log_text)
        
        splitter.addWidget(log_group)
        splitter.setSizes([300, 150])
        
        root.addWidget(splitter, 1)
        
        # Seção de configurações
        config_layout = QHBoxLayout()
        
        # Checkbox: Iniciar com Windows
        self.chk_autostart = QCheckBox("Iniciar com o Windows")
        self.chk_autostart.setToolTip(
            "Inicia o aplicativo automaticamente quando o Windows iniciar (minimizado na bandeja)"
        )
        if is_windows():
            self.chk_autostart.setChecked(is_autostart_enabled())
            self.chk_autostart.stateChanged.connect(self._on_autostart_changed)
        else:
            self.chk_autostart.setEnabled(False)
            self.chk_autostart.setToolTip("Disponível apenas no Windows")
        
        config_layout.addWidget(self.chk_autostart)
        
        # Botão para resetar preferência de fechamento
        self.btn_reset_close = QPushButton("🔄 Resetar preferência de fechamento")
        self.btn_reset_close.setToolTip(
            "Remove a escolha salva de 'Lembrar minha decisão' ao fechar a janela"
        )
        self.btn_reset_close.clicked.connect(self._reset_close_preference)
        config_layout.addWidget(self.btn_reset_close)
        
        config_layout.addStretch()
        
        root.addLayout(config_layout)
        
        # Rodapé com dicas
        tip = QLabel(
            "💡 Dica: O monitoramento funciona enquanto o aplicativo estiver aberto. "
            "Fechar a janela minimiza para a bandeja do sistema."
        )
        tip.setWordWrap(True)
        tip.setStyleSheet("color: #6b7280; font-size: 12px;")
        root.addWidget(tip)
        
        # Contador de arquivos
        self._files_organized = 0
    
    def _on_autostart_changed(self, state):
        """Callback quando checkbox de autostart muda."""
        enabled = state == Qt.CheckState.Checked.value
        success = set_autostart(enabled)
        
        if not success:
            # Reverter checkbox se falhou
            self.chk_autostart.blockSignals(True)
            self.chk_autostart.setChecked(not enabled)
            self.chk_autostart.blockSignals(False)
            
            CustomDialog.warning(
                self, "Erro",
                "Não foi possível alterar a configuração de início automático."
            )
    
    def _reset_close_preference(self):
        """Remove a preferência salva de ação ao fechar."""
        from PyQt6.QtCore import QSettings
        settings = QSettings()
        settings.remove('app/close_action')
        CustomDialog.information(
            self, "Preferência Resetada",
            "A preferência de fechamento foi removida.\n\n"
            "Na próxima vez que você fechar a janela, será perguntado novamente."
        )
    
    def _load_watches(self):
        """Carrega configurações salvas."""
        settings = load_settings()
        
        for config in settings.watches:
            self._watcher.add_watch(config)
        
        self._refresh_table()
        
        # Auto-iniciar se configurado
        if settings.auto_start_monitoring and settings.watches:
            QTimer.singleShot(500, self._start_monitoring)
    
    def _refresh_table(self):
        """Atualiza tabela com as pastas monitoradas."""
        self.table.setRowCount(0)
        
        for config in self._watcher.get_all_configs():
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            # Pasta
            path_item = QTableWidgetItem(config.path)
            path_item.setToolTip(config.path)
            self.table.setItem(row, 0, path_item)
            
            # Categorias (contar do rules_text)
            rule = config.get_rule()
            cats = len(rule.mapping)
            cats_item = QTableWidgetItem(f"{cats} categorias")
            self.table.setItem(row, 1, cats_item)
            
            # Status
            is_active = config.path in [
                obs for obs in self._watcher._observers.keys()
            ] if self._watcher.is_running else False
            
            if config.enabled:
                if self._watcher.is_running:
                    status = "🟢 Ativo" if is_active else "🟡 Aguardando"
                else:
                    status = "⚪ Habilitado"
            else:
                status = "⚫ Desabilitado"
            
            status_item = QTableWidgetItem(status)
            self.table.setItem(row, 2, status_item)
            
            # Toggle button
            toggle_widget = QWidget()
            toggle_layout = QHBoxLayout(toggle_widget)
            toggle_layout.setContentsMargins(4, 2, 4, 2)
            
            toggle_btn = QCheckBox("Ativo")
            toggle_btn.setChecked(config.enabled)
            toggle_btn.stateChanged.connect(
                lambda state, p=config.path: self._toggle_watch(p, state == Qt.CheckState.Checked.value)
            )
            toggle_layout.addWidget(toggle_btn)
            
            self.table.setCellWidget(row, 3, toggle_widget)
    
    def _toggle_monitoring(self):
        """Liga/desliga monitoramento global."""
        if self._watcher.is_running:
            self._stop_monitoring()
        else:
            self._start_monitoring()
    
    def _start_monitoring(self):
        """Inicia monitoramento."""
        configs = self._watcher.get_all_configs()
        if not configs:
            CustomDialog.information(
                self, "Aviso",
                "Adicione pelo menos uma pasta antes de iniciar o monitoramento."
            )
            return
        
        try:
            self._watcher.start()
        except Exception:
            _logger.exception("Falha ao iniciar monitoramento")
            self._log("Erro ao iniciar monitoramento (ver app.log)", color="red")
            return
        _logger.info("Monitoramento iniciado (%d pastas configuradas)",
                     len(self._watcher.watched_paths))
        self._update_ui_state()
        self._log("Monitoramento iniciado")
    
    def _stop_monitoring(self):
        """Para monitoramento."""
        try:
            self._watcher.stop()
        except Exception:
            _logger.exception("Falha ao parar monitoramento")
        _logger.info("Monitoramento parado")
        self._update_ui_state()
        self._log("Monitoramento parado")
    
    def _update_ui_state(self):
        """Atualiza estado visual da UI."""
        if self._watcher.is_running:
            self.status_label.setText("🟢 Ativo")
            self.status_label.setStyleSheet("color: #22c55e; font-weight: bold;")
            self.btn_toggle.setText("⏹ Parar Monitoramento")
            self.btn_toggle.setStyleSheet("background: #ef4444;")
        else:
            self.status_label.setText("⚫ Inativo")
            self.status_label.setStyleSheet("color: #6b7280; font-weight: bold;")
            self.btn_toggle.setText("▶ Iniciar Monitoramento")
            self.btn_toggle.setStyleSheet("")
        
        self._refresh_table()
    
    def _add_watch(self):
        """Adiciona nova pasta ao monitoramento."""
        dialog = AddWatchDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            config = dialog.get_config()
            
            # Verificar duplicata
            for existing in self._watcher.get_all_configs():
                if os.path.normpath(existing.path) == os.path.normpath(config.path):
                    CustomDialog.warning(
                        self, "Aviso",
                        "Esta pasta já está sendo monitorada."
                    )
                    return
            
            # Adicionar
            try:
                self._watcher.add_watch(config)
                add_watch_config(config.path, config.rules_text)
            except Exception:
                _logger.exception("Falha ao adicionar pasta %s", config.path)
                self._log(f"Erro ao adicionar {config.path} (ver app.log)", color="red")
                return
            _logger.info("Pasta adicionada ao watcher: %s", config.path)
            self._refresh_table()
            self._log(f"Pasta adicionada: {config.path}")
    
    def _edit_watch(self):
        """Edita pasta selecionada."""
        row = self.table.currentRow()
        if row < 0:
            CustomDialog.information(self, "Aviso", "Selecione uma pasta para editar.")
            return
        
        configs = self._watcher.get_all_configs()
        if row >= len(configs):
            return
        
        config = configs[row]
        dialog = AddWatchDialog(self, config.path, config.rules_text)
        dialog.setWindowTitle("Editar Pasta Monitorada")
        dialog.path_edit.setEnabled(False)  # Não permitir mudar pasta
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_config = dialog.get_config()
            update_watch_config(config.path, rules_text=new_config.rules_text)
            
            # Recarregar
            self._watcher.remove_watch(config.path)
            new_config.enabled = config.enabled
            self._watcher.add_watch(new_config)
            
            self._refresh_table()
            self._log(f"Pasta editada: {config.path}")
    
    def _remove_watch(self):
        """Remove pasta selecionada."""
        row = self.table.currentRow()
        if row < 0:
            CustomDialog.information(self, "Aviso", "Selecione uma pasta para remover.")
            return
        
        configs = self._watcher.get_all_configs()
        if row >= len(configs):
            return
        
        config = configs[row]
        
        resp = CustomDialog.question(
            self, "Confirmar",
            f"Remover monitoramento da pasta?\n{config.path}"
        )
        
        if resp:
            try:
                self._watcher.remove_watch(config.path)
                remove_watch_config(config.path)
            except Exception:
                _logger.exception("Falha ao remover pasta %s", config.path)
                self._log(f"Erro ao remover {config.path} (ver app.log)", color="red")
                return
            _logger.info("Pasta removida do watcher: %s", config.path)
            self._refresh_table()
            self._log(f"Pasta removida: {config.path}")
    
    def _toggle_watch(self, path: str, enabled: bool):
        """Habilita/desabilita uma pasta."""
        self._watcher.update_watch(path, enabled)
        update_watch_config(path, enabled=enabled)
        self._refresh_table()
    
    def _on_file_organized(self, event: WatchEvent):
        """Callback quando arquivo é organizado."""
        self._files_organized += 1
        self.stats_label.setText(f"Arquivos organizados: {self._files_organized}")
        
        if event.success:
            basename = os.path.basename(event.source)
            self._log(f"✅ {basename} → {event.category}/", color="#22c55e")
        else:
            basename = os.path.basename(event.source)
            self._log(f"❌ Erro ao mover {basename}: {event.error}", color="#ef4444")
        
        self.file_organized.emit(event)
    
    def _on_status_changed(self, path: str, is_active: bool):
        """Callback quando status de uma pasta muda."""
        self._refresh_table()
    
    def _log(self, message: str, color: str = None):
        """Adiciona mensagem ao log."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        if color:
            html = f'<span style="color:{color}">[{timestamp}] {message}</span>'
        else:
            html = f"[{timestamp}] {message}"
        
        self.log_text.append(html)
        
        # Auto-scroll
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def _clear_log(self):
        """Limpa o log."""
        self.log_text.clear()
        self._watcher.clear_events()
    
    def get_watcher(self) -> FolderWatcher:
        """Retorna o watcher para acesso externo."""
        return self._watcher
    
    def closeEvent(self, event):
        """Para watcher ao fechar."""
        try:
            self._watcher.stop()
        except Exception:
            _logger.exception("Falha ao parar watcher no closeEvent")
        
        # Salvar configurações
        configs = self._watcher.get_all_configs()
        settings = WatcherSettings(watches=configs)
        save_settings(settings)
        
        super().closeEvent(event)
