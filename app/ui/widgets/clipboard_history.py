from __future__ import annotations
import os
import re
from datetime import datetime
from typing import Optional, Tuple

from PyQt6.QtCore import QTimer, Qt, QSettings
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QListWidget, QListWidgetItem, QMessageBox, QGroupBox, QCheckBox,
    QMenu, QInputDialog
)
from PyQt6.QtGui import QClipboard, QColor

from app.core.clipboard_history import ClipboardHistoryDB, ClipboardEntry


# ============================================================
# Filtro de Privacidade - Detecção de conteúdo sensível
# ============================================================

# Padrões regex para detectar conteúdo sensível
CREDIT_CARD_PATTERN = re.compile(
    r'\b(?:\d{4}[-\s]?){3}\d{4}\b'  # 16 dígitos com espaços/traços
)

CVV_PATTERN = re.compile(
    r'\b\d{3,4}\b'  # 3-4 dígitos (CVV)
)

API_KEY_PATTERNS = [
    re.compile(r'\b(sk-[a-zA-Z0-9]{20,})\b'),          # OpenAI
    re.compile(r'\b(api[-_]?key[-_:]?\s*[a-zA-Z0-9]{16,})\b', re.I),  # Generic API key
    re.compile(r'\b(ghp_[a-zA-Z0-9]{36})\b'),          # GitHub
    re.compile(r'\b(AKIA[A-Z0-9]{16})\b'),             # AWS
    re.compile(r'\b(AIza[a-zA-Z0-9_-]{35})\b'),        # Google
]

# Padrões que sugerem senha (não detectar textos normais)
PASSWORD_INDICATORS = [
    re.compile(r'^(?=.*[A-Z])(?=.*[a-z])(?=.*\d)(?=.*[!@#$%^&*()]).{8,30}$'),  # Senha forte
    re.compile(r'^[a-zA-Z0-9!@#$%^&*()_+-=]{12,50}$'),  # String aleatória longa
]


def detect_sensitive_content(text: str) -> Tuple[bool, str, str]:
    """
    Detecta se o texto contém conteúdo sensível.
    
    Returns:
        Tuple[is_sensitive, content_type, masked_text]
        - is_sensitive: True se conteúdo sensível detectado
        - content_type: Tipo de conteúdo ('credit_card', 'api_key', 'password', '')
        - masked_text: Versão mascarada do texto
    """
    if not text or len(text) > 500:  # Ignorar textos muito longos
        return False, '', text
    
    text_clean = text.strip()
    
    # 1. Detectar cartão de crédito
    cc_match = CREDIT_CARD_PATTERN.search(text_clean)
    if cc_match:
        # Verificar se parece com número de cartão válido (Luhn check simplificado)
        digits = re.sub(r'\D', '', cc_match.group())
        if len(digits) == 16 and digits.isdigit():
            masked = re.sub(
                CREDIT_CARD_PATTERN,
                lambda m: '**** **** **** ' + re.sub(r'\D', '', m.group())[-4:],
                text_clean
            )
            return True, 'credit_card', masked
    
    # 2. Detectar chaves de API
    for pattern in API_KEY_PATTERNS:
        match = pattern.search(text_clean)
        if match:
            key = match.group(1)
            masked = text_clean.replace(key, key[:4] + '*' * (len(key) - 8) + key[-4:])
            return True, 'api_key', masked
    
    # 3. Detectar possíveis senhas (apenas strings curtas e sem espaços)
    if ' ' not in text_clean and 8 <= len(text_clean) <= 50:
        for pattern in PASSWORD_INDICATORS:
            if pattern.match(text_clean):
                # Mascarar mantendo apenas primeiro e último caractere
                masked = text_clean[0] + '*' * (len(text_clean) - 2) + text_clean[-1]
                return True, 'password', masked
    
    return False, '', text


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
        
        self.chk_privacy = QCheckBox('🔒 Filtro de Privacidade')
        self.chk_privacy.setChecked(True)  # Ativo por padrão
        self.chk_privacy.setToolTip(
            'Detecta e mascara conteúdo sensível:\n'
            '• Cartões de crédito (**** **** **** 1234)\n'
            '• Chaves de API (sk-****...)\n'
            '• Senhas (a****z)'
        )
        # Carregar configuração salva
        self.chk_privacy.setChecked(
            QSettings().value('clipboard/privacy_filter', True, type=bool)
        )
        self.chk_privacy.toggled.connect(self._on_privacy_toggle)
        
        self.btn_clear = QPushButton('🗑 Limpar histórico')
        self.btn_clear.clicked.connect(self._clear_history)
        
        controls_layout.addWidget(self.chk_monitor)
        controls_layout.addWidget(self.chk_privacy)
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
    
    def _on_privacy_toggle(self, enabled: bool) -> None:
        """Salva configuração do filtro de privacidade"""
        QSettings().setValue('clipboard/privacy_filter', enabled)
    
    def _check_clipboard(self) -> None:
        """Verifica se o conteúdo da área de transferência mudou"""
        current_text = self.clipboard.text()
        
        # Ignorar se vazio ou igual ao último
        if not current_text or current_text == self.last_clipboard_text:
            return
        
        # Aplicar filtro de privacidade se ativo
        text_to_save = current_text
        content_type = 'text'
        
        if self.chk_privacy.isChecked():
            is_sensitive, detected_type, masked = detect_sensitive_content(current_text)
            if is_sensitive:
                text_to_save = masked
                content_type = f'🔒 {detected_type}'
        
        # Adicionar ao histórico
        entry_id = self.db.add_entry(text_to_save, content_type)
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
            
            # Verificar se item ainda existe antes de restaurar
            def restore_bg():
                try:
                    # Verificar se o item ainda está na lista
                    if self.list_widget.row(item) >= 0:
                        item.setBackground(original_bg)
                except RuntimeError:
                    pass  # Item foi deletado, ignorar
            
            QTimer.singleShot(200, restore_bg)
    
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
