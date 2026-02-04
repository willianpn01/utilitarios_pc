from __future__ import annotations
import os
from datetime import datetime
from typing import Optional

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QListWidget, QListWidgetItem, QMessageBox, QGroupBox, QCheckBox,
    QMenu, QInputDialog
)
from PyQt6.QtGui import QClipboard, QColor

from app.core.clipboard_history import ClipboardHistoryDB, ClipboardEntry


class ClipboardHistoryWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        
        # Banco de dados
        db_path = os.path.join(
            os.path.expanduser('~'),
            '.utilitarios',
            'clipboard_history.db'
        )
        self.db = ClipboardHistoryDB(db_path)
        
        # Clipboard
        from PyQt6.QtWidgets import QApplication
        self.clipboard: QClipboard = QApplication.clipboard()
        
        # Timer para monitoramento
        self.monitor_timer: Optional[QTimer] = None
        self.last_clipboard_text: str = ''
        
        self._init_ui()
        self._load_history()
    
    def _init_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(16)
        
        # === SEÇÃO 1: Controles ===
        controls_group = QGroupBox('⚙️ Controles')
        controls_layout = QHBoxLayout(controls_group)
        
        self.chk_monitor = QCheckBox('Monitorar área de transferência')
        self.chk_monitor.setChecked(False)
        self.chk_monitor.toggled.connect(self._toggle_monitoring)
        
        self.btn_clear = QPushButton('🗑 Limpar histórico')
        self.btn_clear.clicked.connect(self._clear_history)
        
        controls_layout.addWidget(self.chk_monitor)
        controls_layout.addStretch()
        controls_layout.addWidget(self.btn_clear)
        
        # === SEÇÃO 2: Pesquisa ===
        search_group = QGroupBox('🔍 Pesquisar')
        search_layout = QHBoxLayout(search_group)
        
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText('Digite para pesquisar no histórico...')
        self.search_edit.textChanged.connect(self._on_search)
        
        self.chk_pinned_only = QCheckBox('Apenas fixados')
        self.chk_pinned_only.toggled.connect(self._load_history)
        
        search_layout.addWidget(self.search_edit)
        search_layout.addWidget(self.chk_pinned_only)
        
        # === SEÇÃO 3: Lista de histórico ===
        history_label = QLabel('📋 Histórico (clique para copiar, clique direito para opções):')
        
        self.list_widget = QListWidget()
        self.list_widget.setAlternatingRowColors(True)
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._on_context_menu)
        
        # === SEÇÃO 4: Estatísticas ===
        self.lbl_stats = QLabel('Total: 0 | Fixados: 0')
        
        # Montagem
        root.addWidget(controls_group)
        root.addWidget(search_group)
        root.addWidget(history_label)
        root.addWidget(self.list_widget, 1)
        root.addWidget(self.lbl_stats)
    
    def _toggle_monitoring(self, enabled: bool) -> None:
        """Ativa/desativa monitoramento da área de transferência"""
        if enabled:
            # Iniciar monitoramento
            if not self.monitor_timer:
                self.monitor_timer = QTimer(self)
                self.monitor_timer.timeout.connect(self._check_clipboard)
            
            self.last_clipboard_text = self.clipboard.text()
            self.monitor_timer.start(500)  # Verificar a cada 500ms
            self.chk_monitor.setText('✓ Monitorando...')
        else:
            # Parar monitoramento
            if self.monitor_timer:
                self.monitor_timer.stop()
            self.chk_monitor.setText('Monitorar área de transferência')
    
    def _check_clipboard(self) -> None:
        """Verifica se o conteúdo da área de transferência mudou"""
        current_text = self.clipboard.text()
        
        # Ignorar se vazio ou igual ao último
        if not current_text or current_text == self.last_clipboard_text:
            return
        
        # Adicionar ao histórico
        entry_id = self.db.add_entry(current_text, 'text')
        if entry_id > 0:
            self._load_history()
        
        self.last_clipboard_text = current_text
    
    def _load_history(self) -> None:
        """Carrega o histórico do banco de dados"""
        search = self.search_edit.text().strip()
        pinned_only = self.chk_pinned_only.isChecked()
        
        entries = self.db.get_entries(
            limit=200,
            search=search if search else None,
            pinned_only=pinned_only
        )
        
        self.list_widget.clear()
        
        for entry in entries:
            item = QListWidgetItem()
            
            # Formatar texto de exibição
            preview = entry.content[:100]
            if len(entry.content) > 100:
                preview += '...'
            
            # Substituir quebras de linha por espaço para visualização
            preview = preview.replace('\n', ' ').replace('\r', '')
            
            # Timestamp formatado
            time_str = entry.timestamp.strftime('%d/%m/%Y %H:%M:%S') if entry.timestamp else ''
            
            # Ícone de fixado
            pin_icon = '📌 ' if entry.is_pinned else ''
            
            # Categoria
            cat_str = f'[{entry.category}] ' if entry.category else ''
            
            item.setText(f'{pin_icon}{cat_str}{preview}\n{time_str}')
            item.setData(Qt.ItemDataRole.UserRole, entry)
            
            # Cor para fixados
            if entry.is_pinned:
                item.setBackground(QColor(255, 255, 200))
            
            self.list_widget.addItem(item)
        
        # Atualizar estatísticas
        stats = self.db.get_stats()
        self.lbl_stats.setText(
            f"Total: {stats['total']} | Fixados: {stats['pinned']} | "
            f"Dias com atividade: {stats['days_with_activity']}"
        )
    
    def _on_search(self) -> None:
        """Chamado quando o texto de pesquisa muda"""
        self._load_history()
    
    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        """Copia o conteúdo para a área de transferência"""
        entry: ClipboardEntry = item.data(Qt.ItemDataRole.UserRole)
        if entry:
            self.clipboard.setText(entry.content)
            # Feedback visual temporário
            original_bg = item.background()
            item.setBackground(QColor(144, 238, 144))  # verde claro
            QTimer.singleShot(200, lambda: item.setBackground(original_bg))
    
    def _on_context_menu(self, pos) -> None:
        """Menu de contexto para opções adicionais"""
        item = self.list_widget.itemAt(pos)
        if not item:
            return
        
        entry: ClipboardEntry = item.data(Qt.ItemDataRole.UserRole)
        if not entry or not entry.id:
            return
        
        menu = QMenu(self)
        
        # Fixar/Desafixar
        if entry.is_pinned:
            act_pin = menu.addAction('📌 Desafixar')
        else:
            act_pin = menu.addAction('📌 Fixar')
        
        # Adicionar categoria
        act_category = menu.addAction('🏷️ Adicionar categoria')
        
        # Copiar
        act_copy = menu.addAction('📋 Copiar')
        
        # Excluir
        menu.addSeparator()
        act_delete = menu.addAction('🗑️ Excluir')
        
        # Executar ação
        action = menu.exec(self.list_widget.viewport().mapToGlobal(pos))
        
        if action == act_pin:
            self.db.toggle_pin(entry.id)
            self._load_history()
        elif action == act_category:
            category, ok = QInputDialog.getText(
                self,
                'Adicionar categoria',
                'Digite a categoria:',
                text=entry.category
            )
            if ok:
                self.db.update_category(entry.id, category.strip())
                self._load_history()
        elif action == act_copy:
            self.clipboard.setText(entry.content)
        elif action == act_delete:
            self.db.delete_entry(entry.id)
            self._load_history()
    
    def _clear_history(self) -> None:
        """Limpa o histórico"""
        resp = QMessageBox.question(
            self,
            'Limpar histórico',
            'Deseja limpar todo o histórico?\n\n'
            'Entradas fixadas serão mantidas.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if resp == QMessageBox.StandardButton.Yes:
            removed = self.db.clear_history(keep_pinned=True)
            QMessageBox.information(
                self,
                'Histórico limpo',
                f'{removed} entrada(s) removida(s).'
            )
            self._load_history()
    
    def closeEvent(self, event):  # type: ignore[override]
        """Para o monitoramento ao fechar"""
        if self.monitor_timer:
            self.monitor_timer.stop()
        return super().closeEvent(event)
