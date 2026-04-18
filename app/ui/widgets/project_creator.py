import os
from typing import Dict
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFileDialog, QComboBox, QTextEdit
)

from app.core.project_templates import TEMPLATES, render_tree, create_structure


class ProjectCreatorWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName('ProjectCreator')
        self._build_ui()
        self._update_preview()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        # Caminho base
        path_row = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText('Escolha a pasta onde a estrutura será criada...')
        btn_browse = QPushButton('Escolher...')
        btn_browse.clicked.connect(self._browse)
        path_row.addWidget(QLabel('Diretório base:'))
        path_row.addWidget(self.path_edit, 1)
        path_row.addWidget(btn_browse)

        # Template
        tpl_row = QHBoxLayout()
        tpl_row.addWidget(QLabel('Template:'))
        self.tpl_combo = QComboBox()
        self.tpl_combo.addItems(sorted(TEMPLATES.keys()))
        self.tpl_combo.currentIndexChanged.connect(self._update_preview)
        tpl_row.addWidget(self.tpl_combo, 1)

        # Preview
        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setMinimumHeight(260)

        # Actions
        actions = QHBoxLayout()
        actions.addStretch(1)
        self.btn_create = QPushButton('Criar Estrutura')
        self.btn_create.clicked.connect(self._create)
        actions.addWidget(self.btn_create)

        root.addLayout(path_row)
        root.addLayout(tpl_row)
        root.addWidget(QLabel('Pré-visualização da estrutura:'))
        root.addWidget(self.preview, 1)
        root.addLayout(actions)

    def _browse(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, 'Escolher diretório base')
        if directory:
            self.path_edit.setText(directory)

    def _update_preview(self) -> None:
        name = self.tpl_combo.currentText() if self.tpl_combo.count() else ''
        structure = TEMPLATES.get(name, {})
        self.preview.setPlainText(render_tree(structure))

    def _create(self) -> None:
        base = self.path_edit.text().strip()
        if not base:
            CustomDialog.warning(self, 'Aviso', 'Informe o diretório base.')
            return
        if not os.path.isdir(base):
            CustomDialog.warning(self, 'Aviso', 'Diretório base inválido.')
            return
        name = self.tpl_combo.currentText()
        structure = TEMPLATES.get(name, {})
        try:
            created_paths = create_structure(base, structure)
        except Exception as e:  # noqa: BLE001
            CustomDialog.critical(self, 'Erro', f'Falha ao criar estrutura:\n{e}')
            return
        CustomDialog.information(
            self,
            'Sucesso',
            'Estrutura criada com sucesso!\n' + '\n'.join(created_paths[:50]) + ("\n..." if len(created_paths) > 50 else '')
        )
