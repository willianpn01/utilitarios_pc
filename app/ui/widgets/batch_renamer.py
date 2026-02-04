from __future__ import annotations
import os
from typing import List
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QFileDialog,
    QCheckBox, QComboBox, QSpinBox, QTableWidget, QTableWidgetItem, QMessageBox,
    QGroupBox, QGridLayout
)

from app.core.batch_renamer import RenameRule, preview_renames, apply_renames, RenameItem


class BatchRenamerWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName('BatchRenamer')
        self._items: List[RenameItem] = []
        self._build_ui()

    # UI
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(16)

        # === SEÇÃO 1: Seleção de Arquivos ===
        files_group = QGroupBox('📁 Arquivos')
        files_layout = QGridLayout(files_group)
        files_layout.setSpacing(8)
        
        self.dir_edit = QLineEdit()
        self.dir_edit.setPlaceholderText('Clique em "Escolher pasta" para selecionar os arquivos...')
        btn_browse = QPushButton('Escolher pasta')
        btn_browse.clicked.connect(self._choose_dir)
        
        self.ext_edit = QLineEdit()
        self.ext_edit.setPlaceholderText('Deixe vazio para todos os arquivos, ou especifique: jpg, png, mp4')
        
        self.recursive_chk = QCheckBox('Incluir subpastas')
        
        files_layout.addWidget(QLabel('Pasta:'), 0, 0)
        files_layout.addWidget(self.dir_edit, 0, 1)
        files_layout.addWidget(btn_browse, 0, 2)
        files_layout.addWidget(QLabel('Filtrar por tipo:'), 1, 0)
        files_layout.addWidget(self.ext_edit, 1, 1)
        files_layout.addWidget(self.recursive_chk, 1, 2)

        # === SEÇÃO 2: Como Renomear ===
        naming_group = QGroupBox('✏️ Como você quer renomear?')
        naming_layout = QGridLayout(naming_group)
        naming_layout.setSpacing(8)
        
        # Modo de renomeação
        self.ignore_original = QCheckBox('Criar nomes completamente novos')
        self.ignore_original.setChecked(True)
        self.ignore_original.setToolTip('Marque para ignorar o nome atual e criar um nome do zero')
        
        self.base_name = QLineEdit()
        self.base_name.setPlaceholderText('Ex: Foto_Férias, Episódio_S01E')
        
        naming_layout.addWidget(self.ignore_original, 0, 0, 1, 3)
        naming_layout.addWidget(QLabel('Nome base:'), 1, 0)
        naming_layout.addWidget(self.base_name, 1, 1, 1, 2)
        
        # Buscar e substituir (para modo de edição)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText('Texto a procurar no nome atual')
        self.replace_edit = QLineEdit()
        self.replace_edit.setPlaceholderText('Substituir por...')
        
        naming_layout.addWidget(QLabel('Buscar e substituir:'), 2, 0)
        naming_layout.addWidget(self.search_edit, 2, 1)
        naming_layout.addWidget(self.replace_edit, 2, 2)

        # === SEÇÃO 3: Opções Adicionais ===
        options_group = QGroupBox('⚙️ Opções')
        options_layout = QGridLayout(options_group)
        options_layout.setSpacing(8)
        
        # Numeração
        self.use_sequence = QCheckBox('Adicionar numeração automática')
        self.use_sequence.setChecked(True)
        self.seq_start = QSpinBox()
        self.seq_start.setRange(0, 1_000_000)
        self.seq_start.setValue(1)
        self.seq_start.setToolTip('Número inicial da sequência')
        
        self.seq_pad = QSpinBox()
        self.seq_pad.setRange(0, 10)
        self.seq_pad.setValue(2)
        self.seq_pad.setToolTip('Quantidade de zeros à esquerda (ex: 2 = 01, 02...)')
        
        self.pad_hint = QLabel('Ex.: 01')
        
        options_layout.addWidget(self.use_sequence, 0, 0, 1, 2)
        options_layout.addWidget(QLabel('Começar em:'), 1, 0)
        options_layout.addWidget(self.seq_start, 1, 1)
        options_layout.addWidget(QLabel('Zeros à esquerda:'), 1, 2)
        options_layout.addWidget(self.seq_pad, 1, 3)
        options_layout.addWidget(self.pad_hint, 1, 4)
        
        # Prefixo e Sufixo
        self.prefix_edit = QLineEdit()
        self.prefix_edit.setPlaceholderText('Texto antes do nome')
        self.suffix_edit = QLineEdit()
        self.suffix_edit.setPlaceholderText('Texto depois do nome')
        
        options_layout.addWidget(QLabel('Adicionar no início:'), 2, 0)
        options_layout.addWidget(self.prefix_edit, 2, 1, 1, 2)
        options_layout.addWidget(QLabel('Adicionar no final:'), 2, 3)
        options_layout.addWidget(self.suffix_edit, 2, 4, 1, 2)
        
        # Separador
        self.separator_edit = QLineEdit()
        self.separator_edit.setPlaceholderText('_')
        self.separator_edit.setText('_')
        self.separator_edit.setMaximumWidth(50)
        self.separator_edit.setToolTip('Caractere entre as partes do nome (deixe vazio para juntar tudo)')
        
        options_layout.addWidget(QLabel('Separador:'), 3, 0)
        options_layout.addWidget(self.separator_edit, 3, 1)
        
        # Formatação
        self.case_combo = QComboBox()
        for label, value in [
            ('Manter como está', 'none'),
            ('tudo minúsculo', 'lower'),
            ('TUDO MAIÚSCULO', 'upper'),
            ('Primeira Letra Maiúscula', 'title'),
        ]:
            self.case_combo.addItem(label, userData=value)
        
        self.rm_spaces = QCheckBox('Substituir espaços por _')
        
        self.change_ext = QLineEdit()
        self.change_ext.setPlaceholderText('jpg')
        self.change_ext.setMaximumWidth(80)
        
        options_layout.addWidget(QLabel('Letras:'), 3, 2)
        options_layout.addWidget(self.case_combo, 3, 3, 1, 2)
        options_layout.addWidget(self.rm_spaces, 3, 5)
        options_layout.addWidget(QLabel('Mudar extensão:'), 4, 0)
        options_layout.addWidget(self.change_ext, 4, 1)

        # === AÇÕES ===
        actions = QHBoxLayout()
        actions.addStretch(1)
        self.btn_preview = QPushButton('👁 Visualizar resultado')
        self.btn_apply = QPushButton('✅ Aplicar renomeação')
        self.btn_apply.setEnabled(False)
        self.btn_preview.clicked.connect(self._on_preview)
        self.btn_apply.clicked.connect(self._on_apply)
        actions.addWidget(self.btn_preview)
        actions.addWidget(self.btn_apply)

        # === TABELA DE PRÉVIA ===
        preview_label = QLabel('📋 Prévia das alterações:')
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(['Nome atual', 'Novo nome', 'Status'])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(self.table.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(self.table.EditTrigger.NoEditTriggers)

        # Rodapé
        self.summary = QLabel('Selecione uma pasta e clique em "Visualizar resultado" para começar')

        # Montagem final
        root.addWidget(files_group)
        root.addWidget(naming_group)
        root.addWidget(options_group)
        root.addLayout(actions)
        root.addWidget(preview_label)
        root.addWidget(self.table, 1)
        root.addWidget(self.summary)

        # Reatividade
        self.use_sequence.toggled.connect(self._toggle_sequence)
        self.seq_pad.valueChanged.connect(self._update_pad_hint)
        self.seq_start.valueChanged.connect(self._update_pad_hint)
        self.ignore_original.toggled.connect(self._toggle_naming_mode)
        self._toggle_sequence(self.use_sequence.isChecked())
        self._toggle_naming_mode(self.ignore_original.isChecked())
        self._update_pad_hint()

    # Handlers
    def _choose_dir(self) -> None:
        d = QFileDialog.getExistingDirectory(self, 'Escolher diretório alvo')
        if d:
            self.dir_edit.setText(d)

    def _current_rule(self) -> RenameRule:
        return RenameRule(
            prefix=self.prefix_edit.text(),
            suffix=self.suffix_edit.text(),
            search=self.search_edit.text(),
            replace=self.replace_edit.text(),
            sequence_start=self.seq_start.value(),
            sequence_pad=self.seq_pad.value(),
            case=self.case_combo.currentData(),
            remove_spaces=self.rm_spaces.isChecked(),
            change_extension=self.change_ext.text().strip(),
            ignore_original=self.ignore_original.isChecked(),
            base_name=self.base_name.text().strip(),
            use_sequence=self.use_sequence.isChecked(),
            separator=self.separator_edit.text(),
        )

    def _on_preview(self) -> None:
        base = self.dir_edit.text().strip()
        if not base or not os.path.isdir(base):
            QMessageBox.warning(self, 'Aviso', 'Informe um diretório válido.')
            return
        exts = [e.strip() for e in self.ext_edit.text().split(',') if e.strip()]
        rule = self._current_rule()
        self._items = preview_renames(base, self.recursive_chk.isChecked(), exts, rule)
        self._populate_table(self._items)
        ok = sum(1 for i in self._items if i.status == 'ok')
        skip = sum(1 for i in self._items if i.status == 'skip')
        conf = sum(1 for i in self._items if i.status == 'conflict')
        self.summary.setText(f'Prévia: {ok} prontos, {skip} sem mudança, {conf} conflitos')
        self.btn_apply.setEnabled(ok > 0 and conf == 0)

    def _populate_table(self, items: List[RenameItem]) -> None:
        self.table.setRowCount(0)
        for it in items:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(it.src))
            self.table.setItem(row, 1, QTableWidgetItem(it.dst))
            st = QTableWidgetItem(it.status)
            if it.status == 'ok':
                st.setForeground(Qt.GlobalColor.green)
            elif it.status == 'conflict':
                st.setForeground(Qt.GlobalColor.red)
            else:
                st.setForeground(Qt.GlobalColor.gray)
            self.table.setItem(row, 2, st)

    def _on_apply(self) -> None:
        if not self._items:
            return
        renamed, skipped, errors = apply_renames(self._items)
        QMessageBox.information(self, 'Resultado', f'Renomeados: {renamed}\nIgnorados: {skipped}\nErros: {errors}')
        # refresh preview
        self._on_preview()

    def _toggle_sequence(self, enabled: bool) -> None:
        self.seq_start.setEnabled(enabled)
        self.seq_pad.setEnabled(enabled)
        self.pad_hint.setEnabled(enabled)
        self._update_pad_hint()

    def _toggle_naming_mode(self, ignore_original: bool) -> None:
        """Habilita/desabilita campos baseado no modo de renomeação"""
        self.base_name.setEnabled(ignore_original)
        self.search_edit.setEnabled(not ignore_original)
        self.replace_edit.setEnabled(not ignore_original)

    def _update_pad_hint(self) -> None:
        pad = max(0, self.seq_pad.value())
        seq = max(0, self.seq_start.value())
        try:
            sample = f"{seq:0{pad}d}" if pad > 0 else str(seq)
        except Exception:
            sample = '—'
        self.pad_hint.setText(f"Ex.: {sample}")
